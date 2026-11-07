/* Firefox-native WebExtension contract tests, no browser packages required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = file => fs.readFileSync(path.join(__dirname, '../extension', file), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
const event = () => ({listeners: [], addListener(fn) {this.listeners.push(fn);}});
const token = 'a'.repeat(48);
const session = '11111111-1111-1111-1111-111111111111';

function node(text, {visible = true, editable = false, top = 20} = {}) {
  const element = {tagName:'P', innerText:text, closest: () => editable,
    checkVisibility: () => visible, getAttribute: () => null,
    getBoundingClientRect: () => ({width:100,height:20,left:20,right:120,top,bottom:top+20})};
  return {textContent:text,parentElement:element};
}

function readerFixture() {
  const nodes = [node('Visible paragraph'), node('Offscreen article body',{top:900}),
                 node('PRIVATE_EDITABLE',{editable:true}),node('HIDDEN_TEXT',{visible:false})];
  const heading = {tagName:'H1',innerText:'A visible heading',closest:()=>false,checkVisibility:()=>true,
    getAttribute:()=>null,getBoundingClientRect:()=>({width:100,height:30,left:20,right:120,top:20,bottom:50})};
  const link = {...heading,tagName:'A',innerText:'A link',href:'https://user:secret@example.com/more?private=1#secret'};
  const main = {querySelectorAll: () => [heading,link]};
  const metas = {
    'meta[name="description"]': {getAttribute:()=> 'Page description'},
    'meta[name="author"]': {getAttribute:()=> 'Page author'},
    'link[rel="canonical"]': {href:'https://example.com/article?private=1'}
  };
  const video = {...heading,tagName:'VIDEO',paused:false,ended:false,currentTime:12,duration:100,playbackRate:1,muted:false,
    textTracks:[{mode:'showing',activeCues:[{text:'Visible caption'}]},{mode:'hidden',activeCues:[{text:'HIDDEN_CAPTION'}]}]};
  let rangeNode;
  const document = {title:'Example',body:main,documentElement:{lang:'en',scrollHeight:2400},
    querySelector(selector) {return selector.startsWith('main,') ? main : metas[selector] || null;},
    querySelectorAll: () => [video],
    createTreeWalker() {let i=-1; return {nextNode(){return ++i<nodes.length;},get currentNode(){return nodes[i];}};},
    createRange: () => ({selectNodeContents(n){rangeNode=n;},getClientRects:()=>[rangeNode.parentElement.getBoundingClientRect()]})};
  Object.defineProperty(document,'cookie',{get(){throw new Error('Cookies must not be read');}});
  const context = vm.createContext({document,URL,Date,location:{href:'https://example.com/article?token=secret#private'},
    NodeFilter:{SHOW_TEXT:4},getComputedStyle:()=>({visibility:'visible',display:'block'}),
    innerWidth:800,innerHeight:600,outerWidth:800,outerHeight:680,scrollY:300});
  vm.runInContext(source('reader.js'),context);
  return {context, page:vm.runInContext('readPage()',context)};
}

function backgroundFixture() {
  const saved = {following:false,pairingCode:token};
  const requests = [], badges = [];
  let focused = true, active = {id:1,windowId:5,url:'https://example.com/article',active:true};
  const browser = {
    runtime:{onMessage:event(),onStartup:event(),getURL:file=>'moz-extension://test/'+file},
    storage:{local:{get:async()=>({...saved}),set:async value=>Object.assign(saved,value)}},
    permissions:{contains:async()=>true,onRemoved:event()},
    action:{setBadgeText:async value=>badges.push(value.text),setBadgeBackgroundColor:async()=>{}},
    tabs:{query:async()=>[active],sendMessage:async()=>{},onActivated:event(),onUpdated:event()},
    windows:{get:async()=>({focused}),onFocusChanged:event()},
    scripting:{executeScript:async()=>[],unregisterContentScripts:async()=>{},registerContentScripts:async()=>{}}
  };
  const context=vm.createContext({browser,URL,AbortSignal,Date,crypto:{randomUUID:()=>session},
    fetch:async(url,options)=>{requests.push({url,body:JSON.parse(options.body),headers:options.headers});return {ok:true,json:async()=>({characters:17})};}});
  vm.runInContext(source('background.js'),context);
  const send=(message,sender={url:'moz-extension://test/popup.html'})=>browser.runtime.onMessage.listeners[0](message,sender);
  return {browser,saved,requests,badges,send,setFocused:value=>focused=value,setActive:value=>active=value};
}

async function popupChecks(page) {
  for (const permission of [true,false]) {
    const fields = Object.fromEntries(['code','share','status','follow','feed'].map(id=>['#'+id,
      {value:'',textContent:'',focus(){},addEventListener(_kind,fn){this.click=fn;}}]));
    let enabled = false, posts = 0;
    const browser = {storage:{local:{get:async()=>({pairingCode:token}),set:async()=>{}}},
      permissions:{request:async()=>permission},tabs:{query:async()=>[{id:1,url:page.url}]},
      scripting:{executeScript:async()=>[{result:page}]},runtime:{sendMessage:async message=>{
        if(message.type==='configure-stream') {enabled=message.enabled;return {ok:true,enabled};}
        return {enabled,state:enabled?'live':'off',last_sent:Date.now(),title:'Example',message:'Paused'};
      }}};
    const context=vm.createContext({browser,document:{querySelector:selector=>fields[selector]},
      readPage:()=>page,AbortSignal,Date,setInterval:()=>{},fetch:async()=>{posts++;return {ok:true};}});
    vm.runInContext(source('popup.js'),context); await flush();
    assert.equal(fields['#code'].value,token);
    await fields['#follow'].click();
    assert.equal(enabled,permission);
    if(permission) {await fields['#follow'].click();assert.equal(enabled,false);}
    else assert.match(fields['#status'].textContent,/wasn't granted/);
    await fields['#share'].click();
    assert.equal(posts,1);
    fields['#code'].value='wrong';await fields['#share'].click();assert.equal(posts,1);
  }
}

async function watcherChecks() {
  let clock=1000, heartbeat, timeout, changed, reads=0, following=false, focused=true;
  const messages=[], events={};
  const location={href:'https://example.com/article'};
  const context=vm.createContext({Date:{now:()=>clock},location,
    document:{visibilityState:'visible',hasFocus:()=>focused,documentElement:{},addEventListener:(name,fn)=>events[name]=fn},
    window:{addEventListener:(name,fn)=>events[name]=fn},
    MutationObserver:class {constructor(fn){changed=fn;}observe(){}},
    browser:{runtime:{onMessage:event(),sendMessage:async message=>{
      if(message.type==='may-observe')return {following};messages.push(message);return {ok:true};
    }}},readPage:()=>{reads++;return {title:'Test',text:'Page text'};},
    setInterval:(fn,ms)=>{heartbeat=fn;assert.equal(ms,1000);},setTimeout:fn=>{timeout=fn;return 1;}});
  vm.runInContext(source('watch.js'),context);await flush();assert.equal(reads,0);
  following=true;clock=2000;await heartbeat();assert.equal(reads,1);
  clock=3000;await heartbeat();assert.equal(reads,1,'Static pages reuse extracted content on heartbeats');
  assert.equal(messages.length,2);
  changed();clock=4000;timeout();await flush();assert.equal(reads,2,'DOM changes trigger a fresh extraction');
  focused=false;clock=5000;await heartbeat();assert.equal(reads,2);
  focused=true;following=false;clock=6000;await heartbeat();assert.equal(reads,2);
  following=true;location.href='https://example.com/changed';clock=7000;await heartbeat();
  assert.equal(reads,3,'History changes without DOM mutations refresh the cache');
  assert.ok(events.scroll && events.resize && events.timeupdate && events.popstate);
}

(async()=>{
  const manifest=JSON.parse(source('manifest.json'));
  assert.deepEqual(manifest.background.scripts,['background.js']);
  assert.equal(manifest.background.service_worker,undefined);
  assert.equal(manifest.browser_specific_settings.gecko.strict_min_version,'140.0');
  const {page}=readerFixture();
  assert.equal(page.url,'https://example.com/article');
  assert.equal(page.text,'Visible paragraph');
  assert.match(page.page_text,/Offscreen article body/);
  assert.equal(page.metadata.description,'Page description');
  assert.equal(page.metadata.canonical_url,'https://example.com/article');
  assert.equal(page.links[0].url,'https://example.com/more');
  assert.equal(page.captions,'Visible caption');
  assert.equal(page.media[0].current_time,12);
  assert.equal(page.reading.progress,300/1800);
  assert.doesNotMatch(JSON.stringify(page),/PRIVATE_EDITABLE|HIDDEN_TEXT|HIDDEN_CAPTION|private=|user:secret/);
  await popupChecks(page);
  await watcherChecks();
  const app=backgroundFixture();await flush();
  await app.send({type:'configure-stream',enabled:true});
  const sender={tab:{id:1,windowId:5},frameId:0,url:'https://example.com/article'};
  await app.send({type:'focused-page',page},sender);
  assert.equal(app.requests.filter(r=>r.url.endsWith('/page')).length,1);
  assert.equal(app.requests.at(-1).headers.Authorization,'Bearer '+token);
  assert.equal(app.requests.at(-1).body.session_id,session);
  assert.equal(app.requests.at(-1).body.metadata.description,'Page description');
  assert.ok(app.requests.every(r=>!r.url.endsWith('/status')),'Live updates must not stop when companions sleep');
  app.setActive({id:1,windowId:5,url:'https://example.com/second',active:true});
  await app.send({type:'focused-page',page:{...page,url:'https://example.com/second'}},sender);
  assert.equal(app.requests.at(-1).body.url,'https://example.com/second','SPA routes must use the current tab, not Firefox\'s original sender URL');
  app.setActive({id:1,windowId:5,url:'https://example.com/article',active:true});
  const length=app.requests.length;
  app.setFocused(false);await app.send({type:'focused-page',page},sender);assert.equal(app.requests.length,length);
  app.setFocused(true);await app.send({type:'focused-page',page},{...sender,frameId:1});
  await app.send({type:'focused-page',page},{...sender,tab:{...sender.tab,incognito:true}});
  await app.send({type:'focused-page',page:{...page,url:'https://forged.example/'}},sender);
  assert.equal(app.requests.length,length);
  assert.equal(app.send({type:'configure-stream',enabled:false},sender),undefined,'Content scripts cannot control pairing/stream settings');
  await app.send({type:'configure-stream',enabled:false});
  assert.equal(app.requests.at(-1).body.state,'paused');
  assert.ok(app.requests.at(-1).body.sequence>app.requests[0].body.sequence);
  assert.equal(app.saved.following,false);
  console.log('Firefox extension checks passed: native manifest/API, metadata and captions, form/hidden filtering, live heartbeat/cache/events, popup controls, focused/private/tab guards, stream ordering and pause clearing.');
})().catch(error=>{console.error(error);process.exitCode=1;});

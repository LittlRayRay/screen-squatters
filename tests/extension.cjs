/* Popup contract tests using Node's built-in VM; no browser/package install. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../extension/popup.js'), 'utf8');
const readerSource = fs.readFileSync(require('node:path').join(__dirname, '../extension/reader.js'), 'utf8');
const backgroundSource = fs.readFileSync(require('node:path').join(__dirname, '../extension/background.js'), 'utf8');
const watchSource = fs.readFileSync(require('node:path').join(__dirname, '../extension/watch.js'), 'utf8');

function setup({url = 'https://example.com/article', injectionError = false, fetchError = false, statusCode = 200, permissionGranted = true} = {}) {
  const fields = {
    '#code': {value: '', focus() { this.focused = true; }},
    '#share': {disabled: false, addEventListener(_event, callback) { this.click = callback; }},
    '#follow': {disabled: false, addEventListener(_event, callback) { this.click = callback; }},
    '#status': {textContent: ''}
  };
  const calls = {injections: 0, requests: [], saved: null, registered: []};
  const context = vm.createContext({
    document: {querySelector: selector => fields[selector]},
    chrome: {
      storage: {local: {
        get: async () => ({pairingCode: 'a'.repeat(48)}),
        set: async value => { calls.saved = value; },
        setAccessLevel: async () => {}
      }},
      tabs: {query: async () => [{id: 1, url}]},
      permissions: {request: async () => permissionGranted},
      scripting: {
        registerContentScripts: async scripts => {calls.registered = scripts;},
        unregisterContentScripts: async () => {},
        executeScript: async () => {
        calls.injections++;
        if (injectionError) throw new Error('Cannot access page');
        return [{result: {title: 'Example', url, text: 'Useful article'}}];
      }}
    },
    URL, AbortSignal,
    fetch: async (url, options) => {
      calls.requests.push({url, options});
      if (fetchError) throw new Error('offline');
      return {ok: statusCode === 200, json: async () => statusCode === 200 ? {characters: 14} : {error: 'Pairing code rejected'}};
    }
  });
  vm.runInContext(readerSource, context);
  vm.runInContext(source, context);
  return {fields, calls, context};
}

(async () => {
  let app = setup();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.fields['#code'].value, 'a'.repeat(48));
  await app.fields['#share'].click();
  assert.equal(app.calls.injections, 1);
  assert.equal(app.calls.requests[0].url, 'http://127.0.0.1:17373/page');
  assert.equal(app.calls.requests[0].options.headers.Authorization, 'Bearer ' + 'a'.repeat(48));
  assert.equal(JSON.parse(app.calls.requests[0].options.body).text, 'Useful article');
  assert.match(app.fields['#status'].textContent, /Shared/);
  assert.equal(app.fields['#share'].disabled, false);

  app = setup();
  await new Promise(resolve => setImmediate(resolve));
  app.fields['#code'].value = 'bad';
  await app.fields['#share'].click();
  assert.equal(app.calls.injections, 0);
  assert.equal(app.calls.requests.length, 0);

  for (const options of [{url: 'chrome://settings'}, {injectionError: true}, {fetchError: true}, {statusCode: 403}]) {
    app = setup(options);
    await new Promise(resolve => setImmediate(resolve));
    await app.fields['#share'].click();
    assert.equal(app.fields['#share'].disabled, false);
    assert.doesNotMatch(app.fields['#status'].textContent, /^Shared/);
  }

  app = setup();
  await new Promise(resolve => setImmediate(resolve));
  await app.fields['#follow'].click();
  assert.equal(app.calls.registered[0].id, 'squatters-follow');
  assert.equal(app.calls.saved.following, true);
  await app.fields['#follow'].click();
  assert.equal(app.calls.saved.following, false);
  app = setup({permissionGranted: false});
  await new Promise(resolve => setImmediate(resolve));
  await app.fields['#follow'].click();
  assert.equal(app.calls.registered.length, 0);
  assert.match(app.fields['#status'].textContent, /wasn't granted/);

  // Exercise the actual serialized reader with a small DOM fixture.
  app = setup();
  const nodes = ['First paragraph.', 'Second paragraph.'].map(textContent => ({textContent}));
  let index = -1;
  app.context.document = {
    title: 'Example title', body: {querySelectorAll: () => []},
    querySelector: () => ({querySelectorAll: () => []}),
    createTreeWalker: () => ({nextNode() { index++; return index < nodes.length; }, get currentNode() { return nodes[index]; }})
  };
  app.context.location = {href: 'https://example.com/article?token=private#secret'};
  app.context.innerWidth = 800; app.context.innerHeight = 600;
  app.context.outerWidth = 800; app.context.outerHeight = 680;
  app.context.NodeFilter = {SHOW_TEXT: 4};
  const extracted = vm.runInContext('readPage()', app.context);
  assert.equal(extracted.url, 'https://example.com/article');
  assert.equal(extracted.text, 'First paragraph.\nSecond paragraph.');

  // Exercise visibility/form filtering instead of only stubbing accepted text nodes.
  const fixtures = [
    {textContent: 'Visible sentence', parentElement: parent(false, true)},
    {textContent: 'Private input', parentElement: parent(true, true)},
    {textContent: 'Offscreen text', parentElement: parent(false, false)}
  ];
  function parent(excluded, visible) {
    return {excluded, visible, closest() {return this.excluded;}, checkVisibility() {return true;}};
  }
  app.context.NodeFilter = {SHOW_TEXT: 4, FILTER_REJECT: 2, FILTER_ACCEPT: 1};
  app.context.getComputedStyle = () => ({visibility: 'visible'});
  app.context.innerWidth = 800; app.context.innerHeight = 600;
  let rangeNode;
  app.context.document.createRange = () => ({
    selectNodeContents(node) {rangeNode = node;},
    getClientRects: () => [{top: rangeNode.parentElement.visible ? 20 : 900, bottom: 950, left: 20, right: 100}]
  });
  app.context.document.createTreeWalker = (_root, _what, filter) => {
    const accepted = fixtures.filter(node => filter.acceptNode(node) === 1);
    let index = -1;
    return {nextNode() {return ++index < accepted.length;}, get currentNode() {return accepted[index];}};
  };
  assert.equal(vm.runInContext('readPage()', app.context).text, 'Visible sentence');
  const heading = {innerText: 'Interesting heading', closest: () => null,
    getAttribute: () => null, checkVisibility: () => true,
    getBoundingClientRect: () => ({width: 100, height: 30, left: 20, right: 120, top: 20, bottom: 50})};
  app.context.document.querySelector = () => ({querySelectorAll: () => [heading]});
  const targeted = vm.runInContext('readPage()', app.context);
  assert.equal(targeted.targets[0].label, 'Interesting heading');
  assert.equal(targeted.targets[0].x, 70/800);
  assert.equal(targeted.viewport.outerHeight, 680);

  let listener;
  let awake = true, focused = true, following = true;
  const forwarded = [];
  const worker = vm.createContext({URL, AbortSignal, chrome: {
    runtime: {onMessage: {addListener(value) {listener = value;}}},
    storage: {local: {get: async () => ({following, pairingCode: 'a'.repeat(48)})}},
    tabs: {query: async () => [{id: 1}]}, windows: {get: async () => ({focused})}
  }, fetch: async (url, options) => {
    if (url.endsWith('/status')) return {ok: true, json: async () => ({awake})};
    forwarded.push(JSON.parse(options.body)); return {ok: true};
  }});
  vm.runInContext(backgroundSource, worker);
  const message = {type: 'focused-page', page: {title: 'Example', text: 'Visible', url: 'https://example.com/article?private=1', targets: [{label:'Heading',x:.3,y:.4}], viewport:{width:800,height:600}}};
  const sender = {tab: {id: 1, windowId: 1}, frameId: 0, url: 'https://example.com/article'};
  async function deliver(message, sender) {
    await new Promise(resolve => {if (listener(message, sender, resolve) !== true) resolve();});
  }
  await deliver(message, sender);
  assert.equal(forwarded.length, 1);
  assert.equal(forwarded[0].url, 'https://example.com/article');
  assert.equal(forwarded[0].automatic, true);
  assert.equal(forwarded[0].targets[0].label, 'Heading');
  awake = false; await deliver(message, sender);
  awake = true; focused = false; await deliver(message, sender);
  focused = true; following = false; await deliver(message, sender);
  following = true; await deliver(message, {...sender, frameId: 1});
  await deliver({...message, page: {...message.page, url: 'https://other.example/'}}, sender);
  assert.equal(forwarded.length, 1, 'Sleeping, unfocused, disabled, child-frame and forged pages must not forward');
  let timer, canRead = false, hasFocus = true, reads = 0, watchMessages = 0;
  const watcher = vm.createContext({
    document: {visibilityState: 'visible', hasFocus: () => hasFocus},
    chrome: {runtime: {sendMessage: async message => {
      if (message.type === 'may-observe') return {following: canRead};
      watchMessages++; return {ok: true};
    }}},
    readPage: () => {reads++; return {title: 'Page', url: 'https://example.com/', text: 'Visible'};},
    setInterval: callback => {timer = callback;}
  });
  vm.runInContext(watchSource, watcher);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(reads, 0, 'Disabled watchers must not parse pages');
  canRead = true; await timer();
  assert.equal(reads, 1); assert.equal(watchMessages, 1);
  hasFocus = false; await timer();
  assert.equal(reads, 1, 'Unfocused watchers must not parse pages');
  hasFocus = true; canRead = false; await timer();
  assert.equal(reads, 1, 'Stopped watchers must stop parsing');
  console.log('Extension checks passed: pairing, one-shot sharing, follow on/off, permission denial, visible text filtering, focused-tab and sleeping-house guards.');
})().catch(error => { console.error(error); process.exitCode = 1; });

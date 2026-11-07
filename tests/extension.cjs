/* Popup contract tests using Node's built-in VM; no browser/package install. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../extension/popup.js'), 'utf8');

function setup({url = 'https://example.com/article', injectionError = false, fetchError = false, statusCode = 200} = {}) {
  const fields = {
    '#code': {value: '', focus() { this.focused = true; }},
    '#share': {disabled: false, addEventListener(_event, callback) { this.click = callback; }},
    '#status': {textContent: ''}
  };
  const calls = {injections: 0, requests: [], saved: null};
  const context = vm.createContext({
    document: {querySelector: selector => fields[selector]},
    chrome: {
      storage: {local: {
        get: async () => ({pairingCode: 'a'.repeat(48)}),
        set: async value => { calls.saved = value; },
        setAccessLevel: async () => {}
      }},
      tabs: {query: async () => [{id: 1, url}]},
      scripting: {executeScript: async () => {
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

  // Exercise the actual serialized reader with a small DOM fixture.
  app = setup();
  const nodes = ['First paragraph.', 'Second paragraph.'].map(textContent => ({textContent}));
  let index = -1;
  app.context.document = {
    title: 'Example title', body: {},
    querySelector: () => ({}),
    createTreeWalker: () => ({nextNode() { index++; return index < nodes.length; }, get currentNode() { return nodes[index]; }})
  };
  app.context.location = {href: 'https://example.com/article?token=private#secret'};
  app.context.NodeFilter = {SHOW_TEXT: 4};
  const extracted = vm.runInContext('readPage()', app.context);
  assert.equal(extracted.url, 'https://example.com/article');
  assert.equal(extracted.text, 'First paragraph.\nSecond paragraph.');
  console.log('Extension checks passed: pairing, delivery, restricted pages, offline/error recovery, reader output.');
})().catch(error => { console.error(error); process.exitCode = 1; });

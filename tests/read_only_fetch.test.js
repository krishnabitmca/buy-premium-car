const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync('index.html', 'utf8');
const helper = source.slice(source.indexOf('async function readOnlyFetch('), source.indexOf('function catalogFetch('));

function setup(responses, onFetch = () => {}) {
  let calls = 0, cancelled = 0;
  const context = vm.createContext({ URL, DOMException, location: { href: 'https://fixture.test/' },
    setTimeout: fn => { queueMicrotask(fn); return 1; }, clearTimeout: () => {},
    fetch: async () => {
      onFetch();
      const [status, retry] = responses[Math.min(calls++, responses.length - 1)];
      return { status, headers: { get: () => retry }, body: { cancel: async () => { cancelled++; } } };
    } });
  vm.runInContext(helper, context);
  return { run: context.readOnlyFetch, calls: () => calls, cancelled: () => cancelled };
}

test('catalogue and read-only search recover from admission overload', async () => {
  for (const [url, options] of [['/api/catalog?brand=Honda', {}], ['/api/search', { method: 'POST', body: '{}' }]]) {
    const fixture = setup([[503, '1'], [200, null]]);
    assert.equal((await fixture.run(url, options)).status, 200);
    assert.equal(fixture.calls(), 2);
    assert.equal(fixture.cancelled(), 1);
  }
});
test('retries are bounded and require a usable short Retry-After', async () => {
  const busy = setup([[503, '1']]);
  assert.equal((await busy.run('/api/catalog')).status, 503);
  assert.equal(busy.calls(), 4);
  for (const retry of [null, '', 'bad', '0', '-1', '60']) {
    const fixture = setup([[503, retry]]);
    await fixture.run('/api/catalog');
    assert.equal(fixture.calls(), 1);
  }
});
test('mutation and other failure responses are never replayed', async () => {
  for (const url of ['/api/watch', '/api/intent']) {
    const fixture = setup([[503, '1']]);
    await fixture.run(url, { method: 'POST' });
    assert.equal(fixture.calls(), 1);
  }
  const fixture = setup([[500, '1']]);
  await fixture.run('/api/catalog');
  assert.equal(fixture.calls(), 1);
});
test('cancellation during overload prevents another request', async () => {
  const controller = new AbortController();
  const fixture = setup([[503, '1']], () => controller.abort());
  await assert.rejects(fixture.run('/api/catalog', { signal: controller.signal }), { name: 'AbortError' });
  assert.equal(fixture.calls(), 1);
});

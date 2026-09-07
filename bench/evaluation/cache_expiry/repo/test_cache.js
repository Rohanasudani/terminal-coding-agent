const assert = require('node:assert/strict');
const test = require('node:test');
const { ExpiringCache } = require('./cache');

test('expires at the exact deadline and removes the entry', () => {
  let now = 0;
  const cache = new ExpiringCache(() => now);
  cache.set('a', 1, 10);
  now = 9;
  assert.equal(cache.get('a'), 1);
  now = 10;
  assert.equal(cache.get('a'), undefined);
  assert.equal(cache.entries.has('a'), false);
});

test('presence is independent of value', () => {
  const cache = new ExpiringCache(() => 0);
  for (const value of [false, 0, '', undefined]) {
    cache.set('a', value, 10);
    assert.equal(cache.has('a'), true);
    assert.equal(cache.get('a'), value);
  }
  assert.equal(cache.has('missing'), false);
});

test('zero TTL is expired immediately', () => {
  const cache = new ExpiringCache(() => 50);
  cache.set('a', 1, 0);
  assert.equal(cache.has('a'), false);
});

test('updating a key resets expiration', () => {
  let now = 0;
  const cache = new ExpiringCache(() => now);
  cache.set('a', 'old', 10);
  now = 8;
  cache.set('a', 'new', 10);
  now = 10;
  assert.equal(cache.get('a'), 'new');
  now = 18;
  assert.equal(cache.has('a'), false);
});

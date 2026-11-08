import assert from 'node:assert/strict'
import test from 'node:test'
import { request, ApiError, retryAfterSeconds } from './api.js'

const json = (status, detail, headers = {}) =>
  new Response(JSON.stringify(detail), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })

test('busy recommendation retries are bounded and preserve authentication with query strings', async (t) => {
  let calls = 0
  t.mock.method(Math, 'random', () => 0)
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.headers.Authorization, `Bearer ${'a'.repeat(43)}`)
    calls++
    return json(
      503,
      { detail: 'Recommendation capacity busy; retry shortly' },
      { 'Retry-After': '0' },
    )
  })
  await assert.rejects(
    request('/recommendations/group?decade=2000', {
      method: 'POST',
      body: {},
      token: 'a'.repeat(43),
      retry: true,
    }),
    (e) => e instanceof ApiError && e.status === 503 && e.retryAfter === 0,
  )
  assert.equal(calls, 3)
})

test('mutating requests are never automatically retried and 204 is valid', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => {
    calls++
    return json(
      503,
      { detail: 'Recommendation capacity busy; retry shortly' },
      { 'Retry-After': '0' },
    )
  })
  await assert.rejects(request('/users', { method: 'POST', retry: true }))
  assert.equal(calls, 1)
  t.mock.method(
    globalThis,
    'fetch',
    async () => new Response(null, { status: 204 }),
  )
  assert.equal(
    await request('/users/1/group-invitation', { method: 'DELETE' }),
    undefined,
  )
})

test('request deadline cleans up a stalled operation with an ambiguous-write message', async (t) => {
  t.mock.method(
    globalThis,
    'fetch',
    async (_, { signal }) =>
      new Promise((_, reject) =>
        signal.addEventListener('abort', () => reject(signal.reason), {
          once: true,
        }),
      ),
  )
  await assert.rejects(
    request('/users/1/ratings/1', { method: 'PUT', timeoutMs: 10 }),
    /may have completed/,
  )
})

test('caller cancellation stops pending fetch and retry backoff', async (t) => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', async () => {
    controller.abort(new DOMException('Cancelled', 'AbortError'))
    return json(
      503,
      { detail: 'Recommendation capacity busy; retry shortly' },
      { 'Retry-After': '2' },
    )
  })
  await assert.rejects(
    request('/users/1/recommendations', {
      retry: true,
      signal: controller.signal,
    }),
    (e) => e.name === 'AbortError',
  )
})

test('rate limits, expiration and HTTP-date retry metadata remain structured', async (t) => {
  t.mock.method(globalThis, 'fetch', async () =>
    json(429, { detail: 'limited' }, { 'Retry-After': '60' }),
  )
  await assert.rejects(
    request('/users'),
    (e) => e.status === 429 && e.retryAfter === 60,
  )
  assert.equal(
    retryAfterSeconds(
      'Wed, 01 Jan 2025 00:00:02 GMT',
      Date.parse('Wed, 01 Jan 2025 00:00:00 GMT'),
    ),
    2,
  )
  assert.equal(retryAfterSeconds('nonsense'), null)
})

test('an empty gateway failure remains a 502 and identifies local startup instead of concealing it as a generic API error', async (t) => {
  t.mock.method(
    globalThis,
    'fetch',
    async () =>
      new Response('', {
        status: 502,
        headers: { 'Content-Type': 'text/plain' },
      }),
  )
  await assert.rejects(
    request('/movies/decades'),
    (error) =>
      error instanceof ApiError &&
      error.status === 502 &&
      /gateway.*HTTP 502.*npm run dev/.test(error.message),
  )
})

test('invalid successful JSON and network failures stay distinct and never display raw transport details', async (t) => {
  t.mock.method(
    globalThis,
    'fetch',
    async () =>
      new Response('<html>wrong server</html>', {
        headers: { 'Content-Type': 'text/html' },
      }),
  )
  await assert.rejects(
    request('/movies/decades'),
    (error) =>
      error.status === 200 && /unreadable response/.test(error.message),
  )
  t.mock.method(globalThis, 'fetch', async () => {
    throw new Error('sensitive transport details')
  })
  await assert.rejects(
    request('/movies/decades'),
    (error) =>
      error.status === 0 &&
      /Cannot reach the API/.test(error.message) &&
      !error.message.includes('sensitive'),
  )
})

test('read errors and deadlines never show ambiguous rating-save instructions', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => {
    throw new TypeError('network unavailable')
  })
  for (const [path, options] of [
    ['/movies/decades', {}],
    ['/recommendations/group', { method: 'POST', body: {} }],
    ['/users/1/ratings/lookup', { method: 'POST', body: {} }],
  ]) {
    await assert.rejects(
      request(path, options),
      (error) =>
        /Cannot reach/.test(error.message) &&
        !/ratings|may have completed/.test(error.message),
    )
  }
  t.mock.method(
    globalThis,
    'fetch',
    async (_, { signal }) =>
      new Promise((_, reject) =>
        signal.addEventListener('abort', () => reject(signal.reason), {
          once: true,
        }),
      ),
  )
  await assert.rejects(
    request('/movies/decades', { timeoutMs: 10 }),
    (error) =>
      /timed out/.test(error.message) &&
      !/ratings|may have completed/.test(error.message),
  )
})

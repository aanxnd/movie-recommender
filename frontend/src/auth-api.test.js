import assert from 'node:assert/strict'
import test from 'node:test'
import { createAuthenticatedApi } from './auth-api.js'
import { ApiError } from './api.js'
import { deferred, tick, value, fixture } from './auth-test-support.js'

const origin = 'https://movelle.test', backend = 'https://backend.test'
const json = (status = 200, body = { ok: true }, headers = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })
function config(session, fetcher, base = backend) {
  return { session, fetcher, base, appOrigin: origin, browser: { location: { origin } } }
}
async function ready(t, sessionValue = value()) {
  const f = fixture(), stop = f.session.subscribe(() => {})
  t.after(stop)
  f.stop = stop
  f.load.resolve({ data: { session: sessionValue }, error: null }); await tick()
  return f
}

test('explicit public requests never obtain credentials; authenticated requests pin and attach Bearer', async t => {
  const f = await ready(t), calls = []
  const api = createAuthenticatedApi(config(f.session, async (url, init) => {
    assert.equal(new URL(url).origin, backend); calls.push(init)
    assert.equal(init.redirect, 'error'); assert.equal(init.credentials, 'omit')
    assert.equal(init.cache, 'no-store'); assert.equal(init.referrerPolicy, 'no-referrer')
    return json()
  }))
  assert.deepEqual(await api('/movies/search?q=film', { access: 'public' }), { ok: true })
  assert.equal(calls[0].headers.Authorization, undefined)
  assert.deepEqual(await api('/users/me', { access: 'authenticated' }), { ok: true })
  assert.equal(calls[1].headers.Authorization, 'Bearer synthetic-access-user-a')
  const anonymous = createAuthenticatedApi(config(undefined, async (_, init) => {
    assert.equal(init.headers.Authorization, undefined); return json()
  }, '/api'))
  await anonymous('/movies/decades', { access: 'public' })
  await assert.rejects(anonymous('/users/me', { access: 'authenticated' }), e => e.status === 401)
})

for (const base of ['//evil.invalid', 'http://evil.invalid', 'https://u:p@evil.invalid',
  'https://backend.test/?private=secret', '/api/../other', '/api\\evil', 42]) {
  test('unsafe API configuration rejected without exposing it', () => {
    assert.throws(() => createAuthenticatedApi(config(undefined, async () => json(), base)),
      e => e instanceof ApiError && !e.message.includes('secret'))
  })
}

for (const path of ['https://evil.invalid/users/me', '//evil.invalid/users/me', '/\\evil.invalid/users/me',
  '/users/../users/me', '/users/%2e%2e/users/me', '/users/me#secret', '/users/me?access_token=secret',
  '/users/me?redirectTo=https://evil.invalid', '/users/me\n', '/users/me?code=secret']) {
  test('hostile request target never reaches fetch', async t => {
    const f = await ready(t), api = createAuthenticatedApi(config(f.session, () => assert.fail('Unexpected fetch')))
    await assert.rejects(api(path, { access: 'authenticated' }), e => e instanceof ApiError && e.status === 0)
  })
}

test('classification, caller Authorization and unsafe transport overrides cannot be inferred or supplied', async t => {
  const f = await ready(t), api = createAuthenticatedApi(config(f.session, () => assert.fail('Unexpected fetch')))
  for (const [path, options] of [['/users/me', {}], ['/users/me', { access: 'public' }],
    ['/movies/search', { access: 'authenticated' }], ['/users', { access: 'authenticated', method: 'POST' }],
    ['/users/me', { access: 'authenticated', headers: { Authorization: 'private' } }],
    ['/users/me', { access: 'authenticated', redirect: 'follow' }]])
    await assert.rejects(api(path, options), e => e instanceof ApiError && e.status === 0)
})

for (const status of [401, 403, 503]) {
  test('status-specific errors are redacted and never retried for nonexpired sessions: ' + status, async t => {
    const f = await ready(t); let calls = 0
    const api = createAuthenticatedApi(config(f.session, async () => {
      calls++; return json(status, { detail: 'synthetic-private' }, { 'Retry-After': '2' })
    }))
    await assert.rejects(api('/users/me', { access: 'authenticated' }), e =>
      e instanceof ApiError && e.status === status && e.retryAfter === 2 && !e.message.includes('synthetic'))
    assert.equal(calls, 1); assert.equal(f.counts.refresh, 0)
  })
}

test('eligible expired GET refreshes/retries once and uses the new access token', async t => {
  const f = await ready(t, value('user-a', Date.now()/1000 + 60)); let calls = 0
  const api = createAuthenticatedApi(config(f.session, async (_, init) => {
    calls++
    if (calls === 1) {
      t.mock.method(Date, 'now', () => 9999999999999)
      f.renewal.resolve({ data: { session: { ...value('user-a', 99999999999), access_token: 'synthetic-new-access' } }, error: null })
      return json(401)
    }
    assert.equal(init.headers.Authorization, 'Bearer synthetic-new-access')
    return json(401, { detail: 'private' }) // Second 401 is terminal for this operation.
  }))
  await assert.rejects(api('/users/me', { access: 'authenticated' }), e => e.status === 401)
  assert.equal(calls, 2); assert.equal(f.counts.refresh, 1)
})

for (const [method, path] of [['PUT', '/users/104/ratings/1'], ['POST', '/users/104/group-invitation'],
  ['POST', '/recommendations/group'], ['DELETE', '/users/104/group-invitation']]) {
  test('mutation is not replayed after a 401: ' + method + ' ' + path, async t => {
    const f = await ready(t); let calls = 0
    const api = createAuthenticatedApi(config(f.session, async () => {
      calls++; t.mock.method(Date, 'now', () => 9999999999999); return json(401)
    }))
    await assert.rejects(api(path, { access: 'authenticated', method }), e => e.status === 401)
    assert.equal(calls, 1); assert.equal(f.counts.refresh, 0)
  })
}

test('cross-origin/mocked redirects are rejected without following them', async t => {
  const f = await ready(t)
  for (const response of [new Response(null, { status: 302, headers: { Location: 'https://evil.invalid' } }),
    Object.defineProperty(json(), 'url', { value: 'https://evil.invalid/users/me' })]) {
    let calls = 0
    const api = createAuthenticatedApi(config(f.session, async () => { calls++; return response }))
    await assert.rejects(api('/users/me', { access: 'authenticated' }), e => e instanceof ApiError && e.status === 0)
    assert.equal(calls, 1)
  }
})

for (const action of ['logout', 'switch', 'abort', 'unmount']) {
  test('pending API results cannot update UI after ' + action, async t => {
    const f = await ready(t), pending = deferred(), caller = new AbortController()
    const api = createAuthenticatedApi(config(f.session, async () => pending.promise))
    const request = api('/users/me', { access: 'authenticated', signal: caller.signal }); await tick()
    const rejected = assert.rejects(request, { name: 'AbortError' })
    if (action === 'logout') { const out = f.session.logout(); f.exit.resolve({ error: null }); await out }
    if (action === 'switch') { f.emit('SIGNED_IN', value('user-b')); f.emit('SIGNED_IN', value('user-a')) }
    if (action === 'abort') caller.abort('synthetic-private')
    if (action === 'unmount') f.stop()
    await rejected; pending.resolve(json())
  })
}

test('account switching during eligible refresh cannot send another account credentials', async t => {
  const f = await ready(t); let calls = 0
  const api = createAuthenticatedApi(config(f.session, async () => {
    calls++; t.mock.method(Date, 'now', () => 9999999999999); return json(401)
  }))
  const request = api('/users/me', { access: 'authenticated' }); await tick()
  const rejected = assert.rejects(request, { name: 'AbortError' })
  f.emit('SIGNED_IN', value('user-b', 99999999999))
  f.renewal.resolve({ data: { session: value('user-b', 99999999999) }, error: null })
  await rejected; assert.equal(calls, 1)
})

test('pre-aborted requests and logout during restoration never dispatch credentials', async t => {
  const f = fixture(), stop = f.session.subscribe(() => {}); t.after(stop)
  const caller = new AbortController(); caller.abort('private')
  const api = createAuthenticatedApi(config(f.session, () => assert.fail('Unexpected fetch')))
  await assert.rejects(api('/users/me', { access: 'authenticated', signal: caller.signal }), { name: 'AbortError' })
  const out = f.session.logout(); f.exit.resolve({ error: null }); await out
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
})

test('deadlines cancel hung fetches and network exceptions never expose credentials', async t => {
  const f = await ready(t), pending = deferred()
  const stalled = createAuthenticatedApi(config(f.session, async () => pending.promise))
  await assert.rejects(stalled('/users/me', { access: 'authenticated', timeoutMs: 5 }), { name: 'AbortError' })
  pending.resolve(json())
  const broken = createAuthenticatedApi(config(f.session, async () => { throw new Error('synthetic-access-user-a') }))
  await assert.rejects(broken('/users/me', { access: 'authenticated' }), e =>
    e instanceof ApiError && !e.message.includes('synthetic') && e.status === 0)
})

test('204 responses preserve the existing undefined response contract', async t => {
  const f = await ready(t), api = createAuthenticatedApi(config(f.session, async () => new Response(null, { status: 204 })))
  assert.equal(await api('/users/104/group-invitation', { access: 'authenticated', method: 'DELETE' }), undefined)
})

test('logout cancels a request waiting for initial restoration without waiting for the SDK', async t => {
  const f = fixture(), stop = f.session.subscribe(() => {}); t.after(stop)
  const api = createAuthenticatedApi(config(f.session, () => assert.fail('Unexpected fetch')))
  const request = api('/users/me', { access: 'authenticated' })
  const rejected = assert.rejects(request, { name: 'AbortError' })
  const out = f.session.logout()
  await rejected // Initial getSession remains pending.
  f.exit.resolve({ error: null }); await out
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
})

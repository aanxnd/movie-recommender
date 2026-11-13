import assert from 'node:assert/strict'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { createStagingRuntime } from './staging-runtime.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { json, projectUrl, syntheticSession, subject, signingFixture, code } from './password-test-support.js'
import { tick, deferred } from './auth-test-support.js'

function config(t, fetcher, path = '/') {
  const dom = new JSDOM('', { url: 'http://127.0.0.1:5173' + path }); t.after(() => dom.window.close())
  return { projectUrl, publishableKey: 'sb_publishable_offline', appOrigin: 'http://127.0.0.1:5173',
    base: '/api', browser: dom.window, fetcher }
}

test('one staging runtime restores SDK state, preserves legacy storage and exposes read-only profile data', async t => {
  const calls = [], c = config(t, async (url, init) => {
    const path = new URL(url).pathname; calls.push({ path, method: init.method })
    if (path === '/auth/v1/user') return json({ id: subject })
    if (path === '/api/auth/profile') return json({ status: 'complete', username: 'MovieFan' })
    if (path === '/auth/v1/logout') return json({})
    assert.fail('Unexpected transport')
  })
  c.browser.localStorage.setItem('movelle.identity.v1', 'private-legacy-fixture')
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  assert.equal((await runtime.callbackResult).status, 'missing')
  for (let i = 0; i < 20 && runtime.session.getSnapshot().status === 'restoring'; i++) await tick()
  assert.equal(runtime.session.getSnapshot().status, 'unauthenticated'); assert.equal(calls.length, 0)
  const client = getBrowserSupabaseClient(c)
  assert.equal((await client.auth.setSession(syntheticSession())).error, null)
  assert.equal(runtime.session.getSnapshot().status, 'authenticated')
  assert.deepEqual(await runtime.account.inspect(), { status: 'ready', username: 'MovieFan', revision: 'read-only' })
  assert.deepEqual(await runtime.account.changeUsername({ username: 'Other', revision: 'read-only' }), { status: 'unavailable' })
  assert.equal(calls.filter(c => c.method === 'POST').length, 0)
  await runtime.session.logout()
  assert.equal(c.browser.localStorage.getItem('movelle.identity.v1'), 'private-legacy-fixture')
})

test('unapproved runtime configuration scrubs before any SDK or network request', t => {
  const c = config(t, () => assert.fail('Unexpected provider I/O'), '/?code=private&next=https://evil.invalid')
  assert.throws(() => createStagingRuntime({ ...c, base: 'https://foreign.invalid' }), /Approved local/)
  assert.equal(c.browser.location.href, 'http://127.0.0.1:5173/')
  assert.equal(c.browser.localStorage.length, 0)
})

test('malicious callback parameters cannot turn staging bootstrap into a provider request', async t => {
  const c = config(t, () => assert.fail('Unexpected provider I/O'), '/?code=private&next=https://evil.invalid')
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  assert.equal((await runtime.callbackResult).status, 'invalid')
  assert.equal(c.browser.location.href, 'http://127.0.0.1:5173/')
})

test('fresh bootstrap with a stored session restores before beginning the one PKCE exchange', async t => {
  const keys = await signingFixture(), old = await keys.sign({}, 'password')
  const confirmed = await keys.sign({ session_id: crypto.randomUUID() }, 'email_change')
  Object.assign(confirmed.user, { is_anonymous: false, email_confirmed_at: '2026-01-01T00:00:00Z', factors: [] })
  let exchanges = 0
  const c = config(t, async url => {
    const path = new URL(url).pathname
    if (path.endsWith('/token')) { exchanges++; return json(confirmed) }
    if (path.endsWith('/jwks.json')) return json(keys.jwks)
    if (path.endsWith('/user')) return json(confirmed.user)
    assert.fail('Unexpected provider request')
  }, '/?code=' + code)
  c.browser.localStorage.setItem('movelle.signup-confirmation', JSON.stringify({ ...old, expires_at: Math.floor(Date.now()/1000)+600 }))
  c.browser.localStorage.setItem('movelle.signup-confirmation-code-verifier', JSON.stringify('synthetic-verifier'))
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  assert.equal(c.browser.location.href, 'http://127.0.0.1:5173/')
  assert.deepEqual(await runtime.callbackResult, { status: 'current-confirmed', flow: 'email-change' })
  assert.equal(runtime.session.getSnapshot().userId, subject); assert.equal(exchanges, 1)
})

test('explicit logout during restoration prevents deferred callback redemption', async t => {
  const blocked = deferred(), calls = []
  const c = config(t, async url => { calls.push(new URL(url).pathname); return json({}) }, '/?code=' + code)
  c.storage = { getItem: key => key === 'movelle.signup-confirmation' ? blocked.promise : null,
    setItem() {}, removeItem() {} }
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  const logout = runtime.session.logout()
  assert.equal((await runtime.callbackResult).status, 'unavailable')
  blocked.resolve(null); await logout
  assert.equal(calls.filter(path => path.endsWith('/token')).length, 0)
  assert.equal(runtime.session.getSnapshot().status, 'unauthenticated')
})

test('pinned SDK cross-tab logout during restoration prevents deferred callback redemption', async t => {
  const blocked = deferred(), calls = []
  const c = config(t, async url => {
    const path = new URL(url).pathname; calls.push(path)
    return json(path.endsWith('/token') ? syntheticSession() : {})
  }, '/?code=' + code)
  c.storage = { getItem: key => key === 'movelle.signup-confirmation' ? blocked.promise :
    key.endsWith('-code-verifier') ? JSON.stringify('synthetic-verifier') : null,
    setItem() {}, removeItem() {} }
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  // Exact pinned SDK incoming BroadcastChannel path; private method is test-only.
  await getBrowserSupabaseClient(c).auth._notifyAllSubscribers('SIGNED_OUT', null, false)
  blocked.resolve(null)
  assert.equal((await runtime.callbackResult).status, 'unavailable')
  assert.equal(calls.filter(path => path.endsWith('/token')).length, 0)
  assert.equal(runtime.session.getSnapshot().status, 'unauthenticated')
  assert.equal(runtime.session.getSnapshot().logoutOutcome, 'sdk-observed')
})

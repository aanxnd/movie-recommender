import assert from 'node:assert/strict'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { createSensitiveReauthentication } from './password-reauthentication.js'
import { createNativeEmailSettings } from './email-settings.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { signingFixture, projectUrl, origin, subject, otherSubject, json } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

async function setup(t, failure, pending) {
  const keys = await signingFixture(), old = await keys.sign({ aal: failure === 'aal1' ? 'aal1' : 'aal2' }, 'totp')
  const changes = { session_id: failure === 'same-session' ? undefined : crypto.randomUUID() }
  if (failure === 'same-session') delete changes.session_id
  if (failure === 'foreign') changes.sub = otherSubject
  if (failure === 'wrong-issuer') changes.iss = 'https://evil.invalid/auth/v1'
  if (failure === 'password-aal2') changes.aal = 'aal2'
  const fresh = await keys.sign(changes, failure === 'wrong-method' ? 'oauth' : 'password')
  const dom = new JSDOM('', { url: origin }), calls = [], writes = [], logs = [], cleanupStarted = deferred()
  t.mock.method(console, 'error', e => logs.push(String(e)))
  const user = { ...old.user, is_anonymous: false, email_confirmed_at: '2026-01-01T00:00:00Z',
    factors: [{ id: crypto.randomUUID(), factor_type: 'totp', status: 'verified' }] }
  const config = { projectUrl, appOrigin: origin, publishableKey: 'sb_publishable_offline', browser: dom.window,
    fetcher: async (url, init) => {
      const path = new URL(url).pathname; calls.push(path + ':' + init.method)
      if (path.endsWith('/jwks.json')) return json(keys.jwks)
      if (path.endsWith('/user') && init.method === 'GET') return json(user)
      if (path.endsWith('/token')) {
        assert.equal(JSON.parse(init.body).password, 'synthetic-current')
        if (failure === 'signin') return json({ code: 'invalid_credentials', msg: 'private' }, 400)
        if (failure === 'network') throw new Error('private network diagnostics')
        if (failure === 'malformed') return new Response('private malformed response')
        if (failure === 'blocked') await pending.promise
        return json(fresh)
      }
      if (path.endsWith('/logout')) {
        cleanupStarted.resolve()
        assert.equal(new URL(url).search, '?scope=local')
        assert.equal(init.headers.Authorization, 'Bearer ' + fresh.access_token)
        if (pending) await pending.promise
        return json({}, failure === 'cleanup' ? 503 : 200)
      }
      if (path.endsWith('/user') && init.method === 'PUT') {
        assert.equal(init.headers.Authorization, 'Bearer ' + old.access_token) // Never the isolated AAL1 token.
        writes.push(JSON.parse(init.body))
        return failure === 'mfa-race' ? json({ code: 'insufficient_aal' }, 401) : json(user)
      }
      assert.fail('Unexpected transport')
    } }
  const client = getBrowserSupabaseClient(config), session = getSessionController(client), stop = session.subscribe(() => {})
  t.after(async () => { stop(); await client.auth.stopAutoRefresh(); dom.window.close() })
  for (let i = 0; i < 30 && session.getSnapshot().status === 'restoring'; i++) await tick()
  await client.auth.setSession(old)
  return { config, client, session, old, fresh, user, calls, writes, logs, keys, dom, cleanupStarted,
    passwords: createSensitiveReauthentication(config), email: createNativeEmailSettings(config) }
}

test('MFA password change verifies a separate fresh password session without downgrading primary AAL2', async t => {
  const f = await setup(t)
  assert.deepEqual(await f.passwords.changePassword('synthetic-current', 'synthetic-new'), { status: 'changed' })
  assert.deepEqual(f.writes, [{ password: 'synthetic-new', current_password: 'synthetic-current',
    code_challenge: null, code_challenge_method: null }])
  assert.equal((await f.client.auth.getSession()).data.session.access_token, f.old.access_token)
  assert.equal(f.dom.window.localStorage.getItem('movelle.operation-password-proof'), null)
  assert.ok(f.calls.indexOf('/auth/v1/logout:POST') < f.calls.indexOf('/auth/v1/user:PUT'))
  assert.doesNotMatch(f.logs.join(''), /synthetic-current|synthetic-new|Bearer/)
})

test('MFA email change retains AAL2 and existing native PKCE/current-email boundary', async t => {
  const f = await setup(t)
  assert.deepEqual(await f.email.requestChange('synthetic-current', 'new@example.invalid'), { status: 'check-email' })
  assert.equal(f.writes.length, 1); assert.equal(f.writes[0].email, 'new@example.invalid')
  assert.equal(f.writes[0].code_challenge_method, 's256')
  assert.equal((await f.client.auth.getSession()).data.session.access_token, f.old.access_token)
})

for (const failure of ['aal1', 'foreign', 'wrong-issuer', 'password-aal2', 'wrong-method', 'same-session',
  'signin', 'cleanup', 'mfa-race', 'network', 'malformed']) {
  test('MFA sensitive operations fail closed for ' + failure, async t => {
    const f = await setup(t, failure)
    const result = await f.passwords.changePassword('synthetic-current', 'synthetic-new')
    assert.notEqual(result.status, 'changed')
    assert.equal(f.writes.length, failure === 'mfa-race' ? 1 : 0)
    if (failure === 'aal1') assert.equal(f.calls.filter(c => c.includes('/token:')).length, 0)
    assert.equal((await f.client.auth.getSession()).data.session.access_token, f.old.access_token)
    assert.doesNotMatch(JSON.stringify(result) + f.logs.join(''), /private|synthetic-current|Bearer/)
  })
}

test('account switch during isolated cleanup cancels the old continuation; duplicate operation is refused', { timeout: 10000 }, async t => {
  const pending = deferred(), f = await setup(t, undefined, pending)
  const work = f.passwords.changePassword('synthetic-current', 'synthetic-new')
  await f.cleanupStarted.promise
  assert.equal((await f.passwords.changePassword('synthetic-current', 'synthetic-new')).status, 'busy')
  f.user.id = otherSubject
  const incoming = { ...await f.keys.sign({ sub: otherSubject }), expires_at: Math.floor(Date.now()/1000)+3600 }
  // Mirror another tab's storage write plus the pinned SDK's incoming broadcast path.
  // Private notification hook is fixture-only, as in the existing cross-tab SDK regression.
  f.dom.window.localStorage.setItem('movelle.signup-confirmation', JSON.stringify(incoming))
  await f.client.auth._notifyAllSubscribers('SIGNED_IN', incoming, false)
  pending.resolve()
  assert.equal((await work).status, 'cancelled'); assert.equal(f.writes.length, 0)
  assert.equal(f.session.getSnapshot().userId, otherSubject)
})

test('cancellation bounds a stalled isolated sign-in without restoring or downgrading the primary session', async t => {
  const pending = deferred(), f = await setup(t, 'blocked', pending), abort = new AbortController()
  const work = f.passwords.changePassword('synthetic-current', 'synthetic-new', { signal: abort.signal })
  for (let i = 0; i < 30 && !f.calls.includes('/auth/v1/token:POST'); i++) await tick()
  abort.abort()
  assert.equal((await work).status, 'cancelled')
  pending.resolve(); await tick()
  assert.equal(f.writes.length, 0)
  assert.equal((await f.client.auth.getSession()).data.session.access_token, f.old.access_token)
  assert.doesNotMatch(f.logs.join(''), /synthetic-current|Bearer/)
})

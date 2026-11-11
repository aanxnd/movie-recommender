import assert from 'node:assert/strict'
import test from 'node:test'
import { createPasswordRecovery } from './password-recovery.js'
import { createSignupConfirmation } from './signup-confirmation.js'
import { JSDOM } from 'jsdom'
import { createPasswordServices } from './password-services.js'
import { deferred, tick } from './auth-test-support.js'
import { passwordFixture, signingFixture, json, code, origin, subject, otherSubject } from './password-test-support.js'

async function setup(t, { changes, method, hint = 'recovery', failure, pending, corrupt = false } = {}) {
  const keys = await signingFixture(), signed = await keys.sign(changes, method), writes = []
  if (corrupt) signed.access_token = signed.access_token.slice(0, -10) + 'dGFtcGVyZWQ'
  const f = await passwordFixture(t, async (url, init) => {
    if (url.pathname.endsWith('/jwks.json')) return failure === 'jwks' ? Promise.reject(new Error('synthetic-private')) : json(keys.jwks)
    if (url.pathname.endsWith('/token')) return ['expired', 'replayed'].includes(failure) ?
      json({ code: failure === 'expired' ? 'flow_state_expired' : 'flow_state_not_found', msg: 'synthetic-private' }, 422) : json(signed)
    if (url.pathname.endsWith('/user') && init.method === 'PUT') {
      writes.push(JSON.parse(init.body)); if (pending) await pending.promise
      return failure === 'mfa' ? json({ code: 'insufficient_aal', msg: 'synthetic-private' }, 401) :
        failure === 'weak' ? json({ code: 'weak_password', msg: 'synthetic-private' }, 422) :
        failure === 'network' ? Promise.reject(new Error('synthetic-private')) : json(signed.user)
    }
    if (url.pathname.endsWith('/user') && keys.users.has(init.headers.Authorization?.slice(7))) return json(keys.users.get(init.headers.Authorization.slice(7)))
    return json({ msg: 'Rejected' }, 401) // Unknown signing keys cannot fall back to an accepting fake /user.
  })
  f.dom.window.localStorage.setItem('movelle.signup-confirmation-code-verifier', JSON.stringify('synthetic-verifier' + (hint ? '/' + hint : '')))
  f.dom.window.history.replaceState(null, '', '/?code=' + code)
  return { ...f, keys, signed, writes, recovery: createPasswordRecovery(f.config) }
}

test('native recovery requires the signed recovery AMR as well as the SDK hint; mutation consumes context', async t => {
  const f = await setup(t), first = f.recovery.confirm()
  assert.equal(f.dom.window.location.href, origin + '/')
  assert.equal(first, f.recovery.confirm()); assert.equal((await first).status, 'verified')
  assert.deepEqual(f.recovery.state(), { status: 'verified' })
  assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'changed')
  assert.equal(f.writes.length, 1); assert.equal(f.writes[0].password, 'synthetic-new-password')
  assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'unavailable')
  assert.equal((await createSignupConfirmation(f.config).confirm()).status, 'invalid')
  assert.ok(!f.logs.join('').includes('synthetic'))
})

for (const method of ['password', 'oauth', 'magiclink', 'email/signup', 'email_change', 'token_refresh']) {
  test('a stored recovery hint cannot turn signed ' + method + ' evidence into recovery', async t => {
    const f = await setup(t, { method }); assert.equal((await f.recovery.confirm()).status, 'unproven')
    assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'unavailable'); assert.equal(f.writes.length, 0)
  })
}
test('null recovery hint and ordinary restored sessions are insufficient, even with historical recovery AMR', async t => {
  const f = await setup(t, { hint: '' }); assert.equal((await f.recovery.confirm()).status, 'unproven')
  assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'unavailable')
})

for (const changes of [{ iss: 'https://other.invalid/auth/v1' }, { aud: 'anon' }, { session_id: '0'.repeat(32) },
  { session_id: '00000000-0000-0000-0000-000000000000' }, { session_id: null }, { aal: 'aal3' },
  { amr: ['recovery'] }, { amr: [{ method: 'recovery', timestamp: '123' }] }, { iat: '123' }, { nbf: 9999999999 }]) {
  test('malformed/security-conflicting signed recovery evidence denies: ' + JSON.stringify(changes), async t => {
    const f = await setup(t, { changes }); assert.notEqual((await f.recovery.confirm()).status, 'verified')
    assert.equal(f.recovery.state().status, 'unproven'); assert.equal(f.writes.length, 0)
  })
}
for (const failure of ['mfa', 'weak', 'network']) {
  test('provider-enforced update rejection is generic and never claims password completion: ' + failure, async t => {
    const f = await setup(t, { failure }); await f.recovery.confirm()
    assert.equal((await f.recovery.setPassword('synthetic-new-password')).status,
      { mfa: 'mfa-required', weak: 'invalid-password', network: 'unavailable' }[failure])
    assert.ok(!JSON.stringify(f.recovery.state()).includes('synthetic'))
  })
}
test('logout cancels a late password PUT; duplicate updates cannot replay a possibly committed change', async t => {
  const pending = deferred(), f = await setup(t, { pending }); await f.recovery.confirm()
  const operation = f.recovery.setPassword('synthetic-new-password'); await tick()
  assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'busy')
  await f.session.logout(); assert.notEqual((await operation).status, 'changed')
  pending.resolve(); await tick(); assert.equal((await f.client.auth.getSession()).data.session, null)
})
test('A to B to A invalidates recovery evidence; expiry/consumption and replay cannot authorize mutation', async t => {
  const f = await setup(t); await f.recovery.confirm()
  const b = await f.keys.sign({ sub: otherSubject }); await f.client.auth.setSession(b)
  await f.client.auth.setSession(await f.keys.sign({ sub: subject }))
  assert.notEqual(f.recovery.state().status, 'verified')
  assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'unavailable')
})

for (const options of [{ corrupt: true }, { failure: 'jwks' }, { failure: 'expired' }, { failure: 'replayed' }, { changes: { exp: 1 } }]) {
  test('untrusted, expired or provider-unavailable recovery denies: ' + JSON.stringify(options), async t => {
    const f = await setup(t, options)
    assert.notEqual((await f.recovery.confirm()).status, 'verified'); assert.equal(f.writes.length, 0)
    assert.equal((await f.recovery.setPassword('synthetic-new-password')).status, 'unavailable')
  })
}
test('native token refresh is not new recovery proof and invalidates the previous observation', async t => {
  const f = await setup(t); assert.equal((await f.recovery.confirm()).status, 'verified')
  await f.client.auth.refreshSession(); assert.notEqual(f.recovery.state().status, 'verified')
})
test('aggregate construction performs no SDK/storage I/O; callback scrubs before even blocked storage is read', async t => {
  const dom = new JSDOM('', { url: origin + '/?code=' + code }); t.after(() => dom.window.close())
  let reads = 0
  Object.defineProperty(dom.window, 'localStorage', { get() { reads++; assert.equal(dom.window.location.href, origin + '/'); throw new Error('Storage blocked') } })
  const services = createPasswordServices({ browser: dom.window, projectUrl: `https://${'a'.repeat(20)}.supabase.co`,
    appOrigin: origin, publishableKey: 'sb_publishable_offline' })
  assert.equal(reads, 0)
  const attempt = services.recovery.confirm(); assert.equal(dom.window.location.href, origin + '/')
  assert.equal((await attempt).status, 'unavailable'); assert.equal(reads, 1)
})
test('separate consumers share one exchange and the same private native observation', async t => {
  const f = await setup(t), second = createPasswordRecovery(f.config)
  await Promise.all([f.recovery.confirm(), second.confirm()])
  assert.equal(second.state().status, 'verified'); assert.equal(f.calls.filter(p => p.endsWith('/token')).length, 1)
})
for (const path of ['/', '/?code=bad', '/?code=' + code + '&next=https://evil.invalid', '/#access_token=synthetic-private']) {
  test('malformed callback never authorizes recovery or leaks its URL: ' + path.split('=')[0], async t => {
    const f = await setup(t); f.dom.window.history.replaceState(null, '', path)
    assert.notEqual((await f.recovery.confirm()).status, 'verified')
    assert.equal(f.dom.window.location.href, origin + '/'); assert.equal(f.calls.length, 0)
  })
}

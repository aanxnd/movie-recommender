import assert from 'node:assert/strict'
import test from 'node:test'
import { createStagingCallback } from './staging-callback.js'
import { createSignupConfirmation } from './signup-confirmation.js'
import { passwordFixture, signingFixture, json, code, origin } from './password-test-support.js'

async function setup(t, method, { hint = '', corrupt = false, failure } = {}) {
  const keys = await signingFixture(), signed = await keys.sign({}, method)
  Object.assign(signed.user, { email: 'offline@example.invalid', email_confirmed_at: '2026-01-01T00:00:00Z',
    is_anonymous: false, factors: [] })
  if (corrupt) signed.access_token = signed.access_token.slice(0, -10) + 'dGFtcGVyZWQ'
  let writes = 0
  const f = await passwordFixture(t, async (url, init) => {
    if (url.pathname.endsWith('/jwks.json')) return json(keys.jwks)
    if (url.pathname.endsWith('/token')) return failure ? json({ code: 'flow_state_expired', msg: 'private' }, 422) : json(signed)
    if (url.pathname.endsWith('/user') && init.method === 'PUT') { writes++; return json(signed.user) }
    if (url.pathname.endsWith('/user') && keys.users.has(init.headers.Authorization?.slice(7))) return json(signed.user)
    return json({}, 401)
  })
  f.dom.window.localStorage.setItem('movelle.signup-confirmation-code-verifier', JSON.stringify('synthetic-verifier' + hint))
  f.dom.window.history.replaceState(null, '', '/?code=' + code)
  return { ...f, callback: createStagingCallback(f.config), writes: () => writes }
}

test('one staging callback scrubs once and retains only the signed native recovery continuation', async t => {
  const f = await setup(t, 'recovery', { hint: '/recovery' })
  const first = f.callback.confirm()
  assert.equal(f.dom.window.location.href, origin + '/')
  assert.equal(first, f.callback.confirm())
  assert.equal((await first).flow, 'recovery'); assert.equal(f.callback.state().status, 'verified')
  assert.equal((await f.callback.setPassword('synthetic-new-password')).status, 'changed')
  assert.equal((await f.callback.setPassword('synthetic-new-password')).status, 'unavailable')
  assert.equal(f.writes(), 1)
  assert.equal(f.calls.filter(p => p.endsWith('/token')).length, 1)
  assert.equal((await createSignupConfirmation(f.config).confirm()).status, 'invalid')
  assert.equal(f.logs.length, 0)
})

for (const method of ['email/signup', 'magiclink', 'oauth', 'password', 'recovery']) {
  test('ambiguous null hint is not signup/recovery proof: ' + method, async t => {
    const f = await setup(t, method)
    assert.deepEqual(await f.callback.confirm(), { status: 'unproven', flow: 'confirmation' })
    assert.equal(f.callback.state().status, 'unproven')
    assert.equal((await f.callback.setPassword('synthetic-new-password')).status, 'unavailable')
    assert.equal(f.writes(), 0)
  })
}

test('email-change result requires signed email-change AMR plus fresh current-user state', async t => {
  const f = await setup(t, 'email_change')
  assert.deepEqual(await f.callback.confirm(), { status: 'current-confirmed', flow: 'email-change' })
  assert.equal(f.callback.state().status, 'unproven'); assert.equal(f.writes(), 0)
})

for (const options of [{ hint: '/recovery', corrupt: true }, { hint: '/recovery', failure: true }]) {
  test('invalid/expired proof cannot open a reset continuation', async t => {
    const f = await setup(t, 'recovery', options)
    assert.notEqual((await f.callback.confirm()).status, 'verified')
    assert.equal(f.callback.state().status, 'unproven')
    assert.equal(f.dom.window.location.href, origin + '/')
    assert.equal(f.writes(), 0)
  })
}

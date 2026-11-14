import assert from 'node:assert/strict'
import test from 'node:test'
import { createNativeEmailSettings } from './email-settings.js'
import { createSignupConfirmation } from './signup-confirmation.js'
import { createPasswordRecovery } from './password-recovery.js'
import { passwordFixture, signingFixture, json, code, origin, subject, otherSubject } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

async function setup(t, { user = {}, failure, pending, method = 'email_change' } = {}) {
  const keys = await signingFixture(), old = await keys.sign({}, 'password')
  const fresh = await keys.sign({ session_id: crypto.randomUUID() }, 'password')
  const callback = await keys.sign({ session_id: crypto.randomUUID() }, method), writes = []
  let activated = false
  const snapshot = { id: subject, email: 'private@example.invalid', email_confirmed_at: '2026-01-01T00:00:00Z',
    is_anonymous: false, factors: [], ...user }
  const f = await passwordFixture(t, async (url, init) => {
    if (url.pathname.endsWith('/jwks.json')) return json(keys.jwks)
    if (url.pathname.endsWith('/token')) return failure === 'expired' ? json({ code: 'flow_state_expired' }, 422) :
      json(url.searchParams.get('grant_type') === 'pkce' ? callback : fresh)
    if (url.pathname.endsWith('/user') && init.method === 'GET') {
      const known = keys.users.get(init.headers.Authorization?.slice(7))
      if (activated && failure === 'provider') return json({ msg: 'private@example.invalid' }, 503)
      return known ? json({ ...snapshot, id: known.id, ...(activated && failure === 'substitution' ? { id: otherSubject } : {}) }) : json({}, 401)
    }
    if (url.pathname.endsWith('/user') && init.method === 'PUT') {
      writes.push(JSON.parse(init.body)); assert.equal(url.searchParams.get('redirect_to'), origin + '/')
      if (pending) await pending.promise
      return failure === 'exists' ? json({ code: 'email_exists', msg: 'private@example.invalid' }, 422) :
        failure === 'limited' ? json({ code: 'over_request_rate_limit' }, 429) :
          failure === 'network' ? Promise.reject(new Error('private@example.invalid')) : json({ ...snapshot, new_email: 'new@example.invalid' })
    }
    return json({}, 503)
  })
  assert.equal((await f.client.auth.setSession(old)).error, null)
  activated = true
  return { ...f, keys, snapshot, writes, service: createNativeEmailSettings(f.config) }
}

for (const [user, expected] of [[{}, 'current-confirmed'], [{ new_email: 'pending@example.invalid' }, 'change-pending'],
  [{ email_confirmed_at: null }, 'current-unconfirmed'], [{ email: 'returned@example.invalid' }, 'current-confirmed'],
  [{ new_email: '' }, 'current-confirmed']]) {
  test('fresh current-email observation returns no private addresses: ' + expected, async t => {
    const f = await setup(t, { user }), result = await f.service.inspect()
    assert.deepEqual(result, { status: expected }); assert.doesNotMatch(JSON.stringify(result), /@|12345678|token/)
  })
}
for (const user of [{ new_email: null }, { new_email: 'private@example.invalid' }, { email_confirmed_at: true },
  { email_confirmed_at: '2026-01-01' }, { email_confirmed_at: '2026-02-30T00:00:00Z' },
  { email_confirmed_at: '2999-01-01T00:00:00Z' }, { email_change_sent_at: null }, { email: '' }]) {
  test('malformed current/pending confirmation evidence is not promoted', async t => {
    const f = await setup(t, { user }); assert.equal((await f.service.inspect()).status, 'unavailable')
  })
}
for (const failure of [undefined, 'exists', 'limited', 'network']) {
  test('email update responses cannot enumerate another account: ' + failure, async t => {
    const f = await setup(t, { failure })
    assert.equal((await f.service.requestChange('synthetic-current', 'new@example.invalid')).status, 'check-email')
    assert.equal(f.writes.length, 1); assert.equal(f.writes[0].email, 'new@example.invalid')
    assert.equal(f.writes[0].code_challenge_method, 's256'); assert.ok(f.writes[0].code_challenge)
    assert.equal((await f.service.inspect()).status, 'current-confirmed') // A request did not promote the proposed address.
    assert.doesNotMatch(f.logs.join(''), /private@example.invalid/)
  })
}
for (const user of [{ new_email: 'pending@example.invalid' }, { email_confirmed_at: null }, { factors: null },
  { factors: [{ id: crypto.randomUUID(), factor_type: 'totp', status: 'verified' }] }]) {
  test('pending/unconfirmed/unknown-MFA/enrolled accounts never silently start a sensitive update', async t => {
    const f = await setup(t, { user })
    assert.notEqual((await f.service.requestChange('synthetic-current', 'new@example.invalid')).status, 'check-email')
    assert.equal(f.writes.length, 0)
  })
}
test('duplicate requests and A to B to A/logout reject late results without old SDK persistence', async t => {
  const pending = deferred(), f = await setup(t, { pending })
  const first = f.service.requestChange('synthetic-current', 'new@example.invalid')
  for (let i = 0; i < 40 && !f.writes.length; i++) await tick()
  assert.equal((await f.service.requestChange('synthetic-current', 'new@example.invalid')).status, 'busy')
  await f.client.auth.setSession(await f.keys.sign({ sub: otherSubject }))
  await f.client.auth.setSession(await f.keys.sign({ sub: subject }))
  assert.equal((await first).status, 'cancelled'); pending.resolve(); await tick()
  assert.equal(f.session.getSnapshot().userId, subject)
})
for (const method of ['email_change', 'email/signup', 'recovery', 'password']) {
  test('email callback requires its own signed AMR and fresh state: ' + method, async t => {
    const f = await setup(t, { method })
    f.dom.window.localStorage.setItem('movelle.signup-confirmation-code-verifier', JSON.stringify('synthetic-verifier'))
    f.dom.window.history.replaceState(null, '', '/?code=' + code)
    const first = f.service.confirm(); assert.equal(f.dom.window.location.href, origin + '/')
    assert.equal(first, f.service.confirm())
    assert.equal((await first).status, method === 'email_change' ? 'current-confirmed' : 'unproven')
    assert.equal((await createSignupConfirmation(f.config).confirm()).status, 'invalid')
    assert.equal((await createPasswordRecovery(f.config).confirm()).status, 'invalid')
    assert.equal(f.calls.filter(p => p.endsWith('/token')).length, 1)
  })
}
test('first-half redirect messages and expired callbacks do not prove confirmation', async t => {
  const f = await setup(t, { failure: 'expired' })
  f.dom.window.localStorage.setItem('movelle.signup-confirmation-code-verifier', JSON.stringify('synthetic-verifier'))
  f.dom.window.history.replaceState(null, '', '/?code=' + code)
  assert.equal((await f.service.confirm()).status, 'expired')
  assert.equal(f.dom.window.location.href, origin + '/')
})
for (const failure of ['substitution', 'provider']) {
  test('fresh provider ownership/errors deny without leaking diagnostics: ' + failure, async t => {
    const f = await setup(t, { failure })
    assert.equal((await f.service.inspect()).status, 'unavailable')
    assert.notEqual((await f.service.requestChange('synthetic-current', 'new@example.invalid')).status, 'check-email')
    assert.equal(f.writes.length, 0)
  })
}
test('partial-confirmation URL text cannot assert completion or redeem credentials', async t => {
  const f = await setup(t); f.dom.window.history.replaceState(null, '', '/?message=confirmed&email=private@example.invalid')
  const count = f.calls.length
  assert.equal((await f.service.confirm()).status, 'invalid'); assert.equal(f.calls.length, count)
  assert.equal(f.dom.window.location.href, origin + '/')
})
test('logout or abort during email update cannot publish late success', async t => {
  const pending = deferred(), f = await setup(t, { pending }), abort = new AbortController()
  const first = f.service.requestChange('synthetic-current', 'new@example.invalid', { signal: abort.signal })
  for (let i = 0; i < 40 && !f.writes.length; i++) await tick()
  abort.abort(); await f.session.logout()
  assert.equal((await first).status, 'cancelled'); pending.resolve(); await tick()
  assert.equal((await f.client.auth.getSession()).data.session, null)
})

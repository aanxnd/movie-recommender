import assert from 'node:assert/strict'
import test from 'node:test'
import { createSensitiveReauthentication } from './password-reauthentication.js'
import { passwordFixture, signingFixture, json, subject, otherSubject } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

async function setup(t, { factors = [], failure, pending, sameSession = false } = {}) {
  const keys = await signingFixture(), old = await keys.sign({}, 'oauth')
  const fresh = await keys.sign({ session_id: sameSession ? undefined : crypto.randomUUID() }, 'password')
  if (sameSession) fresh.access_token = (await keys.sign({}, 'password')).access_token
  const writes = [], events = []; let userReads = 0
  const f = await passwordFixture(t, async (url, init) => {
    if (url.pathname.endsWith('/jwks.json')) return json(keys.jwks)
    if (url.pathname.endsWith('/user') && init.method === 'GET') {
      const user = keys.users.get(init.headers.Authorization?.slice(7))
      if (!user) return json({ code: 'bad_jwt' }, 401)
      if (failure === 'provider' && ++userReads > 1) return json({ code: 'unexpected_failure', msg: 'synthetic-private' }, 503)
      return json({ ...user, is_anonymous: false, factors, ...(failure === 'missing-factors' ? { factors: undefined } : {}) })
    }
    if (url.pathname.endsWith('/token')) {
      if (pending && failure === 'signin') await pending.promise
      if (failure === 'network') throw new Error('synthetic-private')
      if (failure === 'foreign') return json(await keys.sign({ sub: otherSubject, session_id: crypto.randomUUID() }, 'password'))
      if (failure === 'limited') return json({ code: 'over_request_rate_limit' }, 429)
      return failure === 'invalid' ? json({ code: 'invalid_credentials', msg: 'synthetic-private' }, 400) : json(fresh)
    }
    if (url.pathname.endsWith('/user') && init.method === 'PUT') {
      writes.push(JSON.parse(init.body)); if (pending && failure === 'update') await pending.promise
      return failure === 'weak' ? json({ code: 'weak_password', msg: 'synthetic-private' }, 422) :
        failure === 'mfa-race' ? json({ code: 'insufficient_aal' }, 401) : json(fresh.user)
    }
    return json({ code: 'unexpected_failure' }, 503)
  })
  assert.equal((await f.client.auth.setSession(old)).error, null)
  return { ...f, keys, writes, events, actions: createSensitiveReauthentication(f.config) }
}

test('fresh provider password sign-in, not refresh, scopes one credential update to the same subject', async t => {
  const f = await setup(t)
  const result = await f.actions.changePassword('synthetic-current', 'synthetic-new', { onProgress: state => f.events.push(state) })
  assert.equal(result.status, 'changed'); assert.equal(f.writes.length, 1)
  assert.deepEqual(f.events, [{ status: 'pending', operation: 'password-change' }, { status: 'verified', operation: 'password-change' }])
  assert.deepEqual(Object.keys(f.writes[0]).sort(), ['code_challenge', 'code_challenge_method', 'current_password', 'password'])
  assert.deepEqual(f.calls.slice(-3), ['/auth/v1/user', '/auth/v1/token', '/auth/v1/user'])
  assert.ok(!JSON.stringify(result).includes('synthetic')); assert.ok(!f.logs.join('').includes('synthetic'))
})

for (const failure of ['invalid', 'missing-factors', 'weak']) {
  test('password change fails closed for ' + failure, async t => {
    const f = await setup(t, { failure })
    const result = await f.actions.changePassword('synthetic-current', 'synthetic-new')
    assert.equal(result.status, { invalid: 'invalid', 'missing-factors': 'unavailable', weak: 'invalid-password' }[failure])
    if (failure !== 'weak') assert.equal(f.writes.length, 0)
  })
}
for (const factors of [null, [{}], [{ id: crypto.randomUUID(), factor_type: 'totp', status: 'verified' }]]) {
  test('unknown or enrolled MFA cannot be interpreted as no MFA', async t => {
    const f = await setup(t, { factors })
    assert.notEqual((await f.actions.changePassword('synthetic-current', 'synthetic-new')).status, 'changed')
    assert.equal(f.calls.filter(p => p.endsWith('/token')).length, 0); assert.equal(f.writes.length, 0)
  })
}
test('explicitly unverified TOTP may use native password reauthentication', async t => {
  const f = await setup(t, { factors: [{ id: crypto.randomUUID(), factor_type: 'totp', status: 'unverified' }] })
  assert.equal((await f.actions.changePassword('synthetic-current', 'synthetic-new')).status, 'changed')
})
test('a provider response reusing a historical password session cannot substitute for fresh reauthentication', async t => {
  const f = await setup(t, { sameSession: true })
  assert.equal((await f.actions.changePassword('synthetic-current', 'synthetic-new')).status, 'unproven')
  assert.equal(f.writes.length, 0)
})
for (const stage of ['signin', 'update']) {
  test('logout cancels ' + stage + ' before a delayed response can restore credentials', async t => {
    const pending = deferred(), f = await setup(t, { failure: stage, pending })
    const promise = f.actions.changePassword('synthetic-current', 'synthetic-new')
    for (let i = 0; i < 30 && !(stage === 'update' ? f.writes.length : f.calls.some(p => p.endsWith('/token'))); i++) await tick()
    assert.equal((await f.actions.changePassword('synthetic-current', 'synthetic-new')).status, 'busy')
    await f.session.logout(); assert.equal((await promise).status, 'cancelled')
    pending.resolve(); await tick(); assert.equal((await f.client.auth.getSession()).data.session, null)
  })
}
test('account A to B to A cannot use a stale password-change continuation', async t => {
  const pending = deferred(), f = await setup(t, { failure: 'signin', pending })
  const promise = f.actions.changePassword('synthetic-current', 'synthetic-new')
  for (let i = 0; i < 30 && !f.calls.some(p => p.endsWith('/token')); i++) await tick()
  await f.client.auth.setSession(await f.keys.sign({ sub: otherSubject }))
  await f.client.auth.setSession(await f.keys.sign({ sub: subject }))
  assert.equal((await promise).status, 'cancelled'); pending.resolve(); await tick()
  assert.equal(f.writes.length, 0)
})

for (const failure of ['provider', 'network', 'foreign', 'limited', 'mfa-race']) {
  test('provider boundaries never silently complete password change: ' + failure, async t => {
    const f = await setup(t, { failure })
    const result = await f.actions.changePassword('synthetic-current', 'synthetic-new')
    assert.equal(result.status, failure === 'limited' ? 'rate-limited' : failure === 'mfa-race' ? 'mfa-required' : 'unavailable')
    if (failure !== 'mfa-race') assert.equal(f.writes.length, 0)
    assert.equal(f.session.getSnapshot().userId, subject)
  })
}
test('pre-aborted and incomplete credentials do not dispatch sensitive operations', async t => {
  const f = await setup(t), abort = new AbortController(); abort.abort()
  const before = f.calls.length
  assert.equal((await f.actions.changePassword('', 'synthetic-new')).status, 'invalid-password')
  assert.equal((await f.actions.changePassword('synthetic-current', 'synthetic-new', { signal: abort.signal })).status, 'cancelled')
  assert.equal(f.calls.length, before)
})

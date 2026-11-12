import test from 'node:test'
import assert from 'node:assert/strict'
import { mfaFixture, factorId, totp } from './mfa-test-support.js'
import { json, otherSubject } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

test('native MFA promotes the shared session through the actual pinned SDK event', async t => {
  const f = await mfaFixture(t), events = []
  const { data } = f.client.auth.onAuthStateChange(event => events.push(event))
  t.after(() => data.subscription.unsubscribe())
  const result = await f.service.verify(factorId, '123456')
  assert.equal(result.status, 'verified')
  assert.equal(events.filter(e => e === 'MFA_CHALLENGE_VERIFIED').length, 1)
  assert.equal((await f.service.inspect()).status, 'verified')
  assert.equal(f.state.actions.length, 2)
  assert.doesNotMatch(JSON.stringify(result), /"code"|access_token|refresh_token|session_id/)
  assert.deepEqual(f.logs, [])
})
for (const [name, handler, expected] of [
  ['invalid code', url => url.pathname.endsWith('/verify') && json({ code: 'mfa_verification_failed', message: 'secret diagnostic' }, 422), 'invalid-code'],
  ['replay', url => url.pathname.endsWith('/verify') && json({ code: 'mfa_verification_failed', message: 'reused' }, 422), 'invalid-code'],
  ['rate limit', () => json({ message: 'private' }, 429), 'rate-limited'],
  ['expired', () => json({ id: factorId, type: 'totp', expires_at: 1 }), 'expired'],
  ['unknown challenge', () => json({ id: 'bad', type: 'totp', expires_at: 9999999999 }), 'expired'],
  ['provider rejection', () => json({ message: 'private' }, 403), 'unavailable'],
  ['network', () => { throw new Error('sensitive network detail') }, 'unavailable'],
]) test('native challenge handles ' + name, async t => {
  const f = await mfaFixture(t, { handler })
  assert.deepEqual(await f.service.verify(factorId, '123456'), { status: expected })
})
for (const name of ['AAL1 response', 'foreign user', 'missing session', 'removed factor'])
  test('never trusts provider success alone: ' + name, async t => {
    const f = await mfaFixture(t)
    f.state.handler = url => {
      if (!url.pathname.endsWith('/verify')) return
      if (name === 'removed factor') f.state.factors = []
      return json(name === 'AAL1 response' ? f.first : name === 'foreign user' ?
        { ...f.state.promoted, user: { id: otherSubject } } : name === 'missing session' ? {} : f.state.promoted)
    }
    assert.notEqual((await f.service.verify(factorId, '123456')).status, 'verified')
  })

test('foreign selection and invalid inputs perform no factor mutation', async t => {
  const f = await mfaFixture(t)
  assert.equal((await f.service.verify('foreign', '123456')).status, 'stale')
  assert.equal((await f.service.verify(factorId, '12345')).status, 'invalid-code')
  assert.deepEqual(f.state.actions, [])
})

for (const phase of ['challenge', 'verify']) for (const change of ['cancel', 'logout', 'account ABA', 'refresh'])
  test(`late ${phase} after ${change} cannot persist stale promotion`, async t => {
    const wait = deferred(), started = deferred()
    const f = await mfaFixture(t, { handler: url => {
      if (url.pathname.endsWith('/' + phase)) { started.resolve(); return wait.promise }
    } })
    const pending = f.service.verify(factorId, '123456'); await started.promise
    assert.equal((await f.service.verify(factorId, '123456')).status, 'busy')
    if (change === 'cancel') f.service.cancel()
    if (change === 'logout') await f.session.logout()
    if (change === 'account ABA') {
      await f.client.auth.setSession(await f.sign({ sub: otherSubject }, 'password'))
      await f.client.auth.setSession(f.first)
    }
    if (change === 'refresh') await f.client.auth.setSession(await f.sign({}, 'password'))
    wait.resolve(phase === 'verify' ? json(f.state.promoted) : json({ id: factorId, type: 'totp', expires_at: Date.now()/1000+100 }))
    assert.notEqual((await pending).status, 'verified'); await tick()
    if (change === 'logout') assert.equal(f.session.getSnapshot().status, 'unauthenticated')
    const storage = f.dom.window.localStorage.getItem('movelle.signup-confirmation') ?? ''
    assert.ok(!storage.includes(f.state.promoted.access_token))
  })

test('pending factor can only become verified after fresh native verification', async t => {
  const f = await mfaFixture(t, { factors: [totp('unverified')] })
  assert.equal((await f.service.inspect()).status, 'pending')
  f.state.handler = url => { if (url.pathname.endsWith('/verify')) f.state.factors = [totp()] }
  assert.equal((await f.service.verify(factorId, '123456')).status, 'verified')
})

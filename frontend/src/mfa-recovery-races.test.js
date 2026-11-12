import test from 'node:test'
import assert from 'node:assert/strict'
import { recoveryFixture, replacementId } from './mfa-recovery-test-support.js'
import { factorId, secondId, challengeId, totp } from './mfa-test-support.js'
import { json, otherSubject } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

for (const phase of ['challenge', 'enroll', 'replacement-verify'])
  for (const change of ['cancel', 'logout', 'account ABA', 'refresh'])
    test(`${phase}: late response after ${change} cannot publish recovery progress`, async t => {
      const f = await recoveryFixture(t), wait = deferred(), started = deferred()
      if (phase !== 'challenge') await f.alternative()
      if (phase === 'replacement-verify') await f.recovery.enrollReplacement()
      f.state.handler = (url, init) => {
        if ((phase === 'challenge' && url.pathname.endsWith('/challenge')) ||
            (phase === 'enroll' && url.pathname.endsWith('/factors')) ||
            (phase === 'replacement-verify' && url.pathname.endsWith('/verify'))) {
          started.resolve(); return wait.promise
        }
        return f.replacementHandler(url, init)
      }
      const pending = phase === 'challenge' ? f.alternative() : phase === 'enroll' ?
        f.recovery.enrollReplacement() : f.recovery.verifyReplacement('123456')
      await started.promise
      assert.equal((await f.recovery.inspect()).status, 'busy')
      if (change === 'cancel') f.recovery.cancel()
      if (change === 'logout') await f.session.logout()
      if (change === 'account ABA') {
        await f.client.auth.setSession(await f.sign({ sub: otherSubject }, 'password'))
        assert.equal(f.session.getSnapshot().userId, otherSubject)
        await f.client.auth.setSession(f.first)
      }
      if (change === 'refresh') await f.client.auth.setSession(f.state.promoted)
      wait.resolve(json(phase === 'challenge' ? { id: challengeId, type: 'totp', expires_at: Math.floor(Date.now()/1000)+60 } :
        phase === 'enroll' ? { id: replacementId, type: 'totp' } : f.state.promoted))
      // During the expected native promotion window, an unrelated refresh can make
      // the SDK outcome uncertain. Both branches discard the continuation.
      assert.equal((await pending).status, change === 'refresh' && phase !== 'enroll' ? 'mutation-uncertain' : 'cancelled'); await tick()
      assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
      assert.ok(!f.state.actions.some(x => x.method === 'DELETE'))
    })

for (const name of ['missing inventory', 'malformed inventory', 'provider failure', 'AAL1 promotion', 'factor vanished'])
  test('untrustworthy alternative evidence: ' + name, async t => {
    const f = await recoveryFixture(t)
    if (name === 'missing inventory') f.state.factors = undefined
    if (name === 'malformed inventory') f.state.factors = {}
    if (name === 'provider failure') t.mock.method(f.client.auth, 'getUser', async () => ({ data: { user: null }, error: { status: 503 } }))
    if (name === 'AAL1 promotion') f.state.promoted = f.first
    if (name === 'factor vanished') f.state.handler = url => {
      if (url.pathname.endsWith('/verify')) f.state.factors = [totp('verified', secondId)]
    }
    assert.notEqual((await f.alternative()).status, 'alternative-verified')
    assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
  })

test('signed recovery AMR and email/password possession cannot replace native TOTP', async t => {
  const f = await recoveryFixture(t)
  await f.client.auth.setSession(await f.sign({}, 'recovery'))
  assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
  assert.deepEqual(f.recovery.allInaccessible(), { status: 'recovery-unavailable' })
  assert.deepEqual(f.state.actions, [])
  assert.equal(f.recovery.resetMfa, undefined)
})

test('expired private evidence cannot authorize replacement', async t => {
  const f = await recoveryFixture(t), now = Date.now()
  await f.alternative()
  t.mock.method(Date, 'now', () => now + 7200000)
  assert.equal((await f.recovery.enrollReplacement()).status, 'expired')
  assert.equal(f.state.actions.filter(x => x.path.endsWith('/factors')).length, 0)
})

for (const failure of ['never verified', 'inventory changed', 'postcheck outage'])
  test('provider verification response alone never establishes replacement: ' + failure, async t => {
    const f = await recoveryFixture(t)
    await f.alternative(); await f.recovery.enrollReplacement()
    f.state.handler = url => {
      if (url.pathname.endsWith('/verify')) {
        if (failure === 'inventory changed') f.state.factors = [totp('verified', replacementId)]
        if (failure === 'postcheck outage') t.mock.method(f.client.auth, 'getUser', async () => ({ data: { user: null }, error: { status: 503 } }))
      }
    }
    assert.notEqual((await f.recovery.verifyReplacement('123456')).status, 'replacement-verified')
    assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
  })

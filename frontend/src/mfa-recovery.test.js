import test from 'node:test'
import assert from 'node:assert/strict'
import { recoveryFixture, replacementId } from './mfa-recovery-test-support.js'
import { factorId, secondId, totp } from './mfa-test-support.js'
import { createNativeMfaRecovery } from './mfa-recovery.js'
import { json, otherSubject } from './password-test-support.js'
import { deferred } from './auth-test-support.js'

test('alternative native factor permits verified replacement, never automatic removal or complete recovery', async t => {
  const f = await recoveryFixture(t)
  assert.equal(createNativeMfaRecovery(f.config), f.recovery)
  assert.equal((await f.recovery.inspect()).status, 'challenge-required')
  assert.equal((await f.alternative()).status, 'alternative-verified')
  assert.equal((await f.recovery.enrollReplacement()).status, 'replacement-pending')
  assert.equal((await f.recovery.enrollReplacement()).status, 'unavailable') // duplicate cancels private context
  assert.equal(f.state.actions.filter(x => x.path.endsWith('/factors')).length, 1)
})

test('full native replacement binds progress to subject/session and verified provider state', async t => {
  const f = await recoveryFixture(t)
  await f.alternative(); await f.recovery.enrollReplacement()
  let visible
  f.recovery.presentSetup(value => { visible = value; return () => { visible = undefined } })
  assert.ok(visible?.secret)
  const result = await f.recovery.verifyReplacement('123456')
  assert.equal(result.status, 'replacement-verified'); assert.equal(visible, undefined)
  assert.equal((await f.recovery.inspect()).status, 'replacement-verified')
  assert.equal((await f.recovery.reviewRemoval()).status, 'removal-unavailable')
  assert.equal(f.state.factors.length, 3)
  assert.ok(!f.state.actions.some(x => x.method === 'DELETE'))
  assert.doesNotMatch(JSON.stringify(result), /secret|qr_code|access_token|session_id|recovery-complete/)
  assert.deepEqual(f.logs, [])
})

for (const [name, factors, aal, expected] of [
  ['two registered', [totp(), totp('verified', secondId)], 'aal2', 'alternative-factor-available'],
  ['one registered', [totp()], 'aal2', 'verified-factor-present'],
  ['pending only', [totp('unverified')], 'aal1', 'abandoned-enrollment'],
  ['one plus pending', [totp(), totp('unverified', secondId)], 'aal1', 'challenge-required'],
  ['empty', [], 'aal1', 'inventory-unknown'],
  ['unsupported', [{ ...totp(), factor_type: 'phone' }], 'aal1', 'inventory-unknown'],
  ['duplicates', [totp(), totp()], 'aal1', 'inventory-unknown'],
]) test('recovery observation: ' + name, async t => {
  const f = await recoveryFixture(t, { factors, aal })
  assert.equal((await f.recovery.inspect()).status, expected)
  assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
  assert.deepEqual(f.state.actions, [])
})

for (const [lost, alternative] of [[factorId, factorId], ['foreign', secondId], [factorId, 'foreign']])
  test('selection cannot establish ownership', async t => {
    const f = await recoveryFixture(t)
    assert.equal((await f.recovery.verifyAlternative(lost, alternative, '123456')).status, 'unavailable')
    assert.deepEqual(f.state.actions, [])
  })

test('all inaccessible refuses even an existing AAL2 session and performs no recovery operation', async t => {
  const f = await recoveryFixture(t, { aal: 'aal2' })
  assert.deepEqual(f.recovery.allInaccessible(), { status: 'recovery-unavailable' })
  assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
  assert.equal(f.state.actions.length, 0)
  assert.equal(f.recovery.remove, undefined)
})

for (const [name, handler, expected] of [
  ['bad code', url => url.pathname.endsWith('/verify') && json({ code: 'mfa_verification_failed', message: 'private' }, 422), 'invalid-code'],
  ['expired', () => json({ id: factorId, type: 'totp', expires_at: 1 }), 'expired'],
  ['throttled', () => json({ message: 'private' }, 429), 'rate-limited'],
  ['provider outage', () => json({ message: 'private' }, 503), 'mutation-uncertain'],
]) test('alternative challenge refusal: ' + name, async t => {
  const f = await recoveryFixture(t, { handler })
  assert.equal((await f.alternative()).status, expected)
  assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
})

test('replacement code rejection can be retried only with fresh same-session pending evidence', async t => {
  const f = await recoveryFixture(t)
  await f.alternative(); await f.recovery.enrollReplacement()
  f.state.handler = url => url.pathname.endsWith('/verify') && json({ code: 'mfa_verification_failed', message: 'private' }, 422)
  assert.equal((await f.recovery.verifyReplacement('123456')).status, 'invalid-code')
  assert.equal((await f.recovery.inspect()).status, 'replacement-pending')
  f.state.handler = f.replacementHandler
  assert.equal((await f.recovery.verifyReplacement('123456')).status, 'replacement-verified')
})

for (const change of ['logout', 'account ABA', 'refresh', 'inventory'])
  test('private replacement continuation invalidated by ' + change, async t => {
    const f = await recoveryFixture(t)
    await f.alternative()
    if (change === 'logout') await f.session.logout()
    if (change === 'account ABA') {
      await f.client.auth.setSession(await f.sign({ sub: otherSubject }, 'password'))
      assert.equal(f.session.getSnapshot().userId, otherSubject)
      await f.client.auth.setSession(f.first)
    }
    if (change === 'refresh') await f.client.auth.setSession(f.state.promoted)
    if (change === 'inventory') f.state.factors = [totp('verified', secondId)]
    assert.notEqual((await f.recovery.enrollReplacement()).status, 'replacement-pending')
    assert.equal(f.state.actions.filter(x => x.path.endsWith('/factors')).length, 0)
  })

test('late enrollment after cancellation never publishes success or permits replay', async t => {
  const f = await recoveryFixture(t), started = deferred(), wait = deferred()
  await f.alternative()
  f.state.handler = () => { started.resolve(); return wait.promise }
  const pending = f.recovery.enrollReplacement(); await started.promise
  assert.equal((await f.recovery.enrollReplacement()).status, 'busy')
  f.recovery.cancel(); wait.resolve(json({ id: replacementId }))
  assert.equal((await pending).status, 'cancelled')
  assert.equal((await f.recovery.enrollReplacement()).status, 'reauthentication-required')
})

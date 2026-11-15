import test from 'node:test'
import assert from 'node:assert/strict'
import { createFactorRemoval } from './factor-removal.js'
import { mfaFixture, factorId, secondId, totp } from './mfa-test-support.js'
import { otherSubject, json } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

const input = () => ({ factorId, authenticatingFactorId: factorId, code: '123456', confirmation: 'REMOVE EVEN IF MFA IS DISABLED' })
async function setup(t, failure) {
  const f = await mfaFixture(t, { aal: 'aal2' }), pending = deferred()
  f.state.handler = async (url, init) => {
    if (url.pathname.endsWith('/verify') && failure === 'wrong-code') return json({ code: 'mfa_verification_failed' }, 422)
    if (url.pathname.endsWith('/verify') && failure === 'inventory-race') f.state.factors.push(totp('verified', secondId))
    if (init.method === 'DELETE') {
      assert.equal(url.pathname, '/auth/v1/factors/' + factorId)
      if (failure === 'pending') await pending.promise
      if (failure === 'provider') return json({ code: 'insufficient_aal' }, 422)
      if (failure === 'network') throw new Error('private factor diagnostics')
      f.state.factors = []
      return json({ id: failure === 'wrong-id' ? secondId : factorId })
    }
  }
  return { ...f, pending, removal: createFactorRemoval(f.config, { reviewed: true }) }
}

test('factor removal remains unavailable without deployment review; booleans cannot replace factor proof', async () => {
  assert.deepEqual(await createFactorRemoval({}).remove({ aal2: true }), { status: 'removal-unavailable' })
})

test('deliberate last-factor removal requires fresh TOTP, exact inventory binding and signs out afterward', async t => {
  const f = await setup(t)
  assert.deepEqual(await f.removal.remove(input()), { status: 'removed' })
  assert.deepEqual(f.state.actions.map(a => a.method), ['POST', 'POST', 'DELETE'])
  assert.equal(f.session.getSnapshot().status, 'unauthenticated')
  assert.equal((await f.client.auth.getSession()).data.session, null)
  assert.deepEqual(f.logs, [])
})

test('password-only session still needs a successful fresh provider challenge before removal', async t => {
  const f = await setup(t)
  await f.client.auth.setSession(f.first = await f.sign({}, 'password'))
  f.state.handler = url => url.pathname.endsWith('/verify') ? json({ code: 'mfa_verification_failed' }, 422) : undefined
  assert.notEqual((await f.removal.remove(input())).status, 'removed')
  assert.equal(f.state.actions.filter(a => a.method === 'DELETE').length, 0)
})

for (const failure of ['wrong-code', 'inventory-race', 'provider', 'network', 'wrong-id']) {
  test('factor-removal failure never fabricates success or retries: ' + failure, async t => {
    const f = await setup(t, failure), outcome = await f.removal.remove(input())
    assert.notEqual(outcome.status, 'removed')
    assert.equal(f.state.actions.filter(a => a.method === 'DELETE').length, ['wrong-code', 'inventory-race'].includes(failure) ? 0 : 1)
    assert.doesNotMatch(JSON.stringify(outcome) + f.logs.join(''), /private factor|123456|Bearer/)
  })
}

test('explicit opt-out warning and owned factor selection cannot be omitted', async t => {
  const f = await setup(t)
  for (const changes of [{ confirmation: true }, { confirmation: 'retain-one' }, { factorId: secondId },
    { authenticatingFactorId: secondId }, { code: '' }]) {
    assert.notEqual((await f.removal.remove({ ...input(), ...changes })).status, 'removed')
  }
  assert.equal(f.state.actions.length, 0)
})

test('account switching and duplicate dispatch cannot delete or sign out the new account', async t => {
  const f = await setup(t, 'pending'), work = f.removal.remove(input())
  for (let i = 0; i < 50 && !f.state.actions.some(a => a.method === 'DELETE'); i++) await tick()
  assert.equal((await f.removal.remove(input())).status, 'busy')
  await f.client.auth.setSession(await f.sign({ sub: otherSubject }, 'password'))
  f.pending.resolve()
  assert.equal((await work).status, 'mutation-uncertain')
  assert.equal(f.session.getSnapshot().userId, otherSubject)
  assert.equal(f.state.actions.filter(a => a.method === 'DELETE').length, 1)
})

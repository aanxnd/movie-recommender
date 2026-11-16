import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'
import { factorId } from './mfa-test-support.js'

const mount = (t, props = {}, name = 'AccountRemovalScreen') => mountAccount(t, 'removal-screens.jsx', name, props, true)
const inspected = { status: 'not-enrolled', factors: [] }

test('both irreversible-operation screens default to disabled with warnings and no destructive form', async t => {
  const f = await mount(t)
  assert.match(f.text(), /Execution is disabled/)
  assert.match(f.text(), /cancellation is not promised/)
  assert.equal(document.querySelector('form'), null)
})

test('deletion requires typed confirmation, clears credentials and labels queueing honestly', async t => {
  const writes = []
  const f = await mount(t, { service: { available: true, inspect: async () => inspected,
    deleteAccount: async input => { writes.push(input); return { status: 'pending' } } } })
  await act(async () => { await tick() })
  f.input('password', 'synthetic-private'); f.input('confirmation', 'DELETE')
  await f.submit(); assert.equal(writes.length, 0)
  f.input('confirmation', 'PERMANENTLY DELETE MY ACCOUNT'); await f.submit()
  assert.equal(writes.length, 1); assert.ok(writes[0].requestId)
  assert.match(f.text(), /does not confirm erasure/)
  assert.doesNotMatch(f.text(), /synthetic-private|account was deleted/)
  assert.equal(document.querySelector('input[name="password"]'), null)
})

test('unknown factor evidence never becomes a non-MFA deletion form', async t => {
  await mount(t, { service: { available: true, inspect: async () => ({ status: 'not-enrolled', factors: null }) } })
  await act(async () => { await tick() })
  assert.equal(document.querySelector('form'), null)
})

test('factor removal requires explicit opt-out warning, fresh code and owned selections', async t => {
  const writes = [], service = { available: true, inspect: async () => ({ status: 'verified',
    factors: [{ id: factorId, label: 'Offline phone', status: 'verified' }] }),
    remove: async input => { writes.push(input); return { status: 'mutation-uncertain' } } }
  const f = await mount(t, { service }, 'FactorRemovalScreen')
  await act(async () => { await tick() })
  assert.match(f.text(), /No backup-retention guarantee/)
  f.input('code', '123456'); f.input('confirmation', 'REMOVE EVEN IF MFA IS DISABLED'); await f.submit()
  assert.deepEqual(writes[0], { factorId, authenticatingFactorId: factorId, code: '123456', confirmation: 'REMOVE EVEN IF MFA IS DISABLED' })
  assert.equal(document.querySelector('input[name="code"]').value, '')
  assert.doesNotMatch(f.text(), /123456/)
})

test('account switching aborts the form and discards a late queued response', async t => {
  const pending = deferred()
  const f = await mount(t, { service: { available: true, inspect: async () => inspected, deleteAccount: () => pending.promise } })
  await act(async () => { await tick() })
  f.input('password', 'synthetic-private'); f.input('confirmation', 'PERMANENTLY DELETE MY ACCOUNT')
  await f.submit()
  await act(async () => { f.emit('SIGNED_IN', value('other')); pending.resolve({ status: 'pending' }); await tick() })
  assert.doesNotMatch(f.text(), /Deletion is pending|synthetic-private/)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { readIdentity, saveIdentity, parseRecoveryCode, clearIdentity, sameIdentity } from './identity.js'

test('identity survives refresh and invalid storage fails closed', () => {
  let value = null
  const storage = { getItem: () => value, setItem: (_, v) => { value = v }, removeItem: () => { value = null } }
  const identity = { id: 7, token: 'a'.repeat(43) }
  saveIdentity(identity, storage)
  assert.deepEqual(readIdentity(storage), identity)
  value = '{'
  assert.equal(readIdentity(storage), null)
  value = JSON.stringify({ id: 7, token: 'short' })
  assert.equal(readIdentity(storage), null)
  assert.throws(() => parseRecoveryCode('7'))
  assert.deepEqual(parseRecoveryCode(`7:${identity.token}`), identity)
  clearIdentity(storage)
  assert.equal(readIdentity(storage), null)
})

test('failed or invalid persistence preserves the previous stored identity', () => {
  const previous = { id: 1, token: 'a'.repeat(43) }
  let value = JSON.stringify(previous)
  const storage = { getItem: () => value, setItem: () => { throw new Error('quota exceeded') } }
  assert.throws(() => saveIdentity({ id: 2, token: 'b'.repeat(43) }, storage), /storage is unavailable/)
  assert.deepEqual(readIdentity(storage), previous)
  assert.throws(() => saveIdentity({ id: 2, token: 'short' }, storage), /Invalid profile/)
  assert.deepEqual(readIdentity(storage), previous)
  assert.equal(sameIdentity(previous, readIdentity(storage)), true)
  assert.equal(sameIdentity(previous, { ...previous, token: 'c'.repeat(43) }), false)
  assert.equal(readIdentity({ getItem() { throw new Error('storage denied') } }), null)
})

test('failed removal does not claim that the stored identity was cleared', () => {
  const previous = { id: 1, token: 'a'.repeat(43) }
  const storage = { getItem: () => JSON.stringify(previous), removeItem() { throw new Error('storage denied') } }
  assert.throws(() => clearIdentity(storage), /storage denied/)
  assert.deepEqual(readIdentity(storage), previous)
})

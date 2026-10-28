import assert from 'node:assert/strict'
import test from 'node:test'
import { readIdentity, saveIdentity, parseRecoveryCode, identityToken, clearIdentity } from './identity.js'

test('identity survives refresh and invalid storage fails closed', () => {
  let value = null
  const storage = { getItem: () => value, setItem: (_, v) => { value = v }, removeItem: () => { value = null } }
  const identity = { id: 7, token: 'a'.repeat(43) }
  saveIdentity(identity, storage)
  assert.deepEqual(readIdentity(storage), identity)
  assert.equal(identityToken(), identity.token)
  value = '{'
  assert.equal(readIdentity(storage), null)
  value = JSON.stringify({ id: 7, token: 'short' })
  assert.equal(readIdentity(storage), null)
  assert.throws(() => parseRecoveryCode('7'))
  assert.deepEqual(parseRecoveryCode(`7:${identity.token}`), identity)
  clearIdentity(storage)
  assert.equal(identityToken(), undefined)
})

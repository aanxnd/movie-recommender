import test from 'node:test'
import assert from 'node:assert/strict'
import { inspectMfa } from './mfa-evidence.js'
import { passwordFixture, signingFixture, json, subject, otherSubject, sessionId } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

const factorId = 'aaaaaaaa-1234-4234-9234-123456789abc'
const factor = status => ({ id: factorId, factor_type: 'totp', status, friendly_name: 'Personal phone' })
for (const [name, factors, aal, expected] of [
  ['verified AAL1', [factor('verified')], 'aal1', 'challenge-required'],
  ['verified AAL2', [factor('verified')], 'aal2', 'verified'],
  ['unverified', [factor('unverified')], 'aal1', 'pending'],
  ['stale AAL2', [factor('unverified')], 'aal2', 'stale'],
  ['empty raw field', [], 'aal1', 'inventory-unknown'],
  ['omitted', undefined, 'aal1', 'inventory-unknown'],
  ['null', null, 'aal2', 'inventory-unknown'],
  ['wrong type', {}, 'aal1', 'inventory-unknown'],
  ['duplicate', [factor('verified'), factor('verified')], 'aal1', 'inventory-unknown'],
  ['unknown type', [{ ...factor('verified'), factor_type: 'phone' }], 'aal1', 'inventory-unknown'],
  ['unknown state', [factor('enabled')], 'aal1', 'inventory-unknown'],
  ['bad ID', [{ ...factor('verified'), id: 'foreign' }], 'aal1', 'inventory-unknown'],
  ['unsafe label', [{ ...factor('verified'), friendly_name: '<bad>\nsecret' }], 'aal1', 'inventory-unknown'],
]) test('native MFA evidence: ' + name, async t => {
  const keys = await signingFixture(), native = await keys.sign({ aal }, 'password')
  const user = { id: subject, is_anonymous: false, ...(factors === undefined ? {} : { factors }) }
  const f = await passwordFixture(t, url => json(url.pathname.endsWith('/jwks.json') ? keys.jwks : user))
  assert.equal((await f.client.auth.setSession(native)).error, null)
  const result = await inspectMfa(f.client, f.config, f.session)
  assert.equal(result.status, expected)
  assert.ok(Object.isFrozen(result))
  assert.doesNotMatch(JSON.stringify(result), /access_token|refresh_token|email|session_id|claims/)
  assert.deepEqual(f.logs, [])
})

for (const [name, response, expected] of [
  ['foreign account', { id: otherSubject, is_anonymous: false, factors: [factor('verified')] }, 'stale'],
  ['anonymous', { id: subject, is_anonymous: true, factors: [factor('verified')] }, 'stale'],
  ['rate limit', null, 'rate-limited'],
]) test('MFA refuses ' + name, async t => {
  const keys = await signingFixture(), native = await keys.sign({}, 'password')
  let probing = false
  const f = await passwordFixture(t, url => url.pathname.endsWith('/jwks.json') ? json(keys.jwks) :
    !probing ? json(native.user) : response ? json(response) : json({ message: 'sensitive provider text' }, 429))
  assert.equal((await f.client.auth.setSession(native)).error, null); probing = true
  assert.deepEqual(await inspectMfa(f.client, f.config, f.session), { status: expected })
})

test('refresh invalidates an in-flight factor read, including same subject', async t => {
  const keys = await signingFixture(), native = await keys.sign({}, 'password'), delayed = deferred()
  let reading = false
  const f = await passwordFixture(t, url => url.pathname.endsWith('/jwks.json') ? json(keys.jwks) :
    reading ? delayed.promise : json({ id: subject }))
  await f.client.auth.setSession(native); reading = true
  const pending = inspectMfa(f.client, f.config, f.session)
  await tick(); await tick()
  reading = false
  await f.client.auth.setSession(await keys.sign({ session_id: sessionId }, 'password'))
  delayed.resolve(json({ id: subject, is_anonymous: false, factors: [factor('verified')] }))
  assert.notEqual((await pending).status, 'challenge-required')
})

test('no session performs no provider inspection', async t => {
  const f = await passwordFixture(t, () => { throw new Error('unexpected request') })
  assert.deepEqual(await inspectMfa(f.client, f.config, f.session), { status: 'not-authenticated' })
  assert.deepEqual(f.calls, [])
})

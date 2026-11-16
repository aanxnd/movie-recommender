import test from 'node:test'
import assert from 'node:assert/strict'
import { createAccountDeletion } from './deletion-adapter.js'
import { mfaFixture } from './mfa-test-support.js'
import { otherSubject, json } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

const input = () => ({ password: 'synthetic-private', confirmation: 'PERMANENTLY DELETE MY ACCOUNT', requestId: crypto.randomUUID() })

test('account deletion default cannot create a client, send credentials or execute a request', async () => {
  const service = createAccountDeletion({})
  assert.equal(service.available, false)
  assert.deepEqual(await service.deleteAccount({ user_id: 42, authorized: true }), { status: 'unavailable' })
})

test('reviewed deletion adapter sends only a fenced native request and reports pending, never deleted', async t => {
  const f = await mfaFixture(t), body = input()
  f.state.handler = (url, init) => {
    assert.equal(url.pathname, '/api/auth/deletion'); assert.equal(init.method, 'POST')
    assert.match(init.headers.Authorization, /^Bearer /)
    assert.deepEqual(JSON.parse(init.body), { password: body.password, confirmation: body.confirmation, request_id: body.requestId })
    return json({ status: 'pending' })
  }
  const service = createAccountDeletion({ ...f.config, base: '/api' }, { reviewed: true })
  assert.deepEqual(await service.deleteAccount(body), { status: 'pending' })
  assert.equal((await service.deleteAccount({ ...body, user_id: 42 })).status, 'invalid')
  assert.equal(f.state.actions.length, 1)
})

for (const kind of ['network', 'deleted', 'rate', 'denied']) test('deletion does not replay or fabricate completion: ' + kind, async t => {
  const f = await mfaFixture(t)
  f.state.handler = () => {
    if (kind === 'network') throw new Error('private diagnostics')
    return json({ status: kind === 'deleted' ? 'deleted' : 'unknown' }, kind === 'rate' ? 429 : kind === 'denied' ? 401 : 200)
  }
  const service = createAccountDeletion({ ...f.config, base: '/api' }, { reviewed: true })
  const outcome = await service.deleteAccount(input())
  assert.equal(outcome.status, kind === 'rate' ? 'rate-limited' : kind === 'denied' ? 'reauthentication-required' : 'uncertain')
  assert.equal(f.state.actions.length, 1)
  assert.doesNotMatch(JSON.stringify(outcome) + f.logs.join(''), /synthetic-private|private diagnostics|Bearer/)
})

test('account switching and duplicate submission never publish old-account deletion status', async t => {
  const f = await mfaFixture(t), pending = deferred(), started = deferred()
  f.state.handler = () => { started.resolve(); return pending.promise }
  const service = createAccountDeletion({ ...f.config, base: '/api' }, { reviewed: true }), first = service.deleteAccount(input())
  await started.promise
  assert.equal((await service.deleteAccount(input())).status, 'busy')
  await f.client.auth.setSession(await f.sign({ sub: otherSubject }))
  pending.resolve(json({ status: 'pending' }))
  assert.equal((await first).status, 'cancelled')
  assert.equal(f.session.getSnapshot().userId, otherSubject)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { createPasswordResetRequest } from './password-reset-request.js'
import { consumePkceCallback, callbackResult } from './pkce-callback.js'
import { createSignupConfirmation } from './signup-confirmation.js'
import { runCredentialRequest } from './supabase-client.js'
import { deferred, tick } from './auth-test-support.js'
import { passwordFixture, json, origin, code, syntheticSession, subject, otherSubject } from './password-test-support.js'

for (const mode of ['existing', 'nonexistent', 'confirmed', 'unconfirmed', 'limited', 'provider', 'network']) {
  test('reset request never enumerates: ' + mode, async t => {
    const f = await passwordFixture(t, (url, init) => {
      assert.equal(url.pathname, '/auth/v1/recover'); assert.equal(url.searchParams.get('redirect_to'), origin + '/')
      const body = JSON.parse(init.body)
      assert.equal(body.code_challenge_method, 's256'); assert.ok(body.code_challenge)
      assert.equal(body.email, 'offline@example.invalid')
      if (mode === 'network') throw new Error('synthetic-private')
      return mode === 'limited' ? json({ msg: 'synthetic-private' }, 429) :
        mode === 'provider' ? json({ msg: 'synthetic-private' }, 503) : json({})
    })
    const request = createPasswordResetRequest(f.config)
    assert.deepEqual(await request('offline@example.invalid'), { status: 'check-email' })
    assert.deepEqual(f.calls, ['/auth/v1/recover'])
    assert.ok(!f.logs.join('').includes('synthetic-private'))
  })
}

test('invalid addresses never reach SDK; duplicate operations cannot release another request lock', async t => {
  const pending = deferred()
  const f = await passwordFixture(t, async () => { await pending.promise; return json({}) })
  const request = createPasswordResetRequest(f.config)
  for (const email of ['', null, 'bad', 'a\n@b.invalid']) assert.equal((await request(email)).status, 'invalid')
  assert.equal(f.calls.length, 0)
  const first = request('offline@example.invalid'); await tick()
  for (let i = 0; i < 2; i++) assert.equal((await request('other@example.invalid')).status, 'busy')
  pending.resolve(); await first; assert.equal(f.calls.length, 1)
})

test('abandoning a recovery request fences a late response that ignores cancellation', async t => {
  const pending = deferred(), abort = new AbortController()
  const f = await passwordFixture(t, async () => { await pending.promise; return json({}) })
  const promise = createPasswordResetRequest(f.config)('offline@example.invalid', { signal: abort.signal })
  await tick(); abort.abort(); assert.equal((await promise).status, 'cancelled')
  pending.resolve(); await tick(); assert.equal(f.session.getSnapshot().userId, null)
})

test('signup and recovery share one callback attempt and scrub secrets before any async work', async t => {
  const f = await passwordFixture(t, () => json(syntheticSession()))
  f.dom.window.localStorage.setItem('movelle.signup-confirmation-code-verifier', JSON.stringify('synthetic-verifier/recovery'))
  f.dom.window.history.replaceState(null, '', '/?code=' + code)
  const first = consumePkceCallback(f.config, 'recovery', () => callbackResult('unproven'))
  assert.equal(f.dom.window.location.href, origin + '/')
  assert.equal((await first).status, 'unproven')
  assert.equal(await first, await consumePkceCallback(f.config, 'recovery', () => assert.fail('Duplicate redemption')))
  assert.equal((await createSignupConfirmation(f.config).confirm()).status, 'invalid')
  assert.equal(f.calls.filter(x => x.endsWith('/token')).length, 1)
})

test('credential subject guard rejects a different account before SDK persistence', async t => {
  const f = await passwordFixture(t, () => json(syntheticSession(otherSubject)))
  const result = await runCredentialRequest(f.client, () => f.client.auth.signInWithPassword({
    email: 'offline@example.invalid', password: 'synthetic-password' }), { subject })
  assert.ok(result.error); assert.equal((await f.client.auth.getSession()).data.session, null)
})

test('SDK persistence guard rejects delayed writes after logout, even outside the HTTP response', async t => {
  const f = await passwordFixture(t, () => json({})), pending = deferred()
  const promise = runCredentialRequest(f.client, async () => {
    await pending.promise
    await f.client.auth.storage.setItem('movelle.signup-confirmation', 'synthetic-private')
  })
  await f.session.logout(); pending.resolve()
  await assert.rejects(promise, { message: 'Authentication configuration unavailable' })
  assert.equal(f.dom.window.localStorage.getItem('movelle.signup-confirmation'), null)
})

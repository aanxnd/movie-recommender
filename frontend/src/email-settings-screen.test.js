import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'

const mount = (t, name, service, signed = true) => mountAccount(t, 'email-settings-screen.jsx', name, { service }, signed)
for (const status of ['current-confirmed', 'current-unconfirmed', 'change-pending', 'unavailable']) {
  test('email settings show only fresh status, not addresses or metadata: ' + status, async t => {
    const f = await mount(t, 'EmailSettingsPanel', { inspect: async () => ({ status, email: 'private@example.invalid' }), requestChange: async () => ({ status: 'check-email' }) })
    assert.doesNotMatch(f.text(), /private@example.invalid|user_id|UUID/)
    assert.equal(Boolean(document.querySelector('form')), status === 'current-confirmed')
    if (status === 'change-pending') assert.match(f.text(), /Both old and new inboxes/)
  })
}
test('email change validates input, clears password/address and prevents double submission', async t => {
  const pending = deferred(), calls = []
  const f = await mount(t, 'EmailSettingsPanel', { inspect: async () => ({ status: 'current-confirmed' }),
    requestChange: async (password, email, options) => { calls.push({ password, email, signal: options.signal }); return pending.promise } })
  f.input('email', 'bad'); f.input('current', 'synthetic-current'); await f.submit(); assert.equal(calls.length, 0)
  f.input('email', 'private@example.invalid'); await f.submit(); await f.submit(); assert.equal(calls.length, 1)
  for (const input of document.querySelectorAll('input')) assert.equal(input.value, '')
  await act(async () => { pending.resolve({ status: 'check-email', private: 'private@example.invalid' }); await tick() })
  assert.match(f.text(), /Delivery and completion cannot be confirmed/); assert.equal(document.querySelector('form'), null)
  assert.equal(document.activeElement.getAttribute('role'), 'status'); assert.doesNotMatch(f.text(), /private@example.invalid|synthetic-current/)
})
for (const status of ['mfa-required', 'rate-limited', 'invalid', 'unavailable']) {
  test('native failures do not promote a requested address or expose diagnostics: ' + status, async t => {
    const f = await mount(t, 'EmailSettingsPanel', { inspect: async () => ({ status: 'current-confirmed' }), requestChange: async () => ({ status }) })
    f.input('email', 'private@example.invalid'); f.input('current', 'synthetic-current'); await f.submit()
    assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(f.text(), /email updated|private@example.invalid/)
  })
}
test('logout/account switches abort native email requests and ignore late results', async t => {
  const pending = deferred(); let signal
  const f = await mount(t, 'EmailSettingsPanel', { inspect: async () => ({ status: 'current-confirmed' }),
    requestChange: async (_, __, options) => { signal = options.signal; return pending.promise } })
  f.input('email', 'private@example.invalid'); f.input('current', 'synthetic-current'); await f.submit()
  await act(async () => { f.emit('SIGNED_IN', value('b')); f.emit('SIGNED_IN', value('a')); await tick(); pending.resolve({ status: 'check-email' }); await tick() })
  assert.equal(signal.aborted, true); assert.doesNotMatch(f.text(), /If this change can proceed/)
  await act(async () => { f.emit('SIGNED_OUT', null); await tick() }); assert.equal(document.querySelector('form'), null)
})
for (const status of ['unproven', 'missing', 'invalid', 'expired', 'unavailable', 'current-confirmed', 'change-pending']) {
  test('Strict Mode email callback reports only bound native evidence: ' + status, async t => {
    let once, count = 0
    const pending = deferred()
    const f = await mount(t, 'EmailChangeCallbackScreen', { confirm: () => once ??= (count++, pending.promise) })
    await act(async () => { pending.resolve({ status, generation: f.session.getSnapshot().generation }); await tick() })
    assert.equal(count, 1); assert.doesNotMatch(f.text(), /email updated|signup confirmed|private@/)
    if (status === 'current-confirmed') {
      assert.match(f.text(), /reports a confirmed current email/)
      await act(async () => { f.emit('SIGNED_IN', value('b')); await tick() })
      assert.doesNotMatch(f.text(), /reports a confirmed current email/)
    }
  })
}
test('an unstamped cached callback result cannot apply to another session generation', async t => {
  const f = await mount(t, 'EmailChangeCallbackScreen', { confirm: async () => ({ status: 'current-confirmed' }) })
  assert.match(f.text(), /did not establish an email-change context/)
})

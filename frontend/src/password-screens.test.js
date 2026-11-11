import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { readFile } from 'node:fs/promises'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'

const mount = (t, name, props, signed = false) => mountAccount(t, 'password-screens.jsx', name, props, signed)
function fill(f, changing = false) {
  if (changing) f.input('current', 'synthetic-current')
  f.input('password', 'synthetic-new'); f.input('confirmation', 'synthetic-new')
}
test('forgot-password validates email, prevents duplicates, clears address and focuses generic check-email guidance', async t => {
  const pending = deferred(); let calls = 0
  const f = await mount(t, 'ForgotPasswordScreen', { requestReset: async () => { calls++; return pending.promise } })
  f.input('email', 'invalid'); await f.submit(); assert.equal(calls, 0)
  f.input('email', 'offline@example.invalid'); await f.submit(); await f.submit()
  assert.equal(calls, 1); assert.equal(document.querySelector('input').value, '')
  await act(async () => { pending.resolve({ status: 'check-email', private: 'synthetic-private' }); await tick() })
  assert.match(f.text(), /Delivery cannot be confirmed/); assert.equal(document.activeElement.getAttribute('role'), 'status')
  assert.doesNotMatch(f.text(), /offline@example.invalid|synthetic-private/)
})
test('request provider failure has the same conditional result, never an email-existence assertion', async t => {
  const f = await mount(t, 'ForgotPasswordScreen', { requestReset: async () => { throw new Error('synthetic-private') } })
  f.input('email', 'offline@example.invalid'); await f.submit()
  assert.match(f.text(), /If an account can receive recovery email/); assert.doesNotMatch(f.text(), /synthetic-private/)
})
test('ordinary sign-in cannot display the recovery password form; missing integrations remain unavailable', async t => {
  const f = await mount(t, 'NewPasswordScreen', { recovery: { state: () => ({ status: 'unproven' }) } }, true)
  assert.equal(document.querySelector('form'), null); assert.match(f.text(), /ordinary sign-in does not authorize/)
})
test('password mismatch, labels, visibility and clearing use no React credential state', async t => {
  let calls = 0
  const f = await mount(t, 'ChangePasswordScreen', { sensitive: { changePassword: async () => { calls++; return { status: 'changed' } } } }, true)
  fill(f, true); f.input('confirmation', 'different'); await f.submit()
  assert.match(f.text(), /do not match/); assert.equal(calls, 0)
  for (const input of document.querySelectorAll('input')) assert.equal(input.value, '')
  for (const label of document.querySelectorAll('label')) assert.ok(document.getElementById(label.htmlFor))
  await f.click('[aria-label="Show new password"]'); assert.equal(document.querySelector('[name="password"]').type, 'text')
  fill(f, true); await f.submit(); assert.equal(calls, 1)
  assert.match(f.text(), /Password updated/); assert.doesNotMatch(f.text(), /synthetic/)
})
for (const status of ['invalid', 'invalid-password', 'mfa-required', 'expired', 'unproven', 'rate-limited', 'unavailable']) {
  test('password update reports only safe errors: ' + status, async t => {
    const f = await mount(t, 'NewPasswordScreen', { recovery: { state: () => ({ status: 'verified' }),
      setPassword: async () => ({ status, private: 'synthetic-private' }) } }, true)
    fill(f); await f.submit()
    assert.ok(document.querySelector('[role="alert"]')); assert.equal(document.activeElement.getAttribute('role'), 'alert')
    assert.doesNotMatch(f.text(), /synthetic-private|Password updated/)
  })
}
test('double-submit and logout cannot publish a late password success', async t => {
  const pending = deferred(); let calls = 0, signal
  const f = await mount(t, 'ChangePasswordScreen', { sensitive: { changePassword: async (_, __, options) => {
    calls++; signal = options.signal; return pending.promise
  } } }, true)
  fill(f, true); await f.submit(); await f.submit(); assert.equal(calls, 1)
  for (const input of document.querySelectorAll('input')) assert.equal(input.value, '')
  await act(async () => { f.emit('SIGNED_OUT', null); await tick(); pending.resolve({ status: 'changed' }); await tick() })
  assert.equal(signal.aborted, true); assert.doesNotMatch(f.text(), /Password updated/)
})
test('unmount cancels sensitive operations, including late progress and A to B to A transitions', async t => {
  const pending = deferred(); let options
  const f = await mount(t, 'SensitiveReauthenticationScreen', { sensitive: { changePassword: async (_, __, opts) => { options = opts; return pending.promise } } }, true)
  fill(f, true); await f.submit()
  await act(async () => { f.emit('SIGNED_IN', value('b')); f.emit('SIGNED_IN', value('a')); await tick() })
  assert.equal(options.signal.aborted, true)
  await act(async () => { options.onProgress({ status: 'verified' }); pending.resolve({ status: 'changed' }); await tick() })
  assert.doesNotMatch(f.text(), /Password updated|Current password confirmed/)
  await act(async () => f.root.render(null))
})
for (const status of ['missing', 'invalid', 'expired', 'unproven', 'unavailable', 'rate-limited']) {
  test('Strict Mode recovery callback remains fail-closed: ' + status, async t => {
    let once, attempts = 0
    const f = await mount(t, 'RecoveryCallbackScreen', { recovery: { state: () => ({ status: 'unproven' }),
      confirm: () => once ??= (attempts++, Promise.resolve({ status })) } }, true)
    assert.equal(attempts, 1); assert.equal(document.querySelector('form'), null)
    assert.doesNotMatch(f.text(), /Password updated|email verified/)
  })
}
test('genuine mocked recovery context can show the form, but production entry stays dormant', async t => {
  const f = await mount(t, 'RecoveryCallbackScreen', { recovery: { state: () => ({ status: 'verified' }),
    confirm: async () => ({ status: 'verified' }), setPassword: async () => ({ status: 'changed' }) } }, true)
  fill(f); await f.submit(); assert.match(f.text(), /Password updated/)
  const entry = await readFile(new URL('./main.jsx', import.meta.url), 'utf8')
  assert.doesNotMatch(entry, /password-|AuthProvider/)
})
for (const name of ['ForgotPasswordScreen', 'ChangePasswordScreen', 'RecoveryCallbackScreen']) {
  test('missing integration is explicitly unavailable: ' + name, async t => {
    const f = await mount(t, name, {}, true)
    assert.equal(document.querySelector('form'), null); assert.doesNotMatch(f.text(), /Password updated/)
  })
}
test('uncertain native mutation displays its error even after recovery context is consumed', async t => {
  let available = true
  const f = await mount(t, 'NewPasswordScreen', { recovery: { state: () => ({ status: available ? 'verified' : 'unproven' }),
    setPassword: async () => { available = false; return { status: 'unavailable' } } } }, true)
  fill(f); await f.submit(); assert.match(f.text(), /may have reached the service/)
  assert.equal(document.querySelector('form'), null)
})

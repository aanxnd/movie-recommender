import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { readFile } from 'node:fs/promises'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'

const mount = (t, actions) => mountAccount(t, 'email-code-screen.jsx', 'EmailCodeScreen', { actions })
test('explicit submit only, six ASCII digits, duplicate prevention and immediate input clearing', async t => {
  let calls = 0; const pending = deferred()
  const f = await mount(t, { verifyEmail: (email, token) => {
    calls++; assert.equal(email, 'offline@example.invalid'); assert.equal(token, '123456'); return pending.promise
  } })
  f.input('email', 'offline@example.invalid'); f.input('code', '12345'); await f.submit(); assert.equal(calls, 0)
  f.input('code', '123456'); await f.submit(); await f.submit()
  assert.equal(calls, 1); assert.equal(document.querySelector('[name="code"]').value, '')
  assert.equal(document.querySelector('[name="code"]').autocomplete, 'one-time-code')
  await act(async () => { pending.resolve({ status: 'expired', message: '123456 private' }); await tick() })
  assert.match(f.text(), /incorrect or expired/); assert.equal(document.activeElement.getAttribute('role'), 'alert')
  assert.doesNotMatch(document.body.innerHTML, /123456|private/)
})

for (const status of ['invalid', 'expired', 'rate-limited', 'unavailable', 'cancelled']) {
  test('safe provider failure and recovery presentation: ' + status, async t => {
    const f = await mount(t, { verifyEmail: async () => ({ status, message: '123456 private' }) })
    f.input('email', 'offline@example.invalid'); f.input('code', '123456'); await f.submit()
    assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(f.text(), /123456|private/)
    if (status === 'rate-limited') assert.equal(document.querySelector('button[type="button"].auth-submit').disabled, true)
  })
}

test('resend needs only an email, uses generic copy and enforces local cooldown', async t => {
  let calls = 0
  const f = await mount(t, { resendConfirmation: async email => { calls++; return { status: 'check-email' } } })
  f.input('email', 'offline@example.invalid'); await f.click('button[type="button"].auth-submit')
  await f.click('button[type="button"].auth-submit')
  assert.equal(calls, 1); assert.match(f.text(), /If signup can proceed/); assert.match(f.text(), /Resend available in/)
})

test('unmount and account changes abort a pending OTP; only the session drives signed-in UI', async t => {
  const pending = deferred(); let signal
  const f = await mount(t, { verifyEmail: (_email, _token, options) => { signal = options.signal; return pending.promise } })
  f.input('email', 'offline@example.invalid'); f.input('code', '123456'); await f.submit()
  await act(async () => { f.emit('SIGNED_IN', value('other')); await tick() })
  assert.equal(signal.aborted, true); assert.equal(document.querySelector('[name="code"]'), null)
  await act(async () => { pending.resolve({ status: 'signed-in' }); await tick() })
  assert.match(f.text(), /profile and MFA access are checked separately/)
})

for (const agent of ['Gmail', 'Microsoft 365 Safe Links']) {
  test(agent + ' scanning sees no redemption link; mounting never submits an OTP', async t => {
    const template = await readFile(new URL('../../supabase/templates/confirmation.html', import.meta.url), 'utf8')
    assert.match(template, /\{\{ \.Token \}\}/); assert.match(template, /Movelle/)
    assert.doesNotMatch(template, /href=|src=|ConfirmationURL|TokenHash|<form|<script/i)
    let calls = 0
    await mount(t, { verifyEmail: async () => { calls++ }, resendConfirmation: async () => { calls++ } })
    await tick(); assert.equal(calls, 0)
  })
}

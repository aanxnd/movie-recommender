import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { readFile } from 'node:fs/promises'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'

const mount = (t, name, props) => mountAccount(t, 'account-screens.jsx', name, props)
function fill(f, signup = false) {
  f.input('email', 'offline@example.invalid'); f.input('password', 'synthetic-private')
  if (signup) f.input('confirmation', 'synthetic-private')
}

test('signup labels, password controls, matching validation and native email validity', async t => {
  let calls = 0
  const f = await mount(t, 'SignupScreen', { actions: { signUp: async () => { calls++; return { status: 'check-email' } } } })
  assert.equal(document.querySelectorAll('label').length, 3)
  for (const label of document.querySelectorAll('label')) assert.ok(document.getElementById(label.htmlFor))
  fill(f, true); f.input('confirmation', 'different'); await f.submit()
  assert.match(f.text(), /passwords do not match/); assert.equal(calls, 0)
  assert.equal(document.activeElement.getAttribute('role'), 'alert')
  await f.click('[aria-label="Show password"]')
  assert.equal(document.querySelector('[name="password"]').type, 'text')
  assert.equal(document.querySelector('[aria-label="Hide password"]').getAttribute('aria-pressed'), 'true')
  f.input('email', 'not-an-email'); f.input('confirmation', 'synthetic-private'); await f.submit()
  assert.equal(calls, 0)
  f.input('email', 'offline@example.invalid'); await f.submit()
  assert.equal(calls, 1); assert.match(f.text(), /If signup can proceed/)
  assert.equal(document.querySelector('form'), null)
  assert.doesNotMatch(document.body.innerHTML, /synthetic-private|email verified|signup confirmed/i)
})

test('double submit is blocked and passwords clear before the request settles', async t => {
  const request = deferred(); let calls = 0
  const f = await mount(t, 'SignupScreen', { actions: { signUp: () => { calls++; return request.promise } } })
  fill(f, true); await f.submit(); await f.submit()
  assert.equal(calls, 1); assert.equal(document.querySelector('form').getAttribute('aria-busy'), 'true')
  assert.equal(document.querySelector('[name="password"]').value, '')
  assert.equal(document.querySelector('[name="confirmation"]').value, '')
  assert.equal(document.querySelector('[type="submit"]').disabled, true)
  await act(async () => { request.resolve({ status: 'check-email' }); await tick() })
  assert.match(f.text(), /Check your email/)
})

for (const status of ['invalid', 'rate-limited', 'unavailable', 'cancelled', 'busy', 'private-provider-error']) {
  test('login fixed error presentation: ' + status, async t => {
    const f = await mount(t, 'LoginScreen', { actions: { signIn: async () => ({ status, message: 'synthetic-private' }) } })
    fill(f); await f.submit()
    assert.ok(document.querySelector('[role="alert"]'))
    assert.equal(document.activeElement.getAttribute('role'), 'alert')
    assert.doesNotMatch(f.text(), /synthetic-private|private-provider-error/)
    assert.equal(document.querySelector('[name="password"]').value, '')
    if (status === 'invalid') assert.match(f.text(), /email confirmation/)
  })
}

test('login cannot grant profile access; SDK account changes discard a stale result', async t => {
  const request = deferred()
  const f = await mount(t, 'LoginScreen', { actions: { signIn: () => request.promise } })
  fill(f); await f.submit()
  await act(async () => { f.emit('SIGNED_IN', value('other')); request.resolve({ status: 'invalid' }); await tick() })
  assert.match(f.text(), /profile and account access are checked separately/)
  assert.doesNotMatch(f.text(), /Check your email and password/)
  await act(async () => { f.emit('SIGNED_OUT', null); await tick() })
  assert.ok(document.querySelector('form')); assert.equal(document.querySelector('[name="email"]').value, '')
})

test('logout during signup and unmount ignore late UI results and provider diagnostics', async t => {
  const request = deferred()
  const f = await mount(t, 'SignupScreen', { actions: { signUp: () => request.promise } })
  fill(f, true); await f.submit()
  await act(async () => { f.emit('SIGNED_OUT', null); await tick() })
  await act(async () => { request.resolve({ status: 'check-email' }); await tick() })
  assert.doesNotMatch(f.text(), /If signup can proceed/)
  await act(async () => f.root.render(null))
  assert.equal(document.querySelector('form'), null)
})

for (const status of ['missing', 'invalid', 'expired', 'unavailable', 'unproven', 'check-email', 'rate-limited']) {
  test('verification preserves the safe ' + status + ' state with no automatic navigation', async t => {
    const result = deferred(); let redemption = 0, once
    const actions = { confirm: () => once ??= (redemption++, result.promise) }
    const f = await mount(t, 'VerificationScreen', { actions, onSignIn() { throw new Error('Unexpected navigation') } })
    assert.match(f.text(), /Opening your link/)
    await act(async () => { result.resolve({ status, session: 'synthetic-private' }); await tick() })
    assert.equal(redemption, 1)
    assert.doesNotMatch(f.text(), /synthetic-private|email verified|signup confirmed/i)
    assert.ok(document.querySelector('[tabindex="-1"]'))
    if (status === 'unproven') assert.match(f.text(), /does not establish signup confirmation/)
    if (status === 'expired') assert.match(f.text(), /expired or already been used/)
  })
}

test('verification network rejection is generic, production startup remains untouched', async t => {
  const f = await mount(t, 'VerificationScreen', { actions: { confirm: async () => { throw new Error('synthetic-private') } } })
  assert.match(f.text(), /account service is unavailable/); assert.doesNotMatch(f.text(), /synthetic-private/)
  const entry = await readFile(new URL('./main.jsx', import.meta.url), 'utf8')
  assert.doesNotMatch(entry, /account-screens|AuthProvider|auth-actions/)
})

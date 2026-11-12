import test from 'node:test'
import assert from 'node:assert/strict'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'

const factors = [{ id: 'lost', label: 'Old phone', status: 'verified' }, { id: 'available', label: 'Independent device', status: 'verified' }]
async function fixture(t, initial = 'challenge-required') {
  const read = deferred(), calls = []
  let f, clear
  const result = (status, list = factors) => ({ status, factors: list, generation: f.session.getSnapshot().generation })
  const service = { inspect: () => read.promise, cancel: () => { clear?.() }, allInaccessible: () => ({ status: 'recovery-unavailable' }),
    verifyAlternative: async (...args) => { calls.push(['alternative', ...args]); return result('alternative-verified') },
    enrollReplacement: async () => { calls.push(['enroll']); return result('replacement-pending', [...factors, { id: 'new', label: 'Replacement', status: 'unverified' }]) },
    verifyReplacement: async (...args) => { clear?.(); calls.push(['verify', ...args]); return result('replacement-verified') },
    reviewRemoval: async () => { calls.push(['review']); return { status: 'removal-unavailable' } },
    presentSetup: mount => { clear = mount({ qr: 'data:image/svg+xml,%3Csvg%2F%3E', secret: 'SYNTHETICSETUPONLY' }); return () => clear?.() } }
  f = await mountAccount(t, 'mfa-recovery-screen.jsx', 'MfaRecoveryScreen', { service }, true)
  await act(async () => { read.resolve(result(initial)); await tick() })
  return { ...f, service, calls, result }
}

test('accessible alternative, pending replacement and verification stay distinct under Strict Mode', async t => {
  const f = await fixture(t)
  assert.equal(f.calls.length, 0)
  await f.input('totp', '123456'); await f.submit()
  assert.deepEqual(f.calls[0].slice(0, 4), ['alternative', 'lost', 'available', '123456'])
  assert.match(f.text(), /can now add a replacement/)
  assert.equal(document.activeElement.getAttribute('role'), 'status')
  await f.click('button.button-primary.auth-submit')
  assert.match(f.text(), /Replacement setup is not complete/)
  assert.match(f.text(), /SYNTHETICSETUPONLY/)
  assert.equal(document.querySelector('[name=totp]').type, 'password')
  await f.input('totp', '654321'); await f.submit()
  assert.match(f.text(), /replacement authenticator is verified/)
  assert.doesNotMatch(f.text(), /SYNTHETIC|654321|recovery complete/i)
  const p = f.dom.window.HTMLDialogElement.prototype
  p.showModal = function () { this.open = true }; p.close = function () { this.open = false }
  await f.click('button.button-secondary.auth-submit')
  assert.equal(document.activeElement.textContent, 'Cancel')
  assert.equal(document.querySelector('dialog .button-primary').disabled, true)
  assert.ok(!f.calls.some(x => x[0] === 'remove'))
  await f.click('dialog .button-secondary')
  assert.equal(document.activeElement.textContent, 'Review lost-authenticator removal')
})

test('all inaccessible explains refusal without password reset, recovery codes or support promises', async t => {
  const f = await fixture(t)
  await f.click('button.text-link.auth-submit')
  assert.match(f.text(), /Self-service recovery is unavailable/)
  assert.match(f.text(), /Password reset or access to email does not remove MFA/)
  assert.equal(document.querySelector('form'), null)
  assert.equal(f.calls.length, 0)
})

for (const status of ['inventory-unknown', 'abandoned-enrollment', 'mutation-uncertain', 'reauthentication-required'])
  test('unproven recovery never exposes mutation controls: ' + status, async t => {
    const f = await fixture(t, status)
    assert.equal(document.querySelector('form'), null)
    assert.equal(f.calls.length, 0)
    assert.doesNotMatch(f.text(), /can now add a replacement|replacement authenticator is verified/)
  })

test('late account A result cannot update account B or retain codes', async t => {
  const f = await fixture(t), wait = deferred()
  f.service.verifyAlternative = () => wait.promise
  await f.input('totp', '123456'); await f.submit()
  assert.equal(document.querySelector('[name=totp]').value, '')
  await act(async () => { f.emit('SIGNED_IN', value('other')); await tick() })
  await act(async () => { wait.resolve({ status: 'alternative-verified', factors, generation: 1 }); await tick() })
  assert.doesNotMatch(f.text(), /can now add a replacement|123456/)
})

test('provider diagnostics are never rendered', async t => {
  const f = await fixture(t)
  f.service.verifyAlternative = async () => { throw new Error('PRIVATE_NATIVE_TOKEN') }
  await f.input('totp', '123456'); await f.submit()
  assert.doesNotMatch(f.text(), /PRIVATE_NATIVE_TOKEN|123456/)
  assert.match(f.text(), /could not establish/)
})

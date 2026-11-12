import test from 'node:test'
import assert from 'node:assert/strict'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'

const factors = [{ id: 'a', label: 'Personal phone', status: 'verified' }, { id: 'b', label: 'Travel device', status: 'verified' }]
async function screen(t, status = 'challenge-required', login = false) {
  const reading = deferred(), calls = []
  let f, clear
  const observation = (state, list = factors) => ({ status: state, factors: list, generation: f.session.getSnapshot().generation })
  const service = { inspect: () => reading.promise, cancel: () => { clear?.(); calls.push('cancel') },
    verify: async (...args) => { calls.push(args); return observation('verified') },
    enroll: async () => observation('setup-pending', [...factors, { id: 'c', label: 'New device', status: 'unverified' }]),
    remove: async id => { calls.push(['remove', id]); return observation('removed', factors.filter(x => x.id !== id)) },
    presentSetup(mount) {
      clear = mount({ qr: 'data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%2F%3E', secret: 'SYNTHETICSETUPKEY' })
      return () => clear?.()
    } }
  f = await mountAccount(t, 'mfa-screens.jsx', login ? 'MfaLoginScreen' : 'MfaScreen', { service }, true)
  await act(async () => { reading.resolve(observation(status)); await tick() })
  return { ...f, service, calls, observation }
}

test('dormant login continuation masks/clears code, selects own factor, announces completion', async t => {
  const f = await screen(t, 'challenge-required', true)
  const input = document.querySelector('[name=totp]')
  assert.equal(input.type, 'password'); assert.equal(input.autocomplete, 'one-time-code')
  assert.equal(input.getAttribute('inputmode'), 'numeric')
  const select = document.querySelector('select'); select.value = 'b'
  await act(async () => { select.dispatchEvent(new f.dom.window.Event('change', { bubbles: true })) })
  await f.input('totp', '123456'); await f.submit()
  assert.equal(f.calls.find(x => Array.isArray(x))[0], 'b')
  assert.match(f.text(), /session passed native MFA/)
  assert.equal(document.activeElement.getAttribute('role'), 'status')
  assert.equal(document.querySelector('[name=totp]'), null)
  assert.doesNotMatch(f.text(), /123456/)
})

for (const state of ['inventory-unknown', 'unavailable', 'stale'])
  test('incomplete or failed evidence blocks operations: ' + state, async t => {
    const f = await screen(t, state)
    assert.equal(document.querySelector('form'), null)
    assert.equal([...document.querySelectorAll('button')].some(b => b.textContent === 'Add an authenticator'), false)
    assert.ok(document.querySelector('[role=alert]'))
    assert.doesNotMatch(f.text(), /MFA enabled|MFA complete/)
  })

test('QR and manual key exist only in the dedicated setup view and clear on cancel', async t => {
  const f = await screen(t, 'verified')
  await f.click('button.button-secondary.auth-submit')
  assert.match(f.text(), /Setup is not complete/)
  assert.equal(document.querySelector('.mfa-secret').textContent, 'SYNTHETICSETUPKEY')
  assert.match(document.querySelector('.mfa-qr').src, /^data:image\/svg/)
  await f.click('button.text-link.auth-submit')
  assert.doesNotMatch(f.text(), /SYNTHETICSETUPKEY/)
  assert.equal(document.querySelector('.mfa-qr'), null)
})

test('factor removal review defaults focus to cancel and cannot dispatch deletion', async t => {
  const f = await screen(t, 'verified')
  const prototype = f.dom.window.HTMLDialogElement.prototype
  prototype.showModal = function () { this.open = true }
  prototype.close = function () { this.open = false }
  await f.click('.mfa-factors button')
  assert.equal(document.activeElement.textContent, 'Cancel')
  assert.match(document.querySelector('dialog').textContent, /No factor will be deleted/)
  assert.equal(document.querySelector('dialog .button-primary').disabled, true)
  assert.equal(f.calls.some(x => Array.isArray(x) && x[0] === 'remove'), false)
  await f.click('dialog [data-cancel]')
  assert.equal(document.querySelector('dialog').open, false)
})

test('late verification after account switch cannot publish success or retain the code', async t => {
  const f = await screen(t), waiting = deferred()
  f.service.verify = () => waiting.promise
  await f.input('totp', '123456'); await f.submit()
  assert.equal(document.querySelector('[name=totp]').value, '')
  await act(async () => { f.emit('SIGNED_IN', value('different')); await tick() })
  await act(async () => { waiting.resolve({ status: 'verified', factors, generation: 1 }); await tick() })
  assert.doesNotMatch(f.text(), /session passed native MFA/)
  assert.doesNotMatch(f.text(), /123456/)
})

test('provider errors show fixed copy and never diagnostics', async t => {
  const f = await screen(t)
  f.service.verify = async () => { throw new Error('SENSITIVE_PROVIDER_RESPONSE') }
  await f.input('totp', '123456'); await f.submit()
  assert.doesNotMatch(f.text(), /SENSITIVE|123456/)
  assert.match(f.text(), /could not be confirmed/)
})

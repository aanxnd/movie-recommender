import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { pendingAccountLifecycle } from './account-lifecycle-contract.js'
import { tick, value } from './auth-test-support.js'

async function mount(t, signedIn = true) {
  const f = await mountAccount(t, 'account-lifecycle.jsx', 'AccountLifecycleControls', {}, signedIn)
  // jsdom lacks the native modal APIs; real focus/Tab/Escape behavior is checked in Chrome.
  f.dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true }
  f.dom.window.HTMLDialogElement.prototype.close = function () { this.open = false }
  return f
}
test('pending lifecycle contract never mutates data, even with forged ownership/authorization inputs', async () => {
  for (const operation of ['disable', 'deleteAccount'])
    assert.deepEqual(await pendingAccountLifecycle[operation]({ requestId: 'not-ownership', user_id: 207,
      subject: 'forged', reauthenticated: true, signal: new AbortController().signal }), { status: 'unavailable' })
})
for (const [kind, title] of [['disable', 'disabling'], ['delete', 'deletion']]) {
  test('review ' + title + ' is accessible and cannot execute a destructive action', async t => {
    const f = await mount(t)
    const trigger = [...document.querySelectorAll('button')].find(b => b.textContent === 'Review ' + title)
    await act(async () => { trigger.focus(); trigger.click(); await tick() })
    const dialog = document.querySelector('dialog')
    assert.equal(dialog.open, true); assert.match(dialog.textContent, /No account or data change/)
    assert.ok(document.getElementById(dialog.getAttribute('aria-labelledby')))
    assert.equal(document.activeElement.textContent, 'Cancel')
    assert.equal(dialog.querySelector('.button-primary').disabled, true)
    await f.click('input[type="checkbox"]'); assert.equal(dialog.querySelector('.button-primary').disabled, true)
    await f.click('[data-cancel]'); assert.equal(dialog.open, false); assert.equal(document.activeElement, trigger)
  })
}
test('signed-out users cannot open lifecycle controls', async t => {
  await mount(t, false)
  assert.ok([...document.querySelectorAll('section > div > button')].every(b => b.disabled))
  assert.equal(document.querySelector('dialog').open, false)
})
test('account switches and logout close confirmation without claiming success', async t => {
  const f = await mount(t)
  await f.click('.account-review-actions button'); assert.equal(document.querySelector('dialog').open, true)
  await act(async () => { f.emit('SIGNED_IN', value('b')); f.emit('SIGNED_IN', value('a')); await tick() })
  assert.equal(document.querySelector('dialog').open, false)
  await f.click('.account-review-actions button')
  await act(async () => { f.emit('SIGNED_OUT', null); await tick() })
  assert.equal(document.querySelector('dialog').open, false); assert.doesNotMatch(f.text(), /account is disabled|account was deleted/)
})

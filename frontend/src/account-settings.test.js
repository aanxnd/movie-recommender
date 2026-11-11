import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { accountSettingsResult } from './account-settings-contract.js'
import { deferred, tick, value } from './auth-test-support.js'

const snapshot = (username = 'MovieFan', revision = 'r1') => ({ status: 'ready', username, revision })
const mount = (t, account, signedIn = true, copies = 1) => mountAccount(t, 'account-settings.jsx', 'AccountSettingsScreen', { account }, signedIn, copies)

test('SDK-only authentication cannot invent a backend profile, username or ownership', async t => {
  const f = await mount(t)
  assert.match(f.text(), /waiting for a trusted backend/); assert.equal(document.querySelector('form'), null)
})
test('signed-out settings perform no backend calls', async t => {
  let calls = 0
  const f = await mount(t, { inspect: async () => { calls++; return snapshot() } }, false)
  assert.equal(calls, 0); assert.match(f.text(), /Sign in to check/)
})
test('malicious ownership claims and extra private fields never become authorized profile data', () => {
  for (const result of [{ ...snapshot(), user_id: 7 }, { ...snapshot(), email: 'private@example.invalid' },
    { ...snapshot(), subject: 'chosen' }, { ...snapshot(), revision: null }, { ...snapshot(), username: 'Admin' },
    { status: 'ready', username: 'MovieFan' }, { ...snapshot(), username: 'Ａlice' }])
    assert.deepEqual(accountSettingsResult(result, 'inspect'), { status: 'unavailable' })
})
test('form applies exact shared username rules and passes only desired state plus backend revision', async t => {
  const calls = [], pending = deferred()
  const f = await mount(t, { inspect: async options => { assert.deepEqual(Object.keys(options), ['signal']); return snapshot() },
    changeUsername: async (input, options) => { calls.push(input); assert.ok(options.signal instanceof AbortSignal); return pending.promise } })
  for (const name of ['Admin', 'ab', ' padded ', 'éclair']) { f.input('username', name); await f.submit() }
  assert.equal(calls.length, 0); assert.equal(document.activeElement.getAttribute('role'), 'alert')
  const forged = document.createElement('input'); forged.name = 'user_id'; forged.value = '207'
  document.querySelector('form').append(forged)
  f.input('username', 'mOvIeFan'); await f.submit(); await f.submit()
  assert.deepEqual(calls, [{ username: 'mOvIeFan', revision: 'r1' }])
  await act(async () => { pending.resolve({ status: 'updated', username: 'mOvIeFan', revision: 'r2' }); await tick() })
  assert.match(f.text(), /username is updated/)
})
test('case-insensitive collisions expose no other profile data', async t => {
  const f = await mount(t, { inspect: async () => snapshot(), changeUsername: async () => ({ status: 'username-taken' }) })
  f.input('username', 'OTHERNAME'); await f.submit()
  assert.match(document.querySelector('[role="alert"]').textContent, /username is unavailable/)
  assert.doesNotMatch(f.text(), /user_id|UUID|@/)
})
test('concurrent views use server revisions; frontend success cannot conceal an intervening update', async t => {
  let current = snapshot(), writes = 0
  // Future server contract simulation only; no endpoint/database implementation is claimed.
  const account = { inspect: async () => current, changeUsername: async ({ username, revision }) => {
    if (revision !== current.revision) return { status: 'conflict' }
    writes++; current = snapshot(username, 'r2'); return { ...current, status: 'updated' }
  } }
  const f = await mount(t, account, true, 2)
  await act(async () => {
    for (const [index, form] of [...document.querySelectorAll('form')].entries()) {
      form.querySelector('input').value = index ? 'SecondName' : 'FirstName'
      form.dispatchEvent(new f.dom.window.Event('submit', { bubbles: true, cancelable: true }))
    }
    await tick()
  })
  assert.equal(writes, 1); assert.match(f.text(), /changed during this request/)
  assert.equal(document.querySelectorAll('form').length, 1)
})
test('interrupted update recovery reinspects authoritative state without replaying mutation', async t => {
  let current = snapshot(), writes = 0
  const f = await mount(t, { inspect: async () => current, changeUsername: async () => {
    writes++; current = snapshot('RecoveredName', 'r2'); return { status: 'unavailable' }
  } })
  f.input('username', 'RecoveredName'); await f.submit(); assert.equal(document.querySelector('form'), null)
  await f.click('.button-secondary'); assert.match(f.text(), /authorized profile: RecoveredName/); assert.equal(writes, 1)
})
test('late update after A to B to A or logout cannot overwrite the current profile view', async t => {
  const pending = deferred(); let signal
  const f = await mount(t, { inspect: async () => snapshot(), changeUsername: async (_, options) => { signal = options.signal; return pending.promise } })
  f.input('username', 'PrivateName'); await f.submit()
  await act(async () => { f.emit('SIGNED_IN', value('b')); f.emit('SIGNED_IN', value('a')); await tick() })
  assert.equal(signal.aborted, true)
  await act(async () => { pending.resolve({ status: 'updated', username: 'PrivateName', revision: 'r2' }); await tick() })
  assert.doesNotMatch(f.text(), /PrivateName|username is updated/)
  await act(async () => { f.emit('SIGNED_OUT', null); await tick() }); assert.equal(document.querySelector('form'), null)
})
test('unexpected provider diagnostics or substituted username results never render as success', async t => {
  const f = await mount(t, { inspect: async () => snapshot(), changeUsername: async () => ({ status: 'updated', username: 'OtherName', revision: 'r2' }) })
  f.input('username', 'WantedName'); await f.submit()
  assert.doesNotMatch(f.text(), /OtherName|username is updated/); assert.equal(document.querySelector('form'), null)
})
test('unmount and server failures publish neither stale profile data nor diagnostics', async t => {
  const pending = deferred(); const signals = []
  const f = await mount(t, { inspect: options => { signals.push(options.signal); return pending.promise } })
  await act(async () => f.root.render(null)); assert.ok(signals.every(s => s.aborted))
  await act(async () => { pending.resolve({ ...snapshot(), email: 'private@example.invalid' }); await tick() })
  assert.doesNotMatch(f.text(), /MovieFan|private@example.invalid/)
})

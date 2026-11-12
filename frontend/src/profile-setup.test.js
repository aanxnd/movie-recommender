import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { mountAccount } from './account-test-support.js'
import { deferred, tick, value } from './auth-test-support.js'
import { usernameError, profileResult, pendingProvisioning } from './profile-provisioning.js'

const mount = (t, service, signedIn = true) => mountAccount(t, 'profile-setup.jsx', 'ProfileSetupScreen', { service }, signedIn)
const complete = username => ({ status: 'complete', username })
const eligible = async () => ({ status: 'eligible' })

test('exact ASCII username rules preserve spelling and reject reserved names without normalization', () => {
  for (const name of ['Ab_', 'CaseSensitive', 'a'.repeat(30)]) assert.equal(usernameError(name), null)
  for (const name of ['', 'ab', 'a'.repeat(31), ' abc', 'abc ', 'a-b', 'café', 'Ａbc', 'a\nb', null, 3, 'Admin', 'SUPPORT'])
    assert.ok(usernameError(name), String(name))
})

test('typed results fail closed for spoofed IDs, email flags and malformed success', () => {
  for (const reply of [null, [], true, { status: 'eligible', email_verified: true },
    { status: 'complete', username: 'Abc', user_id: 7 }, { status: 'complete', username: '<script>' },
    { status: 'complete' }, { status: 'unknown' }]) assert.equal(profileResult(reply, 'inspect').status, 'unavailable')
  assert.equal(profileResult({ status: 'eligible' }, 'provision').status, 'unavailable')
  assert.equal(profileResult({ status: 'username-taken' }, 'inspect').status, 'unavailable')
})

test('no adapter means pending integration, never a legacy registration fallback', async t => {
  const f = await mount(t)
  assert.match(f.text(), /Profile setup is not available yet/); assert.equal(document.querySelector('form'), null)
  assert.equal((await pendingProvisioning.provision({ username: 'Abc' }, { signal: new AbortController().signal })).status, 'unavailable')
})

test('uncertain commit has a focused check-only recovery, never automatic POST replay', async t => {
  let reads = 0, writes = 0
  const f = await mount(t, { inspect: async () => ++reads <= 2 ? { status: 'eligible' } : complete('Original'),
    provision: async () => { writes++; return { status: 'uncertain' } } })
  f.input('username', 'Alice'); await f.submit()
  assert.match(f.text(), /setup may have completed/)
  assert.equal(document.activeElement.getAttribute('role'), 'status')
  assert.equal(document.querySelector('form'), null)
  await f.click('button')
  assert.equal(writes, 1)
})

test('rate denial is sanitized and offers inspection without retrying a write', async t => {
  let writes = 0
  const f = await mount(t, { inspect: eligible, provision: async () => { writes++; return { status: 'rate-limited' } } })
  f.input('username', 'Alice'); await f.submit()
  assert.match(f.text(), /Too many setup attempts/)
  assert.equal(document.querySelector('form'), null)
  await f.click('button'); assert.equal(writes, 1)
})

test('SDK-only sign-in cannot bypass backend email eligibility', async t => {
  let writes = 0
  const f = await mount(t, { inspect: async () => ({ status: 'email-required' }), provision: async () => { writes++ } })
  assert.match(f.text(), /Complete email confirmation/); assert.equal(document.querySelector('form'), null); assert.equal(writes, 0)
})

test('signed-out screens perform no inspection or provisioning', async t => {
  let calls = 0
  const f = await mount(t, { inspect: async () => { calls++; return { status: 'eligible' } } }, false)
  assert.match(f.text(), /Sign in before/); assert.equal(calls, 0)
})

test('validated submission passes only exact username, prevents doubles and handles case collision', async t => {
  const request = deferred(); let calls = 0, received
  const service = { inspect: eligible, provision: (input, options) => {
    received = input; assert.ok(options.signal instanceof AbortSignal); calls++; return request.promise
  } }
  const f = await mount(t, service)
  f.input('username', 'Admin'); await f.submit(); assert.equal(calls, 0); assert.match(f.text(), /reserved/)
  f.input('username', 'mOvIeFan'); await f.submit(); await f.submit()
  assert.equal(calls, 1); assert.deepEqual(received, { username: 'mOvIeFan' })
  await act(async () => { request.resolve({ status: 'username-taken' }); await tick() })
  assert.match(f.text(), /username is unavailable/)
  assert.doesNotMatch(document.querySelector('[role="alert"]').textContent, /user_id|email|UUID/)
  assert.equal(document.activeElement.getAttribute('role'), 'alert')
})

test('concurrent/retried creation relies on an atomic idempotent server contract, not a frontend flag', async t => {
  let profile, calls = 0
  // Models the REQUIRED future server behavior; not proof that an endpoint exists.
  const service = { inspect: eligible, provision: async ({ username }) => {
    calls++; profile ??= complete(username); return profile
  } }
  const f = await mountAccount(t, 'profile-setup.jsx', 'ProfileSetupScreen', { service }, true, 2)
  await act(async () => {
    const forms = [...document.querySelectorAll('form')]
    for (const [index, form] of forms.entries()) {
      form.querySelector('input').value = index ? 'SecondName' : 'FirstName'
      form.dispatchEvent(new f.dom.window.Event('submit', { bubbles: true, cancelable: true }))
    }
    await tick()
  })
  assert.equal(calls, 2)
  assert.equal(document.querySelectorAll('[role="status"]').length, 2)
  for (const notice of document.querySelectorAll('[role="status"]')) assert.match(notice.textContent, /profile is ready: FirstName/)
})

test('interrupted setup recovers existing profile without automatically provisioning again', async t => {
  let writes = 0
  const f = await mount(t, { inspect: async () => complete('Existing_Name'), provision: async () => { writes++ } })
  assert.match(f.text(), /profile is ready: Existing_Name/); assert.equal(writes, 0)
})

for (const event of ['SIGNED_OUT', 'SIGNED_IN']) {
  test('pending setup cannot publish after ' + event + ', including account-switch A to B to A', async t => {
    const request = deferred(); let signal
    const f = await mount(t, { inspect: eligible, provision: (_, options) => { signal = options.signal; return request.promise } })
    f.input('username', 'PrivateName'); await f.submit()
    await act(async () => { f.emit(event, event === 'SIGNED_OUT' ? null : value('b')); await tick() })
    assert.equal(signal.aborted, true)
    await act(async () => { f.emit('SIGNED_IN', value('a')); await tick(); request.resolve(complete('PrivateName')); await tick() })
    assert.doesNotMatch(f.text(), /profile is ready: PrivateName/)
  })
}

test('provider rejection and malformed evidence stay generic; retry reinspects, never replays mutation', async t => {
  let reads = 0, writes = 0
  const f = await mount(t, { inspect: async () => { reads++; return { status: 'eligible' } },
    provision: async () => { writes++; throw new Error('synthetic-private-account') } })
  f.input('username', 'MovieFan'); await f.submit()
  assert.match(f.text(), /not available yet/); assert.doesNotMatch(f.text(), /synthetic-private-account/)
  const before = reads; await f.click('.button-secondary'); assert.ok(reads > before); assert.equal(writes, 1)
})

test('unmount aborts a pending observation without publishing or creating a profile', async t => {
  const request = deferred(); const signals = []; let writes = 0
  const f = await mount(t, { inspect: options => { signals.push(options.signal); return request.promise }, provision: async () => { writes++ } })
  await act(async () => f.root.render(null))
  assert.ok(signals.every(signal => signal.aborted))
  await act(async () => { request.resolve(complete('PrivateName')); await tick() })
  assert.equal(document.querySelector('form'), null); assert.equal(writes, 0)
})

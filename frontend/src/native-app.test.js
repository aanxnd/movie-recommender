import assert from 'node:assert/strict'
import test from 'node:test'
import { act } from 'react'
import { fixture, value, tick } from './auth-test-support.js'
import { mountAccount } from './account-test-support.js'

async function mount(t, signedIn = false, callback = { status: 'missing' }) {
  const f = fixture()
  f.load.resolve({ data: { session: signedIn ? value() : null }, error: null })
  f.exit.resolve({ error: null })
  const runtime = { session: f.session, callbackResult: Promise.resolve(callback), actions: {},
    profile: {}, mfa: {}, recovery: {}, email: { inspect: async () => ({ status: 'current-confirmed' }) },
    account: { inspect: async () => ({ status: 'ready', username: 'MovieFan', revision: '1' }) },
    passwords: { sensitive: {}, recovery: {}, requestReset: async () => ({ status: 'check-email' }) },
    movies: async path => path === '/users/me' ? { id: 1 } : path.includes('/ratings') ? { items: [], total: 0, next_after: null } : [] }
  const view = await mountAccount(t, 'native-app.jsx', 'NativeApp', { runtime })
  await act(async () => { await tick() })
  const click = label => act(async () => {
    const button = [...document.querySelectorAll('nav[aria-label="Account navigation"] button')].find(b => b.textContent === label)
    assert.ok(button); button.click(); await tick()
  })
  return { ...view, ...f, click }
}

test('native app preserves anonymous browsing, cinematic signup and theme controls without operator UI', async t => {
  const f = await mount(t)
  assert.ok(document.querySelector('nav[aria-label="Account navigation"]'))
  assert.doesNotMatch(f.text(), /PRIVATE LOCAL STAGING|Staging account navigation|Refresh session|Offline preview/)
  await f.click('Sign up')
  assert.match(f.text(), /Cinema done your way\./)
  assert.ok(document.querySelector('[aria-label="Change website theme"]'))
  assert.equal(document.querySelector('input[name="email"]').type, 'email')
})

test('native settings use the reviewed mutation screen and logout fences account content', async t => {
  const f = await mount(t, true)
  await f.click('Settings')
  assert.match(f.text(), /MovieFan/)
  assert.ok(document.querySelector('input[name="username"]'))
  assert.doesNotMatch(f.text(), /Username editing is unavailable/)
  await f.click('Sign out')
  assert.equal(f.counts.logout, 1)
  assert.doesNotMatch(f.text(), /MovieFan/)
  assert.match(f.text(), /Welcome back\./)
})

test('callback result cannot render protected profile data or claim signup-purpose evidence', async t => {
  const f = await mount(t, false, { status: 'unproven', flow: 'confirmation' })
  assert.match(f.text(), /does not independently grant access/)
  assert.doesNotMatch(f.text(), /MovieFan|confirmed successfully/)
})

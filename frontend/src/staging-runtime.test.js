import assert from 'node:assert/strict'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { createStagingRuntime } from './staging-runtime.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { json, projectUrl, syntheticSession, subject } from './password-test-support.js'
import { tick } from './auth-test-support.js'

function config(t, fetcher, path = '/') {
  const dom = new JSDOM('', { url: 'http://127.0.0.1:5173' + path }); t.after(() => dom.window.close())
  return { projectUrl, publishableKey: 'sb_publishable_offline', appOrigin: 'http://127.0.0.1:5173',
    base: '/api', browser: dom.window, fetcher }
}

test('one staging runtime restores SDK state, preserves legacy storage and exposes read-only profile data', async t => {
  const calls = [], c = config(t, async (url, init) => {
    const path = new URL(url).pathname; calls.push({ path, method: init.method })
    if (path === '/auth/v1/user') return json({ id: subject })
    if (path === '/api/auth/profile') return json({ status: 'complete', username: 'MovieFan' })
    if (path === '/auth/v1/logout') return json({})
    assert.fail('Unexpected transport')
  })
  c.browser.localStorage.setItem('movelle.identity.v1', 'private-legacy-fixture')
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  assert.equal((await runtime.callbackResult).status, 'missing')
  for (let i = 0; i < 20 && runtime.session.getSnapshot().status === 'restoring'; i++) await tick()
  assert.equal(runtime.session.getSnapshot().status, 'unauthenticated'); assert.equal(calls.length, 0)
  const client = getBrowserSupabaseClient(c)
  assert.equal((await client.auth.setSession(syntheticSession())).error, null)
  assert.equal(runtime.session.getSnapshot().status, 'authenticated')
  assert.deepEqual(await runtime.account.inspect(), { status: 'ready', username: 'MovieFan', revision: 'read-only' })
  assert.deepEqual(await runtime.account.changeUsername({ username: 'Other', revision: 'read-only' }), { status: 'unavailable' })
  assert.equal(calls.filter(c => c.method === 'POST').length, 0)
  await runtime.session.logout()
  assert.equal(c.browser.localStorage.getItem('movelle.identity.v1'), 'private-legacy-fixture')
})

test('unapproved runtime configuration scrubs before any SDK or network request', t => {
  const c = config(t, () => assert.fail('Unexpected provider I/O'), '/?code=private&next=https://evil.invalid')
  assert.throws(() => createStagingRuntime({ ...c, base: 'https://foreign.invalid' }), /Approved local/)
  assert.equal(c.browser.location.href, 'http://127.0.0.1:5173/')
  assert.equal(c.browser.localStorage.length, 0)
})

test('malicious callback parameters cannot turn staging bootstrap into a provider request', async t => {
  const c = config(t, () => assert.fail('Unexpected provider I/O'), '/?code=private&next=https://evil.invalid')
  const runtime = createStagingRuntime(c); t.after(() => runtime.stop())
  assert.equal((await runtime.callbackResult).status, 'invalid')
  assert.equal(c.browser.location.href, 'http://127.0.0.1:5173/')
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { createNativeRuntime } from './native-runtime.js'
import { createAccountSettings } from './account-settings-adapter.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { json, projectUrl, subject, otherSubject, syntheticSession } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

const targets = Object.freeze({ approved: true, mode: 'native-release', frontend_origin: 'https://movelle.test',
  api_origin: 'https://backend.test', supabase_url: projectUrl })
function setup(t, fetcher, path = '/') {
  const dom = new JSDOM('', { url: targets.frontend_origin + path })
  const config = { appOrigin: targets.frontend_origin, base: targets.api_origin, projectUrl,
    publishableKey: 'sb_publishable_offline', browser: dom.window, fetcher }
  const runtime = createNativeRuntime(config, targets), client = getBrowserSupabaseClient(config)
  t.after(async () => { await runtime.stop(); dom.window.close() })
  return { config, runtime, client, dom }
}

test('native composition preserves anonymous reads, uses one SDK and supports owned versioned settings', async t => {
  const calls = []
  const f = setup(t, async (url, init) => {
    const p = new URL(url); calls.push({ path: p.pathname, init })
    if (p.pathname === '/auth/v1/user') return json({ id: subject })
    if (p.pathname === '/movies/decades') return json([])
    if (p.pathname === '/auth/settings') return json({ status: init.method === 'PATCH' ? 'updated' : 'ready',
      username: 'MovieFan', revision: init.method === 'PATCH' ? '2' : '1' })
    assert.fail('Unexpected transport')
  })
  await f.runtime.movies('/movies/decades')
  assert.equal(calls[0].init.headers.Authorization, undefined)
  assert.deepEqual(await f.runtime.account.inspect(), { status: 'unavailable' })
  await f.client.auth.setSession(syntheticSession())
  assert.equal(createAccountSettings(f.config), f.runtime.account)
  assert.deepEqual(await f.runtime.account.inspect(), { status: 'ready', username: 'MovieFan', revision: '1' })
  assert.deepEqual(await f.runtime.account.changeUsername({ username: 'MovieFan', revision: '1' }),
    { status: 'updated', username: 'MovieFan', revision: '2' })
  assert.match(calls.at(-1).init.headers.Authorization, /^Bearer /)
  assert.deepEqual(JSON.parse(calls.at(-1).init.body), { username: 'MovieFan', revision: '1' })
  await f.runtime.account.changeUsername({ username: 'Other', revision: '1', user_id: 42 })
  assert.equal(calls.filter(c => c.init.method === 'PATCH').length, 1)
  await assert.rejects(f.runtime.movies('/users/me', { token: 'legacy' }))
})

test('unknown commits, conflicts and malformed replies never report success or replay writes', async t => {
  let mode = 'network', writes = 0
  const f = setup(t, async (url, init) => {
    if (new URL(url).pathname === '/auth/v1/user') return json({ id: subject })
    writes++; assert.equal(init.method, 'PATCH')
    if (mode === 'network') throw new Error('private diagnostics')
    return mode === 'conflict' ? json({ detail: 'private' }, 409) : json({ status: 'updated', username: 'MovieFan' })
  })
  await f.client.auth.setSession(syntheticSession())
  for (const state of ['network', 'conflict', 'malformed']) {
    mode = state
    assert.equal((await f.runtime.account.changeUsername({ username: 'MovieFan', revision: '1' })).status,
      state === 'conflict' ? 'conflict' : 'unavailable')
  }
  assert.equal(writes, 3)
})

test('account switching fences a delayed update and duplicate dispatch', async t => {
  const pending = deferred(); let writes = 0, current = subject
  const f = setup(t, async url => {
    if (new URL(url).pathname === '/auth/v1/user') return json({ id: current })
    writes++; return pending.promise
  })
  await f.client.auth.setSession(syntheticSession())
  const old = f.runtime.account.changeUsername({ username: 'OldOwner', revision: '1' })
  for (let i = 0; i < 20 && !writes; i++) await tick()
  assert.equal((await f.runtime.account.changeUsername({ username: 'Duplicate', revision: '1' })).status, 'unavailable')
  current = otherSubject; await f.client.auth.setSession(syntheticSession(otherSubject))
  pending.resolve(json({ status: 'updated', username: 'OldOwner', revision: '2' }))
  assert.equal((await old).status, 'unavailable'); assert.equal(writes, 1)
})

test('unapproved origins and malicious callback inputs scrub without network or secret diagnostics', async t => {
  const dom = new JSDOM('', { url: 'https://movelle.test/?code=private&next=https://evil.invalid' })
  t.after(() => dom.window.close())
  assert.throws(() => createNativeRuntime({ browser: dom.window }, targets), /Approved native configuration required/)
  assert.equal(dom.window.location.href, 'https://movelle.test/')
  const f = setup(t, () => assert.fail('Unexpected network'), '/?code=private&next=https://evil.invalid')
  assert.equal((await f.runtime.callbackResult).status, 'invalid')
  assert.equal(f.dom.window.location.href, 'https://movelle.test/')
})

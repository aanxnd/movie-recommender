import assert from 'node:assert/strict'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { readFile } from 'node:fs/promises'
import { getBrowserSupabaseClient } from './supabase-client.js'

const projectUrl = `https://${'a'.repeat(20)}.supabase.co`
function config(t, appOrigin = 'https://movelle.test') {
  const dom = new JSDOM('', { url: appOrigin })
  t.after(() => dom.window.close())
  return { projectUrl, publishableKey: 'sb_publishable_offline', appOrigin, browser: dom.window,
    fetcher: async () => new Response(JSON.stringify({ id: 'offline' }), { headers: { 'Content-Type': 'application/json' } }) }
}

test('one SDK client per browser with PKCE, shared SDK-owned storage and native refresh', async t => {
  const options = config(t), client = getBrowserSupabaseClient(options)
  assert.equal(client, getBrowserSupabaseClient({ ...options }))
  assert.equal(client.auth.flowType, 'pkce')
  assert.equal(client.auth.detectSessionInUrl, false)
  assert.equal(client.auth.autoRefreshToken, true)
  assert.equal(client.auth.storageKey, 'movelle.signup-confirmation')
  assert.equal(client.auth.persistSession, true)
  await client.auth.stopAutoRefresh()
})

for (const change of [{ projectUrl: '' }, { projectUrl: 'https://evil.invalid' },
  { projectUrl: projectUrl + '/auth/v1' }, { publishableKey: 'service_role' },
  { publishableKey: 'sb_secret_private' }, { appOrigin: undefined }, { appOrigin: 'https://movelle.test/' },
  { appOrigin: 'https://other.invalid' }, { storage: {} }, { browser: null }]) {
  test('invalid public configuration fails without exposing values', t => {
    assert.throws(() => getBrowserSupabaseClient({ ...config(t), ...change }),
      error => error.message === 'Authentication configuration unavailable')
  })
}

test('exact approved development origin works; localhost and other HTTP origins do not', t => {
  assert.ok(getBrowserSupabaseClient(config(t, 'http://127.0.0.1:5173')))
  for (const origin of ['http://localhost:5173', 'http://127.0.0.1:5174', 'http://movelle.test'])
    assert.throws(() => getBrowserSupabaseClient(config(t, origin)))
})

test('conflicting clients cannot manage the same browser session', t => {
  const options = config(t)
  getBrowserSupabaseClient(options)
  for (const change of [{ projectUrl: `https://${'b'.repeat(20)}.supabase.co` },
    { publishableKey: 'sb_publishable_another' }, { storage: config(t).browser.localStorage }, { fetcher: async () => {} }])
    assert.throws(() => getBrowserSupabaseClient({ ...options, ...change }))
})

test('SDK transport pins Auth origin, disallows redirects and strips sensitive diagnostics', async t => {
  let calls = 0
  const options = config(t)
  options.fetcher = async (_, init) => {
    calls++
    assert.equal(init.redirect, 'error')
    assert.equal(init.credentials, 'omit')
    assert.equal(init.referrerPolicy, 'no-referrer')
    assert.equal(init.cache, 'no-store')
    assert.ok(init.signal)
    throw new Error('synthetic-private-value')
  }
  const transport = getBrowserSupabaseClient(options).fetch
  await assert.rejects(transport(projectUrl + '/auth/v1/user'), { message: 'Authentication transport unavailable' })
  for (const url of ['https://evil.invalid/auth/v1/user', projectUrl + '/rest/v1/private'])
    await assert.rejects(transport(url), { message: 'Authentication transport unavailable' })
  assert.equal(calls, 1)
})

test('production entry remains dormant', async () => {
  const main = await readFile(new URL('./main.jsx', import.meta.url), 'utf8')
  assert.ok(!main.includes('supabase-client'))
})

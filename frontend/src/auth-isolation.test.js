import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { JSDOM } from 'jsdom'
import { IDENTITY_KEY, parseIdentity, readIdentity, saveIdentity, sameIdentity } from './identity.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { createAuthenticatedApi } from './auth-api.js'
import { fixture, tick, value } from './auth-test-support.js'
import { signingFixture, json, origin, projectUrl } from './password-test-support.js'

test('native SDK restoration/login/logout owns only its namespace and preserves legacy persistence', async t => {
  const dom = new JSDOM('', { url: origin }), keys = await signingFixture(), native = await keys.sign({}, 'password')
  const legacy = { id: 73, token: 'a'.repeat(43) }, entries = new Map(), accessed = [], network = []
  const storage = { getItem(key) { accessed.push(key); return entries.get(key) ?? null },
    setItem(key, data) { accessed.push(key); entries.set(key, data) },
    removeItem(key) { accessed.push(key); entries.delete(key) } }
  saveIdentity(legacy, storage); accessed.length = 0
  const config = { browser: dom.window, projectUrl, appOrigin: origin, storage, publishableKey: 'sb_publishable_offline',
    fetcher: async (url, init) => {
      const path = new URL(url).pathname; network.push(path)
      if (!path.endsWith('/user') && !path.endsWith('/logout')) assert.fail('Unexpected native request')
      assert.ok(!JSON.stringify(init).includes(legacy.token), 'Legacy credential escaped into native transport')
      return json(path.endsWith('/user') ? native.user : {})
    } }
  const client = getBrowserSupabaseClient(config)
  t.after(async () => { await client.auth.stopAutoRefresh(); dom.window.close() })
  assert.equal(getBrowserSupabaseClient(config), client)
  assert.equal((await client.auth.getSession()).data.session, null)
  assert.equal(network.length, 0)
  assert.ok(accessed.every(key => key.startsWith('movelle.signup-confirmation')))
  assert.equal((await client.auth.setSession(native)).error, null)
  assert.ok(sameIdentity(readIdentity(storage), legacy), 'Native login changed legacy identity')
  const sdkRecord = entries.get('movelle.signup-confirmation')
  assert.ok(sdkRecord?.includes(native.access_token))
  saveIdentity({ id: 84, token: 'b'.repeat(43) }, storage)
  assert.ok(entries.get('movelle.signup-confirmation') === sdkRecord, 'Legacy save changed native storage')
  assert.equal((await client.auth.signOut({ scope: 'local' })).error, null)
  assert.ok(sameIdentity(readIdentity(storage), { id: 84, token: 'b'.repeat(43) }))
  assert.ok(![...entries].some(([key, data]) => key !== IDENTITY_KEY && data.includes(native.access_token)))
})

test('a signed native JWT cannot be parsed or persisted as a legacy profile credential', async () => {
  const keys = await signingFixture(), native = await keys.sign({}, 'password')
  let saved = JSON.stringify({ id: 73, token: 'a'.repeat(43) }), writes = 0
  const storage = { getItem: () => saved, setItem: (_, next) => { writes++; saved = next } }
  const before = readIdentity(storage)
  assert.equal(parseIdentity({ id: 73, token: native.access_token }), null)
  assert.throws(() => saveIdentity({ id: 73, token: native.access_token }, storage), { message: 'Invalid profile credential.' })
  assert.equal(writes, 0)
  assert.ok(sameIdentity(before, readIdentity(storage)))
})

for (const status of [401, 403, 503]) test('native API rejection never reads/falls back to stored legacy credentials: ' + status, async t => {
  const f = fixture(), stop = f.session.subscribe(() => {}), keys = await signingFixture(), native = await keys.sign({}, 'password')
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  let reads = 0, calls = 0
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem() { reads++; return JSON.stringify({ id: 73, token: 'a'.repeat(43) }) } } })
  t.after(() => { stop(); if (descriptor) Object.defineProperty(globalThis, 'localStorage', descriptor); else delete globalThis.localStorage })
  f.load.resolve({ data: { session: { ...value(native.user.id), access_token: native.access_token } } }); await tick()
  const api = createAuthenticatedApi({ session: f.session, appOrigin: origin, browser: { location: { origin } }, base: '/api',
    fetcher: async (_, init) => {
      calls++; assert.ok(init.headers.Authorization === 'Bearer ' + native.access_token)
      return json({ detail: 'private-provider-diagnostic' }, status)
    } })
  await assert.rejects(api('/users/me', { access: 'authenticated' }), error =>
    error.status === status && !error.message.includes('private-provider-diagnostic') && !error.message.includes(native.access_token))
  assert.equal(calls, 1); assert.equal(reads, 0); assert.equal(f.counts.refresh, 0)
})

test('production import graph remains legacy-only while anonymous browsing keeps its live entry', async () => {
  const visited = new Set(), pending = [new URL('./main.jsx', import.meta.url)]
  while (pending.length) {
    const file = pending.pop()
    if (visited.has(file.href)) continue
    visited.add(file.href)
    const source = await readFile(file, 'utf8')
    // Literal ESM dependencies only; external packages/styles are not application bootstrap.
    for (const match of source.matchAll(/(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)['"](\.[^'"]+\.(?:js|jsx))['"]/g))
      pending.push(new URL(match[1], file))
  }
  const names = [...visited].map(href => new URL(href).pathname.split('/').pop())
  assert.ok(names.includes('App.jsx') && names.includes('identity.js') && names.includes('api.js'))
  assert.ok(!names.some(name => /^(?:supabase-|auth-|mfa-|password-|signup-confirmation|account-settings)/.test(name)),
    'Production entry imported dormant native authentication')
})

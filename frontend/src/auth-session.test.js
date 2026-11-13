import assert from 'node:assert/strict'
import test from 'node:test'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import { getSessionController } from './auth-session.js'
import { AuthProvider, useAuth } from './auth-context.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { deferred, tick, value, fixture } from './auth-test-support.js'

test('restoration, presentation-only state, shared controller and cleanup', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  assert.equal(f.session, getSessionController(f.client))
  assert.equal(f.session.getSnapshot().status, 'restoring')
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  assert.equal(f.session.getSnapshot().status, 'authenticated')
  assert.equal(f.session.getSnapshot().userId, 'user-a')
  assert.ok(Object.isFrozen(f.session.getSnapshot()))
  assert.ok(!JSON.stringify(f.session.getSnapshot()).includes('synthetic'))
  assert.equal(await f.session.withAccess(lease => lease.userId), 'user-a')
  stop(); assert.equal(f.counts.cleanup, 1)
  await assert.rejects(f.session.withAccess(() => true), { message: 'Session unavailable' })
})

test('Strict Mode subscription teardown/remount shares a pending restore and ignores detached events', async () => {
  const f = fixture()
  const stop = f.session.subscribe(() => {}); await tick(); stop()
  const again = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: null }, error: null }); await tick()
  assert.equal(f.counts.restore, 1)
  assert.equal(f.session.getSnapshot().status, 'unauthenticated')
  again(); f.emit('SIGNED_IN', value())
  assert.equal(f.session.getSnapshot().status, 'unauthenticated')
  assert.equal(f.counts.subscriptions, f.counts.cleanup)
})

test('a newer SDK event cannot be overwritten by late initial restoration', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  await tick(); f.emit('SIGNED_IN', value('user-b'))
  f.load.resolve({ data: { session: value('user-a') }, error: null }); await tick()
  assert.equal(f.session.getSnapshot().userId, 'user-b'); stop()
})

test('observed SDK logout stays distinct from initial absence and fences late restoration', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  await tick(); f.emit('SIGNED_OUT', null)
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  assert.equal(f.session.getSnapshot().status, 'unauthenticated')
  assert.equal(f.session.getSnapshot().logoutOutcome, 'sdk-observed')
  await assert.rejects(f.session.withAccess(() => true))
  f.emit('SIGNED_IN', value()) // A subsequent explicit sign-in remains available.
  assert.equal(f.session.getSnapshot().logoutOutcome, null); stop()
})

test('multiple consumers share one SDK subscription and unmounted restoration cannot publish', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {}), another = f.session.subscribe(() => {})
  await tick(); stop(); assert.equal(f.counts.cleanup, 0)
  another(); f.load.resolve({ data: { session: value() }, error: null }); await tick()
  assert.equal(f.counts.subscriptions, 1); assert.equal(f.counts.cleanup, 1)
  assert.equal(f.session.getSnapshot().userId, null)
})

for (const result of [null, {}, { error: { status: 503, message: 'synthetic-private' } },
  { data: { session: { access_token: 'synthetic-private' } }, error: null }]) {
  test('unusable restoration never produces credentials or raw provider errors', async () => {
    const f = fixture(), stop = f.session.subscribe(() => {})
    f.load.resolve(result); await tick()
    assert.equal(f.session.getSnapshot().userId, null)
    assert.ok(['error', 'unavailable'].includes(f.session.getSnapshot().status))
    assert.ok(!JSON.stringify(f.session.getSnapshot()).includes('synthetic-private'))
    await assert.rejects(f.session.withAccess(() => true)); stop()
  })
}

test('concurrent refreshes share one call; auto-refresh events preserve the identity fence', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  const one = f.session.refresh(), two = f.session.refresh()
  assert.equal(one, two); assert.equal(f.session.getSnapshot().status, 'refreshing')
  const live = deferred(), request = f.session.withAccess(() => live.promise)
  f.emit('TOKEN_REFRESHED', value())
  f.renewal.resolve({ data: { session: value() }, error: null }); await one
  live.resolve('ok'); assert.equal(await request, 'ok')
  assert.equal(f.counts.refresh, 1); stop()
})

for (const status of [0, 400, 401, 429, 503]) {
  test('refresh failure clears credentials and redacts provider diagnostics: ' + status, async () => {
    const f = fixture(), stop = f.session.subscribe(() => {})
    f.load.resolve({ data: { session: value() }, error: null }); await tick()
    const op = f.session.refresh()
    f.renewal.resolve({ data: { session: null }, error: { status, message: 'synthetic-private' } })
    await assert.rejects(op, { message: 'Session unavailable' })
    assert.equal(f.session.getSnapshot().userId, null)
    assert.ok(!JSON.stringify(f.session.getSnapshot()).includes('synthetic'))
    await assert.rejects(f.session.withAccess(() => true)); stop()
  })
}

test('expired restoration refreshes once and cannot accept a still-expired response', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: value('user-a', 1) }, error: null }); await tick()
  assert.equal(f.session.getSnapshot().status, 'refreshing')
  f.renewal.resolve({ data: { session: value('user-a', 1) }, error: null }); await tick()
  assert.equal(f.counts.refresh, 1); assert.equal(f.session.getSnapshot().status, 'error'); stop()
})

test('logout during refresh immediately invalidates requests and stale refresh cannot resurrect it', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  const refresh = f.session.refresh(), out = f.session.logout()
  assert.equal(out, f.session.logout())
  assert.equal(f.session.getSnapshot().status, 'logging-out')
  assert.equal(f.session.getSnapshot().userId, null)
  f.emit('TOKEN_REFRESHED', value())
  f.renewal.resolve({ data: { session: value() }, error: null })
  await assert.rejects(refresh)
  f.exit.resolve({ error: null }); assert.deepEqual(await out, { local: true, provider: 'sdk-accepted' })
  f.emit('TOKEN_REFRESHED', value())
  assert.equal(f.session.getSnapshot().status, 'unauthenticated')
  assert.equal(f.counts.logout, 1); stop()
})

test('logout outage reports unconfirmed provider logout while UI stays locally invalidated', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  const pending = deferred(), request = f.session.withAccess(lease => { assert.ok(!lease.signal.aborted); return pending.promise })
  const out = f.session.logout()
  f.exit.resolve({ error: { status: 0, message: 'synthetic-private' } }); await out
  pending.resolve('late private result'); await assert.rejects(request, { name: 'AbortError' })
  assert.equal(f.session.getSnapshot().logoutOutcome, 'unconfirmed')
  assert.equal(f.session.getSnapshot().userId, null); stop()
})

test('logout cancels operations waiting for refresh before SDK work settles', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  const refresh = f.session.refresh(), refreshRejected = assert.rejects(refresh)
  const request = f.session.withAccess(() => assert.fail('Stale operation dispatched'))
  const rejected = assert.rejects(request, { name: 'AbortError' })
  const out = f.session.logout()
  await rejected // Neither SDK refresh nor logout has completed yet.
  f.exit.resolve({ error: null }); await out
  f.renewal.resolve({ data: { session: value() }, error: null }); await refreshRejected
  stop()
})

test('account switches including A to B to A invalidate old request results', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  const late = deferred(), request = f.session.withAccess(() => late.promise)
  const generation = f.session.getSnapshot().generation
  f.emit('SIGNED_IN', value('user-b')); f.emit('SIGNED_IN', value('user-a'))
  late.resolve('private'); await assert.rejects(request, { name: 'AbortError' })
  assert.ok(f.session.getSnapshot().generation > generation); stop()
})

test('React provider survives actual Strict Mode and exposes no transport credentials', async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'https://movelle.test' })
  globalThis.window = dom.window; globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const { createRoot } = await import('react-dom/client')
  const f = fixture(), root = createRoot(document.getElementById('root'))
  let context
  function Probe() { context = useAuth(); return React.createElement('span', null, context.status) }
  try {
    await act(async () => root.render(React.createElement(React.StrictMode, null,
      React.createElement(AuthProvider, { session: f.session }, React.createElement(Probe)))))
    await act(async () => { f.load.resolve({ data: { session: value() }, error: null }); await tick() })
    assert.equal(context.status, 'authenticated')
    assert.deepEqual(Object.keys(context).sort(), ['error', 'logout', 'logoutOutcome', 'generation', 'refresh', 'status', 'userId'].sort())
    assert.ok(!JSON.stringify(context).includes('synthetic'))
    assert.equal(f.counts.restore, 1)
    await act(async () => root.unmount())
    assert.equal(f.counts.subscriptions, f.counts.cleanup)
  } finally { dom.window.close(); delete globalThis.window; delete globalThis.document; delete globalThis.IS_REACT_ACT_ENVIRONMENT }
})

test('pinned SDK coalesces a concurrent native refresh and clears its storage on local logout outage', async t => {
  const dom = new JSDOM('', { url: 'https://movelle.test' }), pending = deferred(), logs = []
  const id = '12345678-1234-4234-9234-123456789abc'
  const encode = data => Buffer.from(JSON.stringify(data)).toString('base64url')
  const token = encode({ alg: 'ES256' }) + '.' + encode({ sub: id, exp: Math.floor(Date.now()/1000)+3600 }) + '.c3ludGhldGlj'
  const body = { access_token: token, refresh_token: 'synthetic-refresh', expires_in: 3600, token_type: 'bearer', user: { id } }
  let refreshCalls = 0
  t.mock.method(console, 'error', error => logs.push(String(error)))
  const sdk = getBrowserSupabaseClient({ projectUrl: `https://${'a'.repeat(20)}.supabase.co`,
    publishableKey: 'sb_publishable_offline', appOrigin: 'https://movelle.test', browser: dom.window,
    fetcher: async url => {
      const path = new URL(url).pathname
      if (path.endsWith('/logout')) throw new Error('synthetic-private')
      if (path.endsWith('/token')) { refreshCalls++; await pending.promise }
      return new Response(JSON.stringify(path.endsWith('/user') ? { id } : body), {
        headers: { 'Content-Type': 'application/json' } })
    } })
  let stop
  try {
    assert.equal((await sdk.auth.setSession(body)).error, null)
    const controller = getSessionController(sdk)
    stop = controller.subscribe(() => {})
    for (let i = 0; i < 20 && controller.getSnapshot().status !== 'authenticated'; i++) await tick()
    const native = sdk.auth.refreshSession(); await tick()
    const managed = controller.refresh(); pending.resolve()
    await Promise.all([native, managed]); assert.equal(refreshCalls, 1)
    const out = await controller.logout()
    assert.equal(out.provider, 'unconfirmed')
    assert.equal(dom.window.localStorage.getItem('movelle.signup-confirmation'), null)
    assert.equal(controller.getSnapshot().userId, null)
    const diagnostics = logs.join('') + JSON.stringify(controller.getSnapshot())
    assert.ok(![token, 'synthetic-refresh', 'synthetic-private'].some(secret => diagnostics.includes(secret)))
  } finally { stop?.(); await sdk.auth.stopAutoRefresh(); dom.window.close() }
})

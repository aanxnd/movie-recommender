import assert from 'node:assert/strict'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { createAuthActions } from './auth-actions.js'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { deferred, tick } from './auth-test-support.js'

const id = '12345678-1234-4234-9234-123456789abc', other = '87654321-4321-4321-8321-cba987654321'
const user = identifier => ({ id: identifier, email: 'offline@example.invalid', email_confirmed_at: '2026-01-01T00:00:00Z' })
function session(identifier = id) {
  const b64 = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  return { access_token: b64({ alg: 'ES256' }) + '.' + b64({ sub: identifier, exp: Math.floor(Date.now()/1000)+3600 }) + '.c3ludGhldGlj',
    refresh_token: 'synthetic-refresh', token_type: 'bearer', expires_in: 3600, user: user(identifier) }
}
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: {
  'Content-Type': 'application/json', ...(body.code ? { 'X-Supabase-Api-Version': '2024-01-01' } : {}) } })
async function setup(t, mode = 'ok') {
  const dom = new JSDOM('', { url: 'https://movelle.test' }), pending = deferred(), calls = [], logs = [], requests = []
  let redeemed = false
  t.mock.method(console, 'error', error => logs.push(String(error)))
  const config = { projectUrl: `https://${'a'.repeat(20)}.supabase.co`, publishableKey: 'sb_publishable_offline',
    appOrigin: 'https://movelle.test', browser: dom.window, fetcher: async (url, init) => {
      const path = new URL(url).pathname; calls.push(path)
      requests.push({ url, method: init.method, body: init.body && JSON.parse(init.body) })
      if (path.endsWith('/logout')) return json({})
      if (path.endsWith('/user')) return json(user(other))
      if (mode === 'pending') await pending.promise // Deliberately ignores abort.
      if (mode === 'network') throw new Error('synthetic-private')
      if (mode === 'notfound') return json({ code: 'user_not_found' }, 404)
      if (mode === 'expired' || (path.endsWith('/verify') && redeemed)) return json({ code: 'otp_expired' }, 403)
      if (path.endsWith('/verify')) {
        redeemed = true
        const result = session()
        if (mode === 'malformed') return new Response('not JSON')
        if (mode === 'future') result.user.email_confirmed_at = '2999-01-01T00:00:00Z'
        if (mode === 'wrong-account') result.user.email = 'other@example.invalid'
        if (mode === 'unverified') result.user.email_confirmed_at = null
        if (mode === 'rate') return json({ code: 'over_request_rate_limit' }, 429)
        return json(result)
      }
      if (mode === 'rate') return json({ error_code: 'over_request_rate_limit', msg: 'synthetic-private' }, 429)
      if (mode === 'existing') return json({ error_code: 'user_already_exists', msg: 'synthetic-private' }, 400)
      if (['invalid', 'unconfirmed', 'weak'].includes(mode)) return json({ error_code:
        { invalid: 'invalid_credentials', unconfirmed: 'email_not_confirmed', weak: 'weak_password' }[mode], msg: 'synthetic-private' }, 400)
      return json(path.endsWith('/signup') ? user(id) : session())
    } }
  const sdk = getBrowserSupabaseClient(config), controller = getSessionController(sdk), stop = controller.subscribe(() => {})
  t.after(async () => { stop(); await sdk.auth.stopAutoRefresh(); dom.window.close() })
  for (let i = 0; i < 30 && controller.getSnapshot().status === 'restoring'; i++) await tick()
  return { actions: createAuthActions(config), sdk, controller, pending, calls, requests, logs, dom }
}

test('native login uses the shared session, returns no credentials and never provisions', async t => {
  const f = await setup(t)
  assert.deepEqual(await f.actions.signIn('offline@example.invalid', 'synthetic-password'), { status: 'signed-in' })
  assert.equal(f.controller.getSnapshot().userId, id)
  assert.deepEqual(f.calls, ['/auth/v1/token'])
  assert.ok(!JSON.stringify(f.controller.getSnapshot()).includes('synthetic'))
})

test('new and existing signup responses are indistinguishable without claiming verification', async t => {
  for (const mode of ['ok', 'existing']) {
    const f = await setup(t, mode)
    assert.deepEqual(await f.actions.signUp('offline@example.invalid', 'synthetic-password'), { status: 'check-email' })
    assert.equal(f.controller.getSnapshot().userId, null)
  }
})

for (const mode of ['invalid', 'unconfirmed', 'weak', 'network', 'rate']) {
  test('known provider failures expose only safe statuses: ' + mode, async t => {
    const f = await setup(t, mode)
    const result = await f.actions.signIn('offline@example.invalid', 'synthetic-password')
    assert.equal(result.status, mode === 'network' ? 'unavailable' : mode === 'rate' ? 'rate-limited' : 'invalid')
    assert.ok(!JSON.stringify(result).includes('synthetic'))
    assert.ok(!f.logs.join('').includes('synthetic'))
  })
}

test('duplicate consumers cannot clear another credential operation busy lock', async t => {
  const f = await setup(t, 'pending')
  const first = f.actions.signIn('offline@example.invalid', 'synthetic-password'); await tick()
  for (let i = 0; i < 2; i++) assert.equal((await f.actions.signIn('other@example.invalid', 'synthetic-password')).status, 'busy')
  f.pending.resolve(); await first
  assert.equal(f.calls.length, 1)
})

for (const kind of ['signIn', 'signUp']) {
  test('logout cancels a pending ' + kind + ' before late SDK persistence', async t => {
    const f = await setup(t, 'pending')
    const operation = f.actions[kind]('offline@example.invalid', 'synthetic-password'); await tick()
    await f.controller.logout()
    assert.equal((await operation).status, 'cancelled')
    f.pending.resolve(); await tick()
    assert.equal(f.controller.getSnapshot().userId, null)
    assert.equal((await f.sdk.auth.getSession()).data.session, null)
  })
}

test('another account signing in cancels an older credential response instead of overwriting it', async t => {
  const f = await setup(t, 'pending')
  const operation = f.actions.signIn('offline@example.invalid', 'synthetic-password'); await tick()
  await f.sdk.auth.setSession(session(other))
  assert.equal((await operation).status, 'cancelled')
  f.pending.resolve(); await tick()
  assert.equal(f.controller.getSnapshot().userId, other)
  assert.equal((await f.sdk.auth.getSession()).data.session.user.id, other)
})

test('email code uses the pinned SDK POST, never a link, and provider rejects replay', async t => {
  const f = await setup(t)
  assert.equal((await f.actions.verifyEmail('offline@example.invalid', '482913')).status, 'signed-in')
  const request = f.requests[0]
  assert.equal(request.method, 'POST'); assert.equal(new URL(request.url).search, '')
  assert.deepEqual([request.body.email, request.body.token, request.body.type], ['offline@example.invalid', '482913', 'email'])
  assert.ok(!JSON.stringify({ ...f.dom.window.localStorage }).includes('482913'))
  await f.controller.logout()
  assert.equal((await f.actions.verifyEmail('offline@example.invalid', '482913')).status, 'expired')
  assert.equal(f.controller.getSnapshot().userId, null)
})

for (const mode of ['wrong-account', 'unverified', 'future', 'malformed', 'expired', 'network', 'rate']) {
  test('email verification rejects unsafe evidence without persistence or diagnostics: ' + mode, async t => {
    const f = await setup(t, mode)
    const result = await f.actions.verifyEmail('offline@example.invalid', '123456')
    assert.equal(result.status, mode === 'expired' ? 'expired' : mode === 'rate' ? 'rate-limited' : 'unavailable')
    assert.equal(f.controller.getSnapshot().userId, null)
    assert.equal((await f.sdk.auth.getSession()).data.session, null)
    assert.doesNotMatch(JSON.stringify({ result, logs: f.logs }), /123456|offline@|synthetic|other@/)
  })
}

test('invalid codes never reach the provider; resend does not enumerate accounts', async t => {
  const f = await setup(t)
  for (const code of ['', '12345', '1234567', '１２３４５６', ' 123456', 123456, null])
    assert.equal((await f.actions.verifyEmail('offline@example.invalid', code)).status, 'invalid')
  assert.deepEqual(f.calls, [])
  for (const mode of ['ok', 'existing', 'notfound']) {
    const e = await setup(t, mode)
    assert.equal((await e.actions.resendConfirmation('offline@example.invalid')).status, 'check-email')
    assert.equal(e.requests[0].body.type, 'signup')
    assert.equal(e.controller.getSnapshot().userId, null)
  }
  for (const [mode, status] of [['rate', 'rate-limited'], ['network', 'unavailable']])
    assert.equal((await (await setup(t, mode)).actions.resendConfirmation('offline@example.invalid')).status, status)
})

test('abort, duplicate requests and competing account changes cannot persist a late OTP session', async t => {
  for (const change of ['abort', 'account', 'logout']) {
    const f = await setup(t, 'pending'), abort = new AbortController()
    const operation = f.actions.verifyEmail('offline@example.invalid', '123456', { signal: abort.signal }); await tick()
    assert.equal((await f.actions.resendConfirmation('offline@example.invalid')).status, 'busy')
    if (change === 'abort') abort.abort()
    if (change === 'logout') await f.controller.logout()
    if (change === 'account') await f.sdk.auth.setSession(session(other))
    assert.notEqual((await operation).status, 'signed-in')
    f.pending.resolve(); await tick()
    assert.equal(f.controller.getSnapshot().userId, change === 'account' ? other : null)
  }
})

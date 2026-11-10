import assert from 'node:assert/strict'
import test from 'node:test'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { JSDOM } from 'jsdom'
import { createClient } from '@supabase/supabase-js'
import { createSignupConfirmation } from './signup-confirmation.js'

const origin = 'https://movelle.test'
const project = `https://${'a'.repeat(20)}.supabase.co`
const code = '12345678-1234-4234-9234-123456789abc'
const issued = Math.floor(Date.now()/1000)
const user = { id: '87654321-4321-4321-8321-cba987654321', aud: 'authenticated', role: 'authenticated', email: 'offline@example.invalid',
  email_confirmed_at: '2026-01-01T00:00:00Z', app_metadata: {}, user_metadata: {} }
const response = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})
function environment(t, path = '/', mode = 'ok') {
  const dom = new JSDOM('', { url: origin + path })
  t.after(() => dom.window.close())
  const calls = []
  let challenge, used = false
  const config = { projectUrl: project, publishableKey: 'sb_publishable_offline', appOrigin: origin,
    browser: dom.window, fetcher: async (url, init) => {
      const target = new URL(url), body = init.body ? JSON.parse(init.body) : {}
      assert.equal(target.origin, project)
      assert.equal(init.redirect, 'error')
      assert.equal(init.referrerPolicy, 'no-referrer')
      calls.push(target.pathname)
      if (target.pathname === '/auth/v1/user' && init.method === 'GET') return response(user)
      if (['/auth/v1/signup', '/auth/v1/otp', '/auth/v1/recover', '/auth/v1/user'].includes(target.pathname)) {
        if (target.pathname === '/auth/v1/signup') assert.equal(target.searchParams.get('redirect_to'), origin + '/')
        assert.equal(body.code_challenge_method, 's256')
        challenge = body.code_challenge
        return response(mode === 'immediate' ? session() : { ...user, email_confirmed_at: null })
      }
      assert.equal(target.pathname, '/auth/v1/token')
      assert.equal(target.searchParams.get('grant_type'), 'pkce')
      assert.equal(dom.window.location.href, origin + '/')
      assert.equal(dom.window.history.state, null)
      assert.equal(body.auth_code, code)
      assert.equal(createHash('sha256').update(body.code_verifier).digest('base64url'), challenge)
      if (mode === 'network') throw new Error(`private ${code}`)
      if (mode === 'malformed') return new Response('not JSON')
      if (mode === 'expired' || used) return response({ msg: `private ${code}`, error_code: 'otp_expired' }, 400)
      if (mode === 'outage') return response({ msg: `private ${code}` }, 503)
      used = true
      const marker = mode === 'unconfirmed' ? null : mode === 'future' ? '2999-01-01T00:00:00Z' :
        mode === 'badmarker' ? 'invalid' : user.email_confirmed_at
      return response(session(marker))
    } }
  const flow = createSignupConfirmation(config)
  return { dom, flow, config, calls, setChallenge: value => { challenge = value },
    callback: () => dom.window.history.replaceState(null, '', '/?code=' + code) }
}
function session(marker = user.email_confirmed_at) {
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  return { access_token: encode({ alg: 'ES256' }) + '.' + encode({ sub: user.id, exp: issued+3600 }) + '.c3ludGhldGlj',
    refresh_token: 'synthetic-refresh', token_type: 'bearer', expires_in: 3600,
    user: { ...user, email_confirmed_at: marker } }
}

test('native SDK signup uses S256 and fixed redirect; callback is once-only and sanitized', async t => {
  const e = environment(t)
  e.dom.window.localStorage.setItem('movelle.identity.v1', 'legacy-untouched')
  assert.deepEqual(e.calls, [])
  assert.equal((await e.flow.signUp(user.email, 'synthetic-password')).status, 'check-email')
  e.callback()
  const first = e.flow.confirm()
  assert.equal(e.dom.window.location.search, '') // Before awaiting SDK or rendering anything.
  assert.equal(e.flow.confirm(), first)
  assert.equal(createSignupConfirmation(e.config).confirm(), first)
  assert.deepEqual(await first, { status: 'unproven', destination: '/' })
  assert.equal(e.calls.filter(x => x.endsWith('/token')).length, 1)
  assert.equal(e.dom.window.localStorage.getItem('movelle.identity.v1'), 'legacy-untouched')
  // A fresh document/reload at the scrubbed URL cannot redeem again.
  const reload = environment(t)
  assert.equal((await reload.flow.confirm()).status, 'missing')
  assert.deepEqual(reload.calls, [])
})

for (const path of ['/', '/?code=', '/?code=bad', '/?code=' + 'a'.repeat(5000), '/?code=' + code + '&code=' + code,
  '/?code=' + code + '&next=https://evil.invalid', '/?code=' + code + '&next=//evil.invalid',
  '/?code=' + code + '&redirectTo=%2F', '/?code=' + code + '&email=forged@example.invalid',
  '/?code=' + code + '&success=true', '/?code=' + code + '&user_id=' + user.id,
  '/?code=' + code + '&session=forged', '/?code=' + code + '&redirect_to=javascript:bad',
  '/?code=%E0%A4%A', '/?token_hash=' + 'a'.repeat(64) + '&type=email',
  '/#access_token=secret', '/?error=access_denied&error_description=secret', '/other?code=' + code]) {
  test('reject incompatible or unsafe callback without provider request: ' + path.split('?')[0], async t => {
    const e = environment(t, path)
    const value = await e.flow.confirm()
    assert.equal(value.status, path === '/' ? 'missing' : 'invalid')
    assert.equal(e.dom.window.location.href, origin + '/')
    assert.deepEqual(e.calls, [])
    assert.ok(!JSON.stringify(value).includes('secret'))
  })
}

for (const mode of ['expired', 'network', 'outage', 'malformed', 'unconfirmed', 'future', 'badmarker']) {
  test('failure is generic, clean and never retried: ' + mode, async t => {
    const e = environment(t, '/', mode), logs = []
    t.mock.method(console, 'error', (...args) => logs.push(String(args)))
    await e.flow.signUp(user.email, 'synthetic-password')
    e.callback()
    const value = await e.flow.confirm()
    assert.equal(value.status, ['expired', 'unconfirmed', 'future', 'badmarker'].includes(mode) ? 'invalid' : 'unavailable')
    assert.equal(await e.flow.confirm(), value)
    assert.equal(e.calls.filter(x => x.endsWith('/token')).length, 1)
    for (const secret of [code, user.id, user.email, session().access_token, 'synthetic-password', 'synthetic-refresh', 'private'])
      assert.ok(!JSON.stringify({ value, logs }).includes(secret))
    assert.equal(e.dom.window.location.href, origin + '/')
  })
}

test('replayed link without the SDK verifier cannot be accepted', async t => {
  const e = environment(t)
  await e.flow.signUp(user.email, 'synthetic-password')
  e.callback()
  await e.flow.confirm()
  const fresh = environment(t, '/?code=' + code)
  assert.equal((await fresh.flow.confirm()).status, 'invalid')
  assert.deepEqual(fresh.calls, [])
})

test('provider rejects replay even if an old verifier is restored in another document', async t => {
  const e = environment(t)
  await e.flow.signUp(user.email, 'synthetic-password')
  const snapshot = { ...e.dom.window.localStorage }
  e.callback()
  await e.flow.confirm()
  const fresh = environment(t, '/?code=' + code)
  for (const [key, value] of Object.entries(snapshot)) fresh.dom.window.localStorage.setItem(key, value)
  const flow = createSignupConfirmation({ ...fresh.config, fetcher: e.config.fetcher })
  assert.equal((await flow.confirm()).status, 'invalid')
  assert.equal(e.calls.filter(x => x.endsWith('/token')).length, 2)
})

test('failed URL cleanup prevents redemption; invalid config does not leak or redirect', async t => {
  const e = environment(t, '/?code=' + code)
  t.mock.method(e.dom.window.history, 'replaceState', () => { throw new Error('blocked') })
  assert.equal((await e.flow.confirm()).status, 'unavailable')
  assert.deepEqual(e.calls, [])
  const bad = environment(t, '/?code=' + code)
  assert.equal((await createSignupConfirmation({ ...bad.config, appOrigin: 'https://evil.invalid' }).confirm()).status, 'invalid')
  assert.deepEqual(bad.calls, [])
})

test('confirmation-disabled signup is not reported as email-confirmed', async t => {
  const e = environment(t, '/', 'immediate')
  assert.equal((await e.flow.signUp(user.email, 'synthetic-password')).status, 'unavailable')
})

test('missing Web Crypto cannot silently downgrade PKCE', async t => {
  const e = environment(t), descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto')
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: {} })
  t.after(() => Object.defineProperty(globalThis, 'crypto', descriptor))
  assert.equal((await e.flow.signUp(user.email, 'synthetic-password')).status, 'unavailable')
  assert.deepEqual(e.calls, [])
})

for (const kind of ['signup', 'recovery', 'magiclink', 'oauth', 'email_change']) {
  test('real SDK cross-flow hint cannot prove signup: ' + kind, async t => {
    const e = environment(t)
    const sdk = createClient(project, e.config.publishableKey, { auth: { flowType: 'pkce',
      storage: e.dom.window.localStorage, storageKey: 'movelle.signup-confirmation',
      detectSessionInUrl: false, autoRefreshToken: false }, global: { fetch: (url, init) =>
        e.config.fetcher(url, { ...init, redirect: 'error', referrerPolicy: 'no-referrer' }) } })
    if (kind === 'signup') await e.flow.signUp(user.email, 'synthetic-password')
    if (kind === 'recovery') await sdk.auth.resetPasswordForEmail(user.email)
    if (kind === 'magiclink') await sdk.auth.signInWithOtp({ email: user.email })
    if (kind === 'email_change') {
      assert.equal((await sdk.auth.setSession(session())).error, null)
      assert.equal((await sdk.auth.updateUser({ email: 'new@example.invalid' })).error, null)
    }
    if (kind === 'oauth') {
      const { data } = await sdk.auth.signInWithOAuth({ provider: 'github', options: { skipBrowserRedirect: true } })
      e.setChallenge(new URL(data.url).searchParams.get('code_challenge'))
    }
    const key = 'movelle.signup-confirmation-code-verifier', storage = e.dom.window.localStorage
    assert.equal(JSON.parse(storage.getItem(key)).split('/')[1] ?? null, kind === 'recovery' ? 'recovery' : null)
    e.callback()
    assert.equal((await e.flow.confirm()).status, kind === 'recovery' ? 'invalid' : 'unproven')
    assert.equal(e.dom.window.location.href, origin + '/')
  })
}

for (const change of [{ projectUrl: 'https://evil.invalid' }, { publishableKey: 'service_role' },
  { appOrigin: origin + '/' }, { appOrigin: undefined }, { storage: {} },
  { fetcher: async () => { throw new Error('private transport') } }]) {
  test('signup configuration/transport failures stay generic', async t => {
    const e = environment(t), flow = createSignupConfirmation({ ...e.config, ...change })
    const value = await flow.signUp(user.email, 'synthetic-password')
    assert.deepEqual(value, { status: 'unavailable', destination: '/' })
    assert.deepEqual(e.calls, [])
  })
}

test('production entry does not activate the helper; referrer policy precedes assets', async () => {
  const main = await readFile(new URL('./main.jsx', import.meta.url), 'utf8')
  const html = await readFile(new URL('../index.html', import.meta.url), 'utf8')
  assert.ok(!main.includes('signup-confirmation'))
  const meta = html.indexOf('name="referrer" content="no-referrer"')
  assert.ok(meta >= 0 && meta < html.indexOf('<link'))
})

import { JSDOM } from 'jsdom'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { tick } from './auth-test-support.js'

export const subject = '12345678-1234-4234-9234-123456789abc'
export const otherSubject = '87654321-4321-4321-8321-cba987654321'
export const code = '12345678-1234-4234-9234-123456789abc'
export const origin = 'https://movelle.test'
export const projectUrl = `https://${'a'.repeat(20)}.supabase.co`
export const sessionId = '87654321-4321-4321-8321-cba987654321'
export const json = (body, status = 200) => new Response(JSON.stringify(body), { status,
  headers: { 'Content-Type': 'application/json', 'X-Supabase-Api-Version': '2024-01-01' } })
export function syntheticSession(id = subject) {
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  return { access_token: encode({ alg: 'ES256' }) + '.' + encode({ sub: id, exp: Math.floor(Date.now()/1000)+3600 }) + '.c3ludGhldGlj',
    refresh_token: 'synthetic-refresh', expires_in: 3600, token_type: 'bearer', user: { id, email: 'offline@example.invalid' } }
}
export async function passwordFixture(t, handler) {
  const dom = new JSDOM('', { url: origin }), calls = [], logs = []
  t.mock.method(console, 'error', error => logs.push(String(error)))
  const config = { projectUrl, appOrigin: origin, publishableKey: 'sb_publishable_offline', browser: dom.window,
    fetcher: async (url, init) => {
      const target = new URL(url); calls.push(target.pathname)
      if (target.pathname.endsWith('/logout')) return json({})
      return handler(target, init)
    } }
  const client = getBrowserSupabaseClient(config), session = getSessionController(client), stop = session.subscribe(() => {})
  t.after(async () => { stop(); await client.auth.stopAutoRefresh(); dom.window.close() })
  for (let i = 0; i < 30 && session.getSnapshot().status === 'restoring'; i++) await tick()
  return { dom, calls, logs, config, client, session }
}

// Locally signed ES256 fixtures; the real SDK verifies against this mocked project JWKS.
export async function signingFixture() {
  const users = new Map()
  const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify'])
  const kid = 'offline-' + crypto.randomUUID() // SDK caches JWKS by project across clients; never reuse kid with a new key.
  const publicKey = { ...await crypto.subtle.exportKey('jwk', pair.publicKey), kid, alg: 'ES256', use: 'sig' }
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  return { users, jwks: { keys: [publicKey] }, async sign(overrides = {}, method = 'recovery') {
    const now = Math.floor(Date.now()/1000)
    const claims = { iss: projectUrl + '/auth/v1', aud: 'authenticated', sub: subject, session_id: sessionId,
      exp: now+3600, iat: now, aal: 'aal1', role: 'authenticated', amr: [{ method, timestamp: now }], ...overrides }
    const input = encode({ alg: 'ES256', kid, typ: 'JWT' }) + '.' + encode(claims)
    const signature = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, pair.privateKey, new TextEncoder().encode(input))
    const session = { ...syntheticSession(claims.sub), access_token: input + '.' + Buffer.from(signature).toString('base64url') }
    users.set(session.access_token, session.user); return session
  } }
}

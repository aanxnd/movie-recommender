import { JSDOM } from 'jsdom'
import { getBrowserSupabaseClient } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { tick } from './auth-test-support.js'

export const subject = '12345678-1234-4234-9234-123456789abc'
export const otherSubject = '87654321-4321-4321-8321-cba987654321'
export const code = '12345678-1234-4234-9234-123456789abc'
export const origin = 'https://movelle.test'
export const projectUrl = `https://${'a'.repeat(20)}.supabase.co`
export const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
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

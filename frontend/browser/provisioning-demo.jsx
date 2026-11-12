// Test-only real SDK/controller/adapter/React composition; synthetic provider responses.
import React from 'react'
import { createRoot } from 'react-dom/client'
import { getBrowserSupabaseClient } from '../src/supabase-client.js'
import { getSessionController } from '../src/auth-session.js'
import { AuthProvider } from '../src/auth-context.js'
import { createProfileProvisioning } from '../src/profile-adapter.js'
import { ProfileSetupScreen } from '../src/profile-setup.jsx'
import '../src/styles.css'

const id = '12345678-1234-4234-9234-123456789abc', projectUrl = `https://${'a'.repeat(20)}.supabase.co`
const config = { projectUrl, publishableKey: 'sb_publishable_offline', appOrigin: 'http://127.0.0.1:5173',
  base: '/api', fetcher: async (url, init) => {
    const target = new URL(url)
    if (target.origin === projectUrl && ['/auth/v1/user', '/auth/v1/logout'].includes(target.pathname))
      return new Response(JSON.stringify(target.pathname.endsWith('/user') ? { id } : {}), {
        headers: { 'Content-Type': 'application/json' } })
    if (target.origin === location.origin && target.pathname === '/api/auth/profile') return fetch(url, init)
    throw new Error('Offline fixture rejected network')
  } }
const client = getBrowserSupabaseClient(config), session = getSessionController(client)
const stop = session.subscribe(() => {})
const encode = value => btoa(JSON.stringify(value)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
await client.auth.setSession({ access_token: encode({ alg: 'ES256' }) + '.' +
  encode({ sub: id, exp: Math.floor(Date.now()/1000) + 3600 }) + '.c3ludGhldGlj', refresh_token: 'synthetic-refresh' })
const service = createProfileProvisioning(config)
addEventListener('beforeunload', () => { stop(); client.auth.stopAutoRefresh() }, { once: true })
createRoot(document.getElementById('root')).render(<React.StrictMode><AuthProvider session={session}>
  <p className="auth-hint">Offline synthetic provisioning · no hosted accounts</p>
  <ProfileSetupScreen service={service} />
</AuthProvider></React.StrictMode>)

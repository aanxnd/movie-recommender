// Internal operation continuation. No second persistent session/provider or reusable grant.
import { createClient } from '@supabase/supabase-js'
import { runCredentialRequest } from './supabase-client.js'
import { denyPassword, passwordEvidence } from './password-evidence.js'

async function bounded(work, signal) {
  let abort
  try {
    return await Promise.race([work, new Promise((_, reject) => {
      abort = () => reject(new Error('Authentication transport unavailable'))
      if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true })
    })])
  } finally { signal.removeEventListener('abort', abort) }
}

export async function checkIsolatedPassword(client, config, lease, before, password, options) {
  if (before.aal !== 'aal2') denyPassword('mfa-required')
  const signal = AbortSignal.any([lease.signal, options.signal, AbortSignal.timeout(10000)].filter(Boolean))
  const current = () => { before.assertCurrent(); if (signal.aborted) denyPassword('cancelled') }
  await runCredentialRequest(client, async () => {
    let isolated, authenticated = false, cleaned = false
    try {
      current()
      isolated = createClient(config.projectUrl, config.publishableKey, {
        auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false,
          storageKey: 'movelle.operation-password-proof', debug: false },
        global: { fetch: async (url, init) => {
          const target = new URL(url)
          const logout = target.pathname === '/auth/v1/logout' && target.search === '?scope=local'
          if (target.origin !== config.projectUrl || target.username || target.password || target.hash ||
              !(logout || (target.pathname === '/auth/v1/token' && target.search === '?grant_type=password')) ||
              init.method !== 'POST') denyPassword('unavailable')
          if (!logout) current() // Cleanup uses only the isolated session, even after caller cancellation.
          const deadline = logout ? AbortSignal.timeout(5000) : signal
          try {
            const response = await bounded(Promise.resolve().then(() => (config.fetcher ?? globalThis.fetch)(url,
              { ...init, redirect: 'error', credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', signal: deadline })), deadline)
            const body = await bounded(response.arrayBuffer(), deadline)
            if (body.byteLength) JSON.parse(new TextDecoder().decode(body))
            return new Response(body.byteLength ? body : null,
              { status: response.status, statusText: response.statusText, headers: response.headers })
          } catch { throw new Error('Authentication transport unavailable') }
        } },
      })
      // Email is obtained by the caller's fresh exact-subject provider observation.
      const { data, error } = await isolated.auth.signInWithPassword({ email: options.email, password })
      authenticated = !!data?.session
      current()
      if (error || !data?.session) denyPassword(error?.status === 429 ? 'rate-limited' :
        error?.status === 400 ? 'invalid' : 'unavailable')
      if (data.user?.id !== before.subject || data.session.user?.id !== before.subject) denyPassword('unproven')
      const token = data.session.access_token
      // Reuse the pinned SDK's signature validation and existing strict claim checks.
      const proof = await passwordEvidence(client, config, { authorization: 'Bearer ' + token,
        userId: before.subject, assertCurrent: current }, 'password', token)
      if (proof.aal !== 'aal1' || proof.sessionId === before.sessionId) denyPassword('unproven')
      current()
    } finally {
      if (authenticated) {
        try { cleaned = !(await isolated.auth.signOut({ scope: 'local' })).error } catch { /* Fixed denial below. */ }
      }
      await isolated?.auth.stopAutoRefresh()
    }
    current()
    if (!cleaned) denyPassword('unavailable')
  }, { signal: options.signal, subject: before.subject, assertCurrent: current })
  current()
}

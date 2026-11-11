import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'
import { getSessionController } from './auth-session.js'

const busy = new WeakSet()
const result = status => Object.freeze({ status })

export function createPasswordResetRequest(config) {
  return async function requestReset(email, { signal } = {}) {
    let client, session, generation, acquired = false
    try {
      if (typeof email !== 'string' || email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return result('invalid')
      client = getBrowserSupabaseClient(config)
      if (busy.has(client)) return result('busy')
      busy.add(client); acquired = true
      session = getSessionController(client); generation = session.getSnapshot().generation
      await runCredentialRequest(client, () => client.auth.resetPasswordForEmail(email,
        { redirectTo: config.appOrigin + '/' }), { signal })
      if (signal?.aborted || session.getSnapshot().generation !== generation) return result('cancelled')
      // Identical presentation for accepted, nonexistent, rejected, limited and uncertain requests.
      // No claim of delivery/acceptance, and no automatic retry (which could send duplicate mail).
      return result('check-email')
    } catch { return result(signal?.aborted || (session && session.getSnapshot().generation !== generation) ? 'cancelled' : 'check-email') }
    finally { if (acquired) busy.delete(client) }
  }
}

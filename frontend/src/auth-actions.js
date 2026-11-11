import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createSignupConfirmation } from './signup-confirmation.js'

const busy = new WeakSet()
const outcome = status => Object.freeze({ status })

// Trusted bootstrap supplies the same public configuration used by AuthProvider.
export function createAuthActions(config) {
  const confirmation = createSignupConfirmation(config)
  async function credentials(kind, email, password) {
    let client, acquired = false
    try {
      if (typeof email !== 'string' || typeof password !== 'string' || !email || !password) return outcome('invalid')
      client = getBrowserSupabaseClient(config)
      const session = getSessionController(client), initial = session.getSnapshot()
      if (busy.has(client) || ['restoring', 'refreshing', 'logging-out', 'authenticated'].includes(initial.status)) return outcome('busy')
      busy.add(client); acquired = true
      if (kind === 'signup') {
        const result = await confirmation.signUp(email, password)
        return outcome(session.getSnapshot().generation === initial.generation ? result.status : 'cancelled')
      }
      const { data, error } = await runCredentialRequest(client, () => client.auth.signInWithPassword({ email, password }))
      const current = session.getSnapshot()
      if (error) {
        if (current.generation !== initial.generation) return outcome('cancelled')
        return outcome(error.status === 429 ? 'rate-limited' : error.status === 0 || error.status >= 500 ? 'unavailable' : 'invalid')
      }
      // No session/email flags or user objects escape. React still has no backend authorization proof.
      return outcome(data?.session && data?.user?.id === current.userId && current.status === 'authenticated' ? 'signed-in' : 'cancelled')
    } catch { return outcome('unavailable') }
    finally { if (acquired) busy.delete(client) }
  }
  return Object.freeze({ signUp: (email, password) => credentials('signup', email, password),
    signIn: (email, password) => credentials('login', email, password), confirm: confirmation.confirm })
}

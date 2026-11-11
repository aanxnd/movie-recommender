// Dormant, headless PKCE signup flow. Not imported by application startup/routes.
import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'
import { callbackFailure as failure, callbackResult as result, consumePkceCallback } from './pkce-callback.js'

// appOrigin is a trusted, explicit one-origin allowlist; never infer it from callback params.
export function createSignupConfirmation({ projectUrl, publishableKey, appOrigin,
  browser = globalThis.window, storage, fetcher = globalThis.fetch }) {
  const configuredClient = () => getBrowserSupabaseClient({ projectUrl, publishableKey, appOrigin, browser, storage, fetcher })
  return Object.freeze({
    async signUp(email, password) {
      try {
        if (typeof email !== 'string' || typeof password !== 'string') return result('invalid')
        const client = configuredClient()
        const { data, error } = await runCredentialRequest(client, () => client.auth.signUp({ email, password,
          options: { emailRedirectTo: appOrigin + '/' } }))
        if (error) return ['email_exists', 'user_already_exists'].includes(error.code) ? result('check-email') : failure(error)
        // Immediate sessions indicate confirmation is disabled: never call that confirmation.
        return result(data.session ? 'unavailable' : 'check-email')
      } catch { return result('unavailable') }
    },
    confirm() {
      return consumePkceCallback({ projectUrl, publishableKey, appOrigin, browser, storage, fetcher }, 'signup', (_client, data) => {
        if (data.redirectType !== null) return result('invalid') // Recovery hint is not signup proof.
        const marker = data.user?.email_confirmed_at
        const time = typeof marker === 'string' ? Date.parse(marker) : NaN
        // Null is shared across flows; a historical marker cannot prove this link confirmed signup.
        return result(data.session && Number.isFinite(time) && time <= Date.now() ? 'unproven' : 'invalid')
      })
    },
  })
}

// Dormant, headless PKCE signup flow. Not imported by application startup/routes.
import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'

const handled = new WeakMap()
const result = status => Object.freeze({ status, destination: '/' })
const codePattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

// appOrigin is a trusted, explicit one-origin allowlist; never infer it from callback params.
export function createSignupConfirmation({ projectUrl, publishableKey, appOrigin,
  browser = globalThis.window, storage, fetcher = globalThis.fetch }) {
  const configuredClient = () => getBrowserSupabaseClient({ projectUrl, publishableKey, appOrigin, browser, storage, fetcher })
  const failure = error => result(error?.status === 429 ? 'rate-limited' :
    ['otp_expired', 'flow_state_expired', 'flow_state_not_found'].includes(error?.code) ? 'expired' :
    error?.status === 0 || error?.status >= 500 ? 'unavailable' : 'invalid')
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
      if (!browser || typeof browser !== 'object') return Promise.resolve(result('unavailable'))
      if (handled.has(browser)) return handled.get(browser)
      let url
      try {
        url = new URL(browser.location.href)
        // Synchronous and before SDK construction/I/O; never put secrets in history.state.
        browser.history.replaceState(null, '', '/')
      } catch { return Promise.resolve(result('unavailable')) }
      const attempt = (async () => {
        try {
          if (!url.search && !url.hash) return result('missing')
          if (url.href.length > 4096 || url.origin !== appOrigin || url.pathname !== '/' || url.hash ||
              [...url.searchParams].length !== 1 || !codePattern.test(url.searchParams.get('code')))
            return result('invalid')
          const client = configuredClient()
          const { data, error } = await runCredentialRequest(client, () => client.auth.exchangeCodeForSession(url.searchParams.get('code')))
          if (error) return failure(error)
          if (data.redirectType !== null) return result('invalid') // Recovery hint is not signup proof.
          const marker = data.user?.email_confirmed_at
          const time = typeof marker === 'string' ? Date.parse(marker) : NaN
          // Null is shared across flows; a historical marker cannot prove this link confirmed signup.
          return result(data.session && Number.isFinite(time) && time <= Date.now() ? 'unproven' : 'invalid')
        } catch { return result('unavailable') }
      })()
      // Includes failures: StrictMode/repeated consumers cannot retry a possibly consumed code.
      handled.set(browser, attempt)
      return attempt
    },
  })
}

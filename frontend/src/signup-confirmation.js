// Dormant, headless PKCE signup flow. Not imported by application startup/routes.
import { createClient } from '@supabase/supabase-js'

const handled = new WeakMap()
const result = status => Object.freeze({ status, destination: '/' })
const codePattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

// appOrigin is a trusted, explicit one-origin allowlist; never infer it from callback params.
export function createSignupConfirmation({ projectUrl, publishableKey, appOrigin,
  browser = globalThis.window, storage, fetcher = globalThis.fetch }) {
  let client
  function configuredClient() {
    if (typeof globalThis.crypto?.subtle?.digest !== 'function' ||
        typeof globalThis.crypto?.getRandomValues !== 'function') throw new Error('Secure browser unavailable')
    const origin = new URL(appOrigin)
    if (origin.origin !== appOrigin || browser.location.origin !== appOrigin ||
        !(origin.protocol === 'https:' || (origin.protocol === 'http:' &&
          ['localhost', '127.0.0.1'].includes(origin.hostname))) ||
        !/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(projectUrl) ||
        !/^sb_publishable_[A-Za-z0-9_-]{1,256}$/.test(publishableKey)) throw new Error('Invalid configuration')
    const persistence = storage ?? browser.localStorage
    if (!['getItem', 'setItem', 'removeItem'].every(name => typeof persistence?.[name] === 'function'))
      throw new Error('Storage unavailable')
    if (!client) client = createClient(projectUrl, publishableKey, {
      auth: { flowType: 'pkce', detectSessionInUrl: false, autoRefreshToken: false,
        persistSession: true, storage: persistence,
        storageKey: 'movelle.signup-confirmation', debug: false },
      global: { fetch: (url, init) => fetcher(url, { ...init, redirect: 'error',
        credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer',
        signal: AbortSignal.any([init?.signal, AbortSignal.timeout(10000)].filter(Boolean)) }) },
    })
    return client
  }
  const failure = error => result(error?.status === 0 || error?.status === 429 ||
    error?.status >= 500 ? 'unavailable' : 'invalid')
  return Object.freeze({
    async signUp(email, password) {
      try {
        if (typeof email !== 'string' || typeof password !== 'string') return result('invalid')
        const { data, error } = await configuredClient().auth.signUp({ email, password,
          options: { emailRedirectTo: appOrigin + '/' } })
        if (error) return failure(error)
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
      const attempt = Promise.resolve().then(async () => {
        try {
          if (!url.search && !url.hash) return result('missing')
          if (url.href.length > 4096 || url.origin !== appOrigin || url.pathname !== '/' || url.hash ||
              [...url.searchParams].length !== 1 || !codePattern.test(url.searchParams.get('code')))
            return result('invalid')
          const { data, error } = await configuredClient().auth.exchangeCodeForSession(url.searchParams.get('code'))
          if (error) return failure(error)
          if (data.redirectType !== null) return result('invalid') // Recovery hint is not signup proof.
          const marker = data.user?.email_confirmed_at
          const time = typeof marker === 'string' ? Date.parse(marker) : NaN
          // Null is shared across flows; a historical marker cannot prove this link confirmed signup.
          return result(data.session && Number.isFinite(time) && time <= Date.now() ? 'unproven' : 'invalid')
        } catch { return result('unavailable') }
      })
      // Includes failures: StrictMode/repeated consumers cannot retry a possibly consumed code.
      handled.set(browser, attempt)
      return attempt
    },
  })
}

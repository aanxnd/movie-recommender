// Dormant: explicit trusted bootstrap only. Never import/mount from production startup yet.
import { createClient } from '@supabase/supabase-js'

const clients = new WeakMap()
const unavailable = () => new Error('Authentication configuration unavailable')

export function getBrowserSupabaseClient({
  projectUrl = import.meta.env?.VITE_SUPABASE_URL,
  publishableKey = import.meta.env?.VITE_SUPABASE_PUBLISHABLE_KEY,
  appOrigin = import.meta.env?.VITE_AUTH_APP_ORIGIN,
  browser = globalThis.window, storage, fetcher = globalThis.fetch,
} = {}) {
  try {
    const origin = new URL(appOrigin)
    if (!browser || origin.origin !== appOrigin || browser.location.origin !== appOrigin ||
        !(origin.protocol === 'https:' || appOrigin === 'http://127.0.0.1:5173') ||
        !/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(projectUrl) ||
        !/^sb_publishable_[A-Za-z0-9_-]{1,256}$/.test(publishableKey) ||
        typeof globalThis.crypto?.subtle?.digest !== 'function' ||
        typeof globalThis.crypto?.getRandomValues !== 'function' || typeof fetcher !== 'function') throw unavailable()
    const persistence = storage ?? browser.localStorage
    if (!['getItem', 'setItem', 'removeItem'].every(name => typeof persistence?.[name] === 'function')) throw unavailable()
    const previous = clients.get(browser)
    if (previous) {
      if (previous.projectUrl !== projectUrl || previous.publishableKey !== publishableKey ||
          previous.appOrigin !== appOrigin || previous.storage !== persistence || previous.fetcher !== fetcher) throw unavailable()
      return previous.client
    }
    const client = createClient(projectUrl, publishableKey, {
      auth: { flowType: 'pkce', detectSessionInUrl: false, autoRefreshToken: true,
        persistSession: true, storage: persistence, storageKey: 'movelle.signup-confirmation', debug: false },
      global: { fetch: async (url, init) => {
        try {
          const target = new URL(typeof url === 'string' ? url : url.url)
          if (target.origin !== projectUrl || target.username || target.password ||
              !target.pathname.startsWith('/auth/v1/')) throw unavailable()
          return await fetcher(url, { ...init, redirect: 'error', credentials: 'omit', cache: 'no-store',
            referrerPolicy: 'no-referrer', signal: AbortSignal.any(
              [init?.signal, AbortSignal.timeout(10000)].filter(Boolean)) })
        } catch { throw new Error('Authentication transport unavailable') }
      } },
    })
    clients.set(browser, { client, projectUrl, publishableKey, appOrigin, storage: persistence, fetcher })
    return client
  } catch { throw unavailable() }
}

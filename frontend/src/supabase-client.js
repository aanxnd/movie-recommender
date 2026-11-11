// Dormant: explicit trusted bootstrap only. Never import/mount from production startup yet.
import { createClient } from '@supabase/supabase-js'

const clients = new WeakMap()
const credentialRequests = new WeakMap()
const unavailable = () => new Error('Authentication configuration unavailable')

export function cancelCredentialRequests(client) {
  const record = credentialRequests.get(client)
  if (!record) return
  record.epoch++
  for (const request of record.pending) request.abort()
}

export async function runCredentialRequest(client, work) {
  const record = credentialRequests.get(client)
  if (!record || record.action) throw unavailable()
  const action = { epoch: record.epoch }
  record.action = action
  try { return await work() }
  finally { if (record.action === action) record.action = null }
}

async function bounded(promise, signal) {
  let abort
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      abort = () => reject(unavailable())
      if (signal.aborted) abort()
      else signal.addEventListener('abort', abort, { once: true })
    })])
  } finally { signal.removeEventListener('abort', abort) }
}

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
    const record = { pending: new Set(), epoch: 0, action: null }
    const client = createClient(projectUrl, publishableKey, {
      auth: { flowType: 'pkce', detectSessionInUrl: false, autoRefreshToken: true,
        persistSession: true, storage: persistence, storageKey: 'movelle.signup-confirmation', debug: false },
      global: { fetch: async (url, init) => {
        let credential
        try {
          const target = new URL(typeof url === 'string' ? url : url.url)
          if (target.origin !== projectUrl || target.username || target.password ||
              !target.pathname.startsWith('/auth/v1/')) throw unavailable()
          if (target.pathname === '/auth/v1/signup' || (target.pathname === '/auth/v1/token' &&
              ['password', 'pkce'].includes(target.searchParams.get('grant_type')))) {
            if (record.action && record.action.epoch !== record.epoch) throw unavailable()
            credential = new AbortController(); record.pending.add(credential)
          }
          const signal = AbortSignal.any([init?.signal, credential?.signal, AbortSignal.timeout(10000)].filter(Boolean))
          const response = await bounded(fetcher(url, { ...init, redirect: 'error', credentials: 'omit', cache: 'no-store',
            referrerPolicy: 'no-referrer', signal }), signal)
          if (!credential) return response
          // Fence the whole response before the SDK can persist a late credential result.
          const body = await bounded(response.arrayBuffer(), signal)
          if (signal.aborted) throw unavailable()
          return new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers })
        } catch { throw new Error('Authentication transport unavailable') }
        finally { if (credential) record.pending.delete(credential) }
      } },
    })
    credentialRequests.set(client, record)
    clients.set(browser, { client, projectUrl, publishableKey, appOrigin, storage: persistence, fetcher })
    return client
  } catch { throw unavailable() }
}

// Dormant extension: explicit route classification, pinned API origin and private session leases.
import { apiUrl, ApiError, retryAfterSeconds } from './api.js'

const invalid = () => new ApiError('The API request or configuration is invalid.')
const cancelled = () => new DOMException('Request cancelled', 'AbortError')
const publicGet = /^\/(?:movies\/(?:search|decades|[1-9]\d*)|recommendations\/(?:popular|genre\/[A-Za-z0-9%_-]+))$/
const privateGet = /^\/users\/(?:me|[1-9]\d*(?:\/ratings(?:\/details)?|\/recommendations)?)$/
function allowed(route, method, access) {
  if (access === 'public') return (method === 'GET' && publicGet.test(route)) || (method === 'POST' && route === '/movies/artwork')
  if (access !== 'authenticated') return false
  return (['GET', 'POST'].includes(method) && route === '/auth/profile') || (method === 'GET' && privateGet.test(route)) ||
    (method === 'PUT' && /^\/users\/[1-9]\d*\/ratings\/[1-9]\d*$/.test(route)) ||
    (method === 'DELETE' && /^\/users\/[1-9]\d*\/group-invitation$/.test(route)) ||
    (method === 'POST' && (/^\/users\/[1-9]\d*\/(?:group-invitation|ratings\/lookup)$/.test(route) ||
      ['/recommendations/group', '/movies/artwork'].includes(route)))
}

async function abortable(promise, signal) {
  if (signal.aborted) { Promise.resolve(promise).catch(() => {}); throw cancelled() }
  let onAbort
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      onAbort = () => reject(cancelled())
      signal.addEventListener('abort', onAbort, { once: true })
    })])
  } finally { signal.removeEventListener('abort', onAbort) }
}

export function createAuthenticatedApi({ session, base = import.meta.env?.VITE_API_BASE_URL,
  appOrigin = import.meta.env?.VITE_AUTH_APP_ORIGIN, browser = globalThis.window, fetcher = globalThis.fetch } = {}) {
  let root, prefix
  try {
    const app = new URL(appOrigin)
    if (app.origin !== appOrigin || browser?.location.origin !== appOrigin ||
        !(app.protocol === 'https:' || appOrigin === 'http://127.0.0.1:5173') ||
        (base !== undefined && typeof base !== 'string') || typeof fetcher !== 'function' ||
        (session && !['withAccess', 'refresh', 'getSnapshot'].every(k => typeof session[k] === 'function'))) throw invalid()
    prefix = apiUrl('', base)
    root = new URL(prefix, appOrigin)
    if (root.username || root.password || root.search || root.hash ||
        !(root.protocol === 'https:' || (appOrigin === 'http://127.0.0.1:5173' && root.protocol === 'http:' && root.hostname === '127.0.0.1')) ||
        root.href.replace(/\/$/, '') !== (prefix.startsWith('/') ? appOrigin + prefix : prefix).replace(/\/$/, '')) throw invalid()
  } catch { throw invalid() }
  return async function request(path, options = {}) {
    let timer, signal
    try {
      if (!options || typeof options !== 'object' || Object.keys(options).some(k =>
        !['access', 'method', 'body', 'signal', 'timeoutMs'].includes(k))) throw invalid()
      const { access, body, signal: callerSignal, timeoutMs = 45000 } = options
      if (options.method !== undefined && typeof options.method !== 'string') throw invalid()
      const method = (options.method ?? 'GET').toUpperCase()
      if (typeof path !== 'string' || path.length > 4096 || !path.startsWith('/') ||
          /[\\#\s\x00-\x1f\x7f]/.test(path) || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 45000) throw invalid()
      const parsed = new URL(path, appOrigin), route = path.split('?')[0]
      if (parsed.origin !== appOrigin || parsed.pathname !== route || !allowed(route, method, access) ||
          [...parsed.searchParams.keys()].some(k => /token|authorization|password|code|redirect|^next$/i.test(k))) throw invalid()
      const url = new URL(prefix + path, appOrigin)
      if (url.origin !== root.origin || !url.pathname.startsWith(root.pathname.replace(/\/$/, '') + '/')) throw invalid()
      if (method === 'GET' && body !== undefined) throw invalid()
      const encoded = body === undefined ? undefined : JSON.stringify(body)
      const deadline = new AbortController()
      timer = setTimeout(() => deadline.abort(), timeoutMs)
      signal = callerSignal ? AbortSignal.any([deadline.signal, callerSignal]) : deadline.signal
      async function send(lease, retried = false) {
        lease?.assertCurrent()
        const active = lease ? AbortSignal.any([signal, lease.signal]) : signal
        if (active.aborted) throw cancelled()
        let response
        try {
          response = await abortable(Promise.resolve().then(() => {
            if (active.aborted) throw cancelled()
            lease?.assertCurrent()
            return fetcher(url.href, {
            method, redirect: 'error', credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', signal: active,
            headers: { Accept: 'application/json', ...(encoded === undefined ? {} : { 'Content-Type': 'application/json' }),
              ...(lease ? { Authorization: lease.authorization } : {}) }, ...(encoded === undefined ? {} : { body: encoded }),
          }) }), active)
        } catch {
          if (active.aborted) throw cancelled()
          throw new ApiError(method === 'GET' ? 'Cannot reach the API.' : 'Cannot reach the API. The change may have completed.')
        }
        if (response.redirected || (response.url && new URL(response.url).origin !== root.origin) ||
            (response.status >= 300 && response.status < 400)) throw new ApiError('The API response could not be trusted.')
        if (response.status === 401 && lease && method === 'GET' && !retried && lease.expiresAt <= Date.now()/1000) {
          await abortable(session.refresh(), active)
          lease.assertCurrent()
          return session.withAccess(next => {
            lease.assertCurrent()
            if (next.userId !== lease.userId) throw cancelled()
            return send(next, true)
          })
        }
        let data
        try { data = response.status === 204 ? undefined : await abortable(response.json(), active) }
        catch { if (active.aborted) throw cancelled(); if (response.ok) throw new ApiError('The API returned an unreadable response.', response.status) }
        if (active.aborted) throw cancelled()
        if (response.ok) return data
        const message = response.status === 401 ? 'Authentication is required or was rejected.' :
          response.status === 403 ? 'This account is not permitted to perform this action.' :
          response.status === 503 ? 'The API is temporarily unavailable.' : 'The API could not complete this request.'
        throw new ApiError(message, response.status, retryAfterSeconds(response.headers.get('Retry-After')))
      }
      const operation = access === 'public' ? send() : session?.withAccess(lease => send(lease))
      if (!operation) throw new ApiError('Authentication is required.', 401)
      return await abortable(operation, signal)
    } catch (error) {
      if (signal?.aborted || error?.name === 'AbortError') throw cancelled()
      if (error instanceof ApiError) throw error
      throw new ApiError('Authentication is unavailable.', session?.getSnapshot().status === 'unavailable' ? 503 : 401)
    } finally { clearTimeout(timer) }
  }
}

export function apiUrl(path, base = import.meta.env?.VITE_API_BASE_URL) {
  return `${(base || '/api').replace(/\/+$/, '')}${path}`
}

export class ApiError extends Error {
  constructor(message, status = 0, retryAfter = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

export function retryAfterSeconds(value, now = Date.now()) {
  if (!value) return null
  const number = Number(value)
  if (Number.isFinite(number) && number >= 0) return number
  const date = Date.parse(value)
  return Number.isFinite(date) ? Math.max(0, (date - now) / 1000) : null
}

async function pause(ms, signal) {
  signal.throwIfAborted()
  await new Promise((resolve, reject) => {
    const done = () => { clearTimeout(timer); signal.removeEventListener('abort', aborted); resolve() }
    const aborted = () => { clearTimeout(timer); signal.removeEventListener('abort', aborted); reject(signal.reason) }
    const timer = setTimeout(done, ms)
    signal.addEventListener('abort', aborted, { once: true })
  })
}

export async function request(path, { body, token, headers = {}, retry = false, timeoutMs = 45000, signal: callerSignal, ...options } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs)
  const signal = callerSignal ? AbortSignal.any([callerSignal, controller.signal]) : controller.signal
  const route = path.split('?')[0]
  const method = (options.method || 'GET').toUpperCase()
  const mayRetry = retry && ((method === 'GET' && /^\/users\/\d+\/recommendations$/.test(route)) || (method === 'POST' && route === '/recommendations/group'))
  try {
    for (let attempt = 0; ; attempt++) {
      signal.throwIfAborted()
      let response, data
      try {
        response = await fetch(apiUrl(path), {
          ...options, signal, cache: 'no-store', credentials: 'omit',
          headers: { ...headers, ...(token && (route.startsWith('/users/') || route === '/recommendations/group') ? { Authorization: `Bearer ${token}` } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
          ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        })
        data = response.status === 204 ? undefined : await response.json().catch((error) => { signal.throwIfAborted(); return null })
        signal.throwIfAborted()
      } catch (error) {
        signal.throwIfAborted()
        throw new ApiError('Cannot reach the API. Check your connection and retry. If saving, reload your ratings first: the write may have completed.')
      }
      if (response.ok) {
        if (data === null) throw new ApiError('The API returned an unreadable response.', response.status)
        return data
      }
      const wait = retryAfterSeconds(response.headers.get('Retry-After'))
      const capacityBusy = response.status === 503 && data?.detail === 'Recommendation capacity busy; retry shortly'
      if (mayRetry && capacityBusy && attempt < 2 && wait !== null && wait <= 10) {
        await pause(wait * 1000 + Math.random() * 300, signal)
        continue
      }
      let message
      if (response.status === 401) message = 'Your profile credential is missing, invalid, or expired. Restore your private recovery code or create a new profile.'
      else if (response.status === 403) message = 'This credential does not authorize this profile or group. Check the invitation codes.'
      else if (capacityBusy) message = `Recommendation capacity is busy. Try again in ${wait ?? 2} seconds.`
      else if (response.status === 429) message = `Request limit reached. Try again in ${Math.ceil(wait ?? 60)} seconds.`
      else if (response.status === 422 && Array.isArray(data?.detail)) message = data.detail.map((item) => `${(item.loc || []).filter((p) => p !== 'body' && p !== 'query').join(' ')}: ${item.msg || 'Invalid value'}`).join('. ')
      else if (typeof data?.detail === 'string') message = data.detail
      else message = 'The API could not complete this request. Please try again.'
      throw new ApiError(message, response.status, wait)
    }
  } catch (error) {
    if (controller.signal.aborted && !callerSignal?.aborted) throw new ApiError('Request timed out. Reload ratings before retrying a save: it may have completed.')
    throw error
  } finally { clearTimeout(timer) }
}

export function parseUserId(value) {
  const text = value.trim()
  if (!/^\d+$/.test(text) || !Number.isSafeInteger(Number(text)) || Number(text) < 1) throw new Error('Enter a positive whole-number user ID within the browser’s supported integer range.')
  return Number(text)
}

// Server-only source; copied into a separately prepared Vercel project, never Vite.
const project = 'https://jsbulnrcxtvslvvxjizq.supabase.co'
const production = 'https://movie-recommender-api.nicetree-0929c2a3.canadacentral.azurecontainerapps.io'
const fail = (res, status) => {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.end(JSON.stringify({ detail: 'Private request unavailable' }))
}
const exactOrigin = value => typeof value === 'string' && /^https:\/\/[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(value)
const id = '[1-9][0-9]{0,18}'
const routes = [
  ['GET', '/(?:health|ready|movies/search|movies/decades|users/me|auth/profile|recommendations/popular)'],
  ['GET', '/movies/' + id], ['GET', '/movies/artwork-image/' + id + '/(?:poster|backdrop)'],
  ['GET', '/recommendations/genre/[A-Za-z()-]+(?: [A-Za-z()-]+)*'],
  ['GET', '/users/' + id + '(?:/ratings(?:/details)?|/recommendations)?'],
  ['POST', '/(?:auth/profile|movies/artwork|recommendations/group)'],
  ['POST', '/users/' + id + '/(?:ratings/lookup|group-invitation)'],
  ['PUT', '/users/' + id + '/ratings/' + id],
  ['DELETE', '/users/' + id + '/group-invitation'],
].map(([method, route]) => [method, new RegExp('^' + route + '$')])

async function bounded(stream, max, signal) {
  const chunks = []; let size = 0, completed = false
  const reader = stream.getReader?.(), iterator = reader ? undefined : stream[Symbol.asyncIterator]()
  const cancel = () => reader ? reader.cancel().catch(() => {}) : stream.destroy?.()
  // Both an idle stream and a stream that ignores abort must have a finite wait.
  const read = async () => {
    while (true) {
      const item = await (reader ? reader.read() : iterator.next())
      if (item.done) { completed = true; break }
      const bytes = Buffer.from(item.value); size += bytes.length
      if (size > max) throw new Error('Size')
      chunks.push(bytes)
    }
    return Buffer.concat(chunks)
  }
  let abort
  try {
    return await Promise.race([read(), new Promise((_, reject) => {
      abort = () => { cancel(); reject(new Error('Timeout')) }
      signal.addEventListener('abort', abort, { once: true })
      if (signal.aborted) abort()
    })])
  } finally {
    signal.removeEventListener('abort', abort)
    if (!completed) await cancel()
    reader?.releaseLock()
  }
}

export function createGateway(env, targets, fetcher = fetch) {
  // Read/copy once; no caller can replace the destination or capability.
  const frontend = targets.frontend_origin, backend = targets.backend_origin, gate = env.MOVELLE_PRIVATE_GATE_SECRET
  const configured = env.VERCEL_ENV === 'preview' && env.MOVELLE_PRIVATE_MODE === 'private-stage23' &&
    targets.approved === true && targets.azure_app === 'movie-recommender-api-private' && targets.supabase_url === project &&
    exactOrigin(frontend) && frontend.endsWith('.vercel.app') && exactOrigin(backend) &&
    backend.endsWith('.azurecontainerapps.io') && backend !== production && frontend !== backend &&
    typeof gate === 'string' && /^[A-Za-z0-9_-]{43}$/.test(gate)
  return async (req, res) => {
    if (!configured) return fail(res, 503)
    const signal = AbortSignal.timeout(25000)
    try {
      // Vercel's rewrite supplies this one parameter. Direct invocation still has
      // the exact same allowlist; duplicate/injected arrays cannot select a target.
      const path = req.query?.__movelle_route
      const h = req.headers, method = req.method
      if (h.host !== frontend.slice(8) || (h.origin !== undefined && h.origin !== frontend) ||
          (method !== 'GET' && h.origin !== frontend) || typeof path !== 'string' || /[\x00-\x1f\x7f\\%?#]/.test(path) ||
          !routes.some(([m, r]) => method === m && r.test(path))) return fail(res, 403)
      const target = new URL(backend); target.pathname = path
      for (const [key, value] of Object.entries(req.query)) {
        if (key === '__movelle_route') continue
        if (!['q', 'limit', 'after', 'min_rating_count', 'decade'].includes(key) ||
            typeof value !== 'string' || value.length > 256 || /[\x00-\x1f\x7f]/.test(value)) return fail(res, 400)
        target.searchParams.set(key, value)
      }
      const headers = { Origin: frontend, 'X-Movelle-Private-Gate': gate, Accept: 'application/json' }
      if (h.authorization !== undefined) {
        if (typeof h.authorization !== 'string' || !/^Bearer [A-Za-z0-9_.-]{1,8192}$/.test(h.authorization)) return fail(res, 401)
        headers.Authorization = h.authorization
      }
      let body
      if (['POST', 'PUT'].includes(method)) {
        if (h['content-type'] !== 'application/json' ||
            (h['content-length'] !== undefined && !/^(0|[1-9][0-9]{0,4})$/.test(h['content-length']))) return fail(res, 400)
        if (Number(h['content-length']) > 16384) return fail(res, 413)
        body = await bounded(req, 16384, signal)
        JSON.parse(body.toString('utf8')) // Validate, but forward exact bytes; backend validates schema.
        headers['Content-Type'] = 'application/json'
      } else {
        if ((await bounded(req, 0, signal)).length) return fail(res, 400)
      }
      const response = await fetcher(target.href, { method, headers, body,
        redirect: 'error', credentials: 'omit', cache: 'no-store', signal })
      if (response.status >= 300 && response.status < 400) throw new Error('Redirect')
      if (response.status >= 500) { await response.body?.cancel(); return fail(res, 503) }
      const bytes = response.body ? await bounded(response.body, 2 * 1024 * 1024, signal) : Buffer.alloc(0)
      const type = response.headers.get('content-type') ?? 'application/json'
      if (bytes.includes(Buffer.from(gate)) || !/^(application\/json|image\/(jpeg|png|webp|gif))(;.*)?$/.test(type)) throw new Error('Response')
      res.statusCode = response.status
      res.setHeader('Cache-Control', 'no-store')
      res.setHeader('X-Content-Type-Options', 'nosniff')
      res.setHeader('Content-Type', type)
      const retry = response.headers.get('retry-after')
      if (retry && /^[0-9]{1,5}$/.test(retry)) res.setHeader('Retry-After', retry)
      res.end(bytes)
    } catch { return fail(res, 502) } // Never expose upstream URLs, bodies or diagnostics.
  }
}

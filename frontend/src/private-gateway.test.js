import test from 'node:test'
import assert from 'node:assert/strict'
import { Readable } from 'node:stream'
import { createGateway } from '../private/gateway.mjs'

const frontend = 'https://owner-preview.vercel.app', backend = 'https://private.example.azurecontainerapps.io'
const gate = 's'.repeat(43), project = 'https://jsbulnrcxtvslvvxjizq.supabase.co'
const env = { VERCEL_ENV: 'preview', MOVELLE_PRIVATE_MODE: 'private-stage23', MOVELLE_PRIVATE_GATE_SECRET: gate }
const targets = { approved: true, azure_app: 'movie-recommender-api-private', supabase_url: project,
  frontend_origin: frontend, backend_origin: backend }
async function call({ method = 'GET', path = '/users/me', query = {}, headers = {}, chunks = [],
  config = {}, pins = {}, fetcher = async () => Response.json({ ok: true }) } = {}) {
  const req = Object.assign(Readable.from(chunks), { method, query: { __movelle_route: path, ...query },
    headers: { host: frontend.slice(8), origin: frontend, ...headers } })
  const response = { headers: {}, setHeader(k, v) { this.headers[k.toLowerCase()] = v }, end(body) { this.body = Buffer.from(body).toString() } }
  await createGateway({ ...env, ...config }, { ...targets, ...pins }, fetcher)(req, response)
  assert.equal(response.headers['cache-control'], 'no-store')
  assert.ok(!response.body.includes(gate))
  return response
}
const noFetch = () => assert.fail('Unauthorized upstream I/O')

test('pins one destination, preserves JWT, overwrites capability and drops cookies/proxy headers', async () => {
  let calls = 0
  const r = await call({ path: '/movies/search', query: { q: 'First Film', limit: '3' },
    headers: { authorization: 'Bearer synthetic.jwt.signature', cookie: 'owner-private',
      'x-movelle-private-gate': 'attacker', 'x-forwarded-for': 'attacker' },
    fetcher: async (url, init) => {
      calls++
      assert.equal(url, backend + '/movies/search?q=First+Film&limit=3')
      assert.deepEqual(init.headers, { Origin: frontend, 'X-Movelle-Private-Gate': gate,
        Accept: 'application/json', Authorization: 'Bearer synthetic.jwt.signature' })
      assert.equal(init.redirect, 'error'); assert.equal(init.credentials, 'omit'); assert.equal(init.cache, 'no-store')
      assert.ok(init.signal instanceof AbortSignal)
      return new Response('{"ok":true}', { headers: { 'content-type': 'application/json', 'set-cookie': 'secret', location: 'https://evil.invalid' } })
    } })
  assert.equal(r.statusCode, 200); assert.equal(calls, 1)
  assert.deepEqual(Object.keys(r.headers).sort(), ['cache-control', 'content-type', 'x-content-type-options'])
})

test('tested native movie/profile/rating/invitation contracts are reachable without adding legacy routes', async () => {
  for (const [method, path] of [['GET', '/health'], ['GET', '/ready'], ['GET', '/movies/1'],
    ['GET', '/movies/decades'], ['GET', '/movies/artwork-image/1/backdrop'], ['GET', '/recommendations/popular'],
    ['GET', '/recommendations/genre/Sci-Fi'], ['GET', '/recommendations/genre/(no genres listed)'],
    ['GET', '/users/1/ratings/details'], ['GET', '/users/1/ratings'], ['GET', '/users/1/recommendations'],
    ['POST', '/auth/profile'], ['POST', '/movies/artwork'], ['POST', '/users/1/ratings/lookup'],
    ['POST', '/recommendations/group'], ['POST', '/users/1/group-invitation'],
    ['PUT', '/users/1/ratings/1'], ['DELETE', '/users/1/group-invitation']]) {
    const write = ['POST', 'PUT'].includes(method)
    const result = await call({ method, path, chunks: write ? ['{}'] : [],
      headers: write ? { 'content-type': 'application/json' } : {}, fetcher: async (url, init) => {
        assert.equal(new URL(url).origin, backend); assert.equal(init.method, method)
        return Response.json({ ok: true })
      } })
    assert.equal(result.statusCode, 200, method + ' ' + path)
  }
})

for (const pins of [{ approved: false }, { supabase_url: 'https://other.supabase.co' },
  { backend_origin: 'https://movie-recommender-api.nicetree-0929c2a3.canadacentral.azurecontainerapps.io' },
  { backend_origin: backend + '/' }, { backend_origin: 'http://private.azurecontainerapps.io' },
  { backend_origin: 'https://u:p@private.azurecontainerapps.io' }, { azure_app: 'movie-recommender-api' },
  { frontend_origin: 'https://public-custom.example' }]) {
  test('unapproved target configuration denies before I/O: ' + JSON.stringify(pins), async () => {
    assert.equal((await call({ pins, fetcher: noFetch })).statusCode, 503)
  })
}
for (const config of [{ VERCEL_ENV: 'production' }, { VERCEL_ENV: undefined },
  { MOVELLE_PRIVATE_MODE: 'production' }, { MOVELLE_PRIVATE_GATE_SECRET: 'weak' }]) {
  test('private preview mode/credential required: ' + Object.keys(config)[0], async () => {
    assert.equal((await call({ config, fetcher: noFetch })).statusCode, 503)
  })
}
for (const path of ['/users', '/users/restore', '/docs', '//evil.invalid', '/users/../health',
  '/users/%2e%2e/health', '/users/1/ratings%2f1', '/users/1\\ratings', '/health?next=https://evil.invalid',
  '/auth/profile\n', ['/health', '/users/me'], null]) {
  test('nonallowlisted or ambiguous route denied: ' + JSON.stringify(path), async () => {
    assert.equal((await call({ path, fetcher: noFetch })).statusCode, 403)
  })
}
test('wrong Host/Origin, unsafe queries, duplicate parameters and credential headers deny', async () => {
  for (const headers of [{ host: 'evil.invalid' }, { host: [frontend.slice(8)] }, { origin: 'https://evil.invalid' },
    { origin: [frontend] }, { authorization: ['Bearer a', 'Bearer b'] }, { authorization: 'Bearer secret\r\nInjected' }]) {
    assert.ok([401, 403].includes((await call({ headers, fetcher: noFetch })).statusCode))
  }
  for (const query of [{ next: 'https://evil.invalid' }, { q: ['a', 'b'] }, { q: '\u0000' }, { q: 'a'.repeat(257) }]) {
    assert.equal((await call({ query, fetcher: noFetch })).statusCode, 400)
  }
  assert.equal((await call({ method: 'POST', path: '/auth/profile', headers: { origin: undefined }, fetcher: noFetch })).statusCode, 403)
})

test('bounded JSON writes preserve raw request and backend authorization/rate errors', async () => {
  const body = '{"username":"PrivateOwner"}'
  const r = await call({ method: 'POST', path: '/auth/profile', chunks: [body], headers: { 'content-type': 'application/json' },
    fetcher: async (_, init) => { assert.equal(init.body.toString(), body); return Response.json({ detail: 'Denied' }, { status: 429, headers: { 'retry-after': '12' } }) } })
  assert.equal(r.statusCode, 429); assert.equal(r.headers['retry-after'], '12')
  for (const status of [401, 403, 404]) assert.equal((await call({ fetcher: async () => Response.json({ detail: 'Denied' }, { status }) })).statusCode, status)
  assert.equal((await call({ method: 'POST', path: '/auth/profile', chunks: ['x'.repeat(16385)], headers: { 'content-type': 'application/json' }, fetcher: noFetch })).statusCode, 502)
  assert.equal((await call({ method: 'POST', path: '/auth/profile', headers: { 'content-type': 'application/json', 'content-length': '16385' }, fetcher: noFetch })).statusCode, 413)
  assert.equal((await call({ method: 'POST', path: '/auth/profile', chunks: ['{'], headers: { 'content-type': 'application/json' }, fetcher: noFetch })).statusCode, 502)
  assert.equal((await call({ method: 'GET', chunks: ['not-empty'], fetcher: noFetch })).statusCode, 502)
})

test('network/provider errors, redirects, excessive response and capability echoes fail without leaks', async () => {
  for (const fetcher of [async () => { throw new Error('private URL and token') },
    async () => Response.redirect('https://evil.invalid'), async () => Response.json({ private: 'provider' }, { status: 503 }),
    async () => Response.json({ echo: gate }), async () => Response.json({ data: 'x'.repeat(2097153) })]) {
    const r = await call({ fetcher })
    assert.ok([502, 503].includes(r.statusCode)); assert.equal(r.body, '{"detail":"Private request unavailable"}')
  }
})

test('idle request/response streams and provider timeouts terminate without fallback', async t => {
  for (const kind of ['request', 'response', 'provider']) {
    const controller = new AbortController()
    const mock = t.mock.method(AbortSignal, 'timeout', () => controller.signal)
    let cancelled = false
    const timer = setTimeout(() => controller.abort(), 20)
    try {
      const options = kind === 'request' ? { method: 'POST', path: '/auth/profile',
        headers: { 'content-type': 'application/json' }, chunks: new Readable({ read() {} }), fetcher: noFetch } :
        { fetcher: async (_, init) => kind === 'response' ? new Response(new ReadableStream({
          cancel() { cancelled = true },
        }), { headers: { 'content-type': 'application/json' } }) : new Promise((_, reject) => {
          init.signal.addEventListener('abort', () => reject(new Error('private timeout')), { once: true })
        }) }
      // call normally creates a finite Readable; substitute an idle async source.
      if (kind === 'request') options.chunks = (async function* () { await new Promise(() => {}) })()
      const result = await call(options)
      assert.equal(result.statusCode, 502)
      if (kind === 'response') assert.equal(cancelled, true)
    } finally { clearTimeout(timer); mock.mock.restore() }
  }
})

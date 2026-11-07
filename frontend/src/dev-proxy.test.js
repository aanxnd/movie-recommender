import assert from 'node:assert/strict'
import test from 'node:test'
import { createServer as createHttpServer } from 'node:http'
import { createServer as createViteServer } from 'vite'
import { fileURLToPath } from 'node:url'
import { apiProxy, localApiTarget } from '../scripts/api-proxy.mjs'
import {
  devPlan,
  availablePort,
  waitForApi,
  waitForFrontend,
  frontendAddress,
} from '../scripts/dev.mjs'

const listen = (server) =>
  new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const stop = (server) =>
  new Promise((resolve) => {
    server.close(resolve)
    server.closeAllConnections?.()
  })

test('local launcher overrides inherited cloud settings with a persistent isolated SQLite database', () => {
  const plan = devPlan(
    {
      DATABASE_URL: 'postgresql://must-not-use.invalid/db',
      APP_ENV: 'production',
      VITE_API_BASE_URL: 'https://must-not-call.invalid',
      MOVIELENS_PREPARED_DIR: '/other',
      MOVELLE_DEV_API_PORT: '8123',
    },
    '/workspace/movelle',
    'linux',
  )
  assert.match(plan.env.DATABASE_URL, /^sqlite:\/\/\//)
  assert.match(plan.env.DATABASE_URL, /\.movelle-dev\/application\.db$/)
  assert.equal(plan.env.APP_ENV, 'development')
  assert.equal(plan.env.VITE_API_BASE_URL, '/api')
  assert.equal(plan.env.API_PROXY_TARGET, 'http://127.0.0.1:8123')
  assert.equal(plan.env.MOVIELENS_PREPARED_DIR, plan.prepared)
  assert.equal(plan.env.MOVIELENS_ARCHIVE_URL, '')
  assert.equal(plan.env.CORS_ALLOWED_ORIGINS, '')
  assert.throws(() => devPlan({ MOVELLE_DEV_API_PORT: '0' }), /port/)
  assert.throws(() => devPlan({ MOVELLE_DEV_API_PORT: '8000/path' }), /port/)
})

test('development proxy accepts loopback targets and rejects remote targets and embedded secrets without echoing them', () => {
  assert.equal(localApiTarget(), 'http://127.0.0.1:8000')
  assert.equal(
    localApiTarget(' http://localhost:8123/ '),
    'http://localhost:8123',
  )
  assert.equal(localApiTarget('http://[::1]:8123'), 'http://[::1]:8123')
  for (const target of [
    'https://production.invalid',
    'http://localhost:8000/api',
    'http://secret@localhost:8000',
    'http://localhost:8000/?secret=private',
    'bad',
  ]) {
    assert.throws(
      () => localApiTarget(target),
      (error) =>
        /API_PROXY_TARGET/.test(error.message) &&
        !error.message.includes('private'),
    )
  }
})

test('local launcher refuses to reuse an occupied API port and waits for its API health', async () => {
  const backend = createHttpServer((req, res) => {
    res.setHeader('Content-Type', 'application/json')
    res.end(req.url === '/ready' ? '{"status":"ok"}' : '{"status":"ok"}')
  })
  await listen(backend)
  try {
    const port = backend.address().port
    await assert.rejects(
      availablePort(port),
      /will not reuse or stop another service/,
    )
    await waitForApi(`http://127.0.0.1:${port}`, () => true, 2000)
    await assert.rejects(
      waitForApi(`http://127.0.0.1:${port}`, () => false),
      /exited before startup/,
    )
  } finally {
    await stop(backend)
  }
})

test('frontend and API port selection stay explicit and browser instances use separate local databases', () => {
  assert.deepEqual(frontendAddress(['--port', '5174']), {
    port: 5174,
    host: '127.0.0.1',
    origin: 'http://127.0.0.1:5174',
  })
  assert.equal(frontendAddress(['--port=5180']).port, 5180)
  assert.throws(() => frontendAddress(['--port', 'bad']), /frontend --port/)
  assert.throws(() => frontendAddress(['--host', '0.0.0.0']), /loopback/)
  const plan = devPlan({
    MOVELLE_DEV_API_PORT: '8001',
    MOVELLE_DEV_INSTANCE: 'browser-qa',
  })
  assert.equal(plan.env.API_PROXY_TARGET, 'http://127.0.0.1:8001')
  assert.match(plan.env.DATABASE_URL, /instances\/browser-qa\/application.db$/)
  assert.throws(
    () => devPlan({ MOVELLE_DEV_INSTANCE: '../other' }),
    /MOVELLE_DEV_INSTANCE/,
  )
})

test('health alone is insufficient and the frontend proxy must return readiness and actual decade JSON', async () => {
  let ready = false
  const backend = createHttpServer((req, res) => {
    res.setHeader('Content-Type', 'application/json')
    if (req.url.endsWith('/movies/decades')) {
      res.end('[1980,1990]')
      return
    }
    if (req.url.endsWith('/ready')) {
      res.statusCode = ready ? 200 : 503
      res.end('{"status":"ok"}')
      return
    }
    res.end('{"status":"ok"}')
  })
  await listen(backend)
  const target = `http://127.0.0.1:${backend.address().port}`
  try {
    await assert.rejects(
      waitForApi(target, () => true, 40),
      /healthy and ready/,
    )
    ready = true
    await waitForApi(target, () => true, 1000)
    await waitForFrontend(target, () => true, 1000)
    await assert.rejects(
      waitForFrontend(target, () => false, 1000),
      /exited before the frontend proxy/,
    )
  } finally {
    await stop(backend)
  }
})

test('actual Vite proxy preserves query strings, authorization and request bodies across development origins', async () => {
  const calls = []
  const backend = createHttpServer(async (req, res) => {
    let body = ''
    for await (const data of req) body += data
    calls.push({
      path: req.url,
      auth: req.headers.authorization,
      origin: req.headers.origin,
      body,
    })
    res.setHeader('Content-Type', 'application/json')
    res.end(req.url.startsWith('/movies/decades') ? '[1980,1990]' : '[]')
  })
  await listen(backend)
  const vite = await createViteServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    logLevel: 'silent',
    server: {
      host: '127.0.0.1',
      port: 0,
      proxy: {
        '^/api(?:/|$)': apiProxy(`http://127.0.0.1:${backend.address().port}`),
      },
    },
  })
  try {
    await vite.listen()
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`
    for (const developmentOrigin of [
      'http://127.0.0.1:5174',
      'http://localhost:5173',
      'http://127.0.0.1:5173',
    ]) {
      const response = await fetch(origin + '/api/movies/decades', {
        headers: { Origin: developmentOrigin },
      })
      assert.equal(response.status, 200)
      assert.deepEqual(await response.json(), [1980, 1990])
      assert.equal(calls.at(-1).path, '/movies/decades')
    }
    const body = JSON.stringify({
      user_ids: [1, 2],
      invitations: { 2: 'b'.repeat(43) },
    })
    await fetch(origin + '/api/recommendations/group?decade=1990', {
      method: 'POST',
      body,
      headers: {
        Authorization: `Bearer ${'a'.repeat(43)}`,
        'Content-Type': 'application/json',
      },
    })
    assert.equal(calls.at(-1).path, '/recommendations/group?decade=1990')
    assert.equal(calls.at(-1).auth, `Bearer ${'a'.repeat(43)}`)
    assert.equal(calls.at(-1).body, body)
    const count = calls.length
    await fetch(origin + '/apiary')
    assert.equal(calls.length, count, 'unrelated paths must not be forwarded')
    await stop(backend)
    const failed = await fetch(origin + '/api/movies/decades')
    assert.equal(failed.status, 502)
    assert.match(failed.headers.get('Content-Type'), /application\/json/)
    assert.equal(failed.headers.get('Cache-Control'), 'no-store')
    assert.match(
      (await failed.json()).detail,
      /local API is unavailable.*npm run dev/,
    )
  } finally {
    await vite.close()
    if (backend.listening) await stop(backend)
  }
})

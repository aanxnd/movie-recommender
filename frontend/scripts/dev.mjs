import { spawn } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { createServer } from 'node:net'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { setTimeout as pause } from 'node:timers/promises'

const repository = fileURLToPath(new URL('../../', import.meta.url))

export function devPlan(
  env = process.env,
  root = repository,
  platform = process.platform,
) {
  const configuredPort = env.MOVELLE_DEV_API_PORT || '8000'
  if (
    !/^\d+$/.test(configuredPort) ||
    Number(configuredPort) < 1 ||
    Number(configuredPort) > 65535
  )
    throw new Error('MOVELLE_DEV_API_PORT must be a port between 1 and 65535.')
  const instance = env.MOVELLE_DEV_INSTANCE || ''
  if (instance && !/^[a-zA-Z0-9_-]{1,48}$/.test(instance))
    throw new Error(
      'MOVELLE_DEV_INSTANCE must contain only letters, numbers, underscores or hyphens (up to 48).',
    )
  const localRoot = join(root, '.movelle-dev')
  const state = instance ? join(localRoot, 'instances', instance) : localRoot
  const prepared = join(localRoot, 'prepared')
  const target = `http://127.0.0.1:${Number(configuredPort)}`
  const python =
    env.MOVELLE_DEV_PYTHON ||
    join(
      root,
      '.venv',
      platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
    )
  return {
    root,
    state,
    prepared,
    target,
    python,
    port: Number(configuredPort),
    env: {
      ...env,
      APP_ENV: 'development',
      DATABASE_URL: `sqlite:///${join(state, 'application.db').replaceAll('\\', '/')}`,
      MOVIELENS_PREPARED_DIR: prepared,
      MOVIELENS_ARCHIVE_URL: '',
      MOVIELENS_ARCHIVE_SHA256: '',
      TRUSTED_PROXY_IPS: '',
      CORS_ALLOWED_ORIGINS: '',
      VITE_API_BASE_URL: '/api',
      API_PROXY_TARGET: target,
      MOVELLE_ARTWORK_CACHE_DIR:
        env.MOVELLE_ARTWORK_CACHE_DIR || join(localRoot, 'artwork'),
      MOVELLE_ARTWORK_LINKS:
        env.MOVELLE_ARTWORK_LINKS ||
        (existsSync(join(root, 'data/download/ml-latest-small/links.csv'))
          ? join(root, 'data/download/ml-latest-small/links.csv')
          : ''),
    },
  }
}

export function frontendAddress(args = []) {
  let port = '5173',
    host = '127.0.0.1'
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--port' || args[i] === '-p') port = args[++i] || ''
    else if (args[i].startsWith('--port=')) port = args[i].slice(7)
    else if (args[i] === '--host') host = args[++i] || ''
    else if (args[i].startsWith('--host=')) host = args[i].slice(7)
  }
  if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535)
    throw new Error('The frontend --port must be between 1 and 65535.')
  if (!['127.0.0.1', 'localhost', '::1'].includes(host))
    throw new Error(
      'The combined local launcher requires a loopback --host (127.0.0.1, localhost or ::1).',
    )
  return {
    port: Number(port),
    host,
    origin: `http://${host === '::1' ? '[::1]' : host}:${Number(port)}`,
  }
}

export async function availablePort(port, label = 'API', host = '127.0.0.1') {
  await new Promise((resolve, reject) => {
    const server = createServer()
    server.once('error', () =>
      reject(
        new Error(
          `${label} port ${port} is occupied. Stop its existing launcher or choose another ${label === 'API' ? 'MOVELLE_DEV_API_PORT' : '--port'}. The launcher will not reuse or stop another service.`,
        ),
      ),
    )
    server.listen(port, host, () => server.close(resolve))
  })
}

async function readJson(url) {
  const response = await fetch(url, {
    signal: AbortSignal.timeout(1500),
    cache: 'no-store',
  })
  if (!response.ok) throw new Error('Service not ready')
  return response.json()
}

export async function waitForApi(target, alive, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (!alive())
      throw new Error(
        'The local API exited before startup completed. Check the startup output above.',
      )
    try {
      const health = await readJson(`${target}/health`)
      const ready = await readJson(`${target}/ready`)
      if (health.status === 'ok' && ready.status === 'ok' && alive()) return
    } catch {
      /* bounded startup polling */
    }
    await pause(150)
  }
  throw new Error(
    'The API did not become healthy and ready. Check its startup and database messages above.',
  )
}

export async function waitForFrontend(origin, alive, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (!alive())
      throw new Error(
        'A local service exited before the frontend proxy was verified.',
      )
    try {
      const ready = await readJson(`${origin}/api/ready`)
      const decades = await readJson(`${origin}/api/movies/decades`)
      if (
        ready.status === 'ok' &&
        Array.isArray(decades) &&
        decades.every((value) => Number.isInteger(value)) &&
        alive()
      )
        return
    } catch {
      /* Vite may not have bound its socket yet */
    }
    await pause(150)
  }
  throw new Error(
    'The frontend could not reach the selected API through /api. Check the proxy and the startup messages above.',
  )
}

export async function main(args = process.argv.slice(2)) {
  const plan = devPlan()
  const address = frontendAddress(args)
  if (plan.port === address.port)
    throw new Error('Frontend and API ports must be different.')
  if (!existsSync(plan.python))
    throw new Error(
      'Python environment not found. Install requirements-dev.txt in .venv; see README.md.',
    )
  await availablePort(address.port, 'Frontend', address.host)
  await availablePort(plan.port)
  mkdirSync(plan.state, { recursive: true })
  const children = new Set()
  let stopping = false
  const stop = () => {
    if (stopping) return
    stopping = true
    for (const worker of children) worker.kill()
  }
  const launch = (command, commandArgs, cwd) => {
    const worker = spawn(command, commandArgs, {
      cwd,
      env: plan.env,
      stdio: 'inherit',
      windowsHide: true,
    })
    children.add(worker)
    worker.once('exit', () => children.delete(worker))
    return worker
  }
  const run = (command, commandArgs, cwd) =>
    new Promise((resolve, reject) => {
      const worker = launch(command, commandArgs, cwd)
      worker.once('error', () =>
        reject(new Error('Could not start a required development process.')),
      )
      worker.once('exit', (code) =>
        code === 0 || stopping
          ? resolve()
          : reject(
              new Error(
                'Local data preparation failed. Existing data was not overwritten; see the messages above.',
              ),
            ),
      )
    })
  process.once('SIGINT', stop)
  process.once('SIGTERM', stop)
  try {
    console.log(
      `Movelle local startup: frontend ${address.origin}; API ${plan.target}. Local SQLite; core API bound to loopback.`,
    )
    const prepare = join(plan.root, 'scripts/prepare_movielens.py')
    if (existsSync(plan.prepared))
      await run(plan.python, [prepare, '--verify', plan.prepared], plan.root)
    else
      await run(
        plan.python,
        [
          prepare,
          '--source',
          join(plan.root, 'data'),
          '--output',
          plan.prepared,
          '--dataset',
          'latest-small',
        ],
        plan.root,
      )
    if (stopping) return
    const api = launch(
      plan.python,
      [
        '-m',
        'uvicorn',
        'app.main:app',
        '--no-access-log',
        '--host',
        '127.0.0.1',
        '--port',
        String(plan.port),
      ],
      plan.root,
    )
    let apiAlive = true,
      viteAlive = false
    const apiExit = new Promise((resolve, reject) => {
      api.once('error', () => {
        apiAlive = false
        reject(new Error('The local API could not start.'))
      })
      api.once('exit', () => {
        apiAlive = false
        stopping
          ? resolve()
          : reject(
              new Error(
                'The local API stopped. Stopping the frontend; check the API messages above.',
              ),
            )
      })
    })
    apiExit.catch(() => {}) // The same failure is awaited during startup and normal running.
    await Promise.race([
      waitForApi(plan.target, () => apiAlive && !stopping),
      apiExit,
    ])
    if (stopping) return
    const vite = launch(
      process.execPath,
      [
        join(plan.root, 'frontend/node_modules/vite/bin/vite.js'),
        '--host',
        address.host,
        '--port',
        String(address.port),
        '--strictPort',
        ...args,
      ],
      join(plan.root, 'frontend'),
    )
    viteAlive = true
    const viteExit = new Promise((resolve, reject) => {
      vite.once('error', () => {
        viteAlive = false
        reject(new Error('Vite could not start. Run npm ci in frontend first.'))
      })
      vite.once('exit', (code) => {
        viteAlive = false
        code === 0 || stopping
          ? resolve()
          : reject(new Error('Vite exited. Check its messages above.'))
      })
    })
    viteExit.catch(() => {})
    await Promise.race([
      waitForFrontend(address.origin, () => apiAlive && viteAlive && !stopping),
      apiExit,
      viteExit,
    ])
    if (!apiAlive || !viteAlive || stopping) return
    console.log(
      `\nREADY: ${address.origin}\nVerified /health, /ready and /api/movies/decades. Keep this launcher running. Ctrl+C stops both services.\n`,
    )
    await Promise.race([viteExit, apiExit])
  } finally {
    stop()
    process.removeListener('SIGINT', stop)
    process.removeListener('SIGTERM', stop)
  }
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main().catch((error) => {
    console.error(error.message)
    process.exitCode = 1
  })
}

import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { join, resolve } from 'node:path'
import { availablePort, waitForApi, waitForFrontend } from './dev.mjs'

const root = fileURLToPath(new URL('../../', import.meta.url))

// A failed spawn emits error/close, but never exit. Track completion at launch,
// including that case, so cleanup cannot wait on an event that already happened.
export function startStagingWorker(command, args, { spawnProcess = spawn, ...options } = {}) {
  const child = spawnProcess(command, args, options)
  let running = true, complete
  const ended = new Promise(resolve => { complete = resolve })
  const exited = new Promise((resolve, reject) => {
    child.on('error', () => {
      if (!child.pid) { running = false; complete() }
      reject(new Error('Staging process could not start or stop'))
    })
    child.once('exit', () => { running = false; complete(); resolve() })
  })
  exited.catch(() => {})
  return { child, ended, exited, get running() { return running } }
}

export async function stopStagingWorkers(workers, timeoutMs = 5000) {
  const signal = value => {
    for (const worker of workers) if (worker.running) {
      try { worker.child.kill(value) } catch { /* Still require exit evidence below. */ }
    }
  }
  const wait = async () => {
    let timer
    try {
      return await Promise.race([Promise.all(workers.map(worker => worker.ended)).then(() => true),
        new Promise(resolve => { timer = setTimeout(() => resolve(false), timeoutMs) })])
    } finally { clearTimeout(timer) }
  }
  signal('SIGTERM')
  if (await wait()) return
  signal('SIGKILL')
  if (!await wait()) throw new Error('Staging processes did not stop')
}

export function stagingPlan(env = process.env, platform = process.platform) {
  for (const name of ['MOVELLE_STAGING_DATABASE_URL', 'MOVELLE_STAGING_PREPARED_DIR',
    'MOVELLE_STAGING_SUPABASE_URL', 'MOVELLE_STAGING_PUBLISHABLE_KEY'])
    if (typeof env[name] !== 'string' || !env[name]) throw new Error('Explicit staging configuration required')
  if (!/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(env.MOVELLE_STAGING_SUPABASE_URL) ||
      !/^sb_publishable_[A-Za-z0-9_-]{1,256}$/.test(env.MOVELLE_STAGING_PUBLISHABLE_KEY))
    throw new Error('Public staging project configuration required')
  // Pass OS/tool prerequisites and explicit staging inputs, never production secrets.
  const childEnv = Object.fromEntries(Object.entries(env).filter(([key]) =>
    /^(path|systemroot|windir|comspec|pathext|temp|tmp|home|userprofile|appdata|localappdata|lang|lc_all)$/i.test(key) ||
    ['MOVELLE_STAGING_DATABASE_URL', 'MOVELLE_STAGING_PREPARED_DIR', 'MOVELLE_STAGING_SUPABASE_URL',
      'MOVELLE_STAGING_PUBLISHABLE_KEY'].includes(key)))
  return { python: join(root, '.venv', platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'),
    env: { ...childEnv, APP_ENV: 'development', TRUSTED_PROXY_IPS: '', CORS_ALLOWED_ORIGINS: '',
      VITE_STAGING_SUPABASE_URL: env.MOVELLE_STAGING_SUPABASE_URL,
      VITE_STAGING_SUPABASE_PUBLISHABLE_KEY: env.MOVELLE_STAGING_PUBLISHABLE_KEY,
      MOVELLE_STAGING_API_TARGET: 'http://127.0.0.1:8011' } }
}

export async function main() {
  const plan = stagingPlan(), children = [], origin = 'http://127.0.0.1:5173'
  await availablePort(5173, 'Staging frontend'); await availablePort(8011, 'Staging API')
  let stopping = false, interrupt
  const interrupted = new Promise(resolve => { interrupt = resolve })
  const stop = () => { stopping = true; interrupt() }
  const launch = (command, args, cwd) => {
    const worker = startStagingWorker(command, args, { cwd, env: plan.env, stdio: 'inherit', windowsHide: true })
    children.push(worker)
    worker.exited = worker.exited.then(() => { if (!stopping) throw new Error('Staging process stopped') })
    worker.exited.catch(() => {})
    return worker
  }
  process.once('SIGINT', stop); process.once('SIGTERM', stop)
  try {
    const api = launch(plan.python, ['-m', 'uvicorn', 'app.staging_entry:application', '--factory', '--host', '127.0.0.1',
      '--port', '8011', '--no-access-log', '--no-proxy-headers', '--log-level', 'warning'], root)
    await Promise.race([waitForApi(plan.env.MOVELLE_STAGING_API_TARGET, () => !stopping && api.running), api.exited, interrupted])
    if (stopping) return
    const vite = launch(process.execPath, [join(root, 'frontend/node_modules/vite/bin/vite.js'),
      '--config', 'vite.staging.config.js'], join(root, 'frontend'))
    await Promise.race([waitForFrontend(origin, () => !stopping && children.every(worker => worker.running)), api.exited, vite.exited, interrupted])
    if (stopping) return
    console.log('STAGING READY: http://127.0.0.1:5173/ — local only; Ctrl+C stops both services')
    await Promise.race([api.exited, vite.exited, interrupted])
  } finally {
    stopping = true
    try { await stopStagingWorkers(children) }
    finally {
      process.removeListener('SIGINT', stop); process.removeListener('SIGTERM', stop)
    }
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  main().catch(() => { console.error('Isolated staging failed; verify private local configuration and free ports.'); process.exitCode = 1 })

// Test supervisor only: fictional Auth + actual staging HTTP/PG + actual Vite entry.
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import { once } from 'node:events'
import { availablePort, waitForApi, waitForFrontend } from './dev.mjs'
import { stagingPlan } from './staging.mjs'

const root = fileURLToPath(new URL('../../', import.meta.url)), children = []
let stopping
async function stop() {
  if (stopping) return stopping
  stopping = (async () => {
    try { await fetch('http://127.0.0.1:19002/_fixture/shutdown', { method: 'POST', signal: AbortSignal.timeout(3000) }) } catch {}
    const backend = children[0]
    if (backend?.exitCode === null) await Promise.race([once(backend, 'exit'), new Promise(resolve => setTimeout(resolve, 15000))])
    for (const child of children) if (child.exitCode === null) child.kill()
  })()
  return stopping
}
try {
  if (!process.env.POSTGRES_TEST_URL) throw new Error()
  for (const port of [5173, 19001, 19002]) await availablePort(port, 'Offline staging fixture')
  const plan = stagingPlan({ ...process.env, MOVELLE_STAGING_DATABASE_URL: process.env.POSTGRES_TEST_URL,
    MOVELLE_STAGING_PREPARED_DIR: 'fixture-owned', MOVELLE_STAGING_SUPABASE_URL: 'https://aaaaaaaaaaaaaaaaaaaa.supabase.co',
    MOVELLE_STAGING_PUBLISHABLE_KEY: 'sb_publishable_offline' })
  const env = { ...plan.env, POSTGRES_TEST_URL: process.env.POSTGRES_TEST_URL, MOVELLE_STAGING_API_TARGET: 'http://127.0.0.1:19001' }
  const launch = (command, args, cwd) => {
    const child = spawn(command, args, { cwd, env, stdio: 'inherit', windowsHide: true }); children.push(child)
    child.on('error', () => { void stop() }); return child
  }
  process.once('SIGTERM', stop); process.once('SIGINT', stop)
  const backend = launch(plan.python, ['tests/staging_fixture_server.py'], root)
  await waitForApi(env.MOVELLE_STAGING_API_TARGET, () => backend.exitCode === null)
  const vite = launch(process.execPath, [join(root, 'frontend/node_modules/vite/bin/vite.js'), '--config', 'vite.staging.config.js'], join(root, 'frontend'))
  await waitForFrontend('http://127.0.0.1:5173', () => children.every(c => c.exitCode === null))
  console.log('OFFLINE STAGING BROWSER FIXTURE READY')
  await Promise.race(children.map(child => once(child, 'exit')))
} catch { console.error('Offline staging browser fixture failed'); process.exitCode = 1 }
finally { await stop() }

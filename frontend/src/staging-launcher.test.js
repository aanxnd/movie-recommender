import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { EventEmitter } from 'node:events'
import { fileURLToPath } from 'node:url'
import { stagingPlan, startStagingWorker, stopStagingWorkers } from '../scripts/staging.mjs'

const env = { MOVELLE_STAGING_DATABASE_URL: 'disposable-private-fixture', MOVELLE_STAGING_PREPARED_DIR: 'fixture-path',
  MOVELLE_STAGING_SUPABASE_URL: `https://${'a'.repeat(20)}.supabase.co`, MOVELLE_STAGING_PUBLISHABLE_KEY: 'sb_publishable_offline' }

test('staging launcher requires dedicated inputs; production values cannot activate or select it', () => {
  assert.throws(() => stagingPlan({ DATABASE_URL: 'private', SUPABASE_URL: env.MOVELLE_STAGING_SUPABASE_URL }))
  const plan = stagingPlan({ ...env, DATABASE_URL: 'private-production', AZURE_SECRET: 'private',
    FANART_API_KEY: 'private', VITE_API_BASE_URL: 'https://production.invalid', PATH: 'tool-path' }, 'win32')
  assert.equal(plan.env.APP_ENV, 'development'); assert.equal(plan.env.PATH, 'tool-path')
  for (const name of ['DATABASE_URL', 'AZURE_SECRET', 'FANART_API_KEY', 'VITE_API_BASE_URL']) assert.equal(plan.env[name], undefined)
  assert.equal(plan.env.VITE_STAGING_SUPABASE_URL, env.MOVELLE_STAGING_SUPABASE_URL)
  assert.equal(plan.env.MOVELLE_STAGING_API_TARGET, 'http://127.0.0.1:8011')
  assert.match(plan.python, /Scripts[\\/]python.exe$/)
})

test('staging entry and build are explicitly separate from production startup', async () => {
  const [main, staging, config] = await Promise.all(['main.jsx', 'staging-main.jsx', '../vite.staging.config.js']
    .map(path => readFile(new URL(path, import.meta.url), 'utf8')))
  assert.doesNotMatch(main, /staging|Supabase|AuthProvider/)
  assert.match(staging, /createStagingRuntime/)
  assert.match(config, /outDir: 'dist-staging'/)
  assert.match(config, /staging\/index.html/)
})

test('a real missing executable rejects safely and cleanup never waits for nonexistent exit', async () => {
  const worker = startStagingWorker(fileURLToPath(new URL('../.missing-staging-executable', import.meta.url)), [])
  await assert.rejects(worker.exited, { message: 'Staging process could not start or stop' })
  assert.equal(worker.running, false)
  await stopStagingWorkers([worker], 50)
})

function fakeWorker(kill) {
  const child = new EventEmitter()
  child.pid = 123; child.kill = signal => kill(child, signal)
  return startStagingWorker('unused', [], { spawnProcess: () => child })
}

test('cleanup forces an unresponsive child and observes its actual exit', async () => {
  const signals = []
  const worker = fakeWorker((child, signal) => {
    signals.push(signal)
    if (signal === 'SIGKILL') queueMicrotask(() => child.emit('exit', null, signal))
  })
  await stopStagingWorkers([worker], 10)
  assert.deepEqual(signals, ['SIGTERM', 'SIGKILL'])
  assert.equal(worker.running, false)
})

test('failed termination is bounded and a kill error never claims the process exited', async () => {
  const worker = fakeWorker(child => { queueMicrotask(() => child.emit('error', new Error('private process detail'))) })
  await assert.rejects(stopStagingWorkers([worker], 10), { message: 'Staging processes did not stop' })
  assert.equal(worker.running, true)
  worker.child.emit('exit', null, 'SIGKILL') // Only the synthetic child needs final teardown.
})

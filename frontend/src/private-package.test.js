import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, writeFile, readFile, readdir, rm } from 'node:fs/promises'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { preparePrivate } from '../scripts/prepare-private.mjs'
import { readTargets } from '../private/targets.mjs'

test('explicit private bundle builds separately, packages only selected source and never emits server secrets', async t => {
  const repo = fileURLToPath(new URL('../..', import.meta.url))
  const work = resolve(repo, '.pytest-tmp', 'private-package-' + crypto.randomUUID())
  await mkdir(work, { recursive: true })
  t.after(async () => { assert.ok(work.startsWith(resolve(repo, '.pytest-tmp') + '/'.replace('/', process.platform === 'win32' ? '\\' : '/'))); await rm(work, { recursive: true }) })
  const targets = { approved: true, branch_name: 'private-stage23', branch_id: 'br-private-offline',
    azure_app: 'movie-recommender-api-private', supabase_url: 'https://jsbulnrcxtvslvvxjizq.supabase.co',
    frontend_origin: 'https://owner-preview.vercel.app', backend_origin: 'https://private.example.azurecontainerapps.io',
    database_host: 'ep-private-test.canadacentral.azure.neon.tech', protected_database_hosts: ['ep-protected.neon.tech'] }
  const file = join(work, 'targets.json'); await writeFile(file, JSON.stringify(targets))
  const vars = { MOVELLE_PRIVATE_TARGETS_FILE: file, VITE_PRIVATE_PUBLISHABLE_KEY: 'sb_publishable_offline',
    MOVELLE_PRIVATE_GATE_SECRET: 'SERVER_ONLY_GATE_MARKER', DATABASE_URL: 'SERVER_ONLY_DATABASE_MARKER',
    VITE_PRIVATE_PUBLIC_GATE_SECRET: 'ACCIDENTAL_VITE_GATE_MARKER', VITE_API_BASE_URL: 'https://must-not-use.invalid' }
  const previous = Object.fromEntries(Object.keys(vars).map(k => [k, process.env[k]]))
  Object.assign(process.env, vars)
  t.after(() => { for (const [k, v] of Object.entries(previous)) { if (v === undefined) delete process.env[k]; else process.env[k] = v } })
  const bundle = join(work, 'bundle'); assert.equal(await preparePrivate(bundle), bundle)
  await assert.rejects(preparePrivate(bundle)) // No overwrite or recursive cleanup of existing paths.
  await assert.rejects(preparePrivate(resolve(repo, 'frontend')))
  const root = join(bundle, 'frontend'), assets = join(root, 'public/assets')
  const js = (await Promise.all((await readdir(assets)).filter(f => f.endsWith('.js')).map(f => readFile(join(assets, f), 'utf8')))).join('')
  for (const secret of ['SERVER_ONLY_GATE_MARKER', 'SERVER_ONLY_DATABASE_MARKER', 'ACCIDENTAL_VITE_GATE_MARKER', 'must-not-use.invalid', targets.database_host, targets.backend_origin]) assert.ok(!js.includes(secret), secret)
  assert.ok(js.includes(targets.frontend_origin) && js.includes(targets.supabase_url))
  assert.deepEqual((await readdir(root)).sort(), ['api', 'package.json', 'private', 'public', 'vercel.json'])
  assert.match(await readFile(join(root, 'api/gateway.mjs'), 'utf8'), /\.\.\/private\/gateway.mjs/)
  const config = JSON.parse(await readFile(join(root, 'vercel.json'), 'utf8'))
  assert.equal(config.outputDirectory, 'public'); assert.equal(config.framework, null)
  assert.deepEqual(config.rewrites, [{ source: '/api/:path*', destination: '/api/gateway?__movelle_route=/:path*' }])
  const main = await readFile(new URL('./main.jsx', import.meta.url), 'utf8')
  assert.doesNotMatch(main, /private|staging|Supabase/)
  for (const change of [{ approved: false }, { branch_id: 'br-tiny-bonus-b4ec6f9z' },
    { frontend_origin: 'https://custom.invalid' }, { database_host: 'ep-protected.neon.tech' }, { password: 'never-store-this' }]) {
    await writeFile(file, JSON.stringify({ ...targets, ...change }))
    assert.throws(() => readTargets(file), /Approved private targets required/)
  }
})

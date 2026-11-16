import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, writeFile, readFile, readdir, rm } from 'node:fs/promises'
import { resolve, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { prepareNative } from '../scripts/prepare-native.mjs'

test('native Vercel bundle is static-only, exact-origin, secret-free and cannot overwrite staging', async t => {
  const repo = fileURLToPath(new URL('../..', import.meta.url)), parent = resolve(repo, '.pytest-tmp')
  const work = join(parent, 'native-package-' + crypto.randomUUID())
  await mkdir(work, { recursive: true })
  t.after(async () => { assert.ok(relative(parent, work) && !relative(parent, work).startsWith('..')); await rm(work, { recursive: true }) })
  const targets = { approved: true, frontend_origin: 'https://owner.vercel.app', api_origin: 'https://api.example',
    supabase_url: 'https://' + 'a'.repeat(20) + '.supabase.co', database_host: 'ep-private.neon.tech', database_name: 'private_owner_db' }
  const file = join(work, 'targets.json'); await writeFile(file, JSON.stringify(targets))
  const vars = { MOVELLE_NATIVE_TARGETS_FILE: file, MOVELLE_NATIVE_PUBLISHABLE_KEY: 'sb_publishable_offline',
    MOVELLE_NATIVE_DATABASE_URL: 'SERVER_DATABASE_MARKER', MOVELLE_PRIVATE_GATE_SECRET: 'SERVER_GATE_MARKER',
    VITE_API_BASE_URL: 'https://legacy-must-not-appear.invalid' }
  const previous = Object.fromEntries(Object.keys(vars).map(k => [k, process.env[k]]))
  Object.assign(process.env, vars)
  t.after(() => { for (const [k, v] of Object.entries(previous)) { if (v === undefined) delete process.env[k]; else process.env[k] = v } })
  const bundle = join(work, 'bundle'); assert.equal(await prepareNative(bundle), bundle)
  await assert.rejects(prepareNative(bundle))
  await assert.rejects(prepareNative(resolve(repo, 'frontend')))
  const root = join(bundle, 'frontend')
  assert.deepEqual((await readdir(root)).sort(), ['public', 'vercel.json'])
  const assets = join(root, 'public/assets')
  const js = (await Promise.all((await readdir(assets)).filter(f => f.endsWith('.js')).map(f => readFile(join(assets, f), 'utf8')))).join('')
  for (const secret of ['SERVER_DATABASE_MARKER', 'SERVER_GATE_MARKER', targets.database_host, targets.database_name, 'legacy-must-not-appear.invalid']) assert.ok(!js.includes(secret), secret)
  assert.ok(js.includes(targets.api_origin) && js.includes(targets.supabase_url))
  const config = JSON.parse(await readFile(join(root, 'vercel.json'), 'utf8'))
  assert.equal(config.outputDirectory, 'public')
  assert.ok(!config.functions && !config.rewrites)
  const headers = config.headers[0].headers
  assert.equal(headers.find(h => h.key === 'Referrer-Policy').value, 'no-referrer')
  const csp = headers.find(h => h.key === 'Content-Security-Policy').value
  assert.ok(csp.includes(`connect-src 'self' ${targets.api_origin} ${targets.supabase_url};`))
  assert.ok(!csp.includes('https:;'))
  for (const change of [{ approved: false }, { api_origin: "https://api.example;evil" },
    { api_origin: 'https://owner.vercel.app' }, { frontend_origin: 'https://*.vercel.app' }]) {
    await writeFile(file, JSON.stringify({ ...targets, ...change }))
    const rejected = join(work, 'rejected-' + crypto.randomUUID())
    await assert.rejects(prepareNative(rejected)); await assert.rejects(readdir(rejected))
  }
  const normal = JSON.parse(await readFile(join(repo, 'frontend/package.json'), 'utf8'))
  assert.equal(normal.scripts.build, 'vite build') // Existing production selector unchanged.
})

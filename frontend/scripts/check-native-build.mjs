// Offline artifact check only. Synthetic approved targets never authorize deployment.
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const prefix = join(tmpdir(), 'movelle-native-'), folder = mkdtempSync(prefix)
try {
  const file = join(folder, 'targets.json')
  writeFileSync(file, JSON.stringify({ approved: true, frontend_origin: 'https://frontend.example',
    api_origin: 'https://backend.example', supabase_url: 'https://' + 'a'.repeat(20) + '.supabase.co',
    database_host: 'server-only-canary.invalid', database_name: 'server-only-canary' }))
  const env = { ...process.env, MOVELLE_NATIVE_TARGETS_FILE: file, MOVELLE_NATIVE_PUBLISHABLE_KEY: 'sb_publishable_offline' }
  const run = () => spawnSync(process.execPath, ['node_modules/vite/bin/vite.js', 'build', '--config', 'vite.native.config.js'],
    { env, encoding: 'utf8', timeout: 120000 })
  let built = run()
  if (built.status !== 0) { console.error(built.stdout, built.stderr); process.exitCode = 1 }
  else {
    const html = readFileSync('dist-native/index.html', 'utf8')
    const js = readdirSync('dist-native/assets').filter(f => f.endsWith('.js')).map(f => readFileSync('dist-native/assets/' + f, 'utf8')).join('\n')
    assert.match(html, /no-referrer/)
    assert.doesNotMatch(js, /PRIVATE LOCAL STAGING|Staging account navigation|movelle\.identity\.v1|server-only-canary|fictional-provider|account-demo/)
    assert.match(js, /https:\/\/backend\.example/)
    writeFileSync(file, JSON.stringify({ approved: false }))
    built = run(); assert.notEqual(built.status, 0)
    assert.match(built.stderr, /Approved native build configuration required/)
    console.log('Native artifact isolation and unapproved-build refusal passed')
  }
} finally {
  assert.ok(resolve(folder).startsWith(resolve(prefix)))
  rmSync(folder, { recursive: true, force: true })
}

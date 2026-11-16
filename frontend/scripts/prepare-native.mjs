// Offline source bundle only. Never calls Vercel or modifies the live project.
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve, relative, isAbsolute, join } from 'node:path'
import { build } from 'vite'
import { exactHttpsOrigin } from '../src/native-runtime.js'

const frontend = fileURLToPath(new URL('..', import.meta.url)), repo = resolve(frontend, '..')

export async function prepareNative(output) {
  const raw = await readFile(process.env.MOVELLE_NATIVE_TARGETS_FILE, 'utf8')
  if (raw.length > 8192) throw new Error('Reviewed native targets required')
  const t = JSON.parse(raw)
  const safe = value => exactHttpsOrigin(value) && /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(new URL(value).hostname)
  if (t.approved !== true || !safe(t.frontend_origin) || !safe(t.api_origin) || t.frontend_origin === t.api_origin ||
      !/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(t.supabase_url)) throw new Error('Reviewed native targets required')
  const path = resolve(output), allowed = relative(join(repo, '.pytest-tmp'), path)
  if (!allowed || allowed.startsWith('..') || isAbsolute(allowed)) throw new Error('Isolated new bundle path required')
  await mkdir(path) // Exclusive: never overwrite an existing review/staging directory.
  const root = join(path, 'frontend')
  await mkdir(root)
  await build({ root: frontend, configFile: join(frontend, 'vite.native.config.js'), logLevel: 'error',
    build: { outDir: join(root, 'public'), sourcemap: false } })
  const csp = `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ${t.api_origin} ${t.supabase_url}; img-src 'self' data: ${t.api_origin} https://assets.fanart.tv; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`
  await writeFile(join(root, 'vercel.json'), JSON.stringify({ framework: null, buildCommand: '', installCommand: '',
    outputDirectory: 'public', headers: [{ source: '/(.*)', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' }, { key: 'Referrer-Policy', value: 'no-referrer' },
      { key: 'Content-Security-Policy', value: csp }] }] }, null, 2))
  return path
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { console.log(await prepareNative(process.argv[2] ?? join(repo, '.pytest-tmp', 'native-vercel-bundle'))) }
  catch { console.error('Native bundle preparation refused'); process.exitCode = 1 }
}

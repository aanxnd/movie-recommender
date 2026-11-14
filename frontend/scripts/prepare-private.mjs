// Creates a new isolated local source bundle. Never invokes Vercel/Azure/Neon.
import { mkdir, copyFile, writeFile, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve, relative, isAbsolute, join } from 'node:path'
import { build } from 'vite'
import { readTargets } from '../private/targets.mjs'

const frontend = fileURLToPath(new URL('..', import.meta.url)), repo = resolve(frontend, '..')
export async function preparePrivate(output) {
  const t = readTargets(process.env.MOVELLE_PRIVATE_TARGETS_FILE)
  const path = resolve(output), allowed = relative(join(repo, '.pytest-tmp'), path)
  if (!allowed || allowed.startsWith('..') || isAbsolute(allowed)) throw new Error('Isolated new bundle path required')
  await mkdir(path) // Refuse an existing directory; never recursively overwrite/delete.
  const root = join(path, 'frontend')
  await mkdir(join(root, 'api'), { recursive: true }); await mkdir(join(root, 'private'))
  await build({ root: frontend, configFile: join(frontend, 'vite.private.config.js'),
    logLevel: 'error', build: { outDir: join(root, 'public') } })
  await copyFile(join(frontend, 'private/gateway.mjs'), join(root, 'private/gateway.mjs'))
  const handler = await readFile(join(frontend, 'private/handler.mjs'), 'utf8')
  await writeFile(join(root, 'api/gateway.mjs'), handler.replaceAll("'./", "'../private/"))
  await writeFile(join(root, 'private/targets.json'), JSON.stringify(t))
  await writeFile(join(root, 'package.json'), JSON.stringify({ private: true, type: 'module', engines: { node: '24.x' } }))
  await copyFile(join(frontend, 'private/vercel.json'), join(root, 'vercel.json'))
  return path
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { console.log(await preparePrivate(process.argv[2] ?? join(repo, '.pytest-tmp', 'private-stage23-bundle'))) }
  catch { console.error('Private bundle preparation refused'); process.exitCode = 1 }
}

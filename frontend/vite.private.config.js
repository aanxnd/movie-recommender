import { defineConfig } from 'vite'
import { readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readTargets } from './private/targets.mjs'

export default defineConfig(() => {
  const t = readTargets(process.env.MOVELLE_PRIVATE_TARGETS_FILE)
  const key = process.env.VITE_PRIVATE_PUBLISHABLE_KEY
  if (!/^sb_publishable_[A-Za-z0-9_-]{1,256}$/.test(key ?? '')) throw new Error('Private public SDK configuration required')
  return { envPrefix: 'VITE_PRIVATE_PUBLIC_',
    define: { __MOVELLE_PRIVATE_PUBLIC__: JSON.stringify({ approved: true,
      frontend_origin: t.frontend_origin, supabase_url: t.supabase_url }), __MOVELLE_PRIVATE_KEY__: JSON.stringify(key) },
    plugins: [{ name: 'movelle-private-entry', transformIndexHtml: { order: 'pre',
      handler: () => readFileSync(new URL('./private/index.html', import.meta.url), 'utf8') } }, react(), tailwindcss()],
    build: { outDir: 'dist-private', emptyOutDir: true, sourcemap: false },
  }
})

import { defineConfig } from 'vite'
import { readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { apiProxy } from './scripts/api-proxy.mjs'

// Selected explicitly, never by normal build or production environment variables.
export default defineConfig({
  plugins: [{ name: 'movelle-isolated-staging-entry', transformIndexHtml: { order: 'pre',
    handler: () => readFileSync(new URL('./staging/index.html', import.meta.url), 'utf8') } }, react(), tailwindcss()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '^/api(?:/|$)': apiProxy(process.env.MOVELLE_STAGING_API_TARGET ?? 'http://127.0.0.1:8011') } },
  build: { outDir: 'dist-staging', emptyOutDir: true },
})

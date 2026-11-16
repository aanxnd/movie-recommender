import { defineConfig } from 'vite'
import { readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { exactHttpsOrigin } from './src/native-runtime.js'

export default defineConfig(() => {
  try {
    const raw = readFileSync(process.env.MOVELLE_NATIVE_TARGETS_FILE, 'utf8')
    if (raw.length > 8192) throw new Error()
    const t = JSON.parse(raw), key = process.env.MOVELLE_NATIVE_PUBLISHABLE_KEY
    if (t.approved !== true || !exactHttpsOrigin(t.frontend_origin) || !exactHttpsOrigin(t.api_origin) ||
        t.frontend_origin === t.api_origin || !/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(t.supabase_url) ||
        !/^sb_publishable_[A-Za-z0-9_-]{1,256}$/.test(key)) throw new Error()
    return { envPrefix: [], // Native bundles accept only the explicit public definitions below.
      plugins: [{ name: 'movelle-native-entry', transformIndexHtml: { order: 'pre',
      handler: () => readFileSync(new URL('./native/index.html', import.meta.url), 'utf8') } }, react(), tailwindcss()],
      define: { __MOVELLE_NATIVE_PUBLIC__: JSON.stringify({ approved: true, mode: 'native-release',
        frontend_origin: t.frontend_origin, api_origin: t.api_origin, supabase_url: t.supabase_url }),
        __MOVELLE_NATIVE_KEY__: JSON.stringify(key) }, build: { outDir: 'dist-native', emptyOutDir: true } }
  } catch { throw new Error('Approved native build configuration required') }
})

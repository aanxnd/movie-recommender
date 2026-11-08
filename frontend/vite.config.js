import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'
import { apiProxy } from './scripts/api-proxy.mjs'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '^/api(?:/|$)': apiProxy(
        loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), '')
          .API_PROXY_TARGET
      )
    }
  }
}))

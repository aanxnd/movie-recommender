import { defineConfig } from '@playwright/test'
import base from './playwright.config.js'

export default defineConfig({ ...base, testMatch: 'staging-integration.spec.js', testIgnore: [],
  globalTeardown: './browser/staging-teardown.js', timeout: 60000,
  use: { ...base.use, baseURL: 'http://127.0.0.1:5173' },
  webServer: { command: 'node scripts/staging-browser.mjs', url: 'http://127.0.0.1:5173/api/ready',
    timeout: 60000, reuseExistingServer: false, gracefulShutdown: { signal: 'SIGTERM', timeout: 20000 } },
})

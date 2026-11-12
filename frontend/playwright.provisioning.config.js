import { defineConfig } from '@playwright/test'
import base from './playwright.config.js'

// Isolated local fixture uses the one approved development Auth origin.
export default defineConfig({ ...base, testMatch: 'profile-provisioning.spec.js', testIgnore: [],
  use: { ...base.use, baseURL: 'http://127.0.0.1:5173' },
  webServer: { ...base.webServer, command: 'node scripts/dev.mjs --port 5173',
    url: 'http://127.0.0.1:5173/api/ready' },
})

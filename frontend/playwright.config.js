import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './browser',
  testIgnore: 'profile-provisioning.spec.js', // Uses approved Auth origin via its dedicated config.
  workers: 1,
  timeout: 60000,
  expect: { timeout: 12000 },
  reporter: 'list',
  outputDir: '../.pytest-tmp/browser-results',
  use: {
    baseURL: 'http://127.0.0.1:5180',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 900 },
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  webServer: {
    command: 'node scripts/dev.mjs --port 5180',
    url: 'http://127.0.0.1:5180/api/ready',
    timeout: 60000,
    reuseExistingServer: false,
    env: {
      MOVELLE_DEV_API_PORT: '8010',
      MOVELLE_DEV_INSTANCE: `browser-qa-${process.pid}`,
    },
  },
})

import { test, expect } from '@playwright/test'

async function offlineLegacy(page, saved) {
  const calls = [], nativeRequests = []
  await page.addInitScript(({ saved }) => {
    if (saved) localStorage.setItem('movelle.identity.v1', JSON.stringify({ id: 73, token: 'a'.repeat(43) }))
    localStorage.setItem('movelle.signup-confirmation', JSON.stringify({ access_token: 'offline.native.jwt', refresh_token: 'offline-only' }))
    window.__nativeBefore = localStorage.getItem('movelle.signup-confirmation')
  }, { saved })
  page.on('request', request => { if (/supabase\.co|\/auth\/v1/.test(request.url())) nativeRequests.push(true) })
  await page.route('**/*', async route => {
    const request = route.request(), target = new URL(request.url()), method = request.method()
    const path = target.pathname.replace(/^\/api(?=\/)/, '')
    if (!/^\/(?:users|movies|recommendations)(?:\/|$)/.test(path)) {
      if (target.origin === 'http://127.0.0.1:5180') await route.continue()
      else await route.abort() // Never contact a hosted service, regardless of inherited API configuration.
      return
    }
    calls.push({ path, method, hasLegacy: request.headers().authorization === 'Bearer ' + 'a'.repeat(43) })
    let body = path === '/movies/decades' ? [1990, 2000] : path === '/movies/artwork' ? { items: [], configured: false } : []
    if (path === '/users' && method === 'POST') body = { id: 73, token: 'a'.repeat(43), expires_at: Math.floor(Date.now()/1000)+86400 }
    if (path === '/users/73') body = { id: 73 }
    if (path === '/users/73/ratings/details') body = { items: [], total: 0, next_after: null }
    await route.fulfill({ status: path === '/users' ? 201 : 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  return { calls, nativeRequests }
}

test('live entry restores legacy credentials after reload without activating or clearing native sessions', async ({ page }) => {
  const f = await offlineLegacy(page, true)
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1050 })
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Your profile' })).toContainText('User 73')
    await page.reload()
    await expect(page.getByRole('button', { name: 'Your profile' })).toContainText('User 73')
    expect(await page.evaluate(() => localStorage.getItem('movelle.signup-confirmation') === window.__nativeBefore)).toBe(true)
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('movelle.identity.v1')).id)).toBe(73)
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('movelle.identity.v1')).token === 'a'.repeat(43))).toBe(true)
  }
  expect(f.calls.filter(c => c.path === '/users/73').every(c => c.hasLegacy)).toBe(true)
  expect(f.calls.some(c => c.path === '/users' && c.method === 'POST')).toBe(false)
  expect(f.nativeRequests).toEqual([])
})

test('anonymous browsing and explicit legacy registration/restoration remain available', async ({ page }) => {
  const f = await offlineLegacy(page, false)
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Your profile' })).toBeVisible()
  expect(f.calls.some(c => c.path.startsWith('/users'))).toBe(false)
  await page.getByRole('button', { name: 'Your profile' }).click()
  await page.getByRole('button', { name: 'Create new user' }).click()
  await expect(page.locator('.profile-status')).toContainText('User 73')
  expect(f.calls.filter(c => c.path === '/users' && c.method === 'POST').length).toBe(1)
  await page.getByLabel('Private recovery code', { exact: true }).fill('73:' + 'a'.repeat(43))
  await page.getByRole('button', { name: 'Load', exact: true }).click()
  await expect(page.locator('.profile-status')).toContainText('User 73')
  expect(f.nativeRequests).toEqual([])
})

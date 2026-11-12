import { test, expect } from '@playwright/test'

async function fixture(page, mode = 'success') {
  const writes = [], methods = [], messages = []
  let profile
  page.on('console', message => messages.push(message.text()))
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== 'http://127.0.0.1:5173') return route.abort()
    if (url.pathname.startsWith('/api/')) {
      expect(url.pathname).toBe('/api/auth/profile')
      expect(request.headers().authorization).toMatch(/^Bearer /)
      methods.push(request.method())
      if (request.method() === 'POST') {
        const body = request.postDataJSON(); writes.push(body)
        expect(Object.keys(body)).toEqual(['username'])
        if (mode === 'conflict') return route.fulfill({ status: 409, json: { detail: 'private diagnostics' } })
        profile ??= { status: 'complete', username: body.username }
        if (mode === 'lost-ack') return route.abort()
      }
      return route.fulfill({ json: profile ?? { status: 'eligible' } })
    }
    return route.continue()
  })
  await page.goto('/browser/provisioning-demo.html')
  await expect(page.getByLabel('Profile username')).toBeVisible()
  expect(writes).toEqual([]) // StrictMode observations never create profiles.
  return { writes, methods, messages }
}

for (const width of [1440, 390]) {
  test('explicit keyboard provisioning and clean mobile/desktop UI: ' + width, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const f = await fixture(page)
    await page.keyboard.press('Tab'); await expect(page.getByLabel('Profile username')).toBeFocused()
    await page.keyboard.type('MovieFan')
    await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: 'Create my profile' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('status')).toContainText('Your profile is ready: MovieFan')
    await expect(page.getByRole('status')).toBeFocused()
    expect(f.writes).toEqual([{ username: 'MovieFan' }])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(f.messages.join(' ')).not.toMatch(/synthetic-refresh|private diagnostics|Bearer /)
  })
}

test('lost acknowledgement resolves by GET without replay', async ({ page }) => {
  const f = await fixture(page, 'lost-ack')
  await page.getByLabel('Profile username').fill('Original')
  await page.getByRole('button', { name: 'Create my profile' }).click()
  await expect(page.getByRole('status')).toContainText('Your profile is ready: Original')
  expect(f.writes).toHaveLength(1)
  expect(f.methods.slice(-2)).toEqual(['POST', 'GET'])
})

test('username conflict has focused accessible error without private diagnostics', async ({ page }) => {
  const f = await fixture(page, 'conflict')
  await page.getByLabel('Profile username').fill('TakenName')
  await page.getByRole('button', { name: 'Create my profile' }).click()
  await expect(page.getByRole('alert')).toContainText('username is unavailable')
  await expect(page.getByRole('alert')).toBeFocused()
  await expect(page.locator('body')).not.toContainText('private diagnostics')
  expect(f.writes).toHaveLength(1)
})

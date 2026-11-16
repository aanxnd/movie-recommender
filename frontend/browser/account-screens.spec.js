import { test, expect } from '@playwright/test'

test('offline signup works by keyboard, has no overflow and sends no credential requests', async ({ page }) => {
  const authRequests = []
  page.on('request', request => { if (/supabase|\/auth\/v1|\/users(?:\?|$)/.test(request.url())) authRequests.push(request.url()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/browser/account-demo.html')
    await expect(page.getByRole('heading', { name: 'Make yourself at home.' })).toBeVisible()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Change website theme' })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Email address')).toBeFocused()
    await page.keyboard.type('offline@example.invalid')
    await page.keyboard.press('Tab'); await page.keyboard.type('synthetic-private')
    await page.keyboard.press('Tab'); await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: 'Hide password', exact: true })).toBeFocused()
    await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text')
    await page.keyboard.press('Tab'); await page.keyboard.type('synthetic-private')
    await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Enter')
    await expect(page.getByRole('status')).toContainText('If signup can proceed')
    await expect(page.getByRole('status')).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(page.locator('body')).not.toContainText('synthetic-private')
  }
  expect(authRequests).toEqual([])
})

test('offline verification retains ambiguous provenance until explicit navigation', async ({ page }) => {
  await page.goto('/browser/account-demo.html?screen=verification')
  await expect(page.getByRole('status')).toContainText('does not establish signup confirmation')
  await expect(page).toHaveURL(/screen=verification$/)
})

test('profile preview has no premature provisioning controls', async ({ page }) => {
  await page.goto('/browser/account-demo.html?screen=profile')
  await expect(page.getByRole('status')).toContainText('Profile setup is not available yet')
  await expect(page.getByRole('button', { name: 'Create my profile' })).toHaveCount(0)
})

test('irreversible deletion preview requires explicit typed intent, masks secrets and never calls hosted services', async ({ page }) => {
  const requests = []
  page.on('request', r => { if (/supabase|\/auth\/|\/users/.test(r.url())) requests.push(r.url()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/browser/account-demo.html?screen=deletion-review')
    await expect(page.getByRole('heading', { name: 'Delete your account.' })).toBeVisible()
    await expect(page.getByLabel('Accessible authenticator')).toBeVisible()
    await page.getByLabel('Current password', { exact: true }).fill('synthetic-private')
    await page.getByLabel('Fresh six-digit code').fill('123456')
    await page.getByLabel('Type PERMANENTLY DELETE MY ACCOUNT').fill('DELETE')
    await page.getByRole('button', { name: 'Request permanent deletion' }).click()
    await expect(page.getByRole('button', { name: 'Request permanent deletion' })).toBeVisible()
    await page.getByLabel('Type PERMANENTLY DELETE MY ACCOUNT').fill('PERMANENTLY DELETE MY ACCOUNT')
    await page.getByRole('button', { name: 'Request permanent deletion' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'does not confirm erasure' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(page.locator('body')).not.toContainText('synthetic-private')
    await expect(page.locator('body')).not.toContainText('123456')
  }
  expect(requests).toEqual([])
})

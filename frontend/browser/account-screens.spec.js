import { test, expect } from '@playwright/test'

test('offline signup works by keyboard, has no overflow and sends no credential requests', async ({ page }) => {
  const authRequests = []
  page.on('request', request => { if (/supabase|\/auth\/v1|\/users(?:\?|$)/.test(request.url())) authRequests.push(request.url()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/browser/account-demo.html')
    await expect(page.getByRole('heading', { name: 'Make yourself at home.' })).toBeVisible()
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

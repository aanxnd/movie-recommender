import { test, expect } from '@playwright/test'

test('offline settings are keyboard accessible, private and non-destructive on mobile/desktop', async ({ page }) => {
  const requests = []
  page.on('request', r => { if (/supabase|\/auth\/v1|\/users(?:\/|\?|$)/.test(r.url())) requests.push(r.url()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/browser/account-demo.html?screen=settings')
    await expect(page.getByText('Your authorized profile: MovieFan')).toBeVisible()
    await page.getByLabel('New username').fill('MovieFan_2'); await page.getByLabel('New username').press('Enter')
    await expect(page.getByRole('status').filter({ hasText: 'Your username is updated.' })).toBeFocused()
    await page.getByLabel('New email address').fill('private@example.invalid')
    await page.getByLabel('Current password', { exact: true }).fill('synthetic-current')
    await page.getByRole('button', { name: 'Request email change' }).focus(); await page.keyboard.press('Enter')
    await expect(page.getByRole('status').filter({ hasText: 'Delivery and completion cannot be confirmed' })).toBeVisible()
    await expect(page.locator('body')).not.toContainText('private@example.invalid')
    await page.getByRole('button', { name: 'Review deletion' }).click()
    const dialog = page.getByRole('dialog', { name: 'Review account deletion' })
    await expect(dialog).toBeVisible(); await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await expect(dialog.getByRole('button', { name: 'Deletion unavailable' })).toBeDisabled()
    await page.keyboard.press('Tab'); await expect(dialog.getByRole('checkbox')).toBeFocused()
    await page.keyboard.press('Space'); await page.keyboard.press('Shift+Tab')
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible()
    await expect(page.getByRole('button', { name: 'Review deletion' })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  expect(requests).toEqual([])
})
test('pending email and ambiguous callback previews never claim new-address confirmation', async ({ page }) => {
  await page.goto('/browser/account-demo.html?screen=settings-pending')
  await expect(page.getByRole('status').filter({ hasText: 'Both old and new inboxes' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Request email change' })).toHaveCount(0)
  await page.goto('/browser/account-demo.html?screen=email-callback')
  await expect(page.getByRole('alert')).toContainText('did not establish an email-change context')
})

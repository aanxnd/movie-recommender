import { test, expect } from '@playwright/test'

test('offline password journeys work by keyboard on desktop and mobile without provider requests', async ({ page }) => {
  const requests = []
  page.on('request', r => { if (/supabase|\/auth\/v1/.test(r.url())) requests.push(r.url()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/browser/account-demo.html?screen=forgot')
    await page.keyboard.press('Tab'); await expect(page.getByLabel('Email address')).toBeFocused()
    await page.keyboard.type('offline@example.invalid'); await page.keyboard.press('Enter')
    await expect(page.getByRole('status')).toContainText('Delivery cannot be confirmed')
    await expect(page.getByRole('status')).toBeFocused()
    await page.goto('/browser/account-demo.html?screen=change-password')
    for (const [label, text] of [['Current password', 'synthetic-current'], ['New password', 'synthetic-new'], ['Confirm new password', 'synthetic-new']])
      await page.getByLabel(label, { exact: true }).fill(text)
    await page.getByRole('button', { name: 'Show new password', exact: true }).focus(); await page.keyboard.press('Enter')
    await expect(page.getByLabel('New password', { exact: true })).toHaveAttribute('type', 'text')
    await page.getByRole('button', { name: 'Update password' }).focus(); await page.keyboard.press('Enter')
    await expect(page.getByRole('status')).toContainText('Password updated')
    await expect(page.getByRole('status')).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(page.locator('body')).not.toContainText('synthetic-')
  }
  await page.goto('/browser/account-demo.html?screen=recovery')
  await expect(page.getByRole('alert')).toContainText('did not establish recovery authorization')
  await expect(page.getByRole('button', { name: 'Update password' })).toHaveCount(0)
  expect(requests).toEqual([])
})

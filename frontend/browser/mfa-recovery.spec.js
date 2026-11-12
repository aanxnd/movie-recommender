import { test, expect } from '@playwright/test'

test('offline alternative and replacement recovery works by keyboard on mobile/desktop', async ({ page }) => {
  const authRequests = []
  page.on('request', r => { if (/supabase|\/auth\/v1|\/users(?:\/|\?|$)/.test(r.url())) authRequests.push(r.url()) })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1050 })
    await page.goto('/browser/account-demo.html?screen=mfa-recovery')
    await expect(page.getByLabel('Lost authenticator')).toHaveValue('offline-phone')
    await page.getByLabel('Accessible authenticator').focus(); await page.keyboard.press('Tab')
    const code = page.getByLabel('Six-digit authenticator code')
    await expect(code).toBeFocused(); await expect(code).toHaveAttribute('autocomplete', 'one-time-code')
    await code.fill('123456'); await page.keyboard.press('Enter')
    await expect(page.getByRole('status').filter({ hasText: 'alternative authenticator passed' })).toBeFocused()
    await page.getByRole('button', { name: 'Enroll replacement authenticator' }).focus(); await page.keyboard.press('Enter')
    await expect(page.getByRole('status').filter({ hasText: 'Replacement setup is not complete' })).toBeVisible()
    await expect(page.getByRole('img', { name: 'Authenticator setup QR code' })).toBeVisible()
    await page.getByText('Enter the setup key manually', { exact: true }).click()
    await expect(page.locator('.mfa-secret')).toContainText('OFFLINEDEMONOTAREALKEY')
    await code.fill('654321'); await code.press('Enter')
    await expect(page.getByRole('status').filter({ hasText: 'replacement authenticator is verified' })).toBeFocused()
    await expect(page.locator('body')).not.toContainText('OFFLINEDEMONOTAREALKEY')
    await expect(page.locator('body')).not.toContainText('654321')
    await page.getByRole('button', { name: 'Review lost-authenticator removal' }).click()
    const dialog = page.getByRole('dialog', { name: 'Lost-authenticator removal' })
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await expect(dialog.getByRole('button', { name: 'Removal unavailable' })).toBeDisabled()
    await page.keyboard.press('Shift+Tab'); await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Review lost-authenticator removal' })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  expect(authRequests).toEqual([])
})

test('all-device lockout offers refusal, not password/email/support reset', async ({ page }) => {
  await page.goto('/browser/account-demo.html?screen=mfa-recovery')
  await page.getByRole('button', { name: 'None of my authenticators is accessible' }).click()
  await expect(page.getByRole('alert')).toContainText('Self-service recovery is unavailable')
  await expect(page.getByRole('alert')).toContainText('Password reset or access to email does not remove MFA')
  await expect(page.getByRole('button', { name: 'Enroll replacement authenticator' })).toHaveCount(0)
  await expect(page.getByLabel('Six-digit authenticator code')).toHaveCount(0)
})

test('unknown, abandoned and uncertain states require inspection without automatic mutations', async ({ page }) => {
  for (const state of ['unknown', 'abandoned', 'uncertain']) {
    await page.goto('/browser/account-demo.html?screen=mfa-recovery-' + state)
    await expect(page.getByRole('button', { name: 'Check current authenticator state' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Enroll replacement authenticator' })).toHaveCount(0)
    await expect(page.getByLabel('Six-digit authenticator code')).toHaveCount(0)
    await expect(page.locator('body')).not.toContainText('recovery complete')
    await page.reload()
    await expect(page.getByRole('img', { name: 'Authenticator setup QR code' })).toHaveCount(0)
  }
})

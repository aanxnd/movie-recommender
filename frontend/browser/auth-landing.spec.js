import { test, expect } from '@playwright/test'

const login = '/browser/account-demo.html?screen=login'
function contrast(a, b) {
  const luminance = rgb => rgb.match(/[\d.]+/g).slice(0, 3).map(n => Number(n) / 255)
    .map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4)
    .reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0)
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (values[0] + .05) / (values[1] + .05)
}
test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => new URL(route.request().url()).origin === 'http://127.0.0.1:5180' ? route.continue() : route.abort())
})
for (const width of [1440, 1024, 820, 390, 320]) test('cinematic login stays accessible without overflow: ' + width, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 }); await page.goto(login)
  await expect(page.locator('.auth-quote')).toHaveText('Cinema done your way.')
  await expect(page.locator('.auth-description')).toHaveText('Find your next favorite. Keep the ones that stay with you.')
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/01 \/ THE OPENING SCENE|Your next great film is waiting\.|Good films\./)
  await expect(page.getByLabel('Email address')).toBeVisible()
  await expect(page.getByLabel('Password', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled()
  const layout = await page.evaluate(() => {
    const quote = getComputedStyle(document.querySelector('.auth-quote'))
    const description = getComputedStyle(document.querySelector('.auth-description'))
    return { overflow: document.documentElement.scrollWidth > innerWidth, font: quote.fontFamily,
      descriptionFont: description.fontFamily, lines: document.querySelector('.auth-quote').clientHeight / parseFloat(quote.lineHeight),
      quoteSize: parseFloat(quote.fontSize), descriptionSize: parseFloat(description.fontSize) }
  })
  expect(layout.overflow).toBe(false); expect(layout.font).toBe(layout.descriptionFont)
  expect(layout.quoteSize).toBeGreaterThan(layout.descriptionSize)
  const palette = await page.evaluate(() => ({ bg: getComputedStyle(document.body).backgroundColor,
    accent: getComputedStyle(document.querySelector('.auth-quote em')).color,
    button: getComputedStyle(document.querySelector('.auth-submit')).backgroundColor,
    ink: getComputedStyle(document.querySelector('.auth-submit')).color }))
  expect(contrast(palette.accent, palette.bg)).toBeGreaterThanOrEqual(4.5)
  expect(contrast(palette.ink, palette.button)).toBeGreaterThanOrEqual(4.5)
  if (width >= 1024) expect(layout.lines).toBeLessThan(1.2)
  await page.keyboard.press('Tab'); await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog', { name: 'Website theme' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Change website theme' })).toBeFocused()
})

test('all existing palettes update both panels, persist across product navigation and preserve typed credentials', async ({ page, context }) => {
  await page.goto(login); await page.getByLabel('Email address').fill('offline@example.invalid')
  await page.getByLabel('Password', { exact: true }).fill('synthetic-only')
  const before = await page.locator('.auth-card').evaluate(e => getComputedStyle(e).backgroundColor)
  await page.getByRole('button', { name: 'Change website theme' }).click()
  for (const name of ['Forest & wine', 'Midnight & copper', 'Aubergine & olive', 'Pine, petrol & midnight', 'Midnight, wine & olive', 'Grayscale']) {
    await page.getByRole('radio', { name, exact: true }).check()
    expect(await page.locator('.auth-card').evaluate(e => getComputedStyle(e).backgroundColor)).not.toBe(before)
    expect(await page.locator('.auth-quote em').evaluate(e => getComputedStyle(e).color)).not.toBe('rgb(189, 133, 110)')
  }
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(page.getByLabel('Email address')).toHaveValue('offline@example.invalid')
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('synthetic-only')
  await page.reload(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'grayscale')
  await page.goto('/'); await expect(page.locator('html')).toHaveAttribute('data-theme', 'grayscale')
  const other = await context.newPage(); await other.goto(login)
  await other.getByRole('button', { name: 'Change website theme' }).click()
  await other.getByRole('radio', { name: 'Forest & wine', exact: true }).check()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'forest-wine')
  await other.close(); await page.goto('/browser/account-demo.html')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'forest-wine')
  await expect(page.getByRole('heading', { name: 'Make yourself at home.' })).toBeVisible()
})

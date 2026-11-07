import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { THEMES, THEME_KEY } from '../src/themes.js'

const shots = resolve(process.env.MOVELLE_SCREENSHOT_DIR || '../docs/screenshots/movelle', 'themes')
const picker = page => page.getByRole('button', { name: 'Change color theme' })
const dialog = page => page.getByRole('dialog', { name: 'Website theme' })
async function capture(page, name) {
  await mkdir(shots, { recursive: true })
  await page.evaluate(() => document.fonts.ready)
  await page.mouse.move(0, 0)
  await page.screenshot({ path: resolve(shots, `${name}.png`), animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}

test('all palettes preview, persist, sync across tabs and preserve navigation', async ({ page, context }) => {
  await page.goto('/')
  await expect(page.locator('.featured-film')).toBeVisible()
  await expect(page.locator('.movie-cover img').first()).toBeVisible()
  await page.waitForFunction(() => [...document.images].filter(image => {
    const bounds = image.getBoundingClientRect()
    return bounds.width > 0 && bounds.top < innerHeight && bounds.bottom > 0 && bounds.left < innerWidth && bounds.right > 0
  }).every(image => image.complete))
  for (const theme of THEMES) {
    await picker(page).click()
    await expect(dialog(page).getByRole('radio')).toHaveCount(7)
    await page.getByRole('radio', { name: theme.name, exact: true }).check()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme.id)
    await dialog(page).getByRole('button', { name: 'Done', exact: true }).click()
    await expect(picker(page)).toBeFocused()
    await capture(page, `${theme.id}-1440`)
  }
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'grayscale')
  const grayscale = await page.locator('.app-shell').evaluate(element => ({
    color: getComputedStyle(element).color,
    backdrop: getComputedStyle(element).backgroundImage,
  }))
  expect(grayscale.color).toBe('rgb(236, 236, 236)')
  expect(grayscale.backdrop).toContain('rgb(17, 17, 17)')
  expect(grayscale.backdrop).toContain('rgb(39, 39, 39)')
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'For you', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-view', 'for-you')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'grayscale')
  await picker(page).click()
  await expect(page.getByRole('radio', { name: 'Grayscale', exact: true })).toBeChecked()
  await capture(page, 'picker-1440')
  await page.keyboard.press('Escape')
  await expect(picker(page)).toBeFocused()
  const other = await context.newPage()
  await other.goto('/')
  await expect(other.locator('html')).toHaveAttribute('data-theme', 'grayscale')
  await picker(page).click()
  await page.getByRole('radio', { name: 'Forest & wine', exact: true }).check()
  await expect(other.locator('html')).toHaveAttribute('data-theme', 'forest-wine')
  await other.close()
})

test('mobile picker fits, supports keyboard selection and reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.locator('.featured-film')).toBeVisible()
  await picker(page).click()
  await page.getByRole('radio', { name: 'Grayscale', exact: true }).check()
  await expect(dialog(page)).toBeVisible()
  const bounds = await dialog(page).boundingBox()
  expect(bounds.x).toBeGreaterThanOrEqual(0)
  expect(bounds.y).toBeGreaterThanOrEqual(0)
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(844)
  expect(await dialog(page).evaluate(element => getComputedStyle(element).transitionDuration)).toBe('0s')
  await dialog(page).evaluate(element => { element.scrollTop = 0 })
  await capture(page, 'picker-390')
  await page.keyboard.press('ArrowUp')
  await expect(page.getByRole('radio', { name: 'Midnight, wine & olive', exact: true })).toBeChecked()
  for (let index = 0; index < 12; index++) {
    await page.keyboard.press('Tab')
    expect(await dialog(page).evaluate(element => element.contains(document.activeElement))).toBe(true)
  }
  await page.getByRole('radio', { name: 'Grayscale', exact: true }).check()
  await dialog(page).getByRole('button', { name: 'Done', exact: true }).click()
  await capture(page, 'grayscale-390')
  await page.getByRole('button', { name: 'Navigation menu', exact: true }).click()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Groups', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-view', 'groups')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'grayscale')
  await page.setViewportSize({ width: 768, height: 1024 })
  await picker(page).click()
  await capture(page, 'picker-768')
})

test('blocked storage still applies the chosen theme and explains persistence', async ({ page }) => {
  await page.addInitScript(key => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function (name, value) {
      if (name === key) throw new DOMException('Storage unavailable', 'QuotaExceededError')
      return original.call(this, name, value)
    }
  }, THEME_KEY)
  await page.goto('/')
  await picker(page).click()
  await page.getByRole('radio', { name: 'Midnight & copper', exact: true }).check()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'midnight-copper')
  await expect(dialog(page).getByRole('status')).toHaveText('Applied for this visit. Browser storage is unavailable.')
})

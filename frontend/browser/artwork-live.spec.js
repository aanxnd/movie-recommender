import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

test('live missing-poster titles render cached Trakt images and a verified series poster', async ({ page }) => {
  test.skip(!process.env.TRAKT_CLIENT_ID || !process.env.FANART_API_KEY, 'Live provider credentials are optional')
  const shots = resolve(process.env.MOVELLE_SCREENSHOT_DIR || '../.pytest-tmp/artwork-live-screenshots')
  await mkdir(shots, { recursive: true })
  await page.goto('/')
  // Load offscreen images for the full-page QA capture; normal application images stay lazy.
  await page.waitForFunction(() => document.querySelectorAll('.shelf-list .movie-card').length >= 24)
  await expect.poll(async () => {
    await page.locator('.movie-cover img').evaluateAll(images => images.forEach(image => { image.loading = 'eager' }))
    return page.locator('.movie-cover[data-artwork="loading"]').count()
  }, { timeout: 30000 }).toBe(0)
  await page.screenshot({ path: resolve(shots, 'discover-settled-1440.png'), fullPage: true })
  for (const [title, id, cached] of [['Paris Is Burning', 1192, true], ['Harlan County', 26366, true], ['Band of Brothers', 170705, false]]) {
    const search = page.getByRole('searchbox', { name: 'Movie title' })
    await search.fill(title)
    await search.press('Enter')
    const card = page.locator(`#library .movie-card[data-movie-id="${id}"]`)
    await expect(card.locator('.movie-cover')).toHaveAttribute('data-artwork', 'loaded', { timeout: 30000 })
    await expect.poll(() => card.locator('img').evaluate(image => image.naturalWidth)).toBeGreaterThan(0)
    if (cached) await expect(card.locator('img')).toHaveAttribute('src', new RegExp(`/api/movies/artwork-image/${id}/poster$`))
    for (const [width, height] of [[1440, 900], [390, 844]]) {
      await page.setViewportSize({ width, height })
      await page.screenshot({ path: resolve(shots, `live-${id}-${width}.png`), fullPage: true })
    }
    await page.setViewportSize({ width: 1440, height: 900 })
  }
})

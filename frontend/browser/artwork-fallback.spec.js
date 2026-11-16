import { test, expect } from '@playwright/test'

import { artworkCandidates as candidates } from './artwork-fixture.js'

test('image failures advance through Fanart poster, cached Trakt poster, then a correctly labeled Fanart background', async ({ page }) => {
  const requests = await candidates(page, 'background')
  const card = page.locator('.shelf-list .movie-card').first()
  await expect(card.locator('.movie-cover')).toHaveAttribute('data-artwork', 'loaded')
  await expect(card.locator('.movie-cover')).toHaveAttribute('data-kind', 'background')
  await expect(card.getByText('Film still', { exact: true })).toBeVisible()
  await expect(card.locator('img')).toHaveAttribute('alt', / background$/)
  const id = await card.getAttribute('data-movie-id')
  const paths = requests.filter(url => url.includes(`-${id}.jpg`) || url.includes(`/${id}/poster`))
  expect(paths.findIndex(url => url.includes('test-poster'))).toBeLessThan(paths.findIndex(url => url.includes('/poster')))
  expect(paths.findIndex(url => url.includes('/poster'))).toBeLessThan(paths.findIndex(url => url.includes('test-background')))
  await card.getByRole('button').click()
  await expect(page.getByRole('dialog').getByText('Background copyright:', { exact: false }).first()).toBeVisible()
})

test('cached Trakt poster renders without hotlinking the Trakt CDN and is credited to Trakt', async ({ page }) => {
  const hosts = new Set()
  page.on('request', request => hosts.add(new URL(request.url()).hostname))
  await candidates(page, 'trakt')
  const card = page.locator('.shelf-list .movie-card').first()
  await expect(card.locator('.movie-cover')).toHaveAttribute('data-artwork', 'loaded')
  await expect(card.locator('img')).toHaveAttribute('src', /\/api\/movies\/artwork-image\/\d+\/poster$/)
  await card.getByRole('button').click()
  const details = page.getByRole('dialog')
  await expect(details.getByText('Poster copyright: Unknown.', { exact: false })).toBeVisible()
  await expect(details.locator('a[href="https://fanart.tv/"]')).toHaveCount(0)
  expect([...hosts].some(host => host.endsWith('.trakt.tv'))).toBe(false)
})

test('every image failure settles to an honest placeholder', async ({ page }) => {
  await candidates(page, 'missing')
  const card = page.locator('.shelf-list .movie-card').first()
  await expect(card.locator('.movie-cover')).toHaveAttribute('data-artwork', 'unavailable')
  await expect(card.getByText('Poster unavailable', { exact: true })).toBeVisible()
  await expect(card.locator('img')).toHaveCount(0)
  await expect(page.locator('.feature-backdrop')).toHaveCount(0)
})

test('a cached Trakt background is the fourth cover choice and remains labeled as a background', async ({ page }) => {
  await candidates(page, 'trakt-background')
  const card = page.locator('.shelf-list .movie-card').first()
  await expect(card.locator('.movie-cover')).toHaveAttribute('data-artwork', 'loaded')
  await expect(card.locator('img')).toHaveAttribute('src', /\/api\/movies\/artwork-image\/\d+\/backdrop$/)
  await expect(card.locator('img')).toHaveAttribute('alt', / background$/)
  await expect(card.getByText('Film still', { exact: true })).toBeVisible()
})

test('new catalogue rows share one artwork batch pump instead of racing the provider limit', async ({ page }) => {
  let active = 0, maximum = 0, completed = 0
  await page.route('**/api/movies/artwork', async route => {
    active += 1
    maximum = Math.max(active, maximum)
    await new Promise(resolve => setTimeout(resolve, 150))
    await route.fulfill({ json: { provider: 'trakt+fanart.tv', configured: true, items: [] } })
    active -= 1
    completed += 1
  })
  await page.goto('/')
  await expect.poll(() => completed).toBeGreaterThanOrEqual(3)
  expect(maximum).toBe(1)
})

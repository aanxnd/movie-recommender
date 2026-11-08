import { test, expect } from '@playwright/test'

// Synthetic test pixel; never presented as real film artwork outside this intercepted test.
const pixel = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3ioAAAAASUVORK5CYII=', 'base64')

async function candidates(page, mode) {
  await page.route('**/api/movies/artwork', async route => {
    const { movie_ids } = route.request().postDataJSON()
    const items = movie_ids.map(movie_id => {
      const choice = (url, provider, kind) => ({ url, provider, kind, credit: { provider, kind, copyright: 'Unknown' } })
      const cover_candidates = [
        choice(`https://assets.fanart.tv/fanart/test-poster-${movie_id}.jpg`, 'fanart.tv', 'poster'),
        choice(`/movies/artwork-image/${movie_id}/poster`, 'trakt', 'poster'),
        choice(`https://assets.fanart.tv/fanart/test-background-${movie_id}.jpg`, 'fanart.tv', 'background'),
        choice(`/movies/artwork-image/${movie_id}/backdrop`, 'trakt', 'background'),
      ]
      return { movie_id, cover_candidates, backdrop_candidates: cover_candidates.slice(2), source: 'trakt+fanart.tv' }
    })
    await route.fulfill({ json: { provider: 'trakt+fanart.tv', configured: true, items } })
  })
  const requests = []
  await page.route(/\/(?:api\/movies\/artwork-image\/\d+\/(?:poster|backdrop)|(?:bigpreview|fanart|preview)\/test-(?:poster|background)-\d+\.jpg)$/, async route => {
    const url = route.request().url()
    requests.push(url)
    const success = mode === 'background' ? url.includes('test-background') : mode === 'trakt' ? url.endsWith('/poster') : mode === 'trakt-background' ? url.endsWith('/backdrop') : false
    await route.fulfill(success ? { contentType: 'image/png', body: pixel } : { status: 404, body: 'Unavailable' })
  })
  await page.goto('/')
  return requests
}

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

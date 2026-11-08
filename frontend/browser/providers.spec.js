import { test, expect } from '@playwright/test'

test('provider credits and rendered images use Fanart and retain real artwork credits', async ({ page }) => {
  const hosts = new Set()
  page.on('request', request => hosts.add(new URL(request.url()).hostname))
  await page.goto('/')
  const first = page.locator('.shelf-list .movie-card').first()
  await expect(first.locator('img')).toBeVisible()
  await expect.poll(() => first.locator('img').evaluate(img => img.naturalWidth)).toBeGreaterThan(0)
  await expect(first.locator('img')).toHaveAttribute('src', /^https:\/\/assets\.fanart\.tv\/bigpreview\//)
  await first.getByRole('button').click()
  const details = page.getByRole('dialog')
  await expect(details.getByText('Poster copyright:', { exact: false })).toBeVisible()
  await expect(details.locator('a[href="https://fanart.tv/"]')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('footer')).toContainText('Movelle uses Trakt but is not endorsed or certified by Trakt.')
  expect([...hosts].some(host => /tmdb|themoviedb/.test(host))).toBe(false)
})

test('profile creation and recovery remain available without artwork-key controls or artwork credentials', async ({ page }) => {
  const artworkRequests = []
  await page.route('**/api/movies/artwork', async route => {
    artworkRequests.push({ body: route.request().postDataJSON(), authorization: route.request().headers().authorization })
    await route.continue()
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Your profile', exact: true }).click()
  const dialog = page.locator('#profile-dialog')
  const noArtworkSettings = async () => {
    await expect(dialog.getByRole('heading', { name: 'Artwork access', exact: true })).toHaveCount(0)
    await expect(dialog.locator('#fanart-personal-key, .fanart-settings')).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: /personal key/i })).toHaveCount(0)
    await expect(dialog).not.toContainText('Using standard project access.')
  }
  await noArtworkSettings()
  await page.getByRole('button', { name: 'Create new user', exact: true }).click()
  await expect(page.locator('#profile-recovery-code')).toBeVisible()
  await expect(page.locator('#profile-recovery-code')).toHaveAttribute('type', 'password')
  await noArtworkSettings()
  await page.reload()
  await page.getByRole('button', { name: 'Your profile', exact: true }).click()
  await expect(page.locator('#profile-recovery-code')).toBeVisible()
  await noArtworkSettings()
  await expect.poll(() => artworkRequests.length).toBeGreaterThan(0)
  expect(artworkRequests.every(row => !('personal_key' in row.body) && !row.authorization)).toBe(true)
})


test('a previous backend provider response becomes an honest fallback during a coordinated rollout', async ({ page }) => {
  await page.route('**/api/movies/artwork', async route => {
    const body = route.request().postDataJSON()
    await route.fulfill({ json: { provider: 'retired-provider', configured: true, items: body.movie_ids.map(movie_id => ({ movie_id, poster_path: '/old-poster.jpg', backdrop_path: '/old-backdrop.jpg', overview: 'Retired provider text' })) } })
  })
  await page.goto('/')
  const first = page.locator('.shelf-list .movie-card').first()
  await expect(first.locator('.movie-cover')).toHaveAttribute('data-artwork', 'unavailable')
  await expect(first.getByText('Poster unavailable', { exact: true })).toBeVisible()
  await expect(page.getByText('Retired provider text', { exact: true })).toHaveCount(0)
  await expect(page.locator('.feature-backdrop')).toHaveCount(0)
})

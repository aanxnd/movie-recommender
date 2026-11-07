import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const shots = resolve(process.env.MOVELLE_SCREENSHOT_DIR || '../docs/screenshots/movelle')
const nav = (page, name) =>
  page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name, exact: true })
async function navigate(page, name) {
  const target = nav(page, name)
  if (!(await target.isVisible()))
    await page
      .getByRole('button', { name: 'Navigation menu', exact: true })
      .click()
  await target.click()
}
const viewport = (width) => ({
  width,
  height: { 1440: 900, 1280: 800, 1024: 768, 768: 1024, 390: 844 }[width],
})
const recs = (page) => page.locator('.recommendations-section')

async function capture(page, name) {
  await mkdir(shots, { recursive: true })
  await page.evaluate(() => document.fonts.ready)
  if (!(await page.getByRole('dialog').isVisible())) {
    await page.evaluate(async () => {
      const end = Math.min(document.documentElement.scrollHeight, 7000)
      for (let y = 0; y < end; y += innerHeight * 0.75) {
        window.scrollTo({ top: y, behavior: 'instant' })
        await new Promise((resolve) => setTimeout(resolve, 65))
      }
      window.scrollTo({ top: 0, behavior: 'instant' })
    })
  }
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll('.page-view:not([hidden]) .movie-cover')]
        .filter((e) => {
          const r = e.getBoundingClientRect(),
            shelf = e.closest('.shelf-list')?.getBoundingClientRect()
          return (
            r.top < innerHeight &&
            r.bottom > 0 &&
            r.left < Math.min(innerWidth, shelf?.right ?? innerWidth) &&
            r.right > Math.max(0, shelf?.left ?? 0)
          )
        })
        .every((e) => e.dataset.artwork !== 'loading'),
    undefined,
    { timeout: 20000 },
  )
  await page.evaluate(async () => {
    await Promise.all(
      [...document.images]
        .filter((i) => {
          const r = i.getBoundingClientRect(),
            shelf = i.closest('.shelf-list')?.getBoundingClientRect()
          return (
            r.width > 0 &&
            r.top < innerHeight &&
            r.bottom > 0 &&
            r.left < Math.min(innerWidth, shelf?.right ?? innerWidth) &&
            r.right > Math.max(0, shelf?.left ?? 0)
          )
        })
        .map((i) => i.decode().catch(() => {})),
    )
  })
  await page.waitForFunction(() => scrollY === 0)
  await page.mouse.move(0, 0)
  await page.screenshot({
    path: resolve(shots, `${name}.png`),
    fullPage: !(await page.getByRole('dialog').isVisible()),
    animations: 'disabled',
    maskColor: '#293b31',
    mask: [
      page.locator(
        'input[type="password"], #profile-recovery-code, #group-invitation, #user-id',
      ),
    ],
  })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
}

// Avoid embedding private local test credentials in Playwright action logs.
async function enterSecret(field, value) {
  await field.evaluate((element, secret) => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      'value',
    ).set.call(element, secret)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  }, value)
}

async function createProfile(page) {
  await page.getByRole('button', { name: 'Your profile', exact: true }).click()
  await page
    .getByRole('button', { name: 'Create new user', exact: true })
    .click()
  await expect(page.locator('#profile-recovery-code')).toBeVisible()
  await expect(page.locator('#profile-recovery-code')).toHaveAttribute(
    'type',
    'password',
  )
  return page.locator('#profile-recovery-code').inputValue()
}

async function requestPicks(page, path) {
  const response = page.waitForResponse(
    (r) => r.url().includes(path) && r.request().method() !== 'OPTIONS',
  )
  await recs(page)
    .getByRole('button', { name: 'Get recommendations', exact: true })
    .click()
  const reply = await response
  expect(reply.status()).toBe(200)
  const data = await reply.json()
  await expect(recs(page).locator('.movie-card')).toHaveCount(data.length)
  const ids = await recs(page)
    .locator('.movie-card')
    .evaluateAll((cards) => cards.map((card) => Number(card.dataset.movieId)))
  expect(ids).toEqual(data.map((movie) => movie.movie_id))
  return data
}

// Keep the real application's admission quotas unchanged. The responsive/account
// batch is intentionally followed by a fresh minute window for social/error QA.
test.beforeEach(async ({}, info) => {
  if (
    info.title.startsWith('private profile') ||
    info.title.startsWith('two real profiles') ||
    info.title.startsWith('populated collaborative')
  ) {
    info.setTimeout(120000)
    await new Promise((resolve) =>
      setTimeout(resolve, 60050 - (Date.now() % 60000)),
    )
  }
})

for (const width of [1440, 1280, 1024, 768, 390]) {
  test(`all main screens fit and remain navigable at ${width}px`, async ({
    page,
  }) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.setViewportSize(viewport(width))
    await page.goto('/')
    await expect(page.locator('.featured-film')).toHaveCount(1)
    await capture(page, `discover-${width}`)
    for (const [name, heading] of [
      ['My ratings', 'Your ratings'],
      ['For you', 'Your recommendations'],
      ['Groups', 'Group recommendations'],
      ['Discover', 'Discover films'],
    ]) {
      await navigate(page, name)
      await expect(
        page.getByRole('heading', { level: 1, name: heading, exact: true }),
      ).toBeVisible()
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true)
    }
    await page
      .getByRole('button', { name: 'Your profile', exact: true })
      .click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await capture(page, `profile-${width}`)
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).not.toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Your profile', exact: true }),
    ).toBeFocused()
    expect(errors).toEqual([])
  })
}

test('private profile, recovery, exact rating persistence, search and recommendation filters', async ({
  page,
  context,
  browser,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.goto('/')
  const code = await createProfile(page)
  await page
    .getByRole('button', { name: 'Show recovery code', exact: true })
    .click()
  await expect(page.locator('#profile-recovery-code')).toHaveAttribute(
    'type',
    'text',
  )
  await page
    .getByRole('button', { name: 'Copy recovery code', exact: true })
    .click()
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(
    copied === code,
    'the clipboard receives the complete local recovery code',
  ).toBe(true)
  await page
    .getByRole('button', { name: 'Hide recovery code', exact: true })
    .click()
  await capture(page, 'profile-created')
  for (const width of [1280, 1024, 768, 390]) {
    await page.setViewportSize(viewport(width))
    await capture(page, `profile-created-${width}`)
  }
  await page.setViewportSize(viewport(1440))
  await page.keyboard.press('Escape')
  await page.keyboard.press('Control+k')
  await expect(
    page.getByRole('searchbox', { name: 'Movie title' }),
  ).toBeFocused()
  await page.getByRole('searchbox', { name: 'Movie title' }).fill('Matrix')
  await page
    .locator('.search-form')
    .getByRole('button', { name: 'Search', exact: true })
    .click()
  const film = page.locator('#library .movie-card').filter({
    has: page.getByRole('heading', { name: 'The Matrix', exact: true }),
  })
  await expect(film).toBeVisible()
  await film.getByRole('combobox').selectOption('4.5')
  await film.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(film.getByText('Saved: 4.5 / 5', { exact: true })).toBeVisible()
  await capture(page, 'search-and-rating')
  await navigate(page, 'My ratings')
  await expect(page.locator('.collection-list .movie-card')).toHaveCount(1)
  await page.locator('.collection-list select').selectOption('3.5')
  await page
    .locator('.collection-list')
    .getByRole('button', { name: 'Update', exact: true })
    .click()
  await expect(
    page
      .locator('.collection-list')
      .getByText('Saved: 3.5 / 5', { exact: true }),
  ).toBeVisible()
  await capture(page, 'ratings-desktop')
  for (const width of [1280, 1024, 768]) {
    await page.setViewportSize(viewport(width))
    await capture(page, `ratings-${width}`)
  }
  await page.reload()
  await navigate(page, 'My ratings')
  await expect(page.locator('.collection-list select')).toHaveValue('3.5')
  await page.setViewportSize({ width: 390, height: 844 })
  await capture(page, 'ratings-mobile')
  await page.setViewportSize({ width: 1440, height: 900 })
  await navigate(page, 'For you')
  const personal = await requestPicks(page, '/recommendations')
  expect(personal.every((movie) => movie.movie_id !== 2571)).toBe(true)
  await capture(page, 'for-you-cold-start-desktop')
  for (const width of [1280, 1024, 768]) {
    await page.setViewportSize(viewport(width))
    await capture(page, `for-you-cold-start-${width}`)
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await capture(page, 'for-you-cold-start-mobile')
  await recs(page)
    .getByRole('button', { name: 'By genre', exact: true })
    .click()
  await recs(page).getByLabel('Genre', { exact: true }).fill('Sci-Fi')
  await recs(page).getByLabel('Release decade').selectOption('1990')
  const filtered = await requestPicks(page, '/recommendations/genre/')
  expect(filtered.length).toBeGreaterThan(0)
  expect(
    filtered.every(
      (movie) =>
        movie.genres.includes('Sci-Fi') && /\(199\d\)$/.test(movie.title),
    ),
  ).toBe(true)
  await capture(page, 'genre-mobile')
  await recs(page).getByRole('button', { name: 'Popular', exact: true }).click()
  await recs(page).getByLabel('Release decade').selectOption('')
  await requestPicks(page, '/recommendations/popular')

  const other = await browser.newContext()
  try {
    const restored = await other.newPage()
    await restored.goto('http://127.0.0.1:5180/')
    await restored
      .getByRole('button', { name: 'Your profile', exact: true })
      .click()
    await enterSecret(restored.locator('#user-id'), code)
    await restored.getByRole('button', { name: 'Load', exact: true }).click()
    await expect(restored.locator('#profile-recovery-code')).toBeVisible()
    expect(
      (await restored.locator('#profile-recovery-code').inputValue()) === code,
      'recovery restores the original local identity',
    ).toBe(true)
    await restored.keyboard.press('Escape')
    await navigate(restored, 'My ratings')
    await expect(restored.locator('.collection-list select')).toHaveValue('3.5')
  } finally {
    await other.close()
  }
})

test('two real profiles share a temporary invitation, receive group picks, revoke and expire invitations', async ({
  page,
  browser,
}) => {
  await page.goto('/')
  await createProfile(page)
  await page.keyboard.press('Escape')
  const other = await browser.newContext()
  try {
    const friend = await other.newPage()
    await friend.goto('http://127.0.0.1:5180/')
    await createProfile(friend)
    await friend
      .getByRole('button', {
        name: 'Create 10-minute group invitation',
        exact: true,
      })
      .click()
    const invite = friend.getByLabel('Group invitation', { exact: true })
    await expect(invite).toBeVisible()
    await expect(invite).toHaveAttribute('type', 'password')
    const code = await invite.inputValue()
    await capture(friend, 'profile-invitation')
    await navigate(page, 'Groups')
    await enterSecret(
      page.getByLabel('Group invitation codes from other members'),
      code,
    )
    const picks = await requestPicks(page, '/recommendations/group')
    expect(picks.length).toBeGreaterThan(0)
    await capture(page, 'groups-desktop')
    for (const width of [1280, 1024, 768]) {
      await page.setViewportSize(viewport(width))
      await capture(page, `groups-${width}`)
    }
    await page.setViewportSize({ width: 390, height: 844 })
    await capture(page, 'groups-mobile')
    await friend
      .getByRole('button', { name: 'Revoke invitation', exact: true })
      .click()
    await expect(
      friend.getByText('Invitation revoked.', { exact: true }),
    ).toBeVisible()
    await recs(page)
      .getByRole('button', { name: 'Get recommendations', exact: true })
      .click()
    await expect(recs(page).getByRole('alert')).toContainText(/invitation/i)
    await capture(page, 'group-invitation-error')
    await friend.clock.install()
    await friend
      .getByRole('button', {
        name: 'Create 10-minute group invitation',
        exact: true,
      })
      .click()
    await expect(invite).toBeVisible()
    await friend.clock.fastForward(601000)
    await expect(invite).toHaveCount(0)
    await expect(friend.getByText(/This invitation expired/)).toBeVisible()
  } finally {
    await other.close()
  }
})

test('network failure has a useful retry, honest loading state, empty search and reduced motion', async ({
  page,
}) => {
  let offline = true
  await page.route('**/api/movies/decades', (route) =>
    offline ? route.abort() : route.continue(),
  )
  await page.goto('/')
  await navigate(page, 'For you')
  await expect(recs(page).getByRole('alert')).toContainText(
    'Could not load available decades',
  )
  await expect(recs(page).getByRole('alert')).not.toContainText(
    'save may have completed',
  )
  await capture(page, 'api-error')
  offline = false
  await page
    .getByRole('button', { name: 'Retry loading decades', exact: true })
    .click()
  await expect(recs(page).getByRole('alert')).toHaveCount(0)
  await expect(recs(page).getByLabel('Release decade')).toBeEnabled()
  await recs(page).getByRole('button', { name: 'Popular', exact: true }).click()
  let release
  const gate = new Promise((resolve) => {
    release = resolve
  })
  await page.route('**/api/recommendations/popular', async (route) => {
    await gate
    await route.continue()
  })
  const pending = page
    .getByRole('button', { name: 'Get recommendations', exact: true })
    .click()
  await expect(
    recs(page).getByRole('status', { name: 'Finding recommendations…' }),
  ).toBeVisible()
  await capture(page, 'recommendations-loading')
  release()
  await pending
  await expect(recs(page).locator('.movie-card').first()).toBeVisible()
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await navigate(page, 'Discover')
  const duration = await page
    .locator('.page-view:visible')
    .evaluate((element) => getComputedStyle(element).animationDuration)
  expect(parseFloat(duration)).toBeLessThanOrEqual(0.001)
  await page
    .getByRole('searchbox', { name: 'Movie title' })
    .fill('zzzz-no-film-matches-zzzz')
  await page
    .locator('.search-form')
    .getByRole('button', { name: 'Search', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: 'No matching films', exact: true }),
  ).toBeVisible()
  await capture(page, 'search-empty')
  await page.getByRole('button', { name: 'Your profile', exact: true }).click()
  for (let index = 0; index < 10; index++) {
    await page.keyboard.press('Tab')
    expect(
      await page
        .getByRole('dialog')
        .evaluate((dialog) => dialog.contains(document.activeElement)),
    ).toBe(true)
  }
  expect(
    await page.evaluate(
      () => getComputedStyle(document.activeElement).outlineStyle,
    ),
  ).toBe('solid')
  await page.keyboard.press('Shift+Tab')
  expect(
    await page
      .getByRole('dialog')
      .evaluate((dialog) => dialog.contains(document.activeElement)),
  ).toBe(true)
  await page.keyboard.press('Escape')
  await page
    .getByRole('button', { name: 'Clear movie search', exact: true })
    .click()
  await expect(page.locator('.featured-film')).toBeVisible()
  await expect
    .poll(() =>
      page
        .locator('.cover-button')
        .first()
        .evaluate(
          (element) => getComputedStyle(element, '::after').transitionDuration,
        ),
    )
    .toBe('0s')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.locator('.cover-button').first().hover()
  await expect
    .poll(() =>
      page
        .locator('.cover-button')
        .first()
        .evaluate((element) => getComputedStyle(element, '::after').opacity),
    )
    .toBe('1')
})

test('real posters and film details keep canonical IDs; image failure uses an honest fallback', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page.locator('.feature-backdrop')).toBeVisible()
  await expect
    .poll(() =>
      page.locator('.feature-backdrop').evaluate((image) => image.naturalWidth),
    )
    .toBeGreaterThan(0)
  const first = page.locator('.shelf-list .movie-card').first()
  await expect
    .poll(() => first.locator('img').evaluate((image) => image.naturalWidth))
    .toBeGreaterThan(0)
  await first.getByRole('button').click()
  await expect(
    page
      .getByRole('dialog')
      .getByRole('heading', { name: 'The Shawshank Redemption', exact: true }),
  ).toBeVisible()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Find and rate this film', exact: true })
    .click()
  await expect(
    page.getByRole('searchbox', { name: 'Movie title' }),
  ).toHaveValue('Shawshank Redemption, The (1994)')
  await expect(page.locator('#library .movie-card')).toHaveAttribute(
    'data-movie-id',
    '318',
  )
  await page.route('https://image.tmdb.org/**', (route) => route.abort())
  await page.reload()
  await expect(
    page.locator('.shelf-list .movie-card').first().locator('.movie-cover'),
  ).toHaveAttribute('data-artwork', 'unavailable')
  await expect(
    page
      .locator('.shelf-list .movie-card')
      .first()
      .getByText('Poster unavailable', { exact: true }),
  ).toBeVisible()
  await capture(page, 'poster-fallback')
})

test('populated collaborative filtering and collection remain correct at all five sizes', async ({
  page,
}) => {
  await page.goto('/')
  await createProfile(page)
  await page.keyboard.press('Escape')
  // Seed only this newly created isolated QA profile through the real API.
  const statuses = await page.evaluate(async () => {
    const identity = JSON.parse(localStorage.getItem('movelle.identity.v1'))
    const ratings = [
      [1, 3.5],
      [260, 4.5],
      [318, 5],
      [593, 4],
      [858, 4.5],
      [1196, 4],
      [2571, 4.5],
      [296, 4.5],
    ]
    const results = []
    for (const [mid, rating] of ratings) {
      const response = await fetch(`/api/users/${identity.id}/ratings/${mid}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${identity.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rating }),
        signal: AbortSignal.timeout(5000),
      })
      results.push(response.status)
    }
    return results
  })
  expect(statuses).toEqual(Array(8).fill(200))
  await page.reload()
  await navigate(page, 'My ratings')
  await expect(page.locator('.collection-list .movie-card')).toHaveCount(8)
  for (const width of [1440, 1280, 1024, 768, 390]) {
    await page.setViewportSize(viewport(width))
    await capture(
      page,
      width === 1440
        ? 'ratings-desktop'
        : width === 390
          ? 'ratings-mobile'
          : `ratings-${width}`,
    )
  }
  await navigate(page, 'For you')
  const picks = await requestPicks(page, '/recommendations')
  expect(
    picks.some(
      (movie) =>
        movie.method === 'collaborative_filtering' && movie.confidence > 0,
    ),
  ).toBe(true)
  expect(
    picks.every(
      (movie) =>
        ![1, 260, 318, 593, 858, 1196, 2571, 296].includes(movie.movie_id),
    ),
  ).toBe(true)
  for (const width of [1440, 1280, 1024, 768, 390]) {
    await page.setViewportSize(viewport(width))
    await capture(
      page,
      width === 1440
        ? 'for-you-desktop'
        : width === 390
          ? 'for-you-mobile'
          : `for-you-${width}`,
    )
  }
})

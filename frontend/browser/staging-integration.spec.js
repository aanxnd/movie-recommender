import { test, expect } from '@playwright/test'

const provider = 'http://127.0.0.1:19002', project = 'https://aaaaaaaaaaaaaaaaaaaa.supabase.co'
const nav = (page, label) => page.getByRole('navigation', { name: 'Staging account navigation' }).getByRole('button', { name: label, exact: true }).click()
const state = async request => (await request.get(provider+'/_fixture/state')).json()
test.beforeEach(async ({ page, request }) => {
  await request.post(provider+'/_fixture/reset')
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url())
    if (url.origin === project) {
      const headers = { 'access-control-allow-origin': 'http://127.0.0.1:5173',
        'access-control-allow-headers': req.headers()['access-control-request-headers'] ?? 'authorization,apikey,content-type,x-client-info,x-supabase-api-version',
        'access-control-allow-methods': 'GET,POST,PUT,DELETE,OPTIONS' }
      if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
      const response = await route.fetch({ url: provider+url.pathname+url.search, maxRedirects: 0 })
      return route.fulfill({ response, headers: { ...response.headers(), ...headers } })
    }
    if (url.origin === 'http://127.0.0.1:5173') return route.continue()
    return route.abort() // No real hosted provider or customer account can be contacted.
  })
  await page.goto('/')
  await expect(page.locator('.staging-bar')).toContainText('Session: unauthenticated')
})

async function login(page, email = 'alice@example.invalid', password = 'fixture-password') {
  await nav(page, 'Sign in')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.locator('form').getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.locator('.staging-bar')).toContainText('Session: authenticated')
}
async function mfa(page, request) {
  await nav(page, 'MFA challenge')
  await expect(page.getByLabel('Authenticator', { exact: true })).toBeVisible()
  const code = (await (await request.get(provider+'/_fixture/otp')).json()).code
  await page.getByLabel('Six-digit authenticator code').fill(code)
  await page.getByRole('button', { name: 'Verify authenticator', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'passed native MFA verification' })).toBeVisible()
}
async function provision(page, name = 'MovieFan') {
  await nav(page, 'Profile setup')
  await page.getByLabel('Profile username').fill(name)
  await page.getByRole('button', { name: 'Create my profile' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Your profile is ready' })).toBeVisible()
}

for (const width of [1440, 390]) test('real movie/profile/rating roundtrip and refresh: '+width, async ({ page, request }) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.keyboard.press('Tab')
  await expect(page.getByRole('navigation', { name: 'Staging account navigation' }).getByRole('button', { name: 'Movies', exact: true })).toBeFocused()
  expect((await state(request)).users).toBe(0)
  await login(page); await mfa(page, request); await provision(page)
  await nav(page, 'Movies')
  await page.getByPlaceholder('Search movie titles…').fill('First')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await page.getByLabel('Rating for First Film').selectOption('4')
  await page.locator('.rating-control').getByRole('button').click()
  await expect.poll(async () => (await state(request)).ratings).toBe(1)
  await page.reload()
  await expect(page.locator('.staging-bar')).toContainText('Session: authenticated')
  await nav(page, 'Movies'); await page.getByRole('button', { name: 'ratings', exact: true }).click()
  await expect(page.locator('#library')).toContainText('First Film')
  await nav(page, 'Settings'); await expect(page.locator('body')).toContainText('Your authorized profile: MovieFan')
  await expect(page.getByRole('button', { name: 'Save username' })).toHaveCount(0)
  await nav(page, 'Refresh session'); await expect(page.locator('.staging-bar')).toContainText('Session: authenticated')
  expect((await state(request)).credentials).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await nav(page, 'Sign out'); await expect(page.locator('.staging-bar')).toContainText('Session: unauthenticated')
  await expect(page.getByText('Your authorized profile: MovieFan')).toHaveCount(0)
})

test('native signup callback, optional profile, first TOTP and authenticated movies', async ({ page, request }) => {
  await nav(page, 'Sign up')
  await page.getByLabel('Email address').fill('new@example.invalid')
  await page.getByLabel('Password', { exact: true }).fill('fixture-password')
  await page.getByLabel('Confirm password', { exact: true }).fill('fixture-password')
  await page.locator('form').getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'If signup can proceed' })).toBeVisible()
  const link = await (await request.get(provider+'/_fixture/link?flow=email/signup')).json()
  await page.goto('/?code='+link.code)
  await expect(page.locator('body')).toContainText('does not establish signup confirmation')
  await expect(page).toHaveURL('http://127.0.0.1:5173/')
  await provision(page, 'FirstFactorFan')
  await nav(page, 'Authenticators'); await expect(page.locator('body')).toContainText('No authenticator is enrolled')
  await page.getByRole('button', { name: 'Add an authenticator', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Add to your authenticator' })).toBeVisible()
  const code = (await (await request.get(provider+'/_fixture/otp')).json()).code
  await page.getByLabel('Six-digit authenticator code').fill(code)
  await page.getByRole('button', { name: 'Verify authenticator', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'passed native MFA verification' })).toBeVisible()
  await nav(page, 'Movies')
  await page.getByPlaceholder('Search movie titles\u2026').fill('First')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await page.getByLabel('Rating for First Film').selectOption('4')
  await page.locator('.rating-control').getByRole('button').click()
  await expect.poll(async () => (await state(request)).ratings).toBe(1)
  expect((await state(request)).users).toBe(1)
  expect((await state(request)).credentials).toBe(0)
  await nav(page, 'Sign out'); await login(page, 'new@example.invalid')
  await nav(page, 'Movies'); await expect(page.locator('body')).toContainText('Personal access requires')
  await mfa(page, request)
  await nav(page, 'Settings'); await expect(page.locator('body')).toContainText('Your authorized profile: FirstFactorFan')
})

test('failed login, wrong/expired signed JWTs, provider outage and account substitution deny', async ({ page, request }) => {
  await nav(page, 'Sign in'); await page.getByLabel('Email address').fill('alice@example.invalid')
  await page.getByLabel('Password', { exact: true }).fill('wrong-password')
  await page.locator('form').getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Check your email and password')
  for (const kind of ['issuer', 'expired']) {
    const token = (await (await request.get(provider+'/_fixture/token?case='+kind)).json()).token
    const response = await request.get('http://127.0.0.1:5173/api/users/me', { headers: { Authorization: 'Bearer '+token } })
    expect(response.status()).toBe(401)
  }
  await login(page); await mfa(page, request); await provision(page)
  await request.post(provider+'/_fixture/outage?enabled=true')
  await nav(page, 'Movies'); await expect(page.locator('body')).toContainText('Personal access requires')
  await request.post(provider+'/_fixture/outage?enabled=false')
  await nav(page, 'Sign out'); await login(page, 'bob@example.invalid'); await mfa(page, request)
  await nav(page, 'Profile setup'); await page.getByLabel('Profile username').fill('MOVIEFAN')
  await page.getByRole('button', { name: 'Create my profile' }).click()
  await expect(page.getByRole('alert')).toContainText('username is unavailable')
  expect((await state(request)).users).toBe(1)
})

test('supported native password recovery uses the one shared callback continuation', async ({ page, request }) => {
  await nav(page, 'Forgot password'); await page.getByLabel('Email address').fill('plain@example.invalid')
  await page.getByRole('button', { name: 'Send recovery link' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'If an account can receive recovery email' })).toBeVisible()
  const link = await (await request.get(provider+'/_fixture/link?flow=recovery')).json()
  await page.goto('/?code='+link.code)
  await expect(page.getByRole('heading', { name: 'Choose a new password.' })).toBeVisible()
  await page.getByLabel('New password', { exact: true }).fill('fixture-new-password')
  await page.getByLabel('Confirm new password', { exact: true }).fill('fixture-new-password')
  await page.getByRole('button', { name: 'Update password' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Password updated' })).toBeVisible()
  await nav(page, 'Sign out'); await login(page, 'plain@example.invalid', 'fixture-new-password')
  expect((await state(request)).users).toBe(0)
})

test('enrolled-account sensitive changes, removal and all-device recovery remain unavailable', async ({ page, request }) => {
  await login(page); await mfa(page, request)
  await nav(page, 'Change password')
  await page.getByLabel('Current password', { exact: true }).fill('fixture-password')
  await page.getByLabel('New password', { exact: true }).fill('fixture-new-password')
  await page.getByLabel('Confirm new password', { exact: true }).fill('fixture-new-password')
  await page.getByRole('button', { name: 'Update password' }).click()
  await expect(page.getByRole('alert')).toContainText('not available in this flow')
  await nav(page, 'Authenticators'); await page.getByRole('button', { name: 'Review removal' }).first().click()
  await expect(page.getByRole('button', { name: 'Removal unavailable' })).toBeDisabled()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await nav(page, 'Lost device'); await page.getByRole('button', { name: 'None of my authenticators is accessible' }).click()
  await expect(page.locator('body')).toContainText('Self-service recovery is unavailable')
})

test('group invitation UI authorizes computation across separate native accounts', async ({ page, request }) => {
  await login(page, 'bob@example.invalid'); await mfa(page, request); await provision(page, 'PeerUser')
  await nav(page, 'Movies'); await page.getByRole('button', { name: 'Create group invitation' }).click()
  const grant = await page.getByLabel('Temporary group invitation').inputValue()
  await nav(page, 'Sign out'); await login(page); await mfa(page, request); await provision(page, 'OwnerUser')
  await nav(page, 'Movies'); await page.getByRole('button', { name: 'groups', exact: true }).click()
  await page.getByLabel('Group invitation codes from other members').fill(grant)
  await page.getByRole('button', { name: 'Get recommendations', exact: true }).click()
  await expect(page.locator('body')).toContainText('First Film')
  expect((await state(request)).users).toBe(2)
  expect((await state(request)).credentials).toBe(0)
})

test('additional authenticator setup verifies and clears its temporary credentials', async ({ page, request }) => {
  await login(page); await mfa(page, request); await nav(page, 'Authenticators')
  await page.getByRole('button', { name: 'Add an authenticator', exact: true }).click()
  await expect(page.locator('body')).toContainText('Setup is not complete')
  await page.getByLabel('Six-digit authenticator code').fill((await (await request.get(provider+'/_fixture/otp')).json()).code)
  await page.getByRole('button', { name: 'Verify authenticator', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'passed native MFA verification' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('JBSWY3DPEHPK3PXP')
})

test('accessible backup authenticator enables only the approved replacement workflow', async ({ page, request }) => {
  await login(page); await nav(page, 'Lost device')
  await expect(page.getByLabel('Accessible authenticator')).toBeVisible()
  await page.getByLabel('Six-digit authenticator code').fill((await (await request.get(provider+'/_fixture/otp')).json()).code)
  await page.getByRole('button', { name: 'Use accessible authenticator', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'alternative authenticator passed' })).toBeVisible()
  await page.getByRole('button', { name: 'Enroll replacement authenticator' }).click()
  await expect(page.locator('body')).toContainText('Replacement setup is not complete')
  await page.getByLabel('Six-digit authenticator code').fill((await (await request.get(provider+'/_fixture/otp')).json()).code)
  await page.getByRole('button', { name: 'Verify replacement', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'replacement authenticator is verified' })).toBeVisible()
})

test('lost write acknowledgement recovers through the actual backend without duplicate submission', async ({ page, request }) => {
  await login(page); await mfa(page, request)
  let posts = 0
  await page.route('**/api/auth/profile', async route => {
    if (route.request().method() !== 'POST') return route.fallback()
    posts++; const response = await route.fetch()
    expect(response.status()).toBe(200)
    await route.abort() // Commit really happened in PostgreSQL; the browser gets no acknowledgement.
  })
  await nav(page, 'Profile setup'); await page.getByLabel('Profile username').fill('Original')
  await page.locator('form').evaluate(form => { form.requestSubmit(); form.requestSubmit() })
  await expect(page.getByRole('status').filter({ hasText: 'Your profile is ready: Original' })).toBeVisible()
  expect(posts).toBe(1); expect((await state(request)).users).toBe(1)
})

test('supported password and email changes keep the same native account without provisioning', async ({ page, request }) => {
  await login(page, 'plain@example.invalid'); await nav(page, 'Change password')
  await page.getByLabel('Current password', { exact: true }).fill('fixture-password')
  await page.getByLabel('New password', { exact: true }).fill('fixture-new-password')
  await page.getByLabel('Confirm new password', { exact: true }).fill('fixture-new-password')
  await page.getByRole('button', { name: 'Update password' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Password updated' })).toBeVisible()
  await nav(page, 'Settings')
  await page.getByLabel('New email address').fill('changed@example.invalid')
  await page.getByLabel('Current password', { exact: true }).fill('fixture-new-password')
  await page.getByRole('button', { name: 'Request email change' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'If this change can proceed' })).toBeVisible()
  const link = await (await request.get(provider+'/_fixture/link?flow=email_change')).json()
  const exchanges = []
  page.on('response', response => {
    const url = new URL(response.url())
    if (url.origin === project && url.pathname === '/auth/v1/token')
      exchanges.push({ grant: url.searchParams.get('grant_type'), status: response.status() })
  })
  await page.goto('/?code='+link.code)
  await expect.poll(() => exchanges).toContainEqual({ grant: 'pkce', status: 200 })
  await expect(page.locator('body')).toContainText('account service checked your current email')
  await expect(page).toHaveURL('http://127.0.0.1:5173/')
  await nav(page, 'Sign out'); await login(page, 'changed@example.invalid', 'fixture-new-password')
  expect((await state(request)).users).toBe(0)
})

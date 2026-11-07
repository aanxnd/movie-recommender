import assert from 'node:assert/strict'
import test, { before, after } from 'node:test'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

const dom = new JSDOM('<!doctype html><body></body>', {
  url: 'https://movelle.test',
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'localStorage', {
  value: window.localStorage,
  configurable: true,
})
globalThis.IS_REACT_ACT_ENVIRONMENT = true
// JSDOM has no native modal or scrolling implementation. Browser semantics
// (focus trapping/top layer) remain a separate visual-QA requirement.
window.HTMLDialogElement.prototype.showModal = function () {
  this.open = true
  this.querySelector('button')?.focus()
}
window.HTMLDialogElement.prototype.close = function () {
  this.open = false
}
window.scrollTo = () => {}
window.HTMLElement.prototype.scrollIntoView = () => {}
const { createRoot } = await import('react-dom/client')
const KEY = 'movelle.identity.v1'
const identity = (id, letter = String.fromCharCode(96 + id)) => ({
  id,
  token: letter.repeat(43),
})
const json = (data) =>
  new Response(JSON.stringify(data), {
    headers: { 'Content-Type': 'application/json' },
  })
const movie = (id, rating = 3) => ({
  user_id: id,
  movie_id: 1,
  title: 'First Film',
  genres: [],
  available: true,
  rating,
})
let vite, App

before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL('..', import.meta.url)),
    configLoader: 'native',
    server: { middlewareMode: true },
    appType: 'custom',
  })
  App = (await vite.ssrLoadModule('/src/App.jsx')).default
})
after(async () => {
  await vite?.close()
  dom.window.close()
})

function harness(t, responses = {}) {
  window.localStorage.clear()
  document.body.innerHTML = '<div id="root"></div>'
  const root = createRoot(document.getElementById('root'))
  const calls = [],
    held = new Map(),
    deferred = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const path = new URL(url, window.location.href).pathname.replace(
      /^\/api/,
      '',
    )
    const method = options.method || 'GET'
    calls.push({ path, url: String(url), method, ...options })
    const queue = held.get(`${method} ${path}`)
    if (queue?.length) {
      const item = queue.shift()
      item.signal = options.signal
      return item.promise // Deliberately permit a late response even after abort.
    }
    if (responses[path]) return responses[path](options)
    if (path === '/movies/decades') return json([1980, 1990])
    if (path === '/movies/artwork')
      return json({ items: [], configured: false })
    if (path.startsWith('/recommendations/genre/')) return json([])
    if (path === '/recommendations/popular')
      return json(
        Array.from({ length: 8 }, (_, i) => ({
          movie_id: i + 1,
          title: `Popular Film ${i + 1} (1990)`,
          genres: ['Drama'],
          score: 4.5,
        })),
      )
    if (path === '/movies/search')
      return json([{ movie_id: 1, title: 'First Film', genres: [] }])
    const user = path.match(/^\/users\/(\d+)(.*)$/)
    if (user) {
      const id = Number(user[1]),
        route = user[2]
      if (!route) return json({ id })
      if (route.startsWith('/ratings/details'))
        return json({ items: [movie(id)], next_after: null, total: 1 })
      if (route === '/ratings/lookup') return json([movie(id)])
      if (route === '/ratings/1')
        return json(movie(id, JSON.parse(options.body).rating))
      if (route === '/group-invitation')
        return options.method === 'DELETE'
          ? new Response(null, { status: 204 })
          : json({
              code: `${id}:${'z'.repeat(43)}`,
              expires_at: Math.floor(Date.now() / 1000) + 600,
            })
      if (route === '/recommendations') return json([])
    }
    if (path === '/recommendations/group') {
      return json([])
    }
    assert.fail(`Unexpected request: ${method} ${path}`)
  })
  t.after(async () => {
    await act(async () => {
      root.unmount()
      for (const item of deferred) item.resolve(json({}))
    })
    for (const call of calls) {
      const user = call.path.match(/^\/users\/(\d+)/)
      if (user)
        assert.equal(
          call.headers.Authorization,
          `Bearer ${identity(Number(user[1])).token}`,
          `wrong bearer for ${call.path}`,
        )
    }
  })
  const store = (next) =>
    next
      ? window.localStorage.setItem(KEY, JSON.stringify(next))
      : window.localStorage.removeItem(KEY)
  return {
    calls,
    hold(path, method = 'GET') {
      let resolve
      const item = {
        promise: new Promise((done) => {
          resolve = done
        }),
        resolve: (value) => resolve(value),
      }
      const key = `${method} ${path}`
      held.set(key, [...(held.get(key) || []), item])
      deferred.push(item)
      return item
    },
    async mount(next = identity(1)) {
      store(next)
      await act(async () => {
        root.render(React.createElement(App))
      })
    },
    async change(
      next,
      {
        key = KEY,
        area = window.localStorage,
        notify = true,
        newValue = null,
      } = {},
    ) {
      await act(async () => {
        store(next)
        if (notify)
          window.dispatchEvent(
            new window.StorageEvent('storage', {
              key,
              storageArea: area,
              newValue,
            }),
          )
      })
    },
    async settle(item, value) {
      await act(async () => {
        item.resolve(json(value))
      })
    },
    async respond(item, value, status) {
      await act(async () => {
        item.resolve(
          new Response(JSON.stringify(value), {
            status,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      })
    },
    async select(selector, value) {
      await act(async () => {
        const field = document.querySelector(selector)
        field.value = String(value)
        field.dispatchEvent(new window.Event('change', { bubbles: true }))
      })
    },
    async click(label) {
      const buttons = [...document.querySelectorAll('button')]
      const button =
        buttons.find(
          (node) =>
            node.textContent.trim() === label ||
            node.getAttribute('aria-label') === label,
        ) ||
        buttons.find(
          (node) =>
            node.textContent.includes(label) ||
            node.getAttribute('aria-label') === label,
        )
      assert.ok(button, `Missing button ${label}`)
      await act(async () => {
        button.click()
      })
    },
    async input(selector, value) {
      await act(async () => {
        const input = document.querySelector(selector)
        Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          'value',
        ).set.call(input, value)
        input.dispatchEvent(new window.Event('input', { bubbles: true }))
      })
    },
    selected(id) {
      assert.equal(
        document.querySelector('aside [role="status"]').textContent,
        `User ${id}`,
      )
      assert.deepEqual(
        JSON.parse(window.localStorage.getItem(KEY)),
        identity(id),
      )
    },
  }
}

function clipboard(t, writeText) {
  const original = Object.getOwnPropertyDescriptor(
    window.navigator,
    'clipboard',
  )
  Object.defineProperty(window.navigator, 'clipboard', {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  })
  t.after(() => {
    if (original) Object.defineProperty(window.navigator, 'clipboard', original)
    else delete window.navigator.clipboard
  })
}

test('recovery code is masked by default with accessible show/hide controls and a security warning', async (t) => {
  const h = harness(t)
  await h.mount()
  const field = document.getElementById('profile-recovery-code')
  assert.equal(field.type, 'password')
  assert.equal(field.readOnly, true)
  assert.equal(field.labels.length, 1)
  assert.match(
    document.getElementById(field.getAttribute('aria-describedby')).textContent,
    /grants access to your account.*Store it securely/,
  )
  const toggle = document.querySelector(
    'button[aria-controls="profile-recovery-code"]',
  )
  const copy = [...document.querySelectorAll('button')].find(
    (button) => button.getAttribute('aria-label') === 'Copy recovery code',
  )
  for (const button of [toggle, copy]) {
    // Native buttons provide Enter/Space activation and keyboard focus without
    // custom key handlers. Neither control submits the recovery form.
    assert.equal(button.type, 'button')
    assert.equal(button.tabIndex, 0)
    button.focus()
    assert.equal(document.activeElement, button)
  }
  assert.equal(toggle.getAttribute('aria-pressed'), 'false')
  await h.click('Show recovery code')
  assert.equal(field.type, 'text')
  assert.equal(toggle.getAttribute('aria-pressed'), 'true')
  assert.equal(toggle.getAttribute('aria-label'), 'Hide recovery code')
  field.focus()
  assert.equal(field.selectionStart, 0)
  assert.equal(field.selectionEnd, field.value.length)
  await h.click('Hide recovery code')
  assert.equal(field.type, 'password')
  h.selected(1)
})

test('copy writes the complete masked recovery code only to the clipboard and reports success', async (t) => {
  const h = harness(t),
    copied = []
  clipboard(t, async (code) => {
    copied.push(code)
  })
  await h.mount()
  const before = h.calls.filter(
    (call) => call.path !== '/movies/artwork',
  ).length
  await h.click('Copy recovery code')
  assert.deepEqual(copied, [`1:${identity(1).token}`])
  assert.equal(
    document.getElementById('profile-recovery-code').type,
    'password',
  )
  assert.match(
    document
      .querySelector('#profile-recovery-code')
      .parentElement.querySelector('[role="status"]').textContent,
    /Recovery code copied/,
  )
  assert.equal(document.body.textContent.includes(identity(1).token), false)
  assert.equal(
    h.calls.filter((call) => call.path !== '/movies/artwork').length,
    before,
  )
  assert.equal(window.location.href, 'https://movelle.test/')
  h.selected(1)
})

for (const failure of ['unavailable', 'rejected', 'throws'])
  test(`clipboard ${failure} gives safe feedback and permits retry`, async (t) => {
    const h = harness(t),
      copied = []
    let fail = true
    const writeText = (code) => {
      if (fail) {
        const error = new Error(`Sensitive browser details: ${code}`)
        if (failure === 'throws') throw error
        return Promise.reject(error)
      }
      copied.push(code)
      return Promise.resolve()
    }
    clipboard(t, failure === 'unavailable' ? undefined : writeText)
    await h.mount()
    await h.click('Copy recovery code')
    const error = document.querySelector('[role="alert"]')
    assert.match(
      error.textContent,
      /Could not copy recovery code.*copy it manually/,
    )
    assert.equal(document.body.textContent.includes(identity(1).token), false)
    assert.equal(
      document.body.textContent.includes('Sensitive browser details'),
      false,
    )
    fail = false
    if (failure === 'unavailable')
      Object.defineProperty(window.navigator, 'clipboard', {
        configurable: true,
        value: { writeText },
      })
    await h.click('Copy recovery code')
    assert.equal(document.querySelector('[role="alert"]'), null)
    assert.deepEqual(copied, [`1:${identity(1).token}`])
    h.selected(1)
  })

test('pending clipboard feedback and revealed state do not follow a cross-tab profile change', async (t) => {
  const h = harness(t),
    copied = []
  let finish
  clipboard(t, (code) => {
    copied.push(code)
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  await h.mount()
  await h.click('Show recovery code')
  await h.click('Copy recovery code')
  const button = [...document.querySelectorAll('button')].find(
    (button) => button.getAttribute('aria-label') === 'Copy recovery code',
  )
  assert.equal(button.disabled, true)
  await h.click('Copy recovery code')
  assert.equal(copied.length, 1)
  await h.change(identity(2))
  const field = document.getElementById('profile-recovery-code')
  assert.equal(field.type, 'password')
  assert.equal(field.value, `2:${identity(2).token}`)
  await act(async () => {
    finish()
  })
  assert.equal(
    document.body.textContent.includes('Recovery code copied.'),
    false,
  )
  assert.equal(
    document.body.textContent.includes('Copying recovery code...'),
    false,
  )
  h.selected(2)
})

test('stale restore cannot overwrite a newer cross-tab identity before its event arrives', async (t) => {
  const h = harness(t),
    pending = h.hold('/users/1')
  await h.mount()
  await h.change(identity(2), { notify: false })
  await h.settle(pending, { id: 1 })
  h.selected(2)
  assert.equal(document.body.textContent.includes('Could not restore'), false)
})

test('failed persistence keeps the selected identity and its request credential', async (t) => {
  const h = harness(t),
    creation = h.hold('/users', 'POST'),
    copied = []
  clipboard(t, async (code) => {
    copied.push(code)
  })
  await h.mount()
  await h.click('Show recovery code')
  const setItem = t.mock.method(window.Storage.prototype, 'setItem', () => {
    throw new Error('quota exceeded')
  })
  await h.click('Create new user')
  await h.settle(creation, identity(2))
  h.selected(1)
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /storage is unavailable/,
  )
  assert.equal(
    document.querySelector('aside input[readonly]').value,
    `2:${identity(2).token}`,
  )
  assert.equal(document.querySelector('aside input[readonly]').type, 'password')
  await h.click('Copy recovery code')
  assert.deepEqual(copied, [`2:${identity(2).token}`])
  await h.click('Create 10-minute group invitation')
  const invitation = h.calls.find((call) =>
    call.path.endsWith('/group-invitation'),
  )
  assert.equal(invitation.headers.Authorization, `Bearer ${identity(1).token}`)
  setItem.mock.restore()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  h.selected(2)
})

test('an explicit local selection wins over a pending initial restore', async (t) => {
  const h = harness(t),
    pending = h.hold('/users/1'),
    creation = h.hold('/users', 'POST')
  await h.mount()
  await h.click('Create new user')
  await h.settle(creation, identity(2))
  h.selected(2)
  assert.equal(pending.signal.aborted, true)
  await h.settle(pending, { id: 1 })
  h.selected(2)
})

test('rapid cross-tab switches ignore out-of-order restore responses', async (t) => {
  const h = harness(t),
    first = h.hold('/users/1'),
    second = h.hold('/users/2')
  await h.mount()
  await h.change(identity(2))
  await h.change(identity(3))
  h.selected(3)
  assert.equal(first.signal.aborted, true)
  assert.equal(second.signal.aborted, true)
  await h.settle(second, { id: 2 })
  await h.settle(first, { id: 1 })
  h.selected(3)
})

for (const key of [KEY, null])
  test(`cross-tab ${key === null ? 'clear' : 'removal'} cancels restoration without resurrecting it`, async (t) => {
    const h = harness(t),
      pending = h.hold('/users/1')
    await h.mount()
    await h.change(null, { key })
    await h.settle(pending, { id: 1 })
    assert.equal(window.localStorage.getItem(KEY), null)
    assert.equal(
      document.querySelector('aside [role="status"]').textContent,
      'No user selected',
    )
  })

test('storage events read current storage and ignore other keys and session storage', async (t) => {
  const h = harness(t)
  await h.mount()
  const before = h.calls.filter(
    (call) => call.path !== '/movies/artwork',
  ).length
  await h.change(identity(1), { key: 'unrelated' })
  await h.change(identity(1), { area: window.sessionStorage })
  assert.equal(
    h.calls.filter((call) => call.path !== '/movies/artwork').length,
    before,
  )
  await h.change(identity(2), { newValue: JSON.stringify(identity(1)) })
  h.selected(2)
})

test('pending recovery validation is canceled when another tab selects a profile', async (t) => {
  const h = harness(t),
    validation = h.hold('/users/2')
  await h.mount()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  await h.change(identity(3))
  assert.equal(validation.signal.aborted, true)
  await h.settle(validation, { id: 2 })
  h.selected(3)
})

test('pending explicit selection cannot overwrite storage before its change event arrives', async (t) => {
  const h = harness(t),
    validation = h.hold('/users/2')
  await h.mount()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  await h.change(identity(3), { notify: false })
  await h.settle(validation, { id: 2 })
  assert.deepEqual(JSON.parse(window.localStorage.getItem(KEY)), identity(3))
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /changed in another tab/,
  )
  await h.change(identity(3))
  h.selected(3)
})

test('pending rating reads and writes cannot update a later selection, including A to B to A', async (t) => {
  const h = harness(t),
    ratings = h.hold('/users/1/ratings/details')
  await h.mount()
  await h.change(identity(2))
  await h.settle(ratings, { items: [movie(1, 5)], next_after: null, total: 99 })
  h.selected(2)
  await h.click('My ratings')
  const write = h.hold('/users/2/ratings/1', 'PUT')
  await h.click('Update')
  await h.change(identity(1))
  await h.change(identity(2))
  await h.settle(write, movie(2, 5))
  h.selected(2)
  assert.equal(document.body.textContent.includes('Saved 5 / 5'), false)
  await h.click('My ratings')
  assert.match(document.body.textContent, /Saved: 3 \/ 5/)
})

test('storage read failure clears the active view and a later storage event can recover it', async (t) => {
  const h = harness(t)
  await h.mount()
  const getItem = t.mock.method(window.Storage.prototype, 'getItem', () => {
    throw new Error('storage denied')
  })
  await act(async () => {
    window.dispatchEvent(
      new window.StorageEvent('storage', {
        key: KEY,
        storageArea: window.localStorage,
      }),
    )
  })
  assert.equal(
    document.querySelector('aside [role="status"]').textContent,
    'No user selected',
  )
  getItem.mock.restore()
  await h.change(identity(2))
  h.selected(2)
})

test('pending creation and invitations cannot activate or display an old selection', async (t) => {
  const h = harness(t),
    creation = h.hold('/users', 'POST')
  await h.mount()
  await h.click('Create new user')
  await h.change(identity(2))
  assert.equal(creation.signal.aborted, true)
  await h.settle(creation, identity(3))
  h.selected(2)
  const invitation = h.hold('/users/2/group-invitation', 'POST')
  const recommendations = h.hold('/users/2/recommendations')
  await h.click('Create 10-minute group invitation')
  await h.click('Get recommendations')
  await h.change(identity(1))
  assert.equal(invitation.signal.aborted, true)
  assert.equal(recommendations.signal.aborted, true)
  await h.settle(invitation, { code: `2:${'z'.repeat(43)}` })
  await h.settle(recommendations, [])
  h.selected(1)
  assert.equal(document.querySelector('[aria-label="Group invitation"]'), null)
})

test('search, personal and group requests use the selected profile credential', async (t) => {
  const h = harness(t)
  await h.mount()
  await h.input('#movie-search', 'First')
  await h.click('Search')
  assert.ok(h.calls.some((call) => call.path === '/users/1/ratings/lookup'))
  await h.click('Get recommendations')
  assert.ok(h.calls.some((call) => call.path === '/users/1/recommendations'))
  await h.click('Groups')
  await h.input(
    'section[aria-labelledby="recommendations-title"] input',
    `2:${identity(2).token}`,
  )
  await h.click('Get recommendations')
  const group = h.calls.find((call) => call.path === '/recommendations/group')
  assert.equal(group.headers.Authorization, `Bearer ${identity(1).token}`)
  assert.deepEqual(JSON.parse(group.body), {
    user_ids: [1, 2],
    invitations: { 2: identity(2).token },
  })
})

test('main navigation exposes ratings, personal recommendations, groups and discovery with active states', async (t) => {
  const h = harness(t)
  await h.mount()
  await h.click('My ratings')
  assert.equal(
    document.querySelector('nav [aria-current="page"]').textContent,
    'My ratings',
  )
  assert.equal(document.querySelector('#library').parentElement.hidden, false)
  assert.equal(document.querySelector('#hero-title'), null)
  assert.match(
    document.querySelector('#library-title').textContent,
    /Your ratings/,
  )
  assert.equal(document.querySelector('#library-title').tagName, 'H1')
  await h.click('For you')
  assert.equal(
    document.querySelector('nav [aria-current="page"]').textContent,
    'For you',
  )
  assert.equal(document.querySelector('#recommendations-title').tagName, 'H1')
  assert.equal(document.querySelector('#library').parentElement.hidden, true)
  assert.equal(
    document.querySelector('.recommendation-tabs button[aria-pressed="true"]')
      .textContent,
    'For you',
  )
  await h.click('Groups')
  assert.equal(
    document.querySelector('nav [aria-current="page"]').textContent,
    'Groups',
  )
  assert.equal(document.querySelector('.recommendation-tabs'), null)
  assert.equal(
    document.querySelector('#recommendations-title').textContent,
    'Group recommendations',
  )
  assert.equal(document.querySelector('.flexible-field input').type, 'password')
  await h.click('Discover')
  assert.equal(
    document.querySelector('#library-title').textContent,
    'Discover films',
  )
  assert.equal(
    document.querySelector('nav [aria-current="page"]').textContent,
    'Discover',
  )
})

test('profile dialog returns focus, closes with Escape and remasks the recovery code', async (t) => {
  const h = harness(t)
  await h.mount()
  const trigger = document.querySelector('.profile-trigger'),
    dialog = document.querySelector('dialog')
  trigger.focus()
  await act(async () => trigger.click())
  assert.equal(dialog.open, true)
  assert.equal(dialog.getAttribute('aria-labelledby'), 'profile-title')
  await h.click('Show recovery code')
  assert.equal(document.getElementById('profile-recovery-code').type, 'text')
  await act(async () =>
    dialog.dispatchEvent(new window.Event('cancel', { cancelable: true })),
  )
  assert.equal(dialog.open, false)
  assert.equal(document.activeElement, trigger)
  assert.equal(
    document.getElementById('profile-recovery-code').type,
    'password',
  )
  await act(async () => trigger.click())
  assert.equal(
    document.getElementById('profile-recovery-code').type,
    'password',
  )
  await h.click('Close profile')
  assert.equal(dialog.open, false)
})

test('new account creation stores and activates the returned private identity with a masked recovery code', async (t) => {
  const h = harness(t),
    creation = h.hold('/users', 'POST')
  await h.mount(null)
  await h.click('Your profile')
  await h.click('Create new user')
  assert.equal(document.querySelector('.profile-create').disabled, true)
  await h.settle(creation, identity(4))
  h.selected(4)
  const field = document.getElementById('profile-recovery-code')
  assert.equal(field.type, 'password')
  assert.equal(field.value, `4:${identity(4).token}`)
  assert.equal(document.body.textContent.includes(identity(4).token), false)
})

test('recovery validates and activates a saved profile; invalid input makes no network request', async (t) => {
  const h = harness(t)
  await h.mount(null)
  await h.input('#user-id', '2')
  const before = h.calls.filter(
    (call) => call.path !== '/movies/artwork',
  ).length
  await h.click('Load')
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /private recovery code/,
  )
  assert.equal(
    h.calls.filter((call) => call.path !== '/movies/artwork').length,
    before,
  )
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  h.selected(2)
  assert.equal(document.querySelector('#user-id').value, '')
})

test('search shows loading then renders true metadata and saves an exact selected fractional rating', async (t) => {
  const h = harness(t),
    search = h.hold('/movies/search'),
    lookup = h.hold('/users/1/ratings/lookup', 'POST')
  await h.mount()
  await h.input('#movie-search', 'Arrival')
  await h.click('Search')
  assert.match(
    document.querySelector('.loading-state').textContent,
    /Searching the catalogue/,
  )
  await h.settle(search, [
    { movie_id: 1, title: 'Arrival (2016)', genres: ['Sci-Fi', 'Drama'] },
  ])
  await h.settle(lookup, [
    {
      user_id: 1,
      movie_id: 1,
      title: 'Arrival (2016)',
      genres: ['Sci-Fi', 'Drama'],
      rating: 3,
      available: true,
    },
  ])
  assert.equal(
    document.querySelector('#library .movie-card h3').textContent,
    'Arrival',
  )
  assert.match(
    document.querySelector('#library .movie-meta').textContent,
    /2016.*Sci-Fi.*Drama/,
  )
  assert.equal(document.querySelector('#library .loading-state'), null)
  await h.select('#rating-1', 4.5)
  await h.click('Update')
  const write = h.calls.find((call) => call.method === 'PUT')
  assert.deepEqual(JSON.parse(write.body), { rating: 4.5 })
  assert.match(document.body.textContent, /Saved 4.5 \/ 5 for Arrival/)
})

test('empty search results and a temporary API failure have distinct useful feedback', async (t) => {
  const h = harness(t),
    empty = h.hold('/movies/search')
  await h.mount()
  await h.input('#movie-search', 'unknown')
  await h.click('Search')
  await h.settle(empty, [])
  assert.match(
    document.querySelector('#library .empty-state').textContent,
    /No movies found.*shorter title/,
  )
  const failed = h.hold('/movies/search')
  await h.click('Search')
  await h.respond(failed, {}, 503)
  assert.match(
    document.querySelector('#library [role="alert"]').textContent,
    /could not complete this request/,
  )
  assert.equal(document.querySelector('#library .loading-state'), null)
})

test('rating write failure keeps the previous value and allows an explicit retry', async (t) => {
  const h = harness(t),
    write = h.hold('/users/1/ratings/1', 'PUT')
  await h.mount()
  await h.click('My ratings')
  await h.select('#rating-1', 4)
  await h.click('Update')
  assert.equal(document.querySelector('.rating-control button').disabled, true)
  await h.respond(write, {}, 503)
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /Could not save First Film.*Retry/,
  )
  assert.match(
    document.querySelector('.rating-label').textContent,
    /Saved: 3 \/ 5/,
  )
  assert.equal(document.querySelector('.rating-control button').disabled, false)
  await h.click('Update')
  assert.equal(h.calls.filter((call) => call.method === 'PUT').length, 2)
  assert.match(
    document.querySelector('.rating-label').textContent,
    /Saved: 4 \/ 5/,
  )
})

test('recommendations preserve server ordering, scores and explicit popularity fallback labels', async (t) => {
  const h = harness(t),
    picks = h.hold('/users/1/recommendations')
  await h.mount()
  await h.click('Get recommendations')
  assert.match(
    document.querySelector('.loading-state').textContent,
    /Finding recommendations/,
  )
  await h.settle(picks, [
    {
      movie_id: 7,
      title: 'First Pick (2001)',
      genres: ['Drama'],
      score: 4.387,
      confidence: 0.32,
      method: 'collaborative_filtering',
    },
    {
      movie_id: 3,
      title: 'Second Pick (1996)',
      genres: ['Comedy'],
      score: 4.12,
      confidence: null,
      method: 'popularity_fallback',
    },
  ])
  assert.deepEqual(
    [
      ...document.querySelectorAll('.recommendations-section .ranked-grid h3'),
    ].map((node) => node.textContent),
    ['First Pick', 'Second Pick'],
  )
  assert.deepEqual(
    [
      ...document.querySelectorAll(
        '.recommendations-section .movie-score strong',
      ),
    ].map((node) => node.textContent),
    ['4.39', '4.12'],
  )
  assert.match(
    document.querySelectorAll('.recommendations-section .ranked-grid li')[1]
      .textContent,
    /Average · Fallback.*Confidence: N\/A.*Popularity fallback/,
  )
  assert.match(
    document.querySelectorAll('.recommendations-section .ranked-grid li')[0]
      .textContent,
    /Confidence: 0.32/,
  )
  assert.equal(
    document.querySelectorAll('.recommendations-section .ranked-grid form')
      .length,
    0,
  )
})

test('genre and decade filters keep the existing endpoint and clear stale results when changed', async (t) => {
  const h = harness(t)
  await h.mount()
  await h.click('By genre')
  await h.input('.flexible-field input', 'Sci-Fi')
  await h.select('.recommendation-form select', 1990)
  const picks = h.hold('/recommendations/genre/Sci-Fi')
  await h.click('Get recommendations')
  await h.settle(picks, [
    {
      movie_id: 7,
      title: 'A Film (1995)',
      genres: ['Sci-Fi'],
      score: 4.1,
      confidence: null,
      method: 'popularity',
    },
  ])
  assert.match(h.calls.at(-1).url, /genre\/Sci-Fi\?decade=1990$/)
  assert.equal(h.calls.at(-1).headers.Authorization, undefined)
  assert.equal(
    document.querySelectorAll('.recommendations-section .ranked-grid li')
      .length,
    1,
  )
  await h.select('.recommendation-form select', 1980)
  assert.equal(
    document.querySelector('.recommendations-section .ranked-grid'),
    null,
  )
  await h.select('.recommendation-form select', '')
  const unfiltered = h.hold('/recommendations/genre/Sci-Fi')
  await h.click('Get recommendations')
  assert.match(h.calls.at(-1).url, /genre\/Sci-Fi$/)
  await h.settle(unfiltered, [])
  assert.equal(document.querySelector('.recommendation-form select').value, '')
})

test('group invitations can be created and revoked, and duplicate group members are rejected locally', async (t) => {
  const h = harness(t)
  await h.mount()
  await h.click('Create 10-minute group invitation')
  assert.equal(
    document.querySelector('[aria-label="Group invitation"]').value,
    `1:${'z'.repeat(43)}`,
  )
  await h.click('Revoke invitation')
  assert.equal(document.querySelector('[aria-label="Group invitation"]'), null)
  assert.ok(
    h.calls.some(
      (call) =>
        call.path.endsWith('/group-invitation') && call.method === 'DELETE',
    ),
  )
  await h.click('Groups')
  await h.input('.flexible-field input', `1:${identity(1).token}`)
  await h.click('Get recommendations')
  assert.match(
    document.querySelector(
      'section[aria-labelledby="recommendations-title"] [role="alert"]',
    ).textContent,
    /distinct invitation codes/,
  )
  assert.equal(
    h.calls.some((call) => call.path === '/recommendations/group'),
    false,
  )
})

test('expired group invitation feedback allows retry and never reveals entered codes', async (t) => {
  const h = harness(t),
    picks = h.hold('/recommendations/group', 'POST')
  await h.mount()
  await h.click('Groups')
  await h.input('.flexible-field input', `2:${identity(2).token}`)
  await h.click('Get recommendations')
  await h.respond(picks, {}, 403)
  assert.match(
    document.querySelector(
      'section[aria-labelledby="recommendations-title"] [role="alert"]',
    ).textContent,
    /does not authorize.*invitation codes/,
  )
  assert.equal(document.body.textContent.includes(identity(2).token), false)
  assert.equal(
    document.querySelector('.recommendation-form button').disabled,
    false,
  )
})

test('saved-ratings pagination preserves the authenticated cursor and deduplicates overlapping movies', async (t) => {
  const h = harness(t),
    first = h.hold('/users/1/ratings/details')
  await h.mount()
  await h.settle(first, { items: [movie(1)], next_after: 1, total: 2 })
  await h.click('My ratings')
  const more = h.hold('/users/1/ratings/details')
  await h.click('Load more saved ratings')
  assert.match(h.calls.at(-1).url, /ratings\/details\?after=1$/)
  await h.settle(more, {
    items: [movie(1), { ...movie(1, 4), movie_id: 2, title: 'Second Film' }],
    next_after: null,
    total: 2,
  })
  assert.deepEqual(
    [...document.querySelectorAll('#library .movie-card h3')].map(
      (node) => node.textContent,
    ),
    ['First Film', 'Second Film'],
  )
  assert.equal(
    [...document.querySelectorAll('button')].some((node) =>
      node.textContent.includes('Load more saved ratings'),
    ),
    false,
  )
})

test('decades show the unavailable-API error, then recover without a page reload after a retry', async (t) => {
  let offline = true
  const h = harness(t, {
    '/movies/decades': () =>
      offline ? new Response('', { status: 502 }) : json([1980, 1990]),
  })
  await h.mount()
  assert.match(
    document.querySelector('.recommendations-section [role="alert"]')
      .textContent,
    /HTTP 502.*npm run dev/,
  )
  const select = document.querySelector('.recommendation-form select')
  assert.equal(select.disabled, false)
  assert.equal(select.value, '')
  offline = false
  await h.click('Retry loading decades')
  assert.equal(
    document.querySelector('.recommendations-section [role="alert"]'),
    null,
  )
  assert.deepEqual(
    [...select.options].map((option) => option.value),
    ['', '1980', '1990'],
  )
})

test('temporarily failed profile restoration is an error and can retry the existing stored credential', async (t) => {
  let offline = true
  const h = harness(t, {
    '/users/1': () =>
      offline ? new Response('', { status: 502 }) : json({ id: 1 }),
  })
  await h.mount()
  assert.match(
    document.querySelector('.restore-feedback [role="alert"]').textContent,
    /Could not restore profile/,
  )
  assert.equal(document.querySelector('.notice.success'), null)
  assert.equal(JSON.parse(window.localStorage.getItem(KEY)).id, 1)
  offline = false
  await h.click('Retry restoring profile')
  h.selected(1)
  assert.equal(document.querySelector('.restore-feedback'), null)
})

test('recommendation views and main group navigation stay synchronized without duplicate group tabs', async (t) => {
  const h = harness(t)
  await h.mount()
  await h.click('Groups')
  assert.equal(document.querySelector('.recommendation-tabs'), null)
  await h.click('For you')
  await h.click('By genre')
  assert.equal(
    document.querySelector('nav [aria-current="page"]').textContent,
    'For you',
  )
  await h.click('Groups')
  assert.equal(
    document.querySelector('nav [aria-current="page"]').textContent,
    'Groups',
  )
  assert.match(
    document.querySelector('#recommendations-title').textContent,
    /Group recommendations/,
  )
})

test('a failed ratings page can retry the same cursor and clear its previous error', async (t) => {
  const h = harness(t),
    first = h.hold('/users/1/ratings/details')
  await h.mount()
  await h.settle(first, { items: [movie(1)], next_after: 1, total: 2 })
  await h.click('My ratings')
  const failed = h.hold('/users/1/ratings/details')
  await h.click('Load more saved ratings')
  await h.respond(failed, {}, 503)
  assert.ok(document.querySelector('#library [role="alert"]'))
  const retry = h.hold('/users/1/ratings/details')
  await h.click('Load more saved ratings')
  await h.settle(retry, {
    items: [{ ...movie(1, 4), movie_id: 2, title: 'Second Film' }],
    next_after: null,
    total: 2,
  })
  assert.equal(document.querySelector('#library [role="alert"]'), null)
  assert.equal(document.querySelectorAll('#library .movie-card').length, 2)
})

test('invitation codes expire in the interface at the server deadline', async (t) => {
  const h = harness(t),
    creation = h.hold('/users/1/group-invitation', 'POST')
  await h.mount()
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: Date.now() })
  await h.click('Create 10-minute group invitation')
  await h.settle(creation, {
    code: `1:${'z'.repeat(43)}`,
    expires_at: Math.floor(Date.now() / 1000) + 2,
  })
  assert.ok(document.querySelector('[aria-label="Group invitation"]'))
  await act(async () => t.mock.timers.tick(2001))
  assert.equal(document.querySelector('[aria-label="Group invitation"]'), null)
  assert.match(
    document.querySelector('.invitation-panel').textContent,
    /invitation expired.*Create a new invitation/,
  )
  assert.equal(document.body.textContent.includes('z'.repeat(43)), false)
})

test('new ratings use the existing half-step scale and a pending write cannot be submitted twice', async (t) => {
  const film = { movie_id: 2, title: 'Unrated Film (2001)', genres: ['Drama'] }
  const h = harness(t, {
    '/movies/search': () => json([film]),
    '/users/1/ratings/lookup': () => json([]),
  })
  await h.mount()
  await h.input('#movie-search', 'Unrated')
  await h.click('Search')
  assert.deepEqual(
    [...document.querySelector('#rating-2').options].map((option) =>
      Number(option.value),
    ),
    [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5],
  )
  await h.select('#rating-2', 2.5)
  const save = h.hold('/users/1/ratings/2', 'PUT')
  await h.click('Save')
  await act(async () =>
    document
      .querySelector('.rating-control')
      .dispatchEvent(
        new window.Event('submit', { bubbles: true, cancelable: true }),
      ),
  )
  assert.equal(h.calls.filter((call) => call.method === 'PUT').length, 1)
  await h.settle(save, { user_id: 1, movie_id: 2, rating: 2.5 })
  assert.match(
    document.querySelector('.rating-label').textContent,
    /Saved: 2.5 \/ 5/,
  )
  await h.click('My ratings')
  assert.match(
    document.querySelector('#library .collection-count').textContent,
    /2 films rated/,
  )
})

test('server-rejected recovery credentials preserve the active profile and are never rendered as text', async (t) => {
  const h = harness(t, {
    '/users/2': () =>
      new Response('{}', {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
  })
  await h.mount()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  h.selected(1)
  assert.match(
    document.querySelector('aside [role="alert"]').textContent,
    /invalid, or expired/,
  )
  assert.equal(document.querySelector('#user-id').type, 'password')
  assert.equal(document.body.textContent.includes(identity(2).token), false)
})

test('a failed personal recommendation request can be retried and empty results remain explicit', async (t) => {
  const h = harness(t),
    failure = h.hold('/users/1/recommendations')
  await h.mount()
  await h.click('Get recommendations')
  await h.respond(failure, {}, 500)
  assert.ok(document.querySelector('.recommendations-section [role="alert"]'))
  const retry = h.hold('/users/1/recommendations')
  await h.click('Get recommendations')
  await h.settle(retry, [])
  assert.equal(
    document.querySelector('.recommendations-section [role="alert"]'),
    null,
  )
  assert.match(
    document.querySelector('.recommendations-section .empty-state').textContent,
    /No eligible movies found/,
  )
  assert.equal(
    document.querySelector('.recommendations-section .ranked-grid'),
    null,
  )
})

test('malformed group input asks for a temporary invitation rather than a private recovery credential', async (t) => {
  const h = harness(t)
  await h.mount()
  await h.click('Groups')
  await h.input('.flexible-field input', '2')
  await h.click('Get recommendations')
  assert.match(
    document.querySelector('.recommendations-section [role="alert"]')
      .textContent,
    /ID:invitation.*temporary invitations, never private recovery codes/,
  )
  assert.equal(
    h.calls.some((call) => call.path === '/recommendations/group'),
    false,
  )
})

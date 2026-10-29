import assert from 'node:assert/strict'
import test, { before, after } from 'node:test'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

const dom = new JSDOM('<!doctype html><body></body>', { url: 'https://movelle.test' })
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'localStorage', { value: window.localStorage, configurable: true })
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const { createRoot } = await import('react-dom/client')
const KEY = 'movelle.identity.v1'
const identity = (id, letter = String.fromCharCode(96 + id)) => ({ id, token: letter.repeat(43) })
const json = (data) => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
const movie = (id, rating = 3) => ({ user_id: id, movie_id: 1, title: 'First Film', genres: [], available: true, rating })
let vite, App

before(async () => {
  vite = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configLoader: 'native', server: { middlewareMode: true }, appType: 'custom' })
  App = (await vite.ssrLoadModule('/src/App.jsx')).default
})
after(async () => { await vite?.close(); dom.window.close() })

function harness(t) {
  window.localStorage.clear()
  document.body.innerHTML = '<div id="root"></div>'
  const root = createRoot(document.getElementById('root'))
  const calls = [], held = new Map(), deferred = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const path = new URL(url, window.location.href).pathname.replace(/^\/api/, '')
    const method = options.method || 'GET'
    calls.push({ path, method, ...options })
    const queue = held.get(`${method} ${path}`)
    if (queue?.length) {
      const item = queue.shift()
      item.signal = options.signal
      return item.promise // Deliberately permit a late response even after abort.
    }
    if (path === '/movies/decades') return json([])
    if (path === '/movies/search') return json([{ movie_id: 1, title: 'First Film', genres: [] }])
    const user = path.match(/^\/users\/(\d+)(.*)$/)
    if (user) {
      const id = Number(user[1]), route = user[2]
      if (!route) return json({ id })
      if (route.startsWith('/ratings/details')) return json({ items: [movie(id)], next_after: null, total: 1 })
      if (route === '/ratings/lookup') return json([movie(id)])
      if (route === '/ratings/1') return json(movie(id, JSON.parse(options.body).rating))
      if (route === '/group-invitation') return options.method === 'DELETE' ? new Response(null, { status: 204 }) : json({ code: `${id}:${'z'.repeat(43)}` })
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
      if (user) assert.equal(call.headers.Authorization, `Bearer ${identity(Number(user[1])).token}`, `wrong bearer for ${call.path}`)
    }
  })
  const store = (next) => next ? window.localStorage.setItem(KEY, JSON.stringify(next)) : window.localStorage.removeItem(KEY)
  return {
    calls,
    hold(path, method = 'GET') {
      let resolve
      const item = { promise: new Promise(done => { resolve = done }), resolve: value => resolve(value) }
      const key = `${method} ${path}`
      held.set(key, [...(held.get(key) || []), item])
      deferred.push(item)
      return item
    },
    async mount(next = identity(1)) { store(next); await act(async () => { root.render(React.createElement(App)) }) },
    async change(next, { key = KEY, area = window.localStorage, notify = true, newValue = null } = {}) {
      await act(async () => { store(next); if (notify) window.dispatchEvent(new window.StorageEvent('storage', { key, storageArea: area, newValue })) })
    },
    async settle(item, value) { await act(async () => { item.resolve(json(value)) }) },
    async click(label) {
      const button = [...document.querySelectorAll('button')].find(node => node.textContent.includes(label))
      assert.ok(button, `Missing button ${label}`)
      await act(async () => { button.click() })
    },
    async input(selector, value) {
      await act(async () => {
        const input = document.querySelector(selector)
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(input, value)
        input.dispatchEvent(new window.Event('input', { bubbles: true }))
      })
    },
    selected(id) {
      assert.equal(document.querySelector('aside [role="status"]').textContent, `User ${id}`)
      assert.deepEqual(JSON.parse(window.localStorage.getItem(KEY)), identity(id))
    },
  }
}

test('stale restore cannot overwrite a newer cross-tab identity before its event arrives', async (t) => {
  const h = harness(t), pending = h.hold('/users/1')
  await h.mount()
  await h.change(identity(2), { notify: false })
  await h.settle(pending, { id: 1 })
  h.selected(2)
  assert.equal(document.body.textContent.includes('Could not restore'), false)
})

test('failed persistence keeps the selected identity and its request credential', async (t) => {
  const h = harness(t), creation = h.hold('/users', 'POST')
  await h.mount()
  const setItem = t.mock.method(window.Storage.prototype, 'setItem', () => { throw new Error('quota exceeded') })
  await h.click('Create new user')
  await h.settle(creation, identity(2))
  h.selected(1)
  assert.match(document.querySelector('[role="alert"]').textContent, /storage is unavailable/)
  assert.equal(document.querySelector('aside input[readonly]').value, `2:${identity(2).token}`)
  await h.click('Create 10-minute group invitation')
  const invitation = h.calls.find(call => call.path.endsWith('/group-invitation'))
  assert.equal(invitation.headers.Authorization, `Bearer ${identity(1).token}`)
  setItem.mock.restore()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  h.selected(2)
})

test('an explicit local selection wins over a pending initial restore', async (t) => {
  const h = harness(t), pending = h.hold('/users/1'), creation = h.hold('/users', 'POST')
  await h.mount()
  await h.click('Create new user')
  await h.settle(creation, identity(2))
  h.selected(2)
  assert.equal(pending.signal.aborted, true)
  await h.settle(pending, { id: 1 })
  h.selected(2)
})

test('rapid cross-tab switches ignore out-of-order restore responses', async (t) => {
  const h = harness(t), first = h.hold('/users/1'), second = h.hold('/users/2')
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

for (const key of [KEY, null]) test(`cross-tab ${key === null ? 'clear' : 'removal'} cancels restoration without resurrecting it`, async (t) => {
  const h = harness(t), pending = h.hold('/users/1')
  await h.mount()
  await h.change(null, { key })
  await h.settle(pending, { id: 1 })
  assert.equal(window.localStorage.getItem(KEY), null)
  assert.equal(document.querySelector('aside [role="status"]').textContent, 'No user selected')
})

test('storage events read current storage and ignore other keys and session storage', async (t) => {
  const h = harness(t)
  await h.mount()
  const before = h.calls.length
  await h.change(identity(1), { key: 'unrelated' })
  await h.change(identity(1), { area: window.sessionStorage })
  assert.equal(h.calls.length, before)
  await h.change(identity(2), { newValue: JSON.stringify(identity(1)) })
  h.selected(2)
})

test('pending recovery validation is canceled when another tab selects a profile', async (t) => {
  const h = harness(t), validation = h.hold('/users/2')
  await h.mount()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  await h.change(identity(3))
  assert.equal(validation.signal.aborted, true)
  await h.settle(validation, { id: 2 })
  h.selected(3)
})

test('pending explicit selection cannot overwrite storage before its change event arrives', async (t) => {
  const h = harness(t), validation = h.hold('/users/2')
  await h.mount()
  await h.input('#user-id', `2:${identity(2).token}`)
  await h.click('Load')
  await h.change(identity(3), { notify: false })
  await h.settle(validation, { id: 2 })
  assert.deepEqual(JSON.parse(window.localStorage.getItem(KEY)), identity(3))
  assert.match(document.querySelector('[role="alert"]').textContent, /changed in another tab/)
  await h.change(identity(3))
  h.selected(3)
})

test('pending rating reads and writes cannot update a later selection, including A to B to A', async (t) => {
  const h = harness(t), ratings = h.hold('/users/1/ratings/details')
  await h.mount()
  await h.change(identity(2))
  await h.settle(ratings, { items: [movie(1, 5)], next_after: null, total: 99 })
  h.selected(2)
  await h.click('Saved ratings')
  const write = h.hold('/users/2/ratings/1', 'PUT')
  await h.click('Update')
  await h.change(identity(1))
  await h.change(identity(2))
  await h.settle(write, movie(2, 5))
  h.selected(2)
  assert.equal(document.body.textContent.includes('Saved 5 / 5'), false)
  await h.click('Saved ratings')
  assert.match(document.body.textContent, /Saved: 3 \/ 5/)
})

test('storage read failure clears the active view and a later storage event can recover it', async (t) => {
  const h = harness(t)
  await h.mount()
  const getItem = t.mock.method(window.Storage.prototype, 'getItem', () => { throw new Error('storage denied') })
  await act(async () => { window.dispatchEvent(new window.StorageEvent('storage', { key: KEY, storageArea: window.localStorage })) })
  assert.equal(document.querySelector('aside [role="status"]').textContent, 'No user selected')
  getItem.mock.restore()
  await h.change(identity(2))
  h.selected(2)
})

test('pending creation and invitations cannot activate or display an old selection', async (t) => {
  const h = harness(t), creation = h.hold('/users', 'POST')
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
  assert.ok(h.calls.some(call => call.path === '/users/1/ratings/lookup'))
  await h.click('Get recommendations')
  assert.ok(h.calls.some(call => call.path === '/users/1/recommendations'))
  await h.click('For a group')
  await h.input('section[aria-labelledby="recommendations-title"] input', `2:${identity(2).token}`)
  await h.click('Get recommendations')
  const group = h.calls.find(call => call.path === '/recommendations/group')
  assert.equal(group.headers.Authorization, `Bearer ${identity(1).token}`)
  assert.deepEqual(JSON.parse(group.body), { user_ids: [1, 2], invitations: { 2: identity(2).token } })
})

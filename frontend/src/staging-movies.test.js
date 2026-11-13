import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

let server, StagingMovies, AuthProvider, createRoot
before(async () => {
  const browser = new JSDOM(''); globalThis.window = browser.window; globalThis.document = browser.window.document
  ;({ createRoot } = await import('react-dom/client')); browser.window.close()
  server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    envDir: false, server: { middlewareMode: true }, appType: 'custom' })
  ;({ StagingMovies } = await server.ssrLoadModule('/src/staging-movies.jsx'))
  ;({ AuthProvider } = await server.ssrLoadModule('/src/auth-context.js'))
})
after(async () => { await server?.close() })
const movie = { movie_id: 1, title: 'First Film', genres: ['Drama'], rating: 4, score: 4 }
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

async function mount(t, override = () => undefined) {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://127.0.0.1:5173/' })
  for (const name of ['window', 'document', 'HTMLElement', 'Event', 'MouseEvent', 'FormData']) globalThis[name] = dom.window[name]
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const errors = []; dom.window.addEventListener('error', event => errors.push(event.error))
  dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true }
  dom.window.HTMLDialogElement.prototype.close = function () { this.open = false }
  dom.window.HTMLElement.prototype.scrollIntoView = () => {}
  const listeners = new Set(); let snapshot = { status: 'authenticated', generation: 1, userId: 'a' }
  const session = { getSnapshot: () => snapshot, subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn) } }
  const api = async (path, options = {}) => {
    const result = override(path, options); if (result !== undefined) return result
    if (path === '/users/me') return { id: 17 }
    if (path.includes('/ratings/details')) return { items: [movie], total: 1, next_after: null }
    if (path.startsWith('/movies/search') || path.startsWith('/recommendations/popular')) return [movie]
    return []
  }
  const root = createRoot(document.querySelector('#root'))
  await act(async () => root.render(React.createElement(React.StrictMode, null,
    React.createElement(AuthProvider, { session }, React.createElement(StagingMovies, { api, onProfile() {} })))))
  t.after(async () => { await act(async () => root.unmount()); dom.window.close(); assert.deepEqual(errors, []) })
  return { button: text => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text),
    async switchTo(userId) { await act(async () => { snapshot = { ...snapshot, generation: snapshot.generation+1, userId }; for (const fn of listeners) fn() }) } }
}

test('ratings retain total/cursor and load the next real page', async t => {
  const paths = [], f = await mount(t, path => {
    if (!path.includes('/ratings/details')) return
    paths.push(path)
    return path.includes('after=1') ? { items: [{ ...movie, movie_id: 2, title: 'Second Film' }], total: 101, next_after: null } :
      { items: [movie], total: 101, next_after: 1 }
  })
  await act(async () => f.button('ratings').click())
  assert.equal(document.querySelector('.collection-count').textContent, '101 films rated')
  await act(async () => f.button('Load more saved ratings').click())
  assert.ok(paths.some(path => path.includes('after=1')))
  assert.equal(document.querySelectorAll('.rating-control').length, 2)
  assert.equal(f.button('Load more saved ratings'), undefined)
})

test('same-tick rating and invitation submissions issue once and disable their controls', async t => {
  const rating = deferred(), invitation = deferred(); let writes = 0, invites = 0
  const f = await mount(t, (path, options) => {
    if (options.method === 'PUT') { writes++; return rating.promise }
    if (path.endsWith('/group-invitation')) { invites++; return invitation.promise }
  })
  await act(async () => f.button('ratings').click())
  const form = document.querySelector('.rating-control')
  await act(async () => { for (let i=0; i<2; i++) form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })) })
  assert.equal(writes, 1); assert.equal(form.querySelector('button').disabled, true)
  const invite = f.button('Create group invitation')
  await act(async () => { invite.click(); invite.click() })
  assert.equal(invites, 1); assert.equal(invite.disabled, true)
  await f.switchTo('b'); await f.switchTo('a')
  await act(async () => { rating.resolve({}); invitation.resolve({ code: 'old-account-capability' }) })
  assert.equal(document.querySelector('input[readonly]'), null)
})

test('film detail find action opens the actual matching search', async t => {
  let searches = 0
  const f = await mount(t, path => { if (path.startsWith('/movies/search')) { searches++; return [movie] } })
  await act(async () => f.button('Explore film').click())
  await act(async () => f.button('Find and rate this film').click())
  assert.equal(document.querySelector('#movie-search').value, movie.title)
  assert.equal(searches, 1)
})

test('confirmed rating refreshes a search result outside the loaded collection page', async t => {
  let rating = 2
  const f = await mount(t, (path, options) => {
    if (path.includes('/ratings/details')) return { items: [], total: 101, next_after: 100 }
    if (path.includes('/ratings/lookup')) return [{ user_id: 17, movie_id: 1, rating }]
    if (options.method === 'PUT') { rating = 3.5; return {} }
  })
  await act(async () => f.button('Explore film').click())
  await act(async () => f.button('Find and rate this film').click())
  assert.equal(document.querySelector('.rating-label').textContent, 'Saved: 2 / 5')
  await act(async () => document.querySelector('.rating-control').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
  assert.equal(document.querySelector('.rating-label').textContent, 'Saved: 3.5 / 5')
})

test('a discarded page cannot block, append to or unlock a newer reload', async t => {
  const old = deferred(), current = deferred(); let pages = 0
  const f = await mount(t, path => {
    if (!path.includes('/ratings/details')) return
    if (path.includes('after=')) return ++pages === 1 ? old.promise : current.promise
    return { items: [movie], total: 2, next_after: 1 }
  })
  await act(async () => f.button('ratings').click())
  await act(async () => f.button('Load more saved ratings').click())
  await act(async () => f.button('Check personal access').click())
  await act(async () => f.button('Load more saved ratings').click())
  assert.equal(pages, 2)
  await act(async () => old.resolve({ items: [{ ...movie, title: 'Discarded Film' }], total: 2, next_after: null }))
  assert.equal(document.body.textContent.includes('Discarded Film'), false)
  assert.equal(f.button('Load more saved ratings').disabled, true)
  await act(async () => current.resolve({ items: [{ ...movie, movie_id: 2 }], total: 2, next_after: null }))
  assert.equal(document.querySelectorAll('.rating-control').length, 2)
})

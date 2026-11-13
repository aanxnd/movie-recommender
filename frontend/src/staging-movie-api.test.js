import assert from 'node:assert/strict'
import test from 'node:test'
import { createStagingMovieApi } from './staging-movie-api.js'
import { fixture, value, tick, deferred } from './auth-test-support.js'

async function setup(t, fetcher) {
  const f = fixture(), stop = f.session.subscribe(() => {}); t.after(stop)
  f.load.resolve({ data: { session: value() }, error: null }); await tick()
  return { ...f, api: createStagingMovieApi({ session: f.session, base: 'https://api.test',
    appOrigin: 'https://movelle.test', browser: { location: { origin: 'https://movelle.test' } }, fetcher }) }
}

test('shared movie requests distinguish public data from native personal ownership', async t => {
  const calls = [], f = await setup(t, async (url, init) => {
    calls.push({ path: new URL(url).pathname, ...init })
    return new Response(JSON.stringify([]))
  })
  await f.api('/movies/search?q=Film')
  await f.api('/recommendations/popular')
  await f.api('/movies/artwork', { method: 'POST', body: { movie_ids: [1] } })
  await f.api('/users/1/ratings/lookup', { token: undefined, method: 'POST', body: { movie_ids: [1] } })
  await f.api('/users/1/ratings/1', { token: undefined, method: 'PUT', body: { rating: 4 }, retry: true })
  assert.ok(calls.slice(0, 3).every(c => !c.headers.Authorization))
  assert.ok(calls.slice(3).every(c => c.headers.Authorization === 'Bearer synthetic-access-user-a'))
  for (const options of [{ token: 'legacy' }, { headers: {} }, { access: 'public' }])
    await assert.rejects(f.api('/users/1/ratings', options))
  await assert.rejects(f.api('/users', { method: 'POST' }))
  assert.equal(calls.length, 5)
})

test('movie mutation is not replayed and pending personal results are fenced by account switch', async t => {
  let attempts = 0
  const f = await setup(t, async () => { attempts++; return new Response('{}', { status: 503 }) })
  await assert.rejects(f.api('/users/1/ratings/1', { method: 'PUT', body: { rating: 4 }, retry: true }))
  assert.equal(attempts, 1)
  const pending = deferred(), g = await setup(t, () => pending.promise)
  const work = g.api('/users/1/ratings'); await tick()
  g.emit('SIGNED_IN', value('other'))
  pending.resolve(new Response('[]'))
  await assert.rejects(work, e => e.name === 'AbortError')
})

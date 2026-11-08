import assert from 'node:assert/strict'
import test from 'node:test'
import { imageUrl, imageSrcSet, imageCandidates } from './artwork.js'

test('only official credential-free Fanart image URLs reach image elements', () => {
  const url = 'https://assets.fanart.tv/fanart/poster.jpg'
  assert.equal(imageUrl(url), 'https://assets.fanart.tv/bigpreview/poster.jpg')
  assert.equal(imageUrl(url, 'fanart'), url)
  for (const bad of [null, {}, [url], 'https://evil.invalid/fanart/poster.jpg', `${url}?key=private`, 'https://assets.fanart.tv/fanart/../poster.jpg', 'javascript:alert(1)', 'https://user:password@assets.fanart.tv/fanart/poster.jpg']) {
    assert.equal(imageUrl(bad), null)
  }
})

test('cached canonical images resolve through the API once, with no CDN hotlink or invented srcset', () => {
  const route = '/movies/artwork-image/1/poster'
  assert.equal(imageUrl(route), '/api' + route)
  assert.equal(imageUrl(imageUrl(route)), imageUrl(route))
  assert.equal(imageSrcSet(route, { width: 1000, height: 1500 }), undefined)
  for (const value of [route + '?url=https://evil.invalid', route + '#x', route.replace('/1/', '/0/'), route.replace('/poster', ''),
    'https://media.trakt.tv/movies/1/medium/poster.webp', 'https://evil.invalid/api' + route]) assert.equal(imageUrl(value), null)
})

test('candidate order is preserved, unsafe/duplicate paths dropped, and old backgrounds labeled honestly', () => {
  const a = { url: '/movies/artwork-image/1/poster', kind: 'poster', provider: 'trakt' }
  const b = { url: 'https://assets.fanart.tv/fanart/background.jpg', kind: 'background', provider: 'fanart.tv' }
  assert.deepEqual(imageCandidates({ cover_candidates: [a, b, a, { url: 'https://evil.invalid/a.jpg' }] }), [a, b])
  assert.equal(imageCandidates({ poster_path: b.url, poster_credit: { width: 1920, height: 1080 } })[0].kind, 'background')
  assert.equal(imageUrl(imageUrl(b.url)), imageUrl(b.url))
})

test('responsive grid previews use real aspect-ratio widths and reserve full images for details', () => {
  const url = 'https://assets.fanart.tv/fanart/poster.jpg'
  const grid = imageSrcSet(url, { width: 1000, height: 1426 })
  assert.match(grid, /\/preview\/poster.jpg 140w/)
  assert.match(grid, /\/bigpreview\/poster.jpg 281w/)
  assert.doesNotMatch(grid, /1000w/)
  assert.match(imageSrcSet(url, { width: 1000, height: 1426 }, true), /\/fanart\/poster.jpg 1000w/)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { imageUrl, imageSrcSet } from './artwork.js'

test('only official credential-free Fanart image URLs reach image elements', () => {
  const url = 'https://assets.fanart.tv/fanart/poster.jpg'
  assert.equal(imageUrl(url), 'https://assets.fanart.tv/bigpreview/poster.jpg')
  assert.equal(imageUrl(url, 'fanart'), url)
  for (const bad of [null, {}, [url], 'https://evil.invalid/fanart/poster.jpg', `${url}?key=private`, 'https://assets.fanart.tv/fanart/../poster.jpg', 'javascript:alert(1)', 'https://user:password@assets.fanart.tv/fanart/poster.jpg']) {
    assert.equal(imageUrl(bad), null)
  }
})

test('responsive grid previews use real aspect-ratio widths and reserve full images for details', () => {
  const url = 'https://assets.fanart.tv/fanart/poster.jpg'
  const grid = imageSrcSet(url, { width: 1000, height: 1426 })
  assert.match(grid, /\/preview\/poster.jpg 140w/)
  assert.match(grid, /\/bigpreview\/poster.jpg 281w/)
  assert.doesNotMatch(grid, /1000w/)
  assert.match(imageSrcSet(url, { width: 1000, height: 1426 }, true), /\/fanart\/poster.jpg 1000w/)
})

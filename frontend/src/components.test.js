import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

test('actual rating component preserves fractions and handles unavailable catalog entries', async () => {
  const vite = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configLoader: 'native', server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  try {
    const { default: MovieList } = await vite.ssrLoadModule('/src/components/MovieList.jsx')
    const movies = Array.from({ length: 100 }, (_, i) => ({ movie_id: i + 1, title: `Film ${i}`, genres: [], available: i !== 99, rating: 3.25 }))
    const html = renderToStaticMarkup(React.createElement(MovieList, { movies, ratings: movies, onRate: () => {}, userId: 1 }))
    assert.equal((html.match(/<li /g) || []).length, 100)
    assert.equal((html.match(/<form/g) || []).length, 99)
    assert.ok(html.includes('>3.25</option>'))
    assert.ok(!html.includes('>3.3</option>'))
    const { default: MovieCover } = await vite.ssrLoadModule('/src/components/MovieCover.jsx')
    const { ArtworkContext } = await vite.ssrLoadModule('/src/artwork.js')
    const rejected = renderToStaticMarkup(React.createElement(ArtworkContext.Provider, {
      value: { items: new Map([[1, { poster_path: 'https://unsupported.invalid/poster.jpg' }]]) },
    }, React.createElement(MovieCover, { movie: movies[0] })))
    assert.ok(rejected.includes('data-artwork="unavailable"'))
    assert.ok(rejected.includes('Poster unavailable'))
    assert.ok(!rejected.includes('<img'))
  } finally { await vite.close() }
})

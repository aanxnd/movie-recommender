import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

test('actual rating component preserves fractions and handles unavailable catalog entries', async () => {
  const vite = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configLoader: 'native', server: { middlewareMode: true }, appType: 'custom' })
  try {
    const { default: MovieList } = await vite.ssrLoadModule('/src/components/MovieList.jsx')
    const movies = Array.from({ length: 100 }, (_, i) => ({ movie_id: i + 1, title: `Film ${i}`, genres: [], available: i !== 99, rating: 3.25 }))
    const html = renderToStaticMarkup(React.createElement(MovieList, { movies, ratings: movies, onRate: () => {}, userId: 1 }))
    assert.equal((html.match(/<li /g) || []).length, 100)
    assert.equal((html.match(/<form/g) || []).length, 99)
    assert.ok(html.includes('>3.25</option>'))
    assert.ok(!html.includes('>3.3</option>'))
  } finally { await vite.close() }
})

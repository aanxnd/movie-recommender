import assert from 'node:assert/strict'
import test from 'node:test'
import { apiUrl } from './api.js'

test('local API base defaults to the Vite proxy', () => {
  assert.equal(apiUrl('/users'), '/api/users')
  assert.equal(apiUrl('/users', ''), '/api/users')
})

test('production calls the backend without adding an api prefix', () => {
  assert.equal(
    apiUrl('/users', 'https://backend.example.com'),
    'https://backend.example.com/users'
  )
  assert.equal(
    apiUrl('/users', 'https://backend.example.com///'),
    'https://backend.example.com/users'
  )
  assert.equal(apiUrl('/movies/search?q=a', '/api/'), '/api/movies/search?q=a')
})

test('API base resolution trims local configuration and rejects credentials and invalid origins without exposing their values', () => {
  assert.equal(apiUrl('/movies/decades', '   '), '/api/movies/decades')
  assert.equal(
    apiUrl('/movies/decades', ' https://backend.example.com///  '),
    'https://backend.example.com/movies/decades'
  )
  assert.equal(apiUrl('/users', '/'), '/users')
  for (const base of [
    'backend.example.com',
    '//other.invalid',
    'https://secret:private@backend.example.com',
    'https://backend.example.com?key=private',
    'javascript:bad',
    '/api?key=private'
  ]) {
    assert.throws(
      () => apiUrl('/users', base),
      (error) =>
        /base URL is invalid/.test(error.message) &&
        !error.message.includes('private')
    )
  }
})

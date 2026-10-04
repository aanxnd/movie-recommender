import assert from 'node:assert/strict'
import test from 'node:test'
import { apiUrl } from './api.js'

test('local API base defaults to the Vite proxy', () => {
  assert.equal(apiUrl('/users'), '/api/users')
  assert.equal(apiUrl('/users', ''), '/api/users')
})

test('production calls the backend without adding an api prefix', () => {
  assert.equal(apiUrl('/users', 'https://backend.example.com'), 'https://backend.example.com/users')
  assert.equal(apiUrl('/users', 'https://backend.example.com///'), 'https://backend.example.com/users')
  assert.equal(apiUrl('/movies/search?q=a', '/api/'), '/api/movies/search?q=a')
})

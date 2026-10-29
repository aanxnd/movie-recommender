import assert from 'node:assert/strict'
import test from 'node:test'
import { evidenceMessage } from './evidence.js'

test('weak CF evidence is explained without relabeling averages or stronger results', () => {
  assert.match(evidenceMessage([{ method: 'collaborative_filtering', confidence: 0.04 }]), /Rate more movies/)
  assert.equal(evidenceMessage([{ method: 'collaborative_filtering', confidence: 0.4 }]), '')
  assert.equal(evidenceMessage([{ method: 'popularity_fallback', confidence: null }]), '')
  assert.equal(evidenceMessage([]), '')
})

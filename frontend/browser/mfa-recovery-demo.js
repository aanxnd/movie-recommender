// Offline UI simulation only. No SDK, native accounts, OTP generation or network.
import { createMfaPreview } from './mfa-demo.js'
export function createRecoveryPreview(screen) {
  const native = createMfaPreview('mfa')
  let factors = [{ id: 'offline-phone', label: 'Old phone', status: 'verified' },
    { id: 'offline-tablet', label: 'Independent device', status: 'verified' }]
  let phase = screen.endsWith('-unknown') ? 'inventory-unknown' : screen.endsWith('-locked') ? 'recovery-unavailable' :
    screen.endsWith('-abandoned') ? 'abandoned-enrollment' : screen.endsWith('-uncertain') ? 'mutation-uncertain' : 'challenge-required'
  const result = () => ({ status: phase, factors, generation: 0 })
  return {
    inspect: async () => result(), cancel: () => { native.cancel(); if (phase === 'replacement-pending') phase = 'abandoned-enrollment' },
    allInaccessible: () => { native.cancel(); phase = 'recovery-unavailable'; return result() },
    verifyAlternative: async () => { phase = 'alternative-verified'; return result() },
    enrollReplacement: async () => { factors = (await native.enroll()).factors; phase = 'replacement-pending'; return result() },
    verifyReplacement: async () => { factors = (await native.verify()).factors; phase = 'replacement-verified'; return result() },
    presentSetup: native.presentSetup,
    reviewRemoval: async () => ({ status: 'removal-unavailable' }),
  }
}

// Offline presentation fixture. No real keys, native client, OTP generation or network.
export function createMfaPreview(screen) {
  let factors = [{ id: 'offline-phone', label: 'Personal phone', status: 'verified' },
    { id: 'offline-tablet', label: 'Travel device', status: 'verified' }]
  let status = ['mfa-login', 'mfa-error'].includes(screen) ? 'challenge-required' :
    screen === 'mfa-unknown' ? 'inventory-unknown' : 'verified', clear, available = false
  const result = () => ({ status, factors, generation: 0 })
  return {
    inspect: async () => result(), cancel: () => { available = false; clear?.(); if (status === 'setup-pending') status = 'verified' },
    verify: async () => {
      clear?.()
      if (screen === 'mfa-error') return { status: 'invalid-code' }
      factors = factors.map(f => ({ ...f, status: 'verified' })); status = 'verified'; return result()
    },
    enroll: async () => {
      factors = [...factors, { id: 'offline-new', label: 'New authenticator', status: 'unverified' }]
      status = 'setup-pending'; available = true; return result()
    },
    remove: async id => { factors = factors.filter(f => f.id !== id); status = 'verified'; return { ...result(), status: 'removed' } },
    presentSetup(mount) {
      if (!available) return () => {}
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" fill="white"/><path d="M10 10h30v30H10zM80 10h30v30H80zM10 80h30v30H10zM50 50h20v20H50zM80 80h10v30H80zM100 60h10v20h-10zM50 90h20v10H50z" fill="black"/></svg>'
      clear = mount({ qr: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg), secret: 'OFFLINEDEMONOTAREALKEY' })
      return () => clear?.()
    },
  }
}

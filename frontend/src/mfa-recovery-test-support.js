import { mfaFixture, factorId, secondId, totp } from './mfa-test-support.js'
import { createNativeMfaRecovery } from './mfa-recovery.js'
import { json } from './password-test-support.js'

export const replacementId = 'dddddddd-1234-4234-9234-123456789abc'
export async function recoveryFixture(t, options = {}) {
  const f = await mfaFixture(t, { factors: [totp(), totp('verified', secondId)], ...options })
  const recovery = createNativeMfaRecovery(f.config)
  t.after(() => recovery.cancel())
  function replacementHandler(url) {
    if (url.pathname.endsWith('/factors')) {
      f.state.factors.push(totp('unverified', replacementId))
      return json({ id: replacementId, type: 'totp', totp: { secret: 'JBSWY3DPEHPK3PXP',
        uri: 'otpauth://totp/Movelle:offline?secret=JBSWY3DPEHPK3PXP',
        qr_code: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10H0z"/></svg>' } })
    }
    if (url.pathname.endsWith('/' + replacementId + '/verify')) f.state.factors = f.state.factors.map(x =>
      x.id === replacementId ? totp('verified', replacementId) : x)
  }
  f.state.handler = options.handler ?? replacementHandler
  return { ...f, recovery, replacementHandler,
    alternative: () => recovery.verifyAlternative(factorId, secondId, '123456') }
}

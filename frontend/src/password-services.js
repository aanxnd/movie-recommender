import { createPasswordResetRequest } from './password-reset-request.js'
import { createPasswordRecovery } from './password-recovery.js'
import { createSensitiveReauthentication } from './password-reauthentication.js'

/** @typedef {'check-email'|'verified'|'unproven'|'changed'|'missing'|'invalid'|'invalid-password'|'expired'|'rate-limited'|'busy'|'cancelled'|'mfa-required'|'unavailable'} PasswordStatus */
/** @typedef {Readonly<{status: PasswordStatus}>} PasswordOutcome */
/** @typedef {Readonly<{
 * requestReset: ReturnType<typeof createPasswordResetRequest>,
 * recovery: ReturnType<typeof createPasswordRecovery>,
 * sensitive: ReturnType<typeof createSensitiveReauthentication>
 * }>} PasswordServices */

// Explicit trusted bootstrap only; factory modules reuse the shared SDK/controller.
/** @returns {PasswordServices} */
export function createPasswordServices(config = {}) {
  return Object.freeze({ requestReset: createPasswordResetRequest(config),
    recovery: createPasswordRecovery(config), sensitive: Object.freeze({
      changePassword: (...args) => createSensitiveReauthentication(config).changePassword(...args) }) })
}

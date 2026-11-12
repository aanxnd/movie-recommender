// Sanitized UI contract; the dormant profile-adapter uses the authenticated backend.
/** @typedef {Readonly<{status: 'eligible'|'email-required'|'unavailable'|'cancelled'|'rate-limited'}> |
 * Readonly<{status: 'complete', username: string}>} ProfileInspection */
/** @typedef {Readonly<{status: 'username-taken'|'email-required'|'unavailable'|'cancelled'|'rate-limited'|'uncertain'|'busy'}> |
 * Readonly<{status: 'complete', username: string}>} ProfileProvision */
/** @typedef {Readonly<{
 * inspect(options: {signal: AbortSignal}): Promise<ProfileInspection>,
 * provision(input: {username: string}, options: {signal: AbortSignal}): Promise<ProfileProvision>
 * }>} ProfileProvisioning */

export const reservedUsernames = Object.freeze(['admin', 'administrator', 'api', 'auth', 'help',
  'login', 'logout', 'movelle', 'root', 'security', 'settings', 'signup', 'support', 'system'])

export function usernameError(value) {
  if (typeof value !== 'string' || value.length < 3 || value.length > 30 || /[^A-Za-z0-9_]/.test(value))
    return 'Use 3–30 letters (A–Z), numbers or underscores, without spaces.'
  return reservedUsernames.includes(value.toLowerCase()) ? 'Please choose another username. This name is reserved.' : null
}

/** @type {ProfileProvisioning} */
export const pendingProvisioning = Object.freeze({
  inspect: async () => Object.freeze({ status: 'unavailable' }),
  provision: async () => Object.freeze({ status: 'unavailable' }),
})

// Malformed, surplus or unexpected response fields cannot become UI eligibility/success.
export function profileResult(value, operation) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { status: 'unavailable' }
  if (value.status === 'complete' && Object.keys(value).sort().join(',') === 'status,username' && !usernameError(value.username))
    return Object.freeze({ status: 'complete', username: value.username })
  const allowed = ['email-required', 'unavailable', 'cancelled', 'rate-limited',
    ...(operation === 'inspect' ? ['eligible'] : ['username-taken', 'uncertain', 'busy'])]
  return Object.freeze({ status: Object.keys(value).join(',') === 'status' && allowed.includes(value.status) ? value.status : 'unavailable' })
}

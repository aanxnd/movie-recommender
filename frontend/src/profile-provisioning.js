// UI contract only. Prompt 23 must implement the trusted authenticated backend adapter.
/** @typedef {Readonly<{status: 'eligible'|'email-required'|'unavailable'}> |
 * Readonly<{status: 'complete', username: string}>} ProfileInspection */
/** @typedef {Readonly<{status: 'username-taken'|'email-required'|'unavailable'}> |
 * Readonly<{status: 'complete', username: string}>} ProfileProvision */
/** @typedef {Readonly<{
 * inspect(options: {signal: AbortSignal}): Promise<ProfileInspection>,
 * provision(input: {username: string}, options: {signal: AbortSignal}): Promise<ProfileProvision>
 * }>} ProfileProvisioning */

export const reservedUsernames = Object.freeze(['admin', 'administrator', 'api', 'auth', 'help',
  'login', 'logout', 'movelle', 'root', 'security', 'settings', 'signup', 'support', 'system'])

export function usernameError(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_]{3,30}$/.test(value))
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
  const allowed = operation === 'inspect' ? ['eligible', 'email-required', 'unavailable'] : ['username-taken', 'email-required', 'unavailable']
  return Object.freeze({ status: Object.keys(value).join(',') === 'status' && allowed.includes(value.status) ? value.status : 'unavailable' })
}

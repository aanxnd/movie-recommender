import { usernameError } from './profile-provisioning.js'

/** @typedef {Readonly<{status:'ready', username:string, revision:string}>} AccountSnapshot */
/** @typedef {Readonly<{status:'unavailable'|'sign-in-required'|'email-required'|'reauthentication-required'|'mfa-required'}>} AccountDenied */
/** @typedef {Readonly<{status:'updated', username:string, revision:string}> |
 * Readonly<{status:'username-taken'|'conflict'}> | AccountDenied} UsernameUpdate */
/** @typedef {Readonly<{
 * inspect(options:{signal:AbortSignal}):Promise<AccountSnapshot|AccountDenied>,
 * changeUsername(input:{username:string, revision:string}, options:{signal:AbortSignal}):Promise<UsernameUpdate>
 * }>} AccountSettingsService */

// No endpoint exists. Bootstrap must supply a future authenticated, subject-bound server adapter.
/** @type {AccountSettingsService} */
export const pendingAccountSettings = Object.freeze({
  inspect: async () => Object.freeze({ status: 'unavailable' }),
  changeUsername: async () => Object.freeze({ status: 'unavailable' }),
})

export function accountSettingsResult(value, operation) {
  const unavailable = () => Object.freeze({ status: 'unavailable' })
  if (!value || typeof value !== 'object' || Array.isArray(value)) return unavailable()
  const keys = Object.keys(value).sort().join(',')
  if (keys === 'revision,status,username' && value.status === (operation === 'inspect' ? 'ready' : 'updated') &&
      !usernameError(value.username) && typeof value.revision === 'string' && /^[A-Za-z0-9._:-]{1,128}$/.test(value.revision))
    return Object.freeze({ status: value.status, username: value.username, revision: value.revision })
  const denied = ['unavailable', 'sign-in-required', 'email-required', 'reauthentication-required', 'mfa-required']
  if (operation === 'update') denied.push('username-taken', 'conflict')
  return keys === 'status' && denied.includes(value.status) ? Object.freeze({ status: value.status }) : unavailable()
}

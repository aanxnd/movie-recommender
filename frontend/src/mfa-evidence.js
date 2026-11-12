// Dormant native evidence. Neither this observation nor its AAL grants backend access.
import { passwordEvidence, nativeUuid } from './password-evidence.js'

/** @typedef {'not-authenticated'|'inventory-unknown'|'pending'|'challenge-required'|'verified'|'stale'|'unavailable'|'cancelled'|'busy'|'invalid-code'|'rate-limited'|'expired'|'removal-unavailable'|'setup-pending'} MfaStatus */
/** @typedef {Readonly<{id:string,label:string,status:'verified'|'unverified'}>} TotpFactor */
/** @typedef {Readonly<{status:MfaStatus,factors?:ReadonlyArray<TotpFactor>,generation?:number}>} MfaObservation */
export const mfaResult = (status, fields = {}) => Object.freeze({ ...fields, status })
export function denyMfa(status) { throw Object.assign(new Error('Authenticator operation unavailable'), { mfaStatus: status }) }
export function mfaFailure(error) {
  const allowed = ['inventory-unknown', 'stale', 'unavailable', 'cancelled', 'busy', 'expired']
  return mfaResult(error?.name === 'AbortError' ? 'cancelled' : allowed.includes(error?.mfaStatus) ? error.mfaStatus :
    error?.status === 429 ? 'rate-limited' : error?.code === 'mfa_verification_failed' ? 'invalid-code' :
    error?.code === 'mfa_challenge_expired' ? 'expired' : 'unavailable')
}

// Internal continuation only: no caller-supplied claims, AAL booleans or cached inventory.
export async function observeMfa(client, config, lease) {
  const proof = await passwordEvidence(client, config, lease)
  const { data, error } = await client.auth.getUser(lease.authorization.slice(7))
  proof.assertCurrent()
  if (error) throw error
  const user = data?.user
  if (user?.id !== proof.subject || user?.is_anonymous !== false) denyMfa('stale')
  // listFactors() normalizes omission to []; getAAL() decodes claims without verifying.
  // Neither can independently establish completeness. Empty remains unknown until hosted acceptance.
  if (!Array.isArray(user.factors) || !user.factors.length || user.factors.length > 10) denyMfa('inventory-unknown')
  const factors = user.factors.map(f => {
    if (!f || !nativeUuid(f.id) || f.factor_type !== 'totp' || !['verified', 'unverified'].includes(f.status) ||
        (f.friendly_name !== undefined && (typeof f.friendly_name !== 'string' ||
          f.friendly_name.length > 64 || /[\x00-\x1f\x7f]/.test(f.friendly_name)))) denyMfa('inventory-unknown')
    return Object.freeze({ id: f.id, label: f.friendly_name || 'Authenticator', status: f.status })
  })
  if (new Set(factors.map(f => f.id.toLowerCase())).size !== factors.length) denyMfa('inventory-unknown')
  const enrolled = factors.some(f => f.status === 'verified')
  if (!enrolled && proof.aal === 'aal2') denyMfa('stale')
  return Object.freeze({ proof, factors: Object.freeze(factors),
    status: enrolled ? proof.aal === 'aal2' ? 'verified' : 'challenge-required' : 'pending' })
}

export async function inspectMfa(client, config, session) {
  if (session.getSnapshot().status !== 'authenticated') return mfaResult('not-authenticated')
  try {
    return await session.withAccess(async lease => {
      const evidence = await observeMfa(client, config, lease)
      return mfaResult(evidence.status, { factors: evidence.factors, generation: session.getSnapshot().generation })
    })
  } catch (error) { return mfaFailure(error) }
}

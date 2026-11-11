// Internal native evidence; not a React/session store or backend authorization decision.
import { captureCredentialFence, runCredentialRequest } from './supabase-client.js'

const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) && !/^0{8}-0{4}-0{4}-0{4}-0{12}$/.test(value)
export const passwordResult = status => Object.freeze({ status })
export function passwordFailure(error) {
  return passwordResult(error?.name === 'AbortError' ? 'cancelled' : error?.safeStatus ??
    (error?.code === 'insufficient_aal' ? 'mfa-required' :
      ['weak_password', 'same_password'].includes(error?.code) ? 'invalid-password' :
      error?.status === 429 ? 'rate-limited' : error?.status === 401 ? 'expired' : 'unavailable'))
}
export function denyPassword(status) { throw Object.assign(new Error('Account operation unavailable'), { safeStatus: status }) }
function bindObservation(assertLease, assertEpoch, expiresAt) {
  return () => { assertLease(); assertEpoch(); if (Date.now()/1000 >= expiresAt) denyPassword('expired') }
}

// Only callers holding the controller's private lease can read evidence. No claim dictionaries accepted.
export async function passwordEvidence(client, config, lease, method, expectedToken) {
  const assertEpoch = captureCredentialFence(client), token = lease.authorization.slice(7)
  if (expectedToken && token !== expectedToken) denyPassword('cancelled')
  const { data, error } = await client.auth.getClaims(token) // Supported signature verification / provider validation.
  lease.assertCurrent(); assertEpoch()
  if (error || !data) denyPassword('unavailable')
  const c = data.claims, now = Math.floor(Date.now()/1000)
  if (data.header.alg !== 'ES256' || c.iss !== config.projectUrl + '/auth/v1' || c.aud !== 'authenticated' ||
      !uuid(c.sub) || c.sub !== lease.userId || !uuid(c.session_id) || !['aal1', 'aal2'].includes(c.aal) ||
      !Number.isSafeInteger(c.iat) || c.iat <= 0 || c.iat > now || !Number.isSafeInteger(c.exp) || c.exp <= now || c.exp <= c.iat ||
      (c.nbf !== undefined && (!Number.isSafeInteger(c.nbf) || c.nbf > now)) || !Array.isArray(c.amr) || !c.amr.length ||
      c.amr.some(a => !a || typeof a.method !== 'string' || !/^[a-z][a-z0-9/_-]{0,63}$/.test(a.method) ||
        !Number.isSafeInteger(a.timestamp) || a.timestamp <= 0 || a.timestamp > c.iat) ||
      new Set(c.amr.map(a => a.method)).size !== c.amr.length ||
      !c.amr.some(a => a.method === method)) denyPassword('unproven')
  return Object.freeze({ subject: c.sub, sessionId: c.session_id, expiresAt: c.exp, aal: c.aal,
    assertCurrent: bindObservation(lease.assertCurrent, assertEpoch, c.exp) }) // No lease/token/claims retained.
}

export async function updateNativePassword(client, proof, password, signal, currentPassword) {
  if (signal?.aborted) denyPassword('cancelled')
  proof.assertCurrent()
  const { data, error } = await runCredentialRequest(client, () => client.auth.updateUser({ password,
    ...(currentPassword === undefined ? {} : { current_password: currentPassword }) }),
  { signal, subject: proof.subject, assertCurrent: proof.assertCurrent })
  proof.assertCurrent()
  if (error) return passwordFailure(error)
  return passwordResult(data?.user?.id === proof.subject ? 'changed' : 'unavailable')
}

import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { passwordEvidence, updateNativePassword, passwordResult, passwordFailure, denyPassword, nativeUuid } from './password-evidence.js'

/** @typedef {'pending'|'verified'|'expired'|'cancelled'|'unavailable'} ReauthenticationState */
/** @typedef {{signal?: AbortSignal, onProgress?: (state: Readonly<{status: ReauthenticationState, operation: 'password-change'}>) => void}} ReauthenticationOptions */
const busy = new WeakSet()

// Internal, operation-scoped continuation. No reusable reauth grant/flag is returned to a component.
async function withFreshPassword(client, config, session, currentPassword, options, complete) {
  const authenticated = await session.withAccess(async lease => {
    const before = await passwordEvidence(client, config, lease)
    const { data, error } = await client.auth.getUser(lease.authorization.slice(7))
    before.assertCurrent()
    const user = data?.user, factors = user?.factors
    if (error || user?.id !== before.subject || user?.is_anonymous !== false ||
        typeof user.email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(user.email) ||
        !Array.isArray(factors) || factors.length > 10 || factors.some(f => !f || !nativeUuid(f.id) ||
          f.factor_type !== 'totp' || !['verified', 'unverified'].includes(f.status)) ||
        new Set(factors.map(f => f.id)).size !== factors.length) denyPassword('unavailable')
    // Password sign-in creates AAL1. Do not downgrade an enrolled MFA account or bypass its factor.
    if (factors.some(f => f.status === 'verified')) denyPassword('mfa-required')
    const result = await runCredentialRequest(client, () => client.auth.signInWithPassword({ email: user.email,
      password: currentPassword }), { signal: options.signal, subject: before.subject, assertCurrent: before.assertCurrent })
    if (result.error || !result.data?.session) denyPassword(result.error?.status === 429 ? 'rate-limited' :
      result.error?.status === 400 ? 'invalid' : 'unavailable')
    return { token: result.data.session.access_token, subject: before.subject, previousSession: before.sessionId }
  })
  return session.withAccess(async lease => {
    const proof = await passwordEvidence(client, config, lease, 'password', authenticated.token)
    if (proof.subject !== authenticated.subject || proof.sessionId === authenticated.previousSession) denyPassword('unproven')
    if (options.signal?.aborted) denyPassword('cancelled')
    options.onProgress?.(Object.freeze({ status: 'verified', operation: 'password-change' }))
    return complete(proof) // Used immediately in this call; not a portable authorization capability.
  })
}

export function createSensitiveReauthentication(config) {
  const client = getBrowserSupabaseClient(config), session = getSessionController(client)
  return Object.freeze({
    /** @param {string} currentPassword @param {string} password @param {ReauthenticationOptions} options */
    async changePassword(currentPassword, password, options = {}) {
      if (![currentPassword, password].every(v => typeof v === 'string' && v.length > 0)) return passwordResult('invalid-password')
      if (busy.has(client)) return passwordResult('busy')
      const generation = session.getSnapshot().generation
      busy.add(client)
      try {
        if (options.signal?.aborted) denyPassword('cancelled')
        options.onProgress?.(Object.freeze({ status: 'pending', operation: 'password-change' }))
        return await withFreshPassword(client, config, session, currentPassword, options,
          proof => updateNativePassword(client, proof, password, options.signal, currentPassword))
      } catch (error) {
        return options.signal?.aborted || session.getSnapshot().generation !== generation ? passwordResult('cancelled') : passwordFailure(error)
      } finally { busy.delete(client) }
    },
  })
}

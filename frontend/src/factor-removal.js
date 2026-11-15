// Explicit dormant bootstrap only. A deployment-review gate is not authorization.
import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createNativeMfa } from './mfa-service.js'
import { observeMfa, mfaFailure } from './mfa-evidence.js'
import { nativeUuid } from './password-evidence.js'

const result = status => Object.freeze({ status })
const fingerprint = e => JSON.stringify(e.factors.map(f => [f.id, f.status]).sort())
export const pendingFactorRemoval = Object.freeze({ remove: async () => result('removal-unavailable') })

export function createFactorRemoval(config, { reviewed = false } = {}) {
  if (reviewed !== true) return pendingFactorRemoval
  const client = getBrowserSupabaseClient(config), session = getSessionController(client), native = createNativeMfa(config)
  let busy = false
  return Object.freeze({
    async remove({ factorId, authenticatingFactorId, code, confirmation } = {}, { signal } = {}) {
      // Every DELETE can remove the last factor, regardless of an earlier count.
      if (confirmation !== 'REMOVE EVEN IF MFA IS DISABLED' || !nativeUuid(factorId) ||
          !nativeUuid(authenticatingFactorId) || typeof code !== 'string' || !/^\d{6}$/.test(code))
        return result('invalid')
      if (busy) return result('busy')
      busy = true
      let dispatched = false, observation, outcome = result('unavailable')
      const current = () => { if (signal?.aborted) throw new Error('Cancelled') }
      try {
        current()
        const before = await session.withAccess(lease => observeMfa(client, config, lease))
        if (!before.factors.some(f => f.id === factorId && f.status === 'verified') ||
            !before.factors.some(f => f.id === authenticatingFactorId && f.status === 'verified')) return result('stale')
        // A historical AAL2 JWT cannot replace this explicit provider challenge.
        const verified = await native.verify(authenticatingFactorId, code, { signal })
        if (verified.status !== 'verified') return result(verified.status)
        current()
        outcome = await session.withAccess(async lease => {
          const after = await observeMfa(client, config, lease)
          if (after.status !== 'verified' || after.proof.subject !== before.proof.subject ||
              after.proof.sessionId !== before.proof.sessionId || fingerprint(after) !== fingerprint(before))
            return result('stale')
          observation = after
          const assertCurrent = () => { current(); after.proof.assertCurrent() }
          const reply = await runCredentialRequest(client, () => {
            assertCurrent(); dispatched = true
            return client.auth.mfa.unenroll({ factorId }) // Supabase enforces ownership and stored-session AAL2.
          }, { signal, subject: after.proof.subject, assertCurrent })
          assertCurrent()
          if (reply.error) return result('mutation-uncertain')
          return result(reply.data?.id === factorId ? 'removed' : 'mutation-uncertain')
        })
      } catch (error) {
        outcome = result(dispatched ? 'mutation-uncertain' : signal?.aborted ? 'cancelled' : mfaFailure(error).status)
      } finally {
        if (dispatched) {
          // Do not continue with a possibly downgraded session or log out another account.
          try {
            observation.proof.assertCurrent()
            await session.logout() // Local state is fenced even if provider logout is unavailable.
          } catch { outcome = result('mutation-uncertain') }
        }
        busy = false
      }
      return outcome
    },
  })
}

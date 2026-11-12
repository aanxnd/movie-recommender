// Trusted dormant bootstrap only. No MFA controller/claim/secret belongs in AuthContext.
import { getBrowserSupabaseClient, runCredentialRequest, cancelCredentialRequests } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { nativeUuid, passwordEvidence } from './password-evidence.js'
import { inspectMfa, observeMfa, mfaResult, mfaFailure, denyMfa } from './mfa-evidence.js'

const services = new WeakMap()
export function createNativeMfa(config) {
  const client = getBrowserSupabaseClient(config), session = getSessionController(client)
  if (services.has(client)) return services.get(client)
  let active, revision = 0
  const cancel = () => { revision++; active?.abort() }
  async function operation(signal, work) {
    if (active) return mfaResult('busy')
    const local = new AbortController(), ticket = revision
    active = local
    const combined = AbortSignal.any([local.signal, signal].filter(Boolean))
    const current = () => { if (combined.aborted || ticket !== revision) denyMfa('cancelled') }
    try {
      if (session.getSnapshot().status !== 'authenticated') return mfaResult('not-authenticated')
      current()
      const result = await session.withAccess(async lease => {
        const evidence = await observeMfa(client, config, lease)
        current(); evidence.proof.assertCurrent()
        return work(evidence, lease, combined, current)
      })
      current(); return result
    } catch (error) { return mfaFailure(error) }
    finally { if (active === local) active = undefined }
  }
  const service = Object.freeze({
    inspect: () => inspectMfa(client, config, session), cancel,
    async verify(factorId, code, { signal } = {}) {
      if (typeof code !== 'string' || !/^\d{6}$/.test(code)) return mfaResult('invalid-code')
      return operation(signal, async (evidence, lease, combined, current) => {
        const factor = evidence.factors.find(f => f.id === factorId)
        if (!factor) denyMfa('stale') // Selection is not ownership evidence.
        const assertCurrent = () => { current(); evidence.proof.assertCurrent() }
        let promoted
        try {
          const { data, error } = await runCredentialRequest(client, async () => {
            const challenge = await client.auth.mfa.challenge({ factorId: factor.id })
            assertCurrent()
            if (challenge.error) throw challenge.error
            const c = challenge.data
            if (!nativeUuid(c?.id) || c.type !== 'totp' || !Number.isSafeInteger(c.expires_at) ||
                c.expires_at <= Date.now()/1000) denyMfa('expired')
            const verified = await client.auth.mfa.verify({ factorId: factor.id, challengeId: c.id, code })
            assertCurrent()
            return verified
          }, { signal: combined, subject: evidence.proof.subject, assertCurrent })
          if (error) throw error
          // SDK _verify saves its native session and emits MFA_CHALLENGE_VERIFIED once.
          // Do not restore the old token or synthesize a session/event.
          promoted = data?.access_token
          if (typeof promoted !== 'string' || !promoted || data?.user?.id !== evidence.proof.subject) denyMfa('stale')
        } finally {
          // Invalidate other sensitive proofs AFTER the legitimate SDK transition completes.
          cancelCredentialRequests(client)
        }
        current()
        return session.withAccess(async nextLease => {
          const next = await passwordEvidence(client, config, nextLease, undefined, promoted)
          if (next.subject !== evidence.proof.subject || next.aal !== 'aal2') denyMfa('stale')
          const observed = await observeMfa(client, config, nextLease)
          current(); next.assertCurrent()
          if (observed.status !== 'verified' || !observed.factors.some(f => f.id === factor.id && f.status === 'verified')) denyMfa('stale')
          return mfaResult('verified', { factors: observed.factors, generation: session.getSnapshot().generation })
        })
      })
    },
  })
  services.set(client, service)
  return service
}

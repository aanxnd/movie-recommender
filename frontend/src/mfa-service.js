// Trusted dormant bootstrap only. No MFA controller/claim/secret belongs in AuthContext.
import { getBrowserSupabaseClient, runCredentialRequest, cancelCredentialRequests, watchCredentialChanges } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { nativeUuid, passwordEvidence } from './password-evidence.js'
import { inspectMfa, observeMfa, mfaResult, mfaFailure, denyMfa } from './mfa-evidence.js'
import { validateSetup } from './mfa-setup.js'

const services = new WeakMap()
export function createNativeMfa(config) {
  const client = getBrowserSupabaseClient(config), session = getSessionController(client)
  if (services.has(client)) return services.get(client)
  let active, revision = 0, setup, stopSetup, clearView, setupTimer, enrollmentAttempted = false
  const clearSetup = () => {
    setup = undefined; clearTimeout(setupTimer); stopSetup?.(); stopSetup = undefined
    const clear = clearView; clearView = undefined; clear?.()
  }
  const cancel = () => { revision++; active?.abort(); clearSetup() }
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
    // Dedicated setup view only. The callback returns an imperative DOM-secret cleanup.
    presentSetup(mount) {
      try {
        if (!setup || typeof mount !== 'function') denyMfa('unavailable')
        setup.assertCurrent(); clearView?.()
        clearView = mount({ qr: setup.qr, secret: setup.secret })
        if (typeof clearView !== 'function') { clearSetup(); denyMfa('unavailable') }
        return () => clearSetup()
      } catch { clearSetup(); return () => {} }
    },
    async enroll({ signal } = {}) {
      return operation(signal, async (evidence, lease, combined, current) => {
        // First enrollment is blocked while native absence/completeness remains unproven.
        if (enrollmentAttempted || evidence.status !== 'verified' || evidence.factors.length >= 10 ||
            evidence.factors.some(f => f.status === 'unverified')) denyMfa('unavailable')
        enrollmentAttempted = true // No automatic retry after an uncertain provider mutation.
        clearSetup()
        const assertCurrent = () => { current(); evidence.proof.assertCurrent() }
        const { data, error } = await runCredentialRequest(client, () => client.auth.mfa.enroll({
          factorType: 'totp', friendlyName: 'Movelle authenticator' }),
        { signal: combined, subject: evidence.proof.subject, assertCurrent })
        assertCurrent()
        if (error) throw error
        if (!nativeUuid(data?.id) || data.type !== 'totp' || evidence.factors.some(f => f.id === data.id)) denyMfa('stale')
        const credentials = validateSetup(data, config.browser ?? globalThis.window)
        const after = await observeMfa(client, config, lease)
        assertCurrent()
        if (!after.factors.some(f => f.id === data.id && f.status === 'unverified')) denyMfa('stale')
        setup = { ...credentials, assertCurrent }
        stopSetup = watchCredentialChanges(client, clearSetup)
        setupTimer = setTimeout(clearSetup, Math.min(300000, (evidence.proof.expiresAt-Date.now()/1000)*1000))
        return mfaResult('setup-pending', { factors: after.factors, generation: session.getSnapshot().generation })
      })
    },
    async remove(factorId, { signal } = {}) {
      return operation(signal, async (evidence, lease, combined, current) => {
        if (evidence.status !== 'verified' || !evidence.factors.some(f => f.id === factorId) ||
            !evidence.factors.some(f => f.id !== factorId && f.status === 'verified')) denyMfa('unavailable')
        clearSetup()
        const assertCurrent = () => { current(); evidence.proof.assertCurrent() }
        const { data, error } = await runCredentialRequest(client, () => client.auth.mfa.unenroll({ factorId }),
          { signal: combined, subject: evidence.proof.subject, assertCurrent })
        assertCurrent()
        if (error) throw error
        if (data?.id !== factorId) denyMfa('stale')
        const after = await observeMfa(client, config, lease)
        assertCurrent()
        if (after.status !== 'verified' || after.factors.some(f => f.id === factorId)) denyMfa('stale')
        return mfaResult('removed', { factors: after.factors, generation: session.getSnapshot().generation })
      })
    },
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
          clearSetup(); enrollmentAttempted = false
          return mfaResult('verified', { factors: observed.factors, generation: session.getSnapshot().generation })
        })
      })
    },
  })
  services.set(client, service)
  return service
}

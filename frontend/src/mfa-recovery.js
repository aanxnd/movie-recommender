// Dormant orchestration of native MFA, not another session, factor or recovery-token store.
import { getBrowserSupabaseClient, watchCredentialChanges } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createNativeMfa } from './mfa-service.js'
import { observeMfa, mfaResult, mfaFailure } from './mfa-evidence.js'

/** @typedef {'alternative-factor-available'|'verified-factor-present'|'challenge-required'|'alternative-verified'|'replacement-pending'|'replacement-verified'|'abandoned-enrollment'|'removal-unavailable'|'recovery-unavailable'|'inventory-unknown'|'reauthentication-required'|'cancelled'|'expired'|'rate-limited'|'invalid-code'|'busy'|'mutation-uncertain'|'unavailable'} RecoveryStatus */
/** @typedef {Readonly<{status:RecoveryStatus,factors?:ReadonlyArray<import('./mfa-evidence.js').TotpFactor>,generation?:number}>} RecoveryObservation */
const services = new WeakMap()
const fingerprint = factors => JSON.stringify(factors.map(f => [f.id, f.status]).sort())
const deny = status => { throw Object.assign(new Error('Authenticator recovery unavailable'), { recoveryStatus: status }) }
const failures = ['inventory-unknown', 'reauthentication-required', 'cancelled', 'expired', 'rate-limited', 'invalid-code', 'busy', 'mutation-uncertain', 'unavailable']
const knownRejections = ['invalid-code', 'expired', 'rate-limited', 'busy']

export function createNativeMfaRecovery(config) {
  const client = getBrowserSupabaseClient(config), session = getSessionController(client), native = createNativeMfa(config)
  if (services.has(client)) return services.get(client)
  let context, active, revision = 0, promoting = false
  const invalidate = () => { revision++; context = undefined; active?.abort() }
  const cancel = () => { invalidate(); native.cancel() }
  // No additional SDK subscription. Own native promotion is validated by native.verify.
  watchCredentialChanges(client, () => { if (!promoting && (context || active)) invalidate() })
  const read = () => session.withAccess(lease => observeMfa(client, config, lease))
  const describe = (evidence, status) => mfaResult(status, { factors: evidence.factors, generation: session.getSnapshot().generation })
  function bind(evidence, fields) {
    context = { ...fields, proof: evidence.proof, inventory: fingerprint(evidence.factors), generation: session.getSnapshot().generation }
  }
  async function bound() {
    const previous = context
    if (!previous) deny('reauthentication-required')
    previous.proof.assertCurrent()
    const evidence = await read()
    if (previous !== context || previous.generation !== session.getSnapshot().generation ||
        evidence.proof.subject !== previous.proof.subject || evidence.proof.sessionId !== previous.proof.sessionId ||
        evidence.status !== 'verified' || fingerprint(evidence.factors) !== previous.inventory) deny('unavailable')
    return evidence
  }
  async function operation(signal, work) {
    if (active) return mfaResult('busy')
    const local = new AbortController(), ticket = revision, state = session.getSnapshot()
    active = local
    const combined = AbortSignal.any([local.signal, signal].filter(Boolean))
    const current = () => {
      const now = session.getSnapshot()
      if (combined.aborted || revision !== ticket || now.generation !== state.generation || now.userId !== state.userId) deny('cancelled')
    }
    try {
      if (state.status !== 'authenticated') deny('reauthentication-required')
      current(); const result = await work(combined, current); current(); return result
    } catch (error) {
      context = undefined; native.cancel()
      const status = combined.aborted ? 'cancelled' : failures.includes(error?.recoveryStatus) ? error.recoveryStatus :
        error?.safeStatus === 'expired' ? 'expired' : mfaFailure(error).status
      return mfaResult(failures.includes(status) ? status : 'unavailable')
    } finally { if (active === local) active = undefined }
  }
  async function verifyNative(id, code, signal, current) {
    let result
    promoting = true
    try { result = await native.verify(id, code, { signal }) }
    finally { promoting = false }
    current()
    return result
  }
  const service = Object.freeze({
    cancel,
    allInaccessible() { cancel(); return mfaResult('recovery-unavailable') },
    inspect: () => operation(undefined, async () => {
      const evidence = context ? await bound() : await read()
      if (evidence.status === 'not-enrolled') return describe(evidence, 'not-enrolled')
      const verified = evidence.factors.filter(f => f.status === 'verified')
      return describe(evidence, context?.phase ?? (evidence.factors.some(f => f.status === 'unverified') ? 'abandoned-enrollment' :
        evidence.proof.aal === 'aal1' ? 'challenge-required' : verified.length > 1 ? 'alternative-factor-available' : 'verified-factor-present'))
    }),
    verifyAlternative(lostId, alternativeId, code, { signal } = {}) {
      return operation(signal, async (combined, current) => {
        context = undefined
        const before = await read(); current()
        if (lostId === alternativeId || ![lostId, alternativeId].every(id =>
          before.factors.some(f => f.id === id && f.status === 'verified'))) deny('unavailable')
        if (before.factors.some(f => f.status !== 'verified')) deny('unavailable')
        const result = await verifyNative(alternativeId, code, combined, current)
        if (result.status !== 'verified') deny(knownRejections.includes(result.status) ? result.status : 'mutation-uncertain')
        const after = await read(); current()
        if (after.proof.subject !== before.proof.subject || after.status !== 'verified' ||
            fingerprint(before.factors) !== fingerprint(after.factors)) deny('unavailable')
        bind(after, { phase: 'alternative-verified', lostId, alternativeId })
        return describe(after, context.phase)
      })
    },
    enrollReplacement({ signal } = {}) {
      return operation(signal, async (combined, current) => {
        const before = await bound(), previous = context
        if (previous.phase !== 'alternative-verified') deny('unavailable')
        const result = await native.enroll({ signal: combined }); current()
        if (result.status !== 'setup-pending') deny('mutation-uncertain')
        const after = await read(); current()
        const added = after.factors.filter(f => !before.factors.some(old => old.id === f.id))
        if (after.proof.subject !== before.proof.subject || after.proof.sessionId !== before.proof.sessionId ||
            after.status !== 'verified' || added.length !== 1 || added[0].status !== 'unverified' ||
            fingerprint(after.factors.filter(f => f.id !== added[0].id)) !== fingerprint(before.factors)) deny('mutation-uncertain')
        bind(after, { ...previous, phase: 'replacement-pending', replacementId: added[0].id })
        return describe(after, context.phase)
      })
    },
    presentSetup(mount) {
      try {
        if (context?.phase !== 'replacement-pending') return () => {}
        context.proof.assertCurrent()
        return native.presentSetup(mount)
      } catch { cancel(); return () => {} }
    },
    verifyReplacement(code, { signal } = {}) {
      return operation(signal, async (combined, current) => {
        const before = await bound(), previous = context
        if (previous.phase !== 'replacement-pending') deny('unavailable')
        const result = await verifyNative(previous.replacementId, code, combined, current)
        const after = await read(); current()
        if (after.proof.subject !== before.proof.subject || after.status !== 'verified') deny('unavailable')
        if (knownRejections.includes(result.status) && after.proof.sessionId === before.proof.sessionId && fingerprint(after.factors) === previous.inventory) {
          bind(after, previous) // Known native rejection only; fresh same-session evidence, no automatic retry.
          return mfaResult(result.status)
        }
        const expected = before.factors.map(f => f.id === previous.replacementId ? { ...f, status: 'verified' } : f)
        if (result.status !== 'verified' || fingerprint(after.factors) !== fingerprint(expected)) deny('mutation-uncertain')
        bind(after, { ...previous, phase: 'replacement-verified' })
        return describe(after, context.phase)
      })
    },
    reviewRemoval: () => operation(undefined, async () => {
      const evidence = await bound()
      if (context.phase !== 'replacement-verified') deny('unavailable')
      return describe(evidence, 'removal-unavailable') // No remove method, authorization flag or native DELETE.
    }),
  })
  services.set(client, service)
  return service
}

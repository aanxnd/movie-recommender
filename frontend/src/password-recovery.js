import { getBrowserSupabaseClient } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { consumePkceCallback, callbackResult } from './pkce-callback.js'
import { passwordEvidence, updateNativePassword, passwordFailure, passwordResult, denyPassword } from './password-evidence.js'

const recoveries = new WeakMap()
/** Native recovery context stays private; components receive only safe statuses, never a grant/token. */
export function createPasswordRecovery(config = {}) {
  let current, attempt
  return Object.freeze({
    state: () => current?.state() ?? passwordResult('unproven'),
    confirm() {
      // Even factory construction is lazy: URL scrubbing precedes SDK construction/initialization.
      return attempt ??= consumePkceCallback(config, 'recovery', (client, data) => {
        current = nativeRecovery(config, client); return current.accept(data)
      }).then(result => {
        if (result.status === 'verified' && !current) current = nativeRecovery(config, getBrowserSupabaseClient(config))
        return result
      }).catch(() => callbackResult('unavailable'))
    },
    setPassword: (password, options) => current ? current.setPassword(password, options) : Promise.resolve(passwordResult('unavailable')),
  })
}

function nativeRecovery(config, client) {
  if (recoveries.has(client)) return recoveries.get(client)
  const session = getSessionController(client)
  let context, busy = false
  const state = () => {
    if (!context) return passwordResult('unproven')
    try { context.proof.assertCurrent(); return passwordResult('verified') }
    catch { context = undefined; return passwordResult('expired') }
  }
  const recovery = Object.freeze({
    state,
    accept: async data => {
      if (data.redirectType !== 'recovery' || !data.session || data.user?.id !== data.session.user?.id) return callbackResult('unproven')
      try {
        return await session.withAccess(async lease => {
          const proof = await passwordEvidence(client, config, lease, 'recovery', data.session.access_token)
          context = { proof }; return callbackResult('verified')
        })
      } catch (error) { return callbackResult(passwordFailure(error).status) }
    },
    async setPassword(password, { signal } = {}) {
      if (typeof password !== 'string' || !password) return passwordResult('invalid-password')
      if (busy) return passwordResult('busy')
      if (state().status !== 'verified') return passwordResult('unavailable')
      const previous = context; busy = true
      try {
        return await session.withAccess(async lease => {
          const proof = await passwordEvidence(client, config, lease, 'recovery')
          previous.proof.assertCurrent()
          if (proof.subject !== previous.proof.subject || proof.sessionId !== previous.proof.sessionId) denyPassword('cancelled')
          context = undefined // Consume before mutation: uncertain outcomes must never be automatically replayed.
          const result = await updateNativePassword(client, proof, password, signal)
          if (['invalid-password', 'mfa-required', 'rate-limited'].includes(result.status)) context = previous // Known rejection only.
          return result
        })
      } catch (error) { context = undefined; return passwordFailure(error) }
      finally { busy = false }
    },
  })
  recoveries.set(client, recovery)
  return recovery
}

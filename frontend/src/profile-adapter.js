// Dormant, explicit trusted bootstrap only. No production entry-point import.
import { captureCredentialFence, getBrowserSupabaseClient, watchCredentialChanges } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createAuthenticatedApi } from './auth-api.js'
import { profileResult, usernameError } from './profile-provisioning.js'

const adapters = new WeakMap()
const result = status => Object.freeze({ status })
const cancelled = () => new DOMException('Profile setup cancelled', 'AbortError')

/** Shared per SDK client. Requires a mounted shared AuthProvider/session controller.
 * @returns {import('./profile-provisioning.js').ProfileProvisioning}
 */
export function createProfileProvisioning(config = {}) {
  const client = getBrowserSupabaseClient(config), previous = adapters.get(client)
  if (previous) {
    if (previous.base !== config.base) throw new Error('Profile setup configuration unavailable')
    return previous.adapter
  }
  const session = getSessionController(client), api = createAuthenticatedApi({ ...config, session })
  let busy = false
  async function operation(writing, input, { signal: callerSignal } = {}) {
    if (writing && busy) return result('busy')
    if (writing && (!input || Array.isArray(input) || Object.keys(input).join(',') !== 'username' || usernameError(input.username)))
      return result('unavailable')
    if (writing) busy = true
    const epoch = new AbortController()
    let unwatch
    try {
      return await session.withAccess(async lease => {
        const assertEpoch = captureCredentialFence(client)
        unwatch = watchCredentialChanges(client, () => epoch.abort())
        const signal = AbortSignal.any([epoch.signal, callerSignal].filter(Boolean))
        const current = () => {
          try { lease.assertCurrent(); assertEpoch(); if (signal.aborted) throw cancelled() }
          catch { throw cancelled() }
        }
        const inspect = () => api('/auth/profile', { access: 'authenticated', signal })
        try {
          current()
          const reply = writing ? await api('/auth/profile', { access: 'authenticated', method: 'POST',
            body: { username: input.username }, signal }) : await inspect()
          current()
          return profileResult(reply, writing ? 'provision' : 'inspect')
        } catch (error) {
          current() // Never inspect another account after logout, A→B→A or refresh.
          if (error?.status === 409 && writing) return result('username-taken')
          if (error?.status === 429) return result('rate-limited')
          if (!writing || [401, 403, 422].includes(error?.status)) return result('unavailable')
          // POST is never replayed. Recover only through an authoritative GET for
          // the same current credential; an eligible read cannot disprove a late commit.
          try {
            const observed = profileResult(await inspect(), 'inspect')
            current()
            if (observed.status === 'complete') return observed
          } catch { current() }
          return result('uncertain')
        }
      })
    } catch (error) { return result(error?.name === 'AbortError' || epoch.signal.aborted ? 'cancelled' : 'unavailable') }
    finally { unwatch?.(); if (writing) busy = false }
  }
  const adapter = Object.freeze({ inspect: options => operation(false, undefined, options),
    provision: (input, options) => operation(true, input, options) })
  adapters.set(client, { adapter, base: config.base })
  return adapter
}

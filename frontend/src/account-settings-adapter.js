import { captureCredentialFence, getBrowserSupabaseClient, watchCredentialChanges } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createAuthenticatedApi } from './auth-api.js'
import { accountSettingsResult } from './account-settings-contract.js'
import { usernameError } from './profile-provisioning.js'

const adapters = new WeakMap(), denied = () => Object.freeze({ status: 'unavailable' })

export function createAccountSettings(config) {
  const client = getBrowserSupabaseClient(config), previous = adapters.get(client)
  if (previous) {
    if (previous.base !== config.base) throw new Error('Account settings unavailable')
    return previous.adapter
  }
  const session = getSessionController(client), api = createAuthenticatedApi({ ...config, session })
  let busy = false
  async function operate(input, options = {}) {
    if (busy) return denied()
    if (input && (Object.keys(input).sort().join(',') !== 'revision,username' || usernameError(input.username) ||
        typeof input.revision !== 'string' || !/^[1-9][0-9]{0,18}$/.test(input.revision))) return denied()
    busy = true
    const epoch = new AbortController()
    let stop
    try {
      return await session.withAccess(async lease => {
        const fence = captureCredentialFence(client)
        stop = watchCredentialChanges(client, () => epoch.abort())
        const signal = AbortSignal.any([epoch.signal, options.signal].filter(Boolean))
        const current = () => { lease.assertCurrent(); fence(); if (signal.aborted) throw new Error('Cancelled') }
        current()
        try {
          const reply = await api('/auth/settings', { access: 'authenticated', signal,
            ...(input ? { method: 'PATCH', body: input } : {}) })
          current()
          return accountSettingsResult(reply, input ? 'update' : 'inspect')
        } catch (error) {
          current()
          // No mutation replay or guessed outcome. A fresh inspect is an explicit user action.
          return input && error?.status === 409 ? Object.freeze({ status: 'conflict' }) : denied()
        }
      })
    } catch { return denied() }
    finally { stop?.(); busy = false }
  }
  const adapter = Object.freeze({ inspect: options => operate(undefined, options),
    changeUsername: (input, options) => input ? operate(input, options) : Promise.resolve(denied()) })
  adapters.set(client, { base: config.base, adapter })
  return adapter
}

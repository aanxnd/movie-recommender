import { captureCredentialFence, getBrowserSupabaseClient, watchCredentialChanges } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createAuthenticatedApi } from './auth-api.js'
import { createNativeMfa } from './mfa-service.js'
import { nativeUuid } from './password-evidence.js'
import { pendingDeletion } from './removal-contract.js'
export { pendingDeletion }

const result = status => Object.freeze({ status })

export function createAccountDeletion(config, { reviewed = false } = {}) {
  if (reviewed !== true) return pendingDeletion
  const client = getBrowserSupabaseClient(config), session = getSessionController(client)
  const api = createAuthenticatedApi({ ...config, session }), mfa = createNativeMfa(config)
  let busy = false
  return Object.freeze({ available: true, inspect: () => mfa.inspect(),
    async deleteAccount(input, { signal } = {}) {
      if (!input || Object.keys(input).some(k => !['password', 'confirmation', 'requestId', 'factorId', 'code'].includes(k)) ||
          input.confirmation !== 'PERMANENTLY DELETE MY ACCOUNT' || !nativeUuid(input.requestId) ||
          typeof input.password !== 'string' || !input.password || input.password.length > 1024 ||
          (input.factorId !== undefined && (!nativeUuid(input.factorId) || typeof input.code !== 'string' || !/^[0-9]{6}$/.test(input.code))) ||
          (input.code !== undefined && input.factorId === undefined)) return result('invalid')
      if (busy) return result('busy')
      busy = true
      const epoch = new AbortController()
      let stop
      try {
        return await session.withAccess(async lease => {
          const fence = captureCredentialFence(client)
          stop = watchCredentialChanges(client, () => epoch.abort())
          const combined = AbortSignal.any([epoch.signal, signal].filter(Boolean))
          const current = () => { lease.assertCurrent(); fence(); if (combined.aborted) throw new Error('Cancelled') }
          current()
          try {
            const reply = await api('/auth/deletion', { access: 'authenticated', method: 'POST', signal: combined,
              body: { request_id: input.requestId, password: input.password, confirmation: input.confirmation,
                ...(input.factorId ? { factor_id: input.factorId, code: input.code } : {}) } })
            current()
            return result(reply?.status === 'pending' && Object.keys(reply).join(',') === 'status' ? 'pending' : 'uncertain')
          } catch (error) {
            current()
            return result(error?.status === 401 ? 'reauthentication-required' : error?.status === 429 ? 'rate-limited' : 'uncertain')
          }
        })
      } catch { return result('cancelled') }
      finally { stop?.(); busy = false }
    },
  })
}

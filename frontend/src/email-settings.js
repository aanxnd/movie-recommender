// Native account evidence only; never backend profile authorization. No raw addresses escape.
import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { passwordEvidence as nativeEvidence, passwordFailure, passwordResult as outcome, denyPassword } from './password-evidence.js'
import { withFreshPassword } from './password-reauthentication.js'
import { consumePkceCallback, callbackResult } from './pkce-callback.js'

const busy = new WeakSet()
const address = value => typeof value === 'string' && value.length <= 320 && /^[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+$/.test(value)
function timestamp(value) {
  if (typeof value !== 'string' || value.length > 64) return false
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(Z|[+-](\d{2}):(\d{2}))$/.exec(value)
  if (!m) return false
  const [year, month, day, hour, minute, second] = m.slice(1, 7).map(Number)
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return year > 0 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1] &&
    hour <= 23 && minute <= 59 && second <= 59 && (m[7] === 'Z' || (+m[8] <= 23 && +m[9] <= 59)) &&
    Number.isFinite(Date.parse(value)) && Date.parse(value) <= Date.now()
}

async function readEmail(client, proof, lease, signal) {
  const { data, error } = await client.auth.getUser(lease.authorization.slice(7))
  proof.assertCurrent()
  if (signal?.aborted) denyPassword('cancelled')
  const user = data?.user, pending = user && Object.hasOwn(user, 'new_email') ? user.new_email : ''
  if (error || user?.id !== proof.subject || user?.is_anonymous !== false || !address(user.email) ||
      (pending !== '' && (!address(pending) || pending === user.email)) ||
      ('email_change_sent_at' in user && !timestamp(user.email_change_sent_at))) denyPassword('unavailable')
  if (user.email_confirmed_at === null || user.email_confirmed_at === undefined) return outcome('current-unconfirmed')
  if (!timestamp(user.email_confirmed_at)) denyPassword('unavailable')
  return outcome(pending ? 'change-pending' : 'current-confirmed')
}

export function createNativeEmailSettings(config = {}) {
  let attempt
  const configured = () => {
    const client = getBrowserSupabaseClient(config)
    return { client, session: getSessionController(client) }
  }
  return Object.freeze({
    async inspect({ signal } = {}) {
      try {
        const { client, session } = configured()
        return await session.withAccess(async lease => readEmail(client,
          await nativeEvidence(client, config, lease), lease, signal))
      } catch (error) { return passwordFailure(error) }
    },
    async requestChange(currentPassword, email, options = {}) {
      let client, session, generation, acquired = false, attempted = false
      if (!address(email) || typeof currentPassword !== 'string' || !currentPassword) return outcome('invalid')
      try {
        ;({ client, session } = configured()); generation = session.getSnapshot().generation
        if (busy.has(client)) return outcome('busy')
        busy.add(client); acquired = true
        if (options.signal?.aborted) denyPassword('cancelled')
        return await withFreshPassword(client, config, session, currentPassword, options, proof =>
          session.withAccess(async lease => {
            const state = await readEmail(client, proof, lease, options.signal)
            if (state.status !== 'current-confirmed') return state // Never replace pending links silently.
            attempted = true
            await runCredentialRequest(client, () => client.auth.updateUser({ email }, { emailRedirectTo: config.appOrigin + '/' }),
              { signal: options.signal, subject: proof.subject, assertCurrent: proof.assertCurrent })
            proof.assertCurrent()
            // Accepted/duplicate/limited/rejected/uncertain updates have identical conditional guidance.
            return outcome('check-email')
          }), 'email-change')
      } catch (error) {
        if (options.signal?.aborted || (session && session.getSnapshot().generation !== generation)) return outcome('cancelled')
        return attempted ? outcome('check-email') : passwordFailure(error)
      } finally { if (acquired) busy.delete(client) }
    },
    confirm() {
      return attempt ??= consumePkceCallback(config, 'email-change', async (client, data) => {
        if (data.redirectType !== null || !data.session || data.user?.id !== data.session.user?.id) return callbackResult('unproven')
        try {
          const session = getSessionController(client)
          return await session.withAccess(async lease => {
            const proof = await nativeEvidence(client, config, lease, 'email_change', data.session.access_token)
            const result = await readEmail(client, proof, lease)
            return Object.freeze({ ...callbackResult(result.status), generation: session.getSnapshot().generation })
          })
        } catch (error) { return callbackResult(passwordFailure(error).status) }
      })
    },
  })
}

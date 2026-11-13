// Internal callback boundary shared by signup and recovery; never mount from startup.
import { getBrowserSupabaseClient, runCredentialRequest } from './supabase-client.js'

const handled = new WeakMap()
const codePattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
export const callbackResult = status => Object.freeze({ status, destination: '/' })
export const callbackFailure = error => callbackResult(error?.status === 429 ? 'rate-limited' :
  ['otp_expired', 'flow_state_expired', 'flow_state_not_found'].includes(error?.code) ? 'expired' :
  error?.status === 0 || error?.status >= 500 ? 'unavailable' : 'invalid')

// complete is trusted module code, not a caller/URL assertion. Store only its safe result.
export function consumePkceCallback(config, purpose, complete, prepare) {
  const browser = config.browser ?? globalThis.window
  if (!browser || typeof browser !== 'object') return Promise.resolve(callbackResult('unavailable'))
  const previous = handled.get(browser)
  if (previous) return previous.purpose === purpose ? previous.promise : Promise.resolve(callbackResult('invalid'))
  let url
  try {
    url = new URL(browser.location.href)
    browser.history.replaceState(null, '', '/') // Synchronous, before SDK construction/I/O.
  } catch { return Promise.resolve(callbackResult('unavailable')) }
  const promise = (async () => {
    let release
    try {
      if (!url.search && !url.hash) return callbackResult('missing')
      if (url.href.length > 4096 || url.origin !== config.appOrigin || url.pathname !== '/' || url.hash ||
          [...url.searchParams].length !== 1 || !codePattern.test(url.searchParams.get('code'))) return callbackResult('invalid')
      const client = getBrowserSupabaseClient(config)
      if (prepare) release = await prepare(client) // Trusted scheduling only, never authentication evidence.
      const { data, error } = await runCredentialRequest(client, () => client.auth.exchangeCodeForSession(url.searchParams.get('code')))
      if (error) return callbackFailure(error)
      return await complete(client, data)
    } catch { return callbackResult('unavailable') }
    finally { release?.() }
  })()
  handled.set(browser, { purpose, promise }) // Failures are once-only too; no raw session retained here.
  return promise
}

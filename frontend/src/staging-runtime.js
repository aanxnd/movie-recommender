// Explicit staging bootstrap only; production main.jsx never imports this.
import { getBrowserSupabaseClient } from './supabase-client.js'
import { getSessionController } from './auth-session.js'
import { createAuthActions } from './auth-actions.js'
import { createPasswordServices } from './password-services.js'
import { createStagingCallback } from './staging-callback.js'
import { createNativeEmailSettings } from './email-settings.js'
import { createNativeMfa } from './mfa-service.js'
import { createNativeMfaRecovery } from './mfa-recovery.js'
import { createProfileProvisioning } from './profile-adapter.js'
import { createStagingMovieApi } from './staging-movie-api.js'

export function createStagingRuntime(config) {
  const browser = config.browser ?? globalThis.window
  if (config.appOrigin !== 'http://127.0.0.1:5173' || browser.location.origin !== config.appOrigin || config.base !== '/api') {
    browser.history.replaceState(null, '', '/')
    throw new Error('Approved local staging configuration required')
  }
  // Valid callbacks scrub synchronously before SDK construction or provider I/O.
  const callback = createStagingCallback(config), callbackResult = callback.confirm()
  const client = getBrowserSupabaseClient(config), session = getSessionController(client)
  const stop = session.subscribe(() => {}) // Bootstrap lease; same singleton, not a second state manager.
  const profile = createProfileProvisioning(config), passwords = createPasswordServices(config)
  const mfa = createNativeMfa(config), recovery = createNativeMfaRecovery(config)
  return Object.freeze({ session, callbackResult, actions: createAuthActions(config), profile,
    passwords: Object.freeze({ ...passwords, recovery: callback }), email: createNativeEmailSettings(config), mfa, recovery,
    movies: createStagingMovieApi({ ...config, session }),
    account: Object.freeze({
      async inspect(options) {
        const result = await profile.inspect(options)
        return result.status === 'complete' ? Object.freeze({ status: 'ready', username: result.username, revision: 'read-only' }) :
          Object.freeze({ status: 'unavailable' })
      },
      changeUsername: async () => Object.freeze({ status: 'unavailable' }), // No invented update/version endpoint.
    }),
    stop() { mfa.cancel(); recovery.cancel(); stop(); return client.auth.stopAutoRefresh() },
  })
}

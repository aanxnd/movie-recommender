import { createStagingRecoveryConsumer } from './password-recovery.js'
import { inspectEmailCallback } from './email-settings.js'
import { getSessionController } from './auth-session.js'

async function restored(client) {
  const session = getSessionController(client)
  let stop, timer
  try {
    await new Promise((resolve, reject) => {
      const check = () => {
        const state = session.getSnapshot()
        if (['authenticated', 'unauthenticated'].includes(state.status) && !state.logoutOutcome) resolve()
        else if (!['restoring', 'refreshing'].includes(state.status)) reject(new Error('Callback preparation rejected'))
      }
      timer = setTimeout(() => reject(new Error('Callback preparation unavailable')), 15000)
      stop = session.subscribe(check); check()
    })
    return stop // Hold the existing controller through redemption, then release.
  } catch (error) { stop?.(); throw error }
  finally { clearTimeout(timer) }
}

// One root PKCE redemption. No URL flow selector, second token store or raw SDK
// response reaches React. Recovery keeps its existing private one-use continuation.
export function createStagingCallback(config) {
  return createStagingRecoveryConsumer(config, async (client, data) => {
    if (data.redirectType !== null) return Object.freeze({ status: 'invalid', flow: 'confirmation' })
    const email = await inspectEmailCallback(config, client, data)
    if (['current-confirmed', 'current-unconfirmed', 'change-pending'].includes(email.status))
      return Object.freeze({ status: email.status, flow: 'email-change' })
    // Signup, OAuth and magic link share null. Never call any of them confirmed
    // from a historical marker; the backend current-email policy is independent.
    return Object.freeze({ status: 'unproven', flow: 'confirmation' })
  }, restored)
}

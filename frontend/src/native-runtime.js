import { composeNativeRuntime } from './staging-runtime.js'
import { createAccountSettings } from './account-settings-adapter.js'

export function exactHttpsOrigin(value) {
  try { const url = new URL(value); return typeof value === 'string' && url.protocol === 'https:' &&
    url.origin === value && !url.username && !url.password && !value.includes('*') } catch { return false }
}

// Configuration is compiled from reviewed targets, never URL/local-storage claims.
export function createNativeRuntime(config, targets) {
  const browser = config.browser ?? globalThis.window
  if (targets?.approved !== true || targets.mode !== 'native-release' ||
      !exactHttpsOrigin(targets.frontend_origin) || !exactHttpsOrigin(targets.api_origin) ||
      targets.frontend_origin === targets.api_origin || browser.location.origin !== targets.frontend_origin ||
      config.appOrigin !== targets.frontend_origin || config.base !== targets.api_origin ||
      config.projectUrl !== targets.supabase_url || !/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(targets.supabase_url)) {
    browser.history.replaceState(null, '', '/')
    throw new Error('Approved native configuration required')
  }
  const runtime = composeNativeRuntime(config)
  return Object.freeze({ ...runtime, account: createAccountSettings(config) })
}

import { composeNativeRuntime } from './staging-runtime.js'

export function createPrivateRuntime(config, targets) {
  const browser = config.browser ?? globalThis.window
  if (targets?.approved !== true || config.mode !== 'private-stage23' ||
      !/^https:\/\/[a-z0-9-]+\.vercel\.app$/.test(targets.frontend_origin) ||
      config.appOrigin !== targets.frontend_origin || browser.location.origin !== targets.frontend_origin ||
      targets.supabase_url !== 'https://jsbulnrcxtvslvvxjizq.supabase.co' ||
      config.projectUrl !== targets.supabase_url || config.base !== '/api') {
    browser.history.replaceState(null, '', '/')
    throw new Error('Approved private configuration required')
  }
  return composeNativeRuntime(config)
}

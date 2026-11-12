import assert from 'node:assert/strict'
import { passwordFixture, signingFixture, json, subject } from './password-test-support.js'
import { createNativeMfa } from './mfa-service.js'

export const factorId = 'aaaaaaaa-1234-4234-9234-123456789abc'
export const secondId = 'bbbbbbbb-1234-4234-9234-123456789abc'
export const challengeId = 'cccccccc-1234-4234-9234-123456789abc'
export const totp = (status = 'verified', id = factorId) => ({ id, factor_type: 'totp', status, friendly_name: 'Personal phone' })
export async function mfaFixture(t, options = {}) {
  const keys = await signingFixture(), first = await keys.sign({ aal: options.aal ?? 'aal1' }, 'password')
  const promoted = await keys.sign({ aal: 'aal2' }, 'totp')
  const state = { factors: options.factors ?? [totp()], promoted, actions: [], handler: options.handler }
  const f = await passwordFixture(t, async (url, init) => {
    if (url.pathname.endsWith('/jwks.json')) return json(keys.jwks)
    if (url.pathname.endsWith('/user')) return json({
      id: keys.users.get(init.headers?.get?.('Authorization')?.slice(7) ?? init.headers?.Authorization?.slice(7))?.id ?? subject,
      is_anonymous: false, factors: state.factors })
    state.actions.push({ path: url.pathname, method: init.method })
    const response = await state.handler?.(url, init, state)
    if (response) return response
    if (url.pathname.endsWith('/challenge')) return json({ id: challengeId, type: 'totp', expires_at: Math.floor(Date.now()/1000)+120 })
    if (url.pathname.endsWith('/verify')) return json(state.promoted)
    return json({ message: 'unsupported offline operation' }, 400)
  })
  assert.equal((await f.client.auth.setSession(first)).error, null)
  const service = createNativeMfa(f.config)
  t.after(() => service.cancel())
  return { ...f, ...keys, state, first, service }
}

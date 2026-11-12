import test from 'node:test'
import assert from 'node:assert/strict'
import { fixture, tick, value } from './auth-test-support.js'

test('a delayed refresh promise cannot restore AAL1 after native MFA promotion', async () => {
  const f = fixture(), stop = f.session.subscribe(() => {})
  try {
    f.load.resolve({ data: { session: value() } }); await tick()
    const refresh = f.session.refresh().catch(() => {})
    await tick()
    f.emit('MFA_CHALLENGE_VERIFIED', { ...value(), access_token: 'new-native-mfa-token', expires_in: 3600 })
    f.renewal.resolve({ data: { session: value() } }); await refresh
    assert.equal(await f.session.withAccess(lease => lease.authorization), 'Bearer new-native-mfa-token')
    assert.equal(f.counts.subscriptions, 1)
  } finally { stop() }
})

for (const session of [{ ...value('foreign'), expires_in: 3600 }, { ...value(), expires_in: null }, null])
  test('malformed or cross-subject MFA event fails closed', async () => {
    const f = fixture(), stop = f.session.subscribe(() => {})
    try {
      f.load.resolve({ data: { session: value() } }); await tick()
      f.emit('MFA_CHALLENGE_VERIFIED', session)
      await assert.rejects(f.session.withAccess(() => true))
    } finally { stop() }
  })

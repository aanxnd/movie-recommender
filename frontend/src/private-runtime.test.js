import test from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { createPrivateRuntime } from './private-runtime.js'
import { tick } from './auth-test-support.js'

const origin = 'https://owner-preview.vercel.app', project = 'https://jsbulnrcxtvslvvxjizq.supabase.co'
const targets = { approved: true, frontend_origin: origin, supabase_url: project }
function fixture(t) {
  const dom = new JSDOM('', { url: origin + '/?code=private&next=https://evil.invalid' })
  t.after(() => dom.window.close())
  return { appOrigin: origin, projectUrl: project, publishableKey: 'sb_publishable_offline',
    mode: 'private-stage23', base: '/api', browser: dom.window, fetcher: () => assert.fail('Unexpected hosted I/O') }
}
test('private bootstrap uses the same fenced callback/session and preserves legacy storage', async t => {
  const config = fixture(t); config.browser.localStorage.setItem('movelle.identity.v1', 'legacy-private')
  const runtime = createPrivateRuntime(config, targets); t.after(() => runtime.stop())
  assert.equal((await runtime.callbackResult).status, 'invalid')
  assert.equal(config.browser.location.href, origin + '/')
  for (let i = 0; i < 20 && runtime.session.getSnapshot().status === 'restoring'; i++) await tick()
  assert.equal(runtime.session.getSnapshot().status, 'unauthenticated')
  assert.equal(config.browser.localStorage.getItem('movelle.identity.v1'), 'legacy-private')
  assert.equal((await runtime.account.changeUsername()).status, 'unavailable')
})
test('unapproved mode/origin/project/transport scrubs without provider calls', t => {
  for (const change of [{ mode: 'production' }, { appOrigin: 'https://evil.vercel.app' },
    { projectUrl: 'https://' + 'a'.repeat(20) + '.supabase.co' }, { base: 'https://evil.invalid' }]) {
    const config = fixture(t)
    assert.throws(() => createPrivateRuntime({ ...config, ...change }, targets), /^Error: Approved private configuration required$/)
    assert.equal(config.browser.location.href, origin + '/')
    assert.equal(config.browser.localStorage.length, 0)
  }
  const config = fixture(t)
  assert.throws(() => createPrivateRuntime(config, { ...targets, approved: false }))
})

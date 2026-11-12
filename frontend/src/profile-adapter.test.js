import assert from 'node:assert/strict'
import test from 'node:test'
import { createProfileProvisioning } from './profile-adapter.js'
import { passwordFixture, syntheticSession, json, subject, otherSubject } from './password-test-support.js'
import { deferred, tick } from './auth-test-support.js'

async function setup(t, api) {
  const writes = [], requests = []
  const f = await passwordFixture(t, async (url, init) => {
    if (url.pathname === '/auth/v1/user') return json({ id: subject })
    assert.equal(url.origin, 'https://backend.test')
    assert.equal(url.pathname, '/auth/profile'); assert.equal(url.search, '')
    assert.equal(init.credentials, 'omit'); assert.equal(init.redirect, 'error')
    assert.equal(init.cache, 'no-store'); assert.equal(init.referrerPolicy, 'no-referrer')
    assert.match(init.headers.Authorization, /^Bearer /)
    requests.push(init.method)
    if (init.method === 'POST') writes.push(JSON.parse(init.body))
    return api(init)
  })
  await f.client.auth.setSession({ access_token: syntheticSession().access_token, refresh_token: 'synthetic-refresh' })
  await tick()
  const config = { ...f.config, base: 'https://backend.test' }, service = createProfileProvisioning(config)
  return { ...f, config, service, writes, requests }
}

test('explicit creation sends only username; shared SDK/controller/transport, no second token store', async t => {
  const f = await setup(t, init => json(init.method === 'POST' ? { status: 'complete', username: 'Alice' } : { status: 'eligible' }))
  assert.equal(createProfileProvisioning(f.config), f.service)
  assert.deepEqual(await f.service.inspect(), { status: 'eligible' }); assert.equal(f.writes.length, 0)
  assert.deepEqual(await f.service.provision({ username: 'Alice' }), { status: 'complete', username: 'Alice' })
  assert.deepEqual(f.writes, [{ username: 'Alice' }]); assert.equal(f.logs.length, 0)
  assert.equal(f.dom.window.localStorage.length, 1)
})

test('already-provisioned server spelling is authoritative; no frontend rename or IDs', async t => {
  const f = await setup(t, () => json({ status: 'complete', username: 'Original' }))
  assert.equal((await f.service.inspect()).username, 'Original')
  assert.equal((await f.service.provision({ username: 'NewName' })).username, 'Original')
  for (const input of [{ username: 'Alice', subject }, { username: 'Alice', user_id: 7 },
    { username: 'ADMIN' }, { username: 'éabc' }, null, []])
    assert.equal((await f.service.provision(input)).status, 'unavailable')
  assert.equal(f.writes.length, 1)
})

test('simultaneous consumer clicks share one in-flight write', async t => {
  const pending = deferred(), f = await setup(t, () => pending.promise)
  const first = f.service.provision({ username: 'Alice' }); await tick()
  assert.equal((await createProfileProvisioning(f.config).provision({ username: 'Other' })).status, 'busy')
  pending.resolve(json({ status: 'complete', username: 'Alice' }))
  assert.equal((await first).status, 'complete'); assert.equal(f.writes.length, 1)
})

for (const [code, status] of [[401, 'unavailable'], [403, 'unavailable'], [409, 'username-taken'], [422, 'unavailable'], [429, 'rate-limited']]) {
  test('known sanitized rejection is not replayed: ' + code, async t => {
    const f = await setup(t, () => json({ detail: 'private diagnostics' }, code))
    assert.deepEqual(await f.service.provision({ username: 'Alice' }), { status })
    assert.deepEqual(f.requests, ['POST']); assert.equal(f.logs.length, 0)
  })
}

for (const observed of ['complete', 'eligible', 'failure']) {
  test('lost commit acknowledgement uses GET only: ' + observed, async t => {
    const f = await setup(t, init => {
      if (init.method === 'POST') throw new Error('private transport failure')
      return json(observed === 'complete' ? { status: 'complete', username: 'Original' } : { status: observed }, observed === 'failure' ? 503 : 200)
    })
    assert.deepEqual(await f.service.provision({ username: 'Alice' }), observed === 'complete' ?
      { status: 'complete', username: 'Original' } : { status: 'uncertain' })
    assert.deepEqual(f.requests, ['POST', 'GET']); assert.equal(f.writes.length, 1)
    assert.equal(f.logs.length, 0)
  })
}

for (const change of ['logout', 'ABA', 'refresh', 'abort']) {
  test('stale creation result is fenced: ' + change, async t => {
    const pending = deferred(), f = await setup(t, () => pending.promise), abort = new AbortController()
    const work = f.service.provision({ username: 'Alice' }, { signal: abort.signal }); await tick()
    if (change === 'logout') await f.session.logout()
    if (change === 'abort') abort.abort()
    if (change === 'ABA') {
      // Real SDK events drive the shared controller, including account A→B→A.
      await f.client.auth._notifyAllSubscribers('SIGNED_IN', { ...syntheticSession(otherSubject), expires_at: Date.now()/1000+600 })
      await f.client.auth._notifyAllSubscribers('SIGNED_IN', { ...syntheticSession(), expires_at: Date.now()/1000+600 })
    }
    if (change === 'refresh') await f.client.auth._notifyAllSubscribers('TOKEN_REFRESHED', { ...syntheticSession(), expires_at: Date.now()/1000+600 })
    pending.resolve(json({ status: 'complete', username: 'Stale' }))
    assert.equal((await work).status, 'cancelled'); assert.deepEqual(f.requests, ['POST'])
  })
}

test('malformed success cannot expose IDs, private claims or authorization', async t => {
  const f = await setup(t, () => json({ status: 'complete', username: 'Alice', user_id: 7, subject }))
  assert.deepEqual(await f.service.provision({ username: 'Alice' }), { status: 'unavailable' })
  assert.equal(f.logs.length, 0)
})

test('signed-out adapter never uses a legacy credential fallback', async t => {
  const f = await setup(t, () => assert.fail('Unexpected API call'))
  f.dom.window.localStorage.setItem('legacy-profile', 'private-legacy-value')
  await f.session.logout()
  assert.equal((await f.service.provision({ username: 'Alice' })).status, 'unavailable')
  assert.equal(f.dom.window.localStorage.getItem('legacy-profile'), 'private-legacy-value')
  assert.deepEqual(f.requests, [])
})

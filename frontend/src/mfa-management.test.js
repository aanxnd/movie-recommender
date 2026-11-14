import test from 'node:test'
import assert from 'node:assert/strict'
import { mfaFixture, factorId, secondId, totp } from './mfa-test-support.js'
import { json, otherSubject } from './password-test-support.js'
import { deferred } from './auth-test-support.js'

const secret = 'JBSWY3DPEHPK3PXP'
const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><path fill="#000" d="M0 0h10v10H0z"/></svg>'
const enrolled = () => ({ id: secondId, type: 'totp', totp: { secret,
  qr_code: svg, uri: 'otpauth://totp/Movelle:offline?secret=' + secret + '&issuer=Movelle' } })
async function enrollmentFixture(t, options = { aal: 'aal2' }) {
  const f = await mfaFixture(t, options)
  f.state.handler = (url, init) => {
    if (url.pathname.endsWith('/factors')) {
      const request = JSON.parse(init.body)
      assert.equal(request.factor_type, 'totp')
      assert.match(request.friendly_name, /^Movelle authenticator [0-9a-f]{8}$/)
      f.state.factors ??= []
      f.state.factors.push(totp('unverified', secondId)); return json(enrolled())
    }
  }
  return f
}

test('additional native enrollment retains only temporary, explicitly presented credentials', async t => {
  const f = await enrollmentFixture(t)
  const result = await f.service.enroll()
  assert.equal(result.status, 'setup-pending')
  assert.doesNotMatch(JSON.stringify(result), /JBSWY|svg|otpauth/)
  let visible, cleared = 0
  f.service.presentSetup(value => { visible = value; return () => { visible = undefined; cleared++ } })
  assert.equal(visible.secret, secret)
  assert.match(visible.qr, /^data:image\/svg\+xml;charset=utf-8,%3Csvg/)
  assert.equal((await f.service.enroll()).status, 'unavailable')
  assert.equal(f.state.actions.length, 1)
  f.service.cancel(); assert.equal(visible, undefined); assert.equal(cleared, 1)
  assert.ok(!(f.dom.window.localStorage.getItem('movelle.signup-confirmation') ?? '').includes(secret))
})

for (const change of ['logout', 'refresh', 'account ABA', 'verify'])
  test('setup credentials cleared on ' + change, async t => {
    const f = await enrollmentFixture(t)
    assert.equal((await f.service.enroll()).status, 'setup-pending')
    let visible = true
    f.service.presentSetup(() => () => { visible = false })
    if (change === 'logout') await f.session.logout()
    if (change === 'refresh') await f.client.auth.setSession(f.first)
    if (change === 'account ABA') {
      await f.client.auth.setSession(await f.sign({ sub: otherSubject }, 'password'))
      await f.client.auth.setSession(f.first)
    }
    if (change === 'verify') {
      f.state.handler = url => { if (url.pathname.endsWith('/verify')) f.state.factors = [totp(), totp('verified', secondId)] }
      assert.equal((await f.service.verify(secondId, '123456')).status, 'verified')
    }
    assert.equal(visible, false)
  })

for (const [name, change] of [
  ['HTML injection', d => { d.totp.qr_code += '<script>alert(1)</script>' }],
  ['external reference', d => { d.totp.qr_code = '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.invalid"/></svg>' }],
  ['event handler', d => { d.totp.qr_code = d.totp.qr_code.replace('<path ', '<path onload="alert(1)" ') }],
  ['bad secret', d => { d.totp.secret = 'not-a-secret' }],
  ['wrong URI', d => { d.totp.uri = 'https://evil.invalid/' }],
  ['secret mismatch', d => { d.totp.uri = d.totp.uri.replace(secret, 'AAAAAAAAAAAAAAAA') }],
  ['wrong type', d => { d.type = 'phone' }],
]) test('setup rejects ' + name, async t => {
  const f = await enrollmentFixture(t), data = enrolled(); change(data)
  f.state.handler = () => json(data)
  assert.notEqual((await f.service.enroll()).status, 'setup-pending')
  let exposed = false; f.service.presentSetup(() => { exposed = true; return () => {} })
  assert.equal(exposed, false)
  assert.deepEqual(f.logs, [])
})

for (const [name, factors, aal] of [
  ['null inventory', null, 'aal1'], ['stale empty AAL2', [], 'aal2'],
  ['AAL1', [totp()], 'aal1'], ['pending factor', [totp(), totp('unverified', secondId)], 'aal2'],
]) test('enrollment eligibility fails closed: ' + name, async t => {
  const f = await mfaFixture(t, { aal }); f.state.factors = factors
  assert.notEqual((await f.service.enroll()).status, 'setup-pending')
  assert.deepEqual(f.state.actions, [])
})

for (const omitted of [false, true]) test('first TOTP setup and signed AAL2 verification: omitted=' + omitted, async t => {
  const f = await enrollmentFixture(t, { aal: 'aal1', factors: [] })
  if (omitted) f.state.factors = undefined
  assert.equal((await f.service.inspect()).status, 'not-enrolled')
  assert.equal((await f.service.enroll()).status, 'setup-pending')
  assert.equal((await f.service.enroll()).status, 'unavailable')
  f.state.handler = url => {
    if (url.pathname.endsWith('/verify')) f.state.factors = [totp('verified', secondId)]
  }
  assert.equal((await f.service.verify(secondId, '123456')).status, 'verified')
  assert.deepEqual(f.state.actions.map(x => x.path.split('/').pop()), ['factors', 'challenge', 'verify'])
  assert.deepEqual(f.logs, [])
})

test('uncertain enrollment never automatically repeats after cancellation', async t => {
  const wait = deferred(), started = deferred(), f = await enrollmentFixture(t)
  f.state.handler = () => { started.resolve(); return wait.promise }
  const pending = f.service.enroll(); await started.promise
  assert.equal((await f.service.enroll()).status, 'busy')
  f.service.cancel(); wait.resolve(json(enrolled()))
  assert.notEqual((await pending).status, 'setup-pending')
  assert.equal((await f.service.enroll()).status, 'unavailable')
  assert.equal(f.state.actions.length, 1)
})

for (const [name, factors, aal, selection] of [
  ['two verified', [totp(), totp('verified', secondId)], 'aal2', secondId],
  ['abandoned pending', [totp(), totp('unverified', secondId)], 'aal2', secondId],
  ['final usable', [totp(), totp('unverified', secondId)], 'aal2', factorId],
  ['last factor', [totp()], 'aal2', factorId],
  ['AAL1', [totp(), totp('verified', secondId)], 'aal1', secondId],
  ['foreign', [totp(), totp('verified', secondId)], 'aal2', 'foreign'],
  ['unknown', [], 'aal2', factorId],
]) test('native removal: ' + name, async t => {
  const f = await mfaFixture(t, { factors, aal, handler: (url, init, state) => {
    if (init.method === 'DELETE') { state.factors = state.factors.filter(x => x.id !== selection); return json({ id: selection }) }
  } })
  const result = await f.service.remove(selection)
  assert.equal(result.status, 'removal-unavailable')
  assert.equal(f.state.actions.length, 0)
})

for (const name of ['provider error', 'unchanged inventory', 'cancelled response'])
  test('removal never claims success on ' + name, async t => {
    const f = await mfaFixture(t, { aal: 'aal2', factors: [totp(), totp('verified', secondId)] })
    f.state.handler = () => {
      if (name === 'cancelled response') f.service.cancel()
      return name === 'provider error' ? json({ message: secret }, 500) : json({ id: secondId })
    }
    assert.equal((await f.service.remove(secondId)).status, 'removal-unavailable')
    assert.equal(f.state.actions.length, 0)
  })

test('concurrent removals cannot dispatch DELETE, even if the provider would delete every factor', async t => {
  const f = await mfaFixture(t, { aal: 'aal2', factors: [totp(), totp('verified', secondId)],
    handler: () => { throw new Error('unsafe deletion reached provider') } })
  const results = await Promise.all([f.service.remove(factorId), f.service.remove(secondId)])
  assert.deepEqual(results, [{ status: 'removal-unavailable' }, { status: 'removal-unavailable' }])
  await f.session.logout()
  assert.equal((await f.service.remove(factorId)).status, 'removal-unavailable')
  assert.deepEqual(f.state.actions, [])
})

import { useEffect, useId, useRef, useState } from 'react'
import { AuthFrame, AuthNotice } from './account-screens.jsx'
import { useFormScope } from './password-screens.jsx'
import { containDialogFocus } from './dialog.js'
import './account-settings.css'
import './mfa-screens.css'

const messages = {
  'inventory-unknown': 'Authenticator information is incomplete. Setup and account continuation are unavailable here.',
  stale: 'The account evidence changed. Check again before continuing.',
  unavailable: 'The operation could not be confirmed. It may have reached the service. Check your authenticators before trying again.',
  cancelled: 'This step was cancelled. Check your current session before continuing.',
  expired: 'This authenticator step expired. Enter a fresh code and try again.',
  'invalid-code': 'The code was not accepted. Enter a fresh six-digit code from your authenticator.',
  'rate-limited': 'Too many attempts. Wait before trying again.',
  busy: 'Another security request is in progress. Please wait.',
  removed: 'The authenticator was removed. Another verified authenticator remains.',
  verified: 'This session passed native MFA verification. Protected features still require the server’s checks.',
  pending: 'An authenticator is not verified yet. Enrollment alone does not enable MFA.',
  'setup-pending': 'Setup is not complete. Add this key to your app, then enter its code.',
  'challenge-required': 'Enter a code from one of your verified authenticators to continue.',
}

function SetupCredentials({ service }) {
  const image = useRef(null), manual = useRef(null), incarnation = useRef(0), [visible, setVisible] = useState(false)
  useEffect(() => {
    const ticket = ++incarnation.current
    const img = image.current, key = manual.current
    const clear = () => { img?.removeAttribute('src'); if (key) key.textContent = ''; setVisible(false) }
    const release = service?.presentSetup?.(({ qr, secret }) => {
      img.src = qr; key.textContent = secret; setVisible(true)
      return clear
    })
    return () => {
      clear() // DOM clears synchronously; Strict Mode's immediate effect remount may reuse private setup.
      queueMicrotask(() => { if (ticket === incarnation.current) release?.() })
    }
  }, [service])
  return <section className="mfa-setup" aria-label="Temporary authenticator setup">
    <h2>Add to your authenticator</h2>
    <p>Use Google Authenticator, Duo Mobile or another standard TOTP app. Keep this setup key private.</p>
    <img ref={image} className="mfa-qr" alt="Authenticator setup QR code" referrerPolicy="no-referrer" hidden={!visible} />
    <details><summary>Enter the setup key manually</summary><code ref={manual} className="mfa-secret" /></details>
    {!visible && <p role="status">Setup credentials are no longer available here. An unverified factor may remain.</p>}
  </section>
}

// Explicit trusted bootstrap only. Service results are presentation, never backend grants.
export function MfaScreen({ service, login = false }) {
  const f = useFormScope(), id = useId(), dialog = useRef(null), epoch = useRef(0)
  const [view, setView] = useState(null), [selection, setSelection] = useState(''), [removal, setRemoval] = useState(null)
  const authenticated = f.auth.status === 'authenticated'
  const usable = view && ['verified', 'challenge-required', 'pending', 'setup-pending'].includes(view.status)
  const apply = result => {
    const positive = ['verified', 'challenge-required', 'pending', 'setup-pending'].includes(result?.status)
    if (!positive) {
      setView({ status: messages[result?.status] ? result.status : 'unavailable', factors: [] }); return
    }
    if (result.generation !== f.auth.generation || !Array.isArray(result.factors) || !result.factors.length ||
        result.factors.length > 10 || result.factors.some(x => !x || typeof x.id !== 'string' ||
          typeof x.label !== 'string' || !['verified', 'unverified'].includes(x.status))) {
      setView({ status: 'stale', factors: [] }); return
    }
    setView(result)
    setSelection(result.factors.find(x => x.status === (result.status === 'setup-pending' ? 'unverified' : 'verified'))?.id ?? result.factors[0]?.id ?? '')
  }
  useEffect(() => {
    const ticket = ++epoch.current
    setView(null); setSelection(''); setRemoval(null)
    if (authenticated) Promise.resolve().then(() => service?.inspect?.()).then(result => {
      if (ticket === epoch.current) apply(result)
    }, () => { if (ticket === epoch.current) setView({ status: 'unavailable', factors: [] }) })
    return () => { epoch.current++; service?.cancel?.() }
  }, [service, f.auth.generation, authenticated])
  useEffect(() => {
    if (!removal) return
    const element = dialog.current, previous = document.activeElement
    element.showModal(); element.querySelector('[data-cancel]').focus()
    return () => { if (element.open) element.close(); if (previous?.isConnected) previous.focus() }
  }, [removal])
  async function act(kind, value) {
    const scope = f.begin(), ticket = epoch.current
    if (!scope) return
    f.form.current?.reset(); setRemoval(null)
    try {
      const result = await service?.[kind]?.(...(kind === 'verify' ? [selection, value] : kind === 'remove' ? [value] : []), { signal: scope.signal })
      if (scope.signal.aborted || ticket !== epoch.current) return
      const status = messages[result?.status] ? result.status : 'unavailable'
      scope.report(status)
      if (['verified', 'setup-pending', 'removed'].includes(status)) apply({ ...result, status: status === 'removed' ? 'verified' : status })
      else setView({ status, factors: [] })
    } catch { if (!scope.signal.aborted && ticket === epoch.current) { scope.report('unavailable'); setView({ status: 'unavailable', factors: [] }) } }
    finally { scope.finish() }
  }
  async function check() {
    const ticket = ++epoch.current
    service?.cancel?.(); f.form.current?.reset(); f.setStatus(null); setView(null)
    try { const result = await service?.inspect?.(); if (ticket === epoch.current) apply(result) }
    catch { if (ticket === epoch.current) setView({ status: 'unavailable', factors: [] }) }
  }
  const challenge = usable && view.status !== 'verified' && (!login || view.factors.some(x => x.status === 'verified'))
  return <AuthFrame title={login ? 'One more step.' : 'A second layer of care.'}
    description={login ? 'Use your authenticator to finish this session’s security check.' : 'Optional authenticator protection, with you in control.'}>
    <p className="auth-hint">Losing every enrolled authenticator may lock you out. Recovery guidance is a separate reviewed step.</p>
    {!authenticated ? <AuthNotice>Sign in before managing authenticators.</AuthNotice> : <>
      <AuthNotice focus={Boolean(f.status)} error={!usable && Boolean(view)}>
        {messages[f.status] || messages[view?.status] || 'Checking your current authenticator evidence…'}
      </AuthNotice>
      {view?.status === 'setup-pending' && <SetupCredentials service={service} />}
      {usable && <section className="mfa-factors" aria-labelledby={id + '-factors'}>
        <h2 id={id + '-factors'}>Your authenticators</h2>
        <ul>{view.factors.map(factor => <li key={factor.id}><span><strong>{factor.label}</strong><small>{factor.status === 'verified' ? 'Verified factor' : 'Not verified'}</small></span>
          {!login && <button type="button" className="text-link" disabled={f.busy || view.status !== 'verified' ||
            !view.factors.some(other => other.id !== factor.id && other.status === 'verified')}
            onClick={() => setRemoval(factor)}>Review removal</button>}</li>)}</ul>
      </section>}
      {challenge && <form ref={f.form} onSubmit={event => {
        event.preventDefault()
        if (f.form.current.reportValidity()) act('verify', new FormData(f.form.current).get('totp'))
      }} aria-busy={f.busy}>
        <div className="auth-field"><label htmlFor={id + '-factor'}>Authenticator</label>
          <select id={id + '-factor'} value={selection} onChange={event => setSelection(event.target.value)} disabled={f.busy}>
            {view.factors.filter(x => !login || x.status === 'verified').map(x => <option key={x.id} value={x.id}>{x.label} · {x.status}</option>)}
          </select></div>
        <div className="auth-field"><label htmlFor={id + '-code'}>Six-digit authenticator code</label>
          <input id={id + '-code'} name="totp" type="password" inputMode="numeric" autoComplete="one-time-code"
            pattern="[0-9]{6}" minLength={6} maxLength={6} required disabled={f.busy || !selection} /></div>
        <button className="button-primary auth-submit" disabled={f.busy || !selection}>{f.busy ? 'Checking…' : 'Verify authenticator'}</button>
      </form>}
      {!login && usable && <button type="button" className="button-secondary auth-submit" disabled={f.busy || view.status !== 'verified' || view.factors.some(x => x.status !== 'verified')}
        onClick={() => act('enroll')}>Add an authenticator</button>}
      <button type="button" className="text-link auth-submit" disabled={f.busy || !view} onClick={check}>Cancel setup and check again</button>
    </>}
    <dialog ref={dialog} className="account-lifecycle-dialog" aria-labelledby={id + '-remove'} onKeyDown={containDialogFocus}
      onCancel={event => { event.preventDefault(); setRemoval(null) }}>
      <h2 id={id + '-remove'}>Remove this authenticator?</h2><p>{removal?.label}</p>
      <p>This stops that app from verifying new challenges. Another verified factor must remain. Issued tokens may remain valid until expiry.</p>
      <div className="account-review-actions"><button className="button-secondary" data-cancel onClick={() => setRemoval(null)}>Cancel</button>
        <button className="button-primary" disabled={f.busy || !removal} onClick={() => act('remove', removal.id)}>Remove authenticator</button></div>
    </dialog>
  </AuthFrame>
}

export const MfaLoginScreen = props => <MfaScreen {...props} login />

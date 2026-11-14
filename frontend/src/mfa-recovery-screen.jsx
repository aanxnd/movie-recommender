import { useEffect, useId, useRef, useState } from 'react'
import { AuthFrame, AuthNotice } from './account-screens.jsx'
import { SetupCredentials } from './mfa-screens.jsx'
import { useFormScope } from './password-screens.jsx'
import { containDialogFocus } from './dialog.js'

const messages = {
  'not-enrolled': 'No authenticator is enrolled. Optional first setup is available in authenticator settings.',
  'alternative-factor-available': 'Verified authenticators are registered. Choose one you can still access; registration does not prove independent devices.',
  'verified-factor-present': 'One verified authenticator is registered. While you still have access, use authenticator settings to add and verify another on an independently accessible device.',
  'challenge-required': 'Your first-factor session still needs an accessible, already verified authenticator.',
  'alternative-verified': 'Your alternative authenticator passed the native challenge. You can now add a replacement.',
  'replacement-pending': 'Replacement setup is not complete. Add the new key to an independent authenticator and verify its code.',
  'replacement-verified': 'The replacement authenticator is verified. The lost factor has not been removed.',
  'abandoned-enrollment': 'An unverified setup remains. It is not a usable backup. Check your authenticators; no automatic cleanup or recovery is performed here.',
  'recovery-unavailable': 'Self-service recovery is unavailable without an accessible verified authenticator. Password reset or access to email does not remove MFA or prove a second factor. Recovery codes are not available here. We cannot promise an MFA reset or support-assisted recovery.',
  'inventory-unknown': 'Authenticator information is incomplete. Check again; no recovery or setup is authorized here.',
  'reauthentication-required': 'Start again from your current signed-in account. A password or old session alone cannot authorize this recovery.',
  'mutation-uncertain': 'The outcome is uncertain and may have reached the service. Check current authenticator state before any new attempt. Nothing will be replayed automatically.',
  unavailable: 'We could not establish the required account evidence. Check again before continuing.',
  cancelled: 'This step was cancelled. An operation already accepted by the service may still have taken effect.',
  expired: 'This security step expired. Check your current session and enter a fresh authenticator code.',
  'invalid-code': 'That code was not accepted. Enter a fresh six-digit code from the selected authenticator.',
  'rate-limited': 'Too many attempts. Wait before checking or trying again.',
  busy: 'Another security request is in progress. Please wait.',
  'removal-unavailable': 'Removal is unavailable. Concurrent changes could leave no verified factor. No authenticator will be deleted here.',
}
const positive = ['alternative-factor-available', 'verified-factor-present', 'challenge-required', 'alternative-verified', 'replacement-pending', 'replacement-verified', 'abandoned-enrollment']

export function MfaRecoveryScreen({ service, onManageAuthenticators }) {
  const f = useFormScope(), epoch = useRef(0), id = useId(), dialog = useRef(null), reviewTrigger = useRef(null)
  const [view, setView] = useState(null), [lost, setLost] = useState(''), [alternative, setAlternative] = useState(''), [review, setReview] = useState(false)
  const signedIn = f.auth.status === 'authenticated'
  function apply(result) {
    const status = messages[result?.status] ? result.status : 'unavailable'
    if (positive.includes(status) && (result.generation !== f.auth.generation || !Array.isArray(result.factors) ||
        !result.factors.length || result.factors.length > 10 || result.factors.some(x => !x || typeof x.id !== 'string' ||
          typeof x.label !== 'string' || !['verified', 'unverified'].includes(x.status)))) {
      setView({ status: 'unavailable', factors: [] }); return
    }
    setView({ status, factors: positive.includes(status) ? result.factors : [] })
    if (positive.includes(status)) {
      const verified = result.factors.filter(x => x.status === 'verified')
      setLost(verified[0]?.id ?? ''); setAlternative(verified[1]?.id ?? '')
    }
  }
  useEffect(() => {
    const ticket = ++epoch.current
    setView(null); setLost(''); setAlternative(''); setReview(false)
    Promise.resolve().then(async () => {
      if (!signedIn || ticket !== epoch.current) return
      try { const result = await service?.inspect?.(); if (ticket === epoch.current) apply(result) }
      catch { if (ticket === epoch.current) apply(null) }
    })
    return () => { epoch.current++; service?.cancel?.() }
  }, [service, signedIn, f.auth.generation])
  useEffect(() => {
    if (!review) return
    const element = dialog.current, previous = reviewTrigger.current ?? document.activeElement
    element.showModal(); element.querySelector('button:not(:disabled)').focus()
    return () => { if (element.open) element.close(); if (previous?.isConnected) previous.focus() }
  }, [review])
  async function act(method, args = []) {
    const scope = f.begin(), ticket = epoch.current
    if (!scope) return
    f.form.current?.reset()
    try {
      const result = await service?.[method]?.(...args, { signal: scope.signal })
      if (scope.signal.aborted || ticket !== epoch.current) return
      scope.report(messages[result?.status] ? result.status : 'unavailable')
      if (method === 'reviewRemoval' && result?.status === 'removal-unavailable') setReview(true)
      else if (['invalid-code', 'expired', 'rate-limited'].includes(result?.status)) {
        const current = await service?.inspect?.()
        if (!scope.signal.aborted && ticket === epoch.current) apply(current)
      } else apply(result)
    } catch { if (!scope.signal.aborted && ticket === epoch.current) { scope.report('unavailable'); apply(null) } }
    finally { scope.finish() }
  }
  const state = view?.status, verified = view?.factors?.filter(x => x.status === 'verified') ?? []
  const choose = ['alternative-factor-available', 'challenge-required'].includes(state) && verified.length >= 2
  const pending = state === 'replacement-pending'
  return <AuthFrame title="Another way back." description="Use an authenticator you can still access. Keep your next step secure.">
    <p className="auth-hint">A backup should be on a device or app you can access independently. Two registered factors do not guarantee that.</p>
    {!signedIn ? <AuthNotice>Sign in with your ordinary first factor before checking your authenticators.</AuthNotice> : <>
      <AuthNotice focus={Boolean(f.status)} error={Boolean(view) && !positive.includes(state)}>
        {messages[f.status] || messages[state] || 'Checking your current authenticator evidence…'}
      </AuthNotice>
      {pending && <SetupCredentials service={service} />}
      {(choose || pending) && <form ref={f.form} aria-busy={f.busy} onSubmit={event => {
        event.preventDefault()
        if (f.form.current.reportValidity()) {
          const code = new FormData(f.form.current).get('totp')
          act(pending ? 'verifyReplacement' : 'verifyAlternative', pending ? [code] : [lost, alternative, code])
        }
      }}>
        {choose && <><div className="auth-field"><label htmlFor={id + '-lost'}>Lost authenticator</label>
          <select id={id + '-lost'} value={lost} disabled={f.busy} onChange={event => {
            const next = event.target.value; setLost(next)
            if (next === alternative) setAlternative(verified.find(x => x.id !== next)?.id ?? '')
          }}>{verified.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></div>
          <div className="auth-field"><label htmlFor={id + '-available'}>Accessible authenticator</label>
            <select id={id + '-available'} value={alternative} disabled={f.busy} onChange={event => setAlternative(event.target.value)}>
              {verified.filter(x => x.id !== lost).map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></div></>}
        <div className="auth-field"><label htmlFor={id + '-code'}>Six-digit authenticator code</label>
          <input id={id + '-code'} name="totp" type="password" inputMode="numeric" autoComplete="one-time-code"
            pattern="[0-9]{6}" minLength={6} maxLength={6} required disabled={f.busy} /></div>
        <button className="button-primary auth-submit" disabled={f.busy}>{f.busy ? 'Checking…' : pending ? 'Verify replacement' : 'Use accessible authenticator'}</button>
      </form>}
      {state === 'alternative-verified' && <button className="button-primary auth-submit" disabled={f.busy} onClick={() => act('enrollReplacement')}>Enroll replacement authenticator</button>}
      {state === 'replacement-verified' && <button className="button-secondary auth-submit" disabled={f.busy} onClick={event => {
        reviewTrigger.current = event.currentTarget; act('reviewRemoval')
      }}>Review lost-authenticator removal</button>}
      {onManageAuthenticators && <button className="text-link auth-submit" disabled={f.busy} onClick={onManageAuthenticators}>Authenticator settings</button>}
      <button className="text-link auth-submit" disabled={f.busy} onClick={() => {
        epoch.current++; f.form.current?.reset(); apply(service?.allInaccessible?.() ?? { status: 'recovery-unavailable' }); f.setStatus(null)
      }}>None of my authenticators is accessible</button>
      <button className="text-link auth-submit" onClick={() => {
        epoch.current++; service?.cancel?.(); f.form.current?.reset(); f.setStatus('cancelled'); apply({ status: 'cancelled' })
      }}>Cancel this step</button>
      <button className="text-link auth-submit" disabled={f.busy || !view} onClick={() => { service?.cancel?.(); act('inspect') }}>Check current authenticator state</button>
    </>}
    <dialog ref={dialog} className="account-lifecycle-dialog" aria-labelledby={id + '-review'} onKeyDown={containDialogFocus}
      onCancel={event => { event.preventDefault(); setReview(false) }}>
      <h2 id={id + '-review'}>Lost-authenticator removal</h2><p>{messages['removal-unavailable']}</p>
      <p>Losing access to all remaining authenticators may lock you out. Password recovery does not remove MFA. Issued tokens may remain valid until expiry.</p>
      <div className="account-review-actions"><button className="button-secondary" onClick={() => setReview(false)}>Cancel</button>
        <button className="button-primary" disabled>Removal unavailable</button></div>
    </dialog>
  </AuthFrame>
}

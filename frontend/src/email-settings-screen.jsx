import { useEffect, useId, useState } from 'react'
import { useAuth } from './auth-context.js'
import { AuthFrame, AuthNotice, Password } from './account-screens.jsx'
import { useFormScope } from './password-screens.jsx'

const states = {
  loading: 'Checking your email status…',
  'current-confirmed': 'The account service reports a confirmed current email. Profile access is checked separately.',
  'current-unconfirmed': 'A confirmed current email has not been established. Complete confirmation before changing it.',
  'change-pending': 'An email change is pending. Follow every confirmation email the service sends. Both old and new inboxes may be required; we cannot tell which confirmation remains.',
  unchecked: 'Check your current email status before starting another change.',
  unavailable: 'Email settings are unavailable here. No email state can be established from device sign-in alone.',
}
const outcomes = {
  'check-email': 'If this change can proceed, follow the confirmation emails. Delivery and completion cannot be confirmed here. Check your email status again before retrying.',
  invalid: 'Check the new address and your current password, then try again.',
  'mfa-required': 'An authenticator step is required. This email-change flow is not available for your account yet.',
  'rate-limited': 'Too many attempts. Wait before trying again.',
  requesting: 'Password confirmed. Requesting the email change…',
  busy: 'Another account request is in progress. Please wait.',
  unavailable: 'The request could not be established. Check your email status before trying again.',
  cancelled: 'Your session changed. Start again.',
  expired: 'Your security step expired. Sign in and check the current email status again.',
  unproven: 'The required security evidence could not be established. Start again.',
}

export function EmailSettingsPanel({ service }) {
  const f = useFormScope(), id = useId(), signedIn = f.auth.status === 'authenticated'
  const [observed, setObserved] = useState({ status: 'loading', generation: -1 }), [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setObserved({ status: 'loading', generation: f.auth.generation })
    if (signedIn) (async () => {
      let status = 'unavailable'
      try { const result = await service?.inspect?.({ signal: controller.signal }); if (states[result?.status]) status = result.status }
      catch { /* Never render native errors, addresses or metadata. */ }
      if (!controller.signal.aborted) setObserved({ status, generation: f.auth.generation })
    })()
    return () => controller.abort()
  }, [f.auth.generation, signedIn, service, retry])
  const current = observed.generation === f.auth.generation ? observed.status : 'loading'
  async function submit(event) {
    event.preventDefault()
    if (!signedIn || current !== 'current-confirmed' || !f.form.current.reportValidity()) return
    const fields = new FormData(f.form.current), password = fields.get('current'), email = fields.get('email'), scope = f.begin()
    if (!scope) return
    f.form.current.reset()
    try {
      const result = await service.requestChange(password, email, { signal: scope.signal,
        onProgress: step => { if (step?.status === 'verified' && step.operation === 'email-change') scope.report('requesting') } })
      scope.report(outcomes[result?.status] ? result.status : states[result?.status] ? null : 'unavailable')
      if (!scope.signal.aborted) setObserved({ status: states[result?.status] ? result.status : 'unchecked', generation: f.auth.generation })
    } catch { scope.report('unavailable'); if (!scope.signal.aborted) setObserved({ status: 'unchecked', generation: f.auth.generation }) }
    finally { scope.finish() }
  }
  return <section className="account-section" aria-labelledby={id + '-title'}><h2 id={id + '-title'}>Your email</h2>
    {!signedIn ? <AuthNotice focus={false}>Sign in to check email settings.</AuthNotice> : <>
      <AuthNotice focus={false}>{states[current] || states.unavailable}</AuthNotice>
      {f.status && <AuthNotice error={!['check-email', 'requesting'].includes(f.status)}>{outcomes[f.status] || outcomes.unavailable}</AuthNotice>}
      {(current === 'current-confirmed' || f.busy) && typeof service?.requestChange === 'function' && <form ref={f.form} onSubmit={submit} aria-busy={f.busy}>
        <div className="auth-field"><label htmlFor={id}>New email address</label>
          <input id={id} name="email" type="email" required maxLength={320} autoComplete="email" disabled={f.busy} /></div>
        <Password key={f.auth.generation} label="Current password" name="current" autoComplete="current-password" disabled={f.busy} />
        <button className="button-primary auth-submit" disabled={f.busy}>{f.busy ? 'Please wait…' : 'Request email change'}</button>
      </form>}
      <button className="button-secondary auth-submit" disabled={f.busy || current === 'loading'} onClick={() => setRetry(retry + 1)}>Check email status</button>
    </>}
  </section>
}

const callback = { missing: 'No complete email-change callback was found.', invalid: 'This link is incomplete or unsupported.',
  expired: 'This link may have expired or already been used.', unproven: 'This link did not establish an email-change context.',
  unavailable: 'The account service could not establish this email change.', 'rate-limited': 'Too many attempts. Wait before checking again.' }
export function EmailChangeCallbackScreen({ service, onReturn }) {
  const auth = useAuth(), [view, setView] = useState({ status: 'loading', generation: -1 })
  useEffect(() => {
    let alive = true
    try {
      if (typeof service?.confirm !== 'function') { window.history.replaceState(null, '', '/'); setView({ status: 'unavailable' }); return }
      Promise.resolve(service.confirm()).then(result => {
        if (alive) setView({ status: states[result?.status] || callback[result?.status] ? result.status : 'unavailable', generation: result?.generation })
      }, () => { if (alive) setView({ status: 'unavailable' }) })
    } catch { setView({ status: 'unavailable' }) }
    return () => { alive = false }
  }, [service])
  const bound = auth.status === 'authenticated' && Number.isSafeInteger(view.generation) && view.generation === auth.generation
  const message = view.status === 'loading' ? states.loading : states[view.status] ?
    (bound ? states[view.status] : callback.unproven) : callback[view.status] || callback.unavailable
  return <AuthFrame title="Check your email change." description="The current address is checked with the account service. A processed link alone does not approve profile access.">
    <AuthNotice error={view.status !== 'loading' && (!bound || !['current-confirmed', 'current-unconfirmed', 'change-pending'].includes(view.status))}>{message}</AuthNotice>
    {onReturn && view.status !== 'loading' && <button className="button-primary auth-submit" onClick={onReturn}>Return to settings</button>}
  </AuthFrame>
}

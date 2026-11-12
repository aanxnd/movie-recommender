import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from './auth-context.js'
import { AuthFrame, AuthNotice, Password } from './account-screens.jsx'

const messages = {
  mismatch: 'The new passwords do not match. Please enter them again.',
  invalid: 'We could not confirm your current password. Please try again.',
  'invalid-password': 'The password was not accepted. Use a different password that meets the account service requirements.',
  'mfa-required': 'An authenticator step is required. Password changes for this account are not available in this flow yet.',
  expired: 'This security step has expired. Start again with a new link or sign in.',
  cancelled: 'Your session changed. Please start again.',
  'rate-limited': 'Too many attempts. Wait before trying again.',
  busy: 'Another account request is in progress. Please wait.',
  unavailable: 'We could not complete the change. It may have reached the service. Check your account before starting again.',
  unproven: 'We could not establish the required security step. No password change is authorized here.',
  verified: 'Current password confirmed. Saving your new password…',
}

// Transient form state only. Each explicit request owns an abort scope, never credentials.
export function useFormScope() {
  const auth = useAuth(), form = useRef(null), active = useRef(null)
  const [status, setStatus] = useState(null), [busy, setBusy] = useState(false)
  useEffect(() => {
    active.current?.abort(); active.current = null; form.current?.reset(); setBusy(false); setStatus(null)
    return () => { active.current?.abort(); active.current = null; form.current?.reset() }
  }, [auth.generation])
  function begin() {
    if (active.current) return null
    const controller = new AbortController(); active.current = controller; setBusy(true); setStatus(null)
    return { signal: controller.signal,
      report(value) { if (active.current === controller && !controller.signal.aborted) setStatus(value) },
      finish() { if (active.current === controller) { active.current = null; setBusy(false) } } }
  }
  return { auth, form, status, setStatus, busy, begin }
}

export function ForgotPasswordScreen({ requestReset, onSignIn }) {
  const f = useFormScope(), id = useId()
  async function submit(event) {
    event.preventDefault()
    if (!f.form.current.reportValidity()) return
    const email = new FormData(f.form.current).get('email'), scope = f.begin()
    if (!scope) return
    f.form.current.reset() // Do not retain the requested address in React or application persistence.
    try { const result = await requestReset(email, { signal: scope.signal }); scope.report(result?.status === 'cancelled' ? 'cancelled' : 'check-email') }
    catch { scope.report('check-email') } // Same conditional guidance for all provider outcomes.
    finally { scope.finish() }
  }
  return <AuthFrame title={f.status === 'check-email' ? 'Check your email.' : 'Find your way back.'}
    description="A fresh start for your next great film.">
    {typeof requestReset !== 'function' ? <AuthNotice>Password recovery is not available here yet.</AuthNotice> :
      f.status === 'check-email' ? <AuthNotice>If an account can receive recovery email, follow the link in the same browser where you started. Delivery cannot be confirmed. If nothing arrives, wait before trying again.</AuthNotice> :
      <form ref={f.form} onSubmit={submit} aria-busy={f.busy}>
        <div className="auth-field"><label htmlFor={id}>Email address</label>
          <input id={id} name="email" type="email" required maxLength={254} autoComplete="email" disabled={f.busy} /></div>
        {f.status && <AuthNotice error>{messages[f.status] || messages.unavailable}</AuthNotice>}
        <button className="button-primary auth-submit" disabled={f.busy}>{f.busy ? 'Please wait…' : 'Send recovery link'}</button>
      </form>}
    {onSignIn && <button className="text-link auth-submit" type="button" onClick={onSignIn}>Back to sign in</button>}
  </AuthFrame>
}

function recoveryState(service) {
  try { return service?.state?.().status ?? 'unavailable' } catch { return 'unavailable' }
}

function PasswordForm({ recovery, sensitive, changing = false, title, onSignIn }) {
  const f = useFormScope(), hint = useId()
  const available = f.auth.status === 'authenticated' && (changing ? typeof sensitive?.changePassword === 'function' :
    recoveryState(recovery) === 'verified' && typeof recovery?.setPassword === 'function')
  async function submit(event) {
    event.preventDefault()
    if (!available || !f.form.current.reportValidity()) return
    const fields = new FormData(f.form.current), password = fields.get('password'), current = fields.get('current')
    const matches = password === fields.get('confirmation'); f.form.current.reset()
    if (!matches) { f.setStatus('mismatch'); return }
    const scope = f.begin(); if (!scope) return
    try {
      const result = changing ? await sensitive.changePassword(current, password, { signal: scope.signal,
        onProgress: progress => { if (progress?.status === 'verified') scope.report('verified') } }) :
        await recovery.setPassword(password, { signal: scope.signal })
      scope.report(result?.status === 'changed' ? 'changed' : messages[result?.status] ? result.status : 'unavailable')
    } catch { scope.report('unavailable') }
    finally { scope.finish() }
  }
  return <AuthFrame title={title || (changing ? 'A little account care.' : 'Choose a new password.')}
    description={changing ? 'Confirm your current password to approve this password change.' : 'Your recovery link is checked separately from access to your Movelle profile.'}>
    {f.status === 'changed' ? <AuthNotice>Password updated. Sign in again if needed. Account access and any authenticator requirements are checked separately.</AuthNotice> :
      !available && !f.busy ? <AuthNotice error={Boolean(f.status)}>{f.status ? messages[f.status] || messages.unavailable :
        changing ? 'Sign in to use supported password changes. This security flow may not be available for your account yet.' :
          'Open a valid recovery link first. An ordinary sign-in does not authorize a password reset.'}</AuthNotice> :
      <form ref={f.form} onSubmit={submit} aria-busy={f.busy}>
        {changing && <Password key={'current-' + f.auth.generation} label="Current password" name="current" autoComplete="current-password" disabled={f.busy} />}
        <Password key={'new-' + f.auth.generation} label="New password" name="password" autoComplete="new-password" disabled={f.busy} describedBy={hint} />
        <p className="auth-hint" id={hint}>Use a unique password. The account service checks its password requirements.</p>
        <Password key={'confirm-' + f.auth.generation} label="Confirm new password" name="confirmation" autoComplete="new-password" disabled={f.busy} />
        {f.status && <AuthNotice error={f.status !== 'verified'}>{messages[f.status] || messages.unavailable}</AuthNotice>}
        <button className="button-primary auth-submit" disabled={f.busy}>{f.busy ? 'Please wait…' : 'Update password'}</button>
      </form>}
    {onSignIn && <button className="text-link auth-submit" type="button" onClick={onSignIn}>Go to sign in</button>}
  </AuthFrame>
}
export const NewPasswordScreen = props => <PasswordForm {...props} />
export const ChangePasswordScreen = props => <PasswordForm {...props} changing />
// Same single-operation form, not a standalone reusable authorization grant or MFA UI.
export const SensitiveReauthenticationScreen = props => <PasswordForm {...props} changing title="Confirm it’s you." />

const callbackMessages = {
  pending: 'Checking your recovery link…', missing: 'No recovery link was found. Open the full link from your email.',
  invalid: 'This recovery link cannot be used. It may be incomplete or unsupported.',
  expired: 'This recovery link may have expired or already been used. Request a new one.',
  'rate-limited': 'Too many attempts. Wait before starting a new recovery request.',
  unavailable: 'Recovery could not be established. This link may already have been processed. Start a new request later.',
  unproven: 'The link did not establish recovery authorization. An existing session or processed link is not enough.',
}
export function RecoveryCallbackScreen({ recovery, onSignIn }) {
  const auth = useAuth(), [status, setStatus] = useState('pending')
  useEffect(() => {
    let alive = true
    if (typeof recovery?.confirm !== 'function') {
      try { window.history.replaceState(null, '', '/') } catch { /* No redemption if unavailable. */ }
      setStatus('unavailable'); return () => { alive = false }
    }
    try { Promise.resolve(recovery?.confirm?.()).then(result => {
      if (alive) setStatus(result?.status === 'verified' || callbackMessages[result?.status] ? result.status : 'unavailable')
    }, () => { if (alive) setStatus('unavailable') }) } catch { setStatus('unavailable') }
    return () => { alive = false } // Do not cancel the once-only exchange on Strict Mode remount.
  }, [recovery])
  if (status === 'verified' && auth.status === 'authenticated' && recoveryState(recovery) === 'verified')
    return <NewPasswordScreen recovery={recovery} onSignIn={onSignIn} />
  return <AuthFrame title="A secure way back." description="Password recovery for your Movelle account.">
    <AuthNotice error={status !== 'pending'}>{callbackMessages[status] || callbackMessages.expired}</AuthNotice>
    {onSignIn && status !== 'pending' && <button className="button-primary auth-submit" onClick={onSignIn}>Back to sign in</button>}
  </AuthFrame>
}

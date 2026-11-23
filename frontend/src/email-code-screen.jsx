import { useEffect, useId, useState } from 'react'
import { AuthFrame, AuthNotice } from './account-screens.jsx'
import { useFormScope } from './password-screens.jsx'

const messages = {
  'check-email': 'If signup can proceed, a Movelle verification code will arrive. Check your junk folder too.',
  invalid: 'That code is incorrect or expired. Check the latest email or request a new code.',
  expired: 'That code is incorrect or expired. Check the latest email or request a new code.',
  'rate-limited': 'Too many attempts. Wait before trying again; the account service controls the limit.',
  unavailable: 'Verification could not be confirmed. Try signing in before submitting another code.',
  cancelled: 'Your session changed. Start again before continuing.',
  busy: 'Another account request is in progress. Please wait.',
}

export function EmailCodeScreen({ actions, initialEmail = '' }) {
  const f = useFormScope(), id = useId(), [cooldown, setCooldown] = useState(initialEmail ? 60 : 0)
  useEffect(() => {
    if (cooldown) { const timer = setTimeout(() => setCooldown(x => Math.max(0, x - 1)), 1000); return () => clearTimeout(timer) }
  }, [cooldown])
  const disabled = f.busy || ['restoring', 'refreshing', 'logging-out', 'authenticated'].includes(f.auth.status)
  async function submit(kind) {
    if (disabled || (kind === 'resend' && cooldown) || !f.form.current.elements.email.reportValidity() ||
        (kind === 'verify' && !f.form.current.reportValidity())) return
    const email = f.form.current.elements.email.value, token = kind === 'verify' ? f.form.current.elements.code.value : undefined
    f.form.current.elements.code.value = '' // Never put the OTP in React state, storage, URLs or diagnostics.
    const scope = f.begin()
    if (!scope) return
    try {
      const result = await (kind === 'verify' ? actions.verifyEmail(email, token, { signal: scope.signal }) :
        actions.resendConfirmation(email, { signal: scope.signal }))
      if (scope.signal.aborted) return
      if (kind === 'resend' || result?.status === 'rate-limited') setCooldown(60)
      scope.report(messages[result?.status] ? result.status : 'unavailable')
    } catch { scope.report('unavailable') }
    finally { scope.finish() }
  }
  return <AuthFrame title="Check your inbox." description="A six-digit code. A secure start to your Movelle story.">
    {f.auth.status === 'authenticated' ? <AuthNotice>Signed in on this device. Your profile and MFA access are checked separately.</AuthNotice> : <>
      <AuthNotice error={Boolean(f.status && f.status !== 'check-email')}>
        {messages[f.status] || messages['check-email']}</AuthNotice>
      <form ref={f.form} onSubmit={event => { event.preventDefault(); submit('verify') }} aria-busy={f.busy}>
        <div className="auth-field"><label htmlFor={id + '-email'}>Email address</label>
          <input id={id + '-email'} name="email" type="email" defaultValue={initialEmail} autoComplete="email" required maxLength={254} disabled={disabled} /></div>
        <div className="auth-field"><label htmlFor={id + '-code'}>Six-digit email code</label>
          <input id={id + '-code'} className="email-code" name="code" type="text" inputMode="numeric" autoComplete="one-time-code"
            pattern="[0-9]{6}" minLength={6} maxLength={6} required aria-describedby={id + '-hint'} disabled={disabled} /></div>
        <p id={id + '-hint'} className="auth-hint">Enter the latest code from Movelle. It is not your authenticator code. Opening this page does not verify your email.</p>
        <button type="submit" className="button-primary auth-submit" disabled={disabled}>{f.busy ? 'Checking…' : 'Verify email'}</button>
        <button type="button" className="text-link auth-submit" disabled={disabled || cooldown > 0} onClick={() => submit('resend')}>
          {cooldown ? `Resend available in ${cooldown}s` : 'Resend code'}</button>
      </form>
    </>}
  </AuthFrame>
}

import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from './auth-context.js'
import { Brand } from './components/ui.jsx'
import './account-screens.css'

export function AuthFrame({ title, description, children }) {
  return <main className="auth-shell"><aside className="auth-editorial">
    <Brand /><p className="eyebrow">A LITTLE MORE YOU</p>
    <p className="auth-quote">Good films.<br />Great company.<br /><em>Your kind of cinema.</em></p>
    <p>Find your next favourite. Keep the ones that stay with you.</p>
    <span className="auth-reel" aria-hidden="true">01 / THE OPENING SCENE</span>
  </aside><section className="auth-card" aria-label={title}>
    <p className="eyebrow">YOUR MOVELLE</p><h1>{title}</h1><p className="auth-intro">{description}</p>
    {children}<p className="auth-footnote">Just looking? Movie browsing stays open to everyone.</p>
  </section></main>
}

export function AuthNotice({ children, error = false }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.focus() }, [children])
  return <div className={'auth-notice' + (error ? ' auth-error' : '')} ref={ref} tabIndex={-1}
    role={error ? 'alert' : 'status'}>{children}</div>
}

export function Password({ label, name, autoComplete, disabled, describedBy }) {
  const id = useId(), [visible, setVisible] = useState(false)
  return <div className="auth-field"><label htmlFor={id}>{label}</label><div className="auth-password">
    <input id={id} name={name} type={visible ? 'text' : 'password'} required disabled={disabled}
      autoComplete={autoComplete} aria-describedby={describedBy} />
    <button type="button" disabled={disabled} aria-label={(visible ? 'Hide ' : 'Show ') + label.toLowerCase()}
      aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? 'Hide' : 'Show'}</button>
  </div></div>
}

const errors = {
  invalid: 'Check your email and password, and complete any email confirmation. For signup, use a password accepted by the service.',
  mismatch: 'Your passwords do not match. Please enter them again.',
  'rate-limited': 'Too many attempts. Please wait before trying again.',
  unavailable: 'We could not reach the account service. Please try again later.',
  busy: 'An account request is already in progress. Please wait.',
  cancelled: 'Your session changed. Please start again.',
}

function CredentialScreen({ signup, actions, onSwitch }) {
  const auth = useAuth(), id = useId(), form = useRef(null), ticket = useRef(0), active = useRef(false)
  const [busy, setBusy] = useState(false), [status, setStatus] = useState(null)
  useEffect(() => {
    ticket.current++; active.current = false; setBusy(false); setStatus(null); form.current?.reset()
    return () => { ticket.current++; active.current = false; form.current?.reset() }
  }, [auth.generation])
  const disabled = busy || ['restoring', 'refreshing', 'logging-out', 'authenticated'].includes(auth.status)
  async function submit(event) {
    event.preventDefault()
    if (active.current || disabled || !form.current.reportValidity()) return
    const fields = new FormData(form.current), email = fields.get('email'), password = fields.get('password')
    if (signup && password !== fields.get('confirmation')) { setStatus('mismatch'); return }
    active.current = true; const current = ++ticket.current; setBusy(true); setStatus(null)
    // Uncontrolled fields only; passwords are never retained in React state.
    for (const input of form.current.querySelectorAll('input[name="password"], input[name="confirmation"]')) input.value = ''
    try {
      const result = await (signup ? actions.signUp(email, password) : actions.signIn(email, password))
      if (ticket.current === current) setStatus(result?.status === 'check-email' && signup ? 'check-email' :
        result?.status === 'signed-in' && !signup ? 'signed-in' : errors[result?.status] ? result.status : 'unavailable')
    } catch { if (ticket.current === current) setStatus('unavailable') }
    finally { if (ticket.current === current) { active.current = false; setBusy(false) } }
  }
  return <AuthFrame title={signup ? 'Make yourself at home.' : 'Welcome back.'}
    description={signup ? 'A place for your ratings, discoveries and films worth sharing.' : 'Your next great film is waiting.'}>
    {auth.status === 'authenticated' || status === 'signed-in' ?
      <AuthNotice>Signed in on this device. Your profile and account access are checked separately.</AuthNotice> :
      status === 'check-email' ? <AuthNotice>Check your email. If signup can proceed, you will receive a confirmation link. Already have an account? Sign in instead.</AuthNotice> :
      <form ref={form} onSubmit={submit} aria-busy={busy}>
        <div className="auth-field"><label htmlFor={id}>Email address</label>
          <input id={id} name="email" type="email" autoComplete="username" required disabled={disabled} /></div>
        <Password label="Password" name="password" autoComplete={signup ? 'new-password' : 'current-password'}
          disabled={disabled} describedBy={signup ? id + '-policy' : undefined} />
        {signup && <><p id={id + '-policy'} className="auth-hint">Use a unique password. The account service checks its password requirements.</p>
          <Password label="Confirm password" name="confirmation" autoComplete="new-password" disabled={disabled} /></>}
        {status && <AuthNotice error>{errors[status] || errors.unavailable}</AuthNotice>}
        <button className="button-primary auth-submit" type="submit" disabled={disabled}>
          {busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}</button>
      </form>}
    {onSwitch && <p className="auth-switch">{signup ? 'Already have an account?' : 'New to Movelle?'}{' '}
      <button className="text-link" type="button" onClick={onSwitch}>{signup ? 'Sign in' : 'Create an account'}</button></p>}
  </AuthFrame>
}

export const SignupScreen = props => <CredentialScreen {...props} signup />
export const LoginScreen = props => <CredentialScreen {...props} signup={false} />

const verification = {
  loading: ['Opening your link…', 'Please wait while the account service processes this link.'],
  'check-email': ['Check your email.', 'If signup can proceed, a confirmation link will arrive. Check your junk folder too.'],
  missing: ['No confirmation link here.', 'Open the complete link from your email in the browser where you started.'],
  invalid: ['We could not use this link.', 'It may be incomplete, unsupported or no longer usable. Return to sign in.'],
  expired: ['This link is no longer usable.', 'It may have expired or already been used. Return to sign in to continue.'],
  unavailable: ['A pause in the opening scene.', 'The account service is unavailable. Return to sign in later; this link may already have been processed.'],
  'rate-limited': ['A little breathing room.', 'Too many attempts. Wait before returning to sign in.'],
  unproven: ['Link processed. One more step.', 'This link does not establish signup confirmation. Sign in to continue; account access is checked separately.'],
}

export function VerificationScreen({ actions, onSignIn }) {
  const [status, setStatus] = useState('loading')
  useEffect(() => {
    let alive = true
    // Helper scrubs synchronously, before the first await; its per-document promise is once-only.
    try { Promise.resolve(actions.confirm()).then(result => {
      if (alive) setStatus(verification[result?.status] ? result.status : 'invalid')
    }, () => { if (alive) setStatus('unavailable') }) } catch { setStatus('unavailable') }
    return () => { alive = false }
  }, [actions])
  const [title, message] = verification[status]
  return <AuthFrame title={title} description="A secure start to your Movelle story.">
    <AuthNotice error={!['loading', 'check-email', 'unproven'].includes(status)}>{message}</AuthNotice>
    {onSignIn && status !== 'loading' && <button className="button-primary auth-submit" type="button" onClick={onSignIn}>Go to sign in</button>}
  </AuthFrame>
}

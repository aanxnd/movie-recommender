import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from './auth-context.js'
import { AuthFrame, AuthNotice } from './account-screens.jsx'
import { pendingProvisioning, profileResult, usernameError } from './profile-provisioning.js'

/** @param {{service?: import('./profile-provisioning.js').ProfileProvisioning}} props */
export function ProfileSetupScreen({ service = pendingProvisioning }) {
  const auth = useAuth(), id = useId(), form = useRef(null), scope = useRef(null), active = useRef(false)
  const [view, setView] = useState({ status: 'loading', generation: -1 }), [retry, setRetry] = useState(0)
  const signedIn = auth.status === 'authenticated'
  useEffect(() => {
    const controller = new AbortController(); scope.current = controller; active.current = false
    form.current?.reset()
    const publish = result => { if (!controller.signal.aborted) setView({ ...result, generation: auth.generation }) }
    publish({ status: signedIn ? 'loading' : 'sign-in' })
    if (signedIn) (async () => {
      try { publish(profileResult(await service.inspect({ signal: controller.signal }), 'inspect')) }
      catch { publish({ status: 'unavailable' }) }
    })()
    return () => { controller.abort(); form.current?.reset() }
  }, [auth.generation, signedIn, service, retry])
  const current = view.generation === auth.generation ? view : { status: 'loading' }
  async function submit(event) {
    event.preventDefault()
    if (active.current || !signedIn || current.status !== 'eligible') return
    const username = new FormData(form.current).get('username'), error = usernameError(username)
    if (error) { setView({ ...view, error }); return }
    const controller = scope.current
    if (!controller || controller.signal.aborted) return
    active.current = true; setView({ ...view, busy: true, error: null })
    try {
      // No client ID/UUID/email/verification flag is sent. Backend derives ownership.
      const result = profileResult(await service.provision({ username }, { signal: controller.signal }), 'provision')
      if (!controller.signal.aborted) setView(result.status === 'username-taken' ?
        { status: 'eligible', generation: auth.generation, error: 'That username is unavailable. Try another.' } :
        { ...result, generation: auth.generation })
    } catch { if (!controller.signal.aborted) setView({ status: 'unavailable', generation: auth.generation }) }
    finally { if (scope.current === controller) active.current = false }
  }
  return <AuthFrame title="Your own opening credit." description="Choose a name for your Movelle profile. You will still sign in with your email.">
    {!signedIn ? <AuthNotice>Sign in before setting up your profile.</AuthNotice> :
      current.status === 'loading' ? <AuthNotice>Checking your profile…</AuthNotice> :
      current.status === 'complete' ? <AuthNotice>Your profile is ready: {current.username}. Personal features still require server authorization.</AuthNotice> :
      current.status === 'email-required' ? <AuthNotice>Complete email confirmation, then return here. Profile creation has not been approved.</AuthNotice> :
      current.status !== 'eligible' ? <><AuthNotice>Profile setup is not available yet. Your account has not been linked to a new Movelle profile here.</AuthNotice>
        <button className="button-secondary auth-submit" onClick={() => setRetry(retry + 1)}>Check again</button></> :
      <form ref={form} onSubmit={submit} aria-busy={Boolean(current.busy)}>
        <div className="auth-field"><label htmlFor={id}>Profile username</label>
          <input id={id} name="username" required minLength={3} maxLength={30} pattern="[A-Za-z0-9_]{3,30}"
            autoComplete="off" autoCapitalize="none" spellCheck={false} disabled={current.busy} aria-describedby={id + '-hint'} /></div>
        <p className="auth-hint" id={id + '-hint'}>3–30 letters (A–Z), numbers or underscores. Capitalization is kept; names differing only in capitalization count as the same name. Some names are reserved.</p>
        {current.error && <AuthNotice error>{current.error}</AuthNotice>}
        <button type="submit" className="button-primary auth-submit" disabled={current.busy}>
          {current.busy ? 'Setting up…' : 'Create my profile'}</button>
      </form>}
  </AuthFrame>
}

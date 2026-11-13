import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from './auth-context.js'
import { AuthFrame, AuthNotice } from './account-screens.jsx'
import { usernameError } from './profile-provisioning.js'
import { accountSettingsResult, pendingAccountSettings } from './account-settings-contract.js'
import { EmailSettingsPanel } from './email-settings-screen.jsx'
import { AccountLifecycleControls } from './account-lifecycle.jsx'
import './account-settings.css'

/** @param {{account?:import('./account-settings-contract.js').AccountSettingsService, emailSettings?:ReturnType<typeof import('./email-settings.js').createNativeEmailSettings>, children?:import('react').ReactNode}} props */
export function AccountSettingsScreen({ account = pendingAccountSettings, emailSettings, children, readOnlyProfile = false }) {
  const auth = useAuth(), id = useId(), form = useRef(null), scope = useRef(null), active = useRef(false)
  const [view, setView] = useState({ status: 'loading', generation: -1 }), [retry, setRetry] = useState(0)
  const signedIn = auth.status === 'authenticated'
  useEffect(() => {
    const controller = new AbortController(); scope.current = controller; active.current = false
    form.current?.reset()
    const publish = value => { if (!controller.signal.aborted) setView({ ...value, generation: auth.generation }) }
    publish({ status: signedIn ? 'loading' : 'sign-in-required' })
    if (signedIn) (async () => {
      try { publish(accountSettingsResult(await account.inspect({ signal: controller.signal }), 'inspect')) }
      catch { publish({ status: 'unavailable' }) }
    })()
    return () => { controller.abort(); form.current?.reset() }
  }, [auth.generation, signedIn, account, retry])
  const current = view.generation === auth.generation ? view : { status: 'loading' }
  async function submit(event) {
    event.preventDefault()
    if (!signedIn || active.current || current.status !== 'ready') return
    const username = new FormData(form.current).get('username'), error = usernameError(username)
    if (error) { setView({ ...view, error, notice: null }); return }
    const controller = scope.current
    if (!controller || controller.signal.aborted) return
    active.current = true; setView({ ...view, busy: true, error: null, notice: null })
    try {
      const result = accountSettingsResult(await account.changeUsername({ username, revision: current.revision },
        { signal: controller.signal }), 'update')
      if (controller.signal.aborted) return
      if (result.status === 'updated' && result.username === username)
        setView({ ...result, status: 'ready', generation: auth.generation, notice: 'Your username is updated.' })
      else if (result.status === 'username-taken') setView({ ...current, busy: false, notice: null, error: 'That username is unavailable. Try another.' })
      else setView({ status: result.status === 'updated' ? 'unavailable' : result.status, generation: auth.generation })
    } catch { if (!controller.signal.aborted) setView({ status: 'unavailable', generation: auth.generation }) }
    finally { if (scope.current === controller) active.current = false }
  }
  return <AuthFrame title="Make it yours." description="Manage your profile and account. Device sign-in and access to your profile are checked separately.">
    <section className="account-section" aria-labelledby={id + '-title'}><h2 id={id + '-title'}>Your profile</h2>
      {!signedIn ? <AuthNotice>Sign in to check your account settings.</AuthNotice> : current.status === 'loading' ?
        <AuthNotice>Checking profile access…</AuthNotice> : current.status === 'ready' ? <>
          <p>Your authorized profile: <strong>{current.username}</strong></p>
          {readOnlyProfile ? <p>Username editing is unavailable in this staging composition.</p> : <form ref={form} onSubmit={submit} aria-busy={Boolean(current.busy)}>
            <div className="auth-field"><label htmlFor={id}>New username</label>
              <input id={id} name="username" defaultValue={current.username} required minLength={3} maxLength={30}
                pattern="[A-Za-z0-9_]{3,30}" autoComplete="off" autoCapitalize="none" spellCheck={false}
                disabled={current.busy} aria-describedby={id + '-hint'} /></div>
            <p className="auth-hint" id={id + '-hint'}>3–30 ASCII letters, numbers or underscores. No spaces. Capitalization is kept, but names are unique regardless of case. Some names are reserved. Sign in with email.</p>
            {current.error && <AuthNotice error>{current.error}</AuthNotice>}
            {current.notice && <AuthNotice>{current.notice}</AuthNotice>}
            <button className="button-primary auth-submit" disabled={current.busy}>{current.busy ? 'Saving…' : 'Save username'}</button>
          </form>}</> : <AuthNotice error={current.status === 'conflict'}>{
            current.status === 'conflict' ? 'Your profile changed during this request. Check again before choosing a username.' :
              ['email-required', 'reauthentication-required', 'mfa-required'].includes(current.status) ?
                'The account service requires another security step. This update is unavailable until that step is supported.' :
                'Profile settings are waiting for a trusted backend connection. A previous change may have completed; check again before retrying.'}</AuthNotice>}
      {signedIn && <button className="button-secondary auth-submit" disabled={current.busy || current.status === 'loading'}
        onClick={() => setRetry(retry + 1)}>Check profile again</button>}
    </section><EmailSettingsPanel service={emailSettings} /><AccountLifecycleControls />{children}
  </AuthFrame>
}

import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './auth-context.js'
import { AuthFrame, AuthNotice, SignupScreen, LoginScreen } from './account-screens.jsx'
import { ProfileSetupScreen } from './profile-setup.jsx'
import { AccountSettingsScreen } from './account-settings.jsx'
import { ForgotPasswordScreen, NewPasswordScreen, ChangePasswordScreen } from './password-screens.jsx'
import { MfaScreen, MfaLoginScreen } from './mfa-screens.jsx'
import { MfaRecoveryScreen } from './mfa-recovery-screen.jsx'
import { StagingMovies } from './staging-movies.jsx'

export function StagingApp({ runtime }) {
  return <AuthProvider session={runtime.session}><Workspace runtime={runtime} /></AuthProvider>
}

function Workspace({ runtime }) {
  const auth = useAuth(), [screen, setScreen] = useState('movies'), [callback, setCallback] = useState(null)
  useEffect(() => {
    let alive = true
    runtime.callbackResult.then(result => {
      if (!alive || result.status === 'missing') return
      setCallback(result)
      setScreen(result.flow === 'recovery' && result.status === 'verified' ? 'reset' : 'callback')
    })
    return () => { alive = false }
  }, [runtime])
  const go = setScreen, screens = {
    signup: <SignupScreen actions={runtime.actions} onSwitch={() => go('login')} />,
    login: <LoginScreen actions={runtime.actions} onSwitch={() => go('signup')} />,
    profile: <ProfileSetupScreen service={runtime.profile} />,
    settings: <AccountSettingsScreen account={runtime.account} emailSettings={runtime.email} readOnlyProfile />,
    forgot: <ForgotPasswordScreen requestReset={runtime.passwords.requestReset} onSignIn={() => go('login')} />,
    reset: <NewPasswordScreen recovery={runtime.passwords.recovery} onSignIn={() => go('login')} />,
    password: <ChangePasswordScreen sensitive={runtime.passwords.sensitive} />,
    authenticators: <MfaScreen service={runtime.mfa} />,
    challenge: <MfaLoginScreen service={runtime.mfa} />,
    lost: <MfaRecoveryScreen service={runtime.recovery} onManageAuthenticators={() => go('authenticators')} />,
    movies: <StagingMovies api={runtime.movies} onProfile={() => go(auth.status === 'authenticated' ? 'profile' : 'login')} />,
    callback: <AuthFrame title="Account link checked." description="Your account service and backend check access separately.">
      <AuthNotice>{callback?.flow === 'email-change' ? 'Native current-email state: ' + callback.status :
        'This link does not establish signup confirmation. Sign in to continue; account access is checked separately.'}</AuthNotice>
      <button onClick={() => go('login')}>Go to sign in</button></AuthFrame>,
  }
  return <><header className="staging-bar"><strong>PRIVATE LOCAL STAGING — NOT PRODUCTION</strong>
    <nav aria-label="Staging account navigation">
      {Object.entries({ movies: 'Movies', signup: 'Sign up', login: 'Sign in', profile: 'Profile setup', settings: 'Settings',
        forgot: 'Forgot password', password: 'Change password', authenticators: 'Authenticators', challenge: 'MFA challenge', lost: 'Lost device' })
        .map(([key, label]) => <button key={key} aria-current={screen === key ? 'page' : undefined} onClick={() => go(key)}>{label}</button>)}
      <button onClick={() => auth.refresh()}>Refresh session</button>
      <button onClick={() => auth.logout().then(() => go('login'))}>Sign out</button>
    </nav><p role="status">Session: {auth.status}{auth.logoutOutcome ? ' · provider logout: ' + auth.logoutOutcome : ''}</p>
  </header><div key={screen + ':' + auth.generation}>{screens[screen] || screens.movies}</div></>
}

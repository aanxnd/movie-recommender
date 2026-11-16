import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './auth-context.js'
import { AuthFrame, AuthNotice, SignupScreen, LoginScreen } from './account-screens.jsx'
import { ProfileSetupScreen } from './profile-setup.jsx'
import { AccountSettingsScreen } from './account-settings.jsx'
import { ForgotPasswordScreen, NewPasswordScreen, ChangePasswordScreen } from './password-screens.jsx'
import { MfaScreen, MfaLoginScreen } from './mfa-screens.jsx'
import { MfaRecoveryScreen } from './mfa-recovery-screen.jsx'
import { StagingMovies } from './staging-movies.jsx'
import { useTheme } from './use-theme.js'
import { AccountRemovalScreen, FactorRemovalScreen } from './removal-screens.jsx'

export function NativeApp({ runtime }) {
  useTheme()
  return <AuthProvider session={runtime.session}><Workspace runtime={runtime} /></AuthProvider>
}

function Workspace({ runtime }) {
  const auth = useAuth(), [screen, go] = useState('movies'), [callback, setCallback] = useState(null)
  const signedIn = auth.status === 'authenticated'
  useEffect(() => {
    let alive = true
    runtime.callbackResult.then(result => {
      if (!alive || result.status === 'missing') return
      setCallback(result); go(result.flow === 'recovery' && result.status === 'verified' ? 'reset' : 'callback')
    })
    return () => { alive = false }
  }, [runtime])
  const screens = {
    movies: <StagingMovies api={runtime.movies} onProfile={() => go(signedIn ? 'profile' : 'login')} />,
    signup: <SignupScreen actions={runtime.actions} onSwitch={() => go('login')} />,
    login: <LoginScreen actions={runtime.actions} onSwitch={() => go('signup')} />,
    profile: <ProfileSetupScreen service={runtime.profile} />,
    settings: <AccountSettingsScreen account={runtime.account} emailSettings={runtime.email} />,
    deletion: <AccountRemovalScreen service={runtime.deletion} />,
    removal: <FactorRemovalScreen service={runtime.factorRemoval} />,
    forgot: <ForgotPasswordScreen requestReset={runtime.passwords.requestReset} onSignIn={() => go('login')} />,
    reset: <NewPasswordScreen recovery={runtime.passwords.recovery} onSignIn={() => go('login')} />,
    password: <ChangePasswordScreen sensitive={runtime.passwords.sensitive} />,
    authenticators: <MfaScreen service={runtime.mfa} />,
    challenge: <MfaLoginScreen service={runtime.mfa} />,
    lost: <MfaRecoveryScreen service={runtime.recovery} onManageAuthenticators={() => go('authenticators')} />,
    callback: <AuthFrame title="Account link checked." description="Account access is checked separately.">
      <AuthNotice>{callback?.flow === 'email-change' && callback.status === 'current-confirmed' ?
        'The account service checked your current email. Sign in to check profile access.' :
        'Sign in to check account access. This link may have expired or already been handled; it does not independently grant access.'}</AuthNotice>
      <button onClick={() => go('login')}>Go to sign in</button></AuthFrame>,
  }
  const links = signedIn ? { profile: 'Profile setup', settings: 'Settings', password: 'Change password',
    authenticators: 'Authenticators', challenge: 'Verify authenticator', lost: 'Lost device',
    removal: 'Review authenticator removal', deletion: 'Review deletion' } :
    { signup: 'Sign up', login: 'Sign in', forgot: 'Forgot password', challenge: 'Verify authenticator', lost: 'Lost device' }
  return <><header className="native-header"><a href="/" onClick={event => { event.preventDefault(); go('movies') }}>Movelle</a>
    <nav aria-label="Account navigation"><button onClick={() => go('movies')}>Movies</button>
      {Object.entries(links).map(([key, label]) => <button key={key} aria-current={screen === key ? 'page' : undefined}
        onClick={() => go(key)}>{label}</button>)}
      {signedIn && <button onClick={() => auth.logout().then(() => go('login'))}>Sign out</button>}
    </nav></header><div key={screen + ':' + auth.generation}>{screens[screen] || screens.movies}</div></>
}

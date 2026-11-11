// Test-only Vite entry, excluded from the production entry/build. No SDK/config/network.
import React from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from '../src/auth-context.js'
import { SignupScreen, LoginScreen, VerificationScreen } from '../src/account-screens.jsx'
import { ProfileSetupScreen } from '../src/profile-setup.jsx'
import { ForgotPasswordScreen, RecoveryCallbackScreen, NewPasswordScreen, ChangePasswordScreen, SensitiveReauthenticationScreen } from '../src/password-screens.jsx'
import '../src/styles.css'

const screen = new URLSearchParams(location.search).get('screen')
const state = Object.freeze({ status: ['profile', 'new-password', 'change-password', 'reauth'].includes(screen) ? 'authenticated' : 'unauthenticated', userId: null, generation: 0 })
const session = { getSnapshot: () => state, subscribe: () => () => {}, logout: async () => {}, refresh: async () => {} }
const actions = Object.freeze({ signUp: async () => ({ status: 'check-email' }),
  signIn: async () => ({ status: 'invalid' }), confirm: async () => ({ status: 'unproven' }) })
const previews = { profile: ProfileSetupScreen, login: LoginScreen, verification: VerificationScreen,
  forgot: ForgotPasswordScreen, recovery: RecoveryCallbackScreen, 'new-password': NewPasswordScreen,
  'change-password': ChangePasswordScreen, reauth: SensitiveReauthenticationScreen }
const Screen = previews[screen] || SignupScreen
const recovery = { state: () => ({ status: screen === 'new-password' ? 'verified' : 'unproven' }),
  confirm: async () => ({ status: 'unproven' }), setPassword: async () => ({ status: 'changed' }) }
const sensitive = { changePassword: async () => ({ status: 'changed' }) } // UI simulation, never provider evidence.
createRoot(document.getElementById('root')).render(<React.StrictMode><AuthProvider session={session}>
  <p className="auth-hint" style={{ padding: '12px 24px' }}>Offline preview · No account requests are sent.</p>
  <Screen actions={actions} recovery={recovery} sensitive={sensitive} requestReset={async () => ({ status: 'check-email' })} />
</AuthProvider></React.StrictMode>)

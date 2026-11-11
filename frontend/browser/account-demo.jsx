// Test-only Vite entry, excluded from the production entry/build. No SDK/config/network.
import React from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from '../src/auth-context.js'
import { SignupScreen, LoginScreen, VerificationScreen } from '../src/account-screens.jsx'
import '../src/styles.css'

const state = Object.freeze({ status: 'unauthenticated', userId: null, generation: 0 })
const session = { getSnapshot: () => state, subscribe: () => () => {}, logout: async () => {}, refresh: async () => {} }
const actions = Object.freeze({ signUp: async () => ({ status: 'check-email' }),
  signIn: async () => ({ status: 'invalid' }), confirm: async () => ({ status: 'unproven' }) })
const screen = new URLSearchParams(location.search).get('screen')
const Screen = screen === 'login' ? LoginScreen : screen === 'verification' ? VerificationScreen : SignupScreen
createRoot(document.getElementById('root')).render(<React.StrictMode><AuthProvider session={session}>
  <p className="auth-hint" style={{ padding: '12px 24px' }}>Offline preview · No account requests are sent.</p>
  <Screen actions={actions} />
</AuthProvider></React.StrictMode>)

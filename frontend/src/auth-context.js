import { createContext, createElement, useContext, useSyncExternalStore } from 'react'

const AuthContext = createContext(null)

// Explicit controller from trusted bootstrap; no default client/configuration or production mount.
export function AuthProvider({ session, children }) {
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot)
  return createElement(AuthContext.Provider, { value: Object.freeze({ ...state,
    refresh: () => session.refresh().then(() => true, () => false), logout: session.logout }) }, children)
}

export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('AuthProvider is required')
  return auth
}

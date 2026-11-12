// Client presentation/transport only. The backend remains the authorization authority.
import { cancelCredentialRequests } from './supabase-client.js'
const controllers = new WeakMap()
const changed = () => new DOMException('Authentication changed', 'AbortError')
const failed = () => new Error('Session unavailable')

async function waitFor(promise, signal) {
  let cancel
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      cancel = () => reject(changed())
      if (signal.aborted) cancel()
      else signal.addEventListener('abort', cancel, { once: true })
    })])
  } finally { signal.removeEventListener('abort', cancel) }
}

export function getSessionController(client) {
  if (controllers.has(client)) return controllers.get(client)
  const auth = client?.auth
  if (!['getSession', 'onAuthStateChange', 'refreshSession', 'signOut'].every(k => typeof auth?.[k] === 'function')) throw failed()
  const listeners = new Set()
  let state = Object.freeze({ status: 'restoring', userId: null, error: null, logoutOutcome: null, generation: 0 })
  let generation = 0, assuranceRevision = 0
  let token, userId, expiresAt, revision = 0, fence = new AbortController(), locked = false
  let restoring, refreshing, signingOut, subscription
  const publish = (status, error = null, logout = null) => {
    const next = { status, userId: userId ?? null, error, logoutOutcome: logout, generation }
    if (Object.keys(next).every(k => state[k] === next[k])) return
    state = Object.freeze(next)
    for (const listener of listeners) listener()
  }
  const invalidate = () => {
    fence.abort(); fence = new AbortController(); generation++
    token = userId = expiresAt = undefined
  }
  const rejectSession = error => {
    const unavailable = !Number.isInteger(error?.status) || error.status === 0 || error.status === 429 || error.status >= 500
    if (!unavailable) locked = true
    invalidate()
    publish(unavailable ? 'unavailable' : 'error', unavailable ? 'session-unavailable' : 'session-rejected')
  }
  function valid(session) {
    return session && typeof session.access_token === 'string' && session.access_token.length > 0 &&
      session.access_token.length <= 8192 && typeof session.user?.id === 'string' && session.user.id.length <= 64 &&
      session.user.id.length > 0 && Number.isFinite(session.expires_at)
  }
  function accept(session) {
    if (session === null) { invalidate(); publish('unauthenticated'); return }
    if (!valid(session)) throw { status: 400 }
    if (userId !== session.user.id) { cancelCredentialRequests(client); invalidate() }
    userId = session.user.id; token = session.access_token; expiresAt = session.expires_at
    if (expiresAt <= Date.now() / 1000) {
      publish('refreshing')
      // Never call an SDK auth method from inside its synchronous event callback.
      queueMicrotask(() => { if (listeners.size && !locked) refresh().catch(() => {}) })
    } else publish('authenticated')
  }
  function restore() {
    if (restoring) return restoring
    const ticket = revision
    restoring = Promise.resolve().then(() => auth.getSession()).then(({ data, error }) => {
      if (!listeners.size || locked || ticket !== revision) return
      if (error) throw error
      accept(data?.session)
    }).catch(error => {
      if (listeners.size && !locked && ticket === revision) rejectSession(error)
    }).finally(() => { restoring = undefined })
    return restoring
  }
  function refresh() {
    if (restoring) return restoring.then(() => refresh())
    if (refreshing) return refreshing
    if (!listeners.size || locked || signingOut) return Promise.reject(failed())
    const epoch = fence, subject = userId, assurance = assuranceRevision
    publish('refreshing')
    refreshing = Promise.resolve().then(() => auth.refreshSession()).then(({ data, error }) => {
      if (fence !== epoch || assurance !== assuranceRevision || locked || signingOut || !listeners.size) throw failed()
      if (error) throw error
      if (!valid(data?.session) || data.session.expires_at <= Date.now() / 1000 ||
          (subject && data.session.user.id !== subject)) throw { status: 400 }
      revision++; accept(data.session)
    }).catch(error => {
      if (fence === epoch && assurance === assuranceRevision && !locked && !signingOut && listeners.size) rejectSession(error)
      throw failed()
    }).finally(() => { refreshing = undefined })
    return refreshing
  }
  function logout() {
    if (signingOut) return signingOut
    cancelCredentialRequests(client)
    revision++; locked = true; invalidate(); publish('logging-out')
    signingOut = Promise.resolve().then(() => auth.signOut({ scope: 'local' })).then(
      result => result?.error ? 'unconfirmed' : 'sdk-accepted', () => 'unconfirmed',
    ).then(outcome => {
      invalidate()
      publish(outcome === 'unconfirmed' ? 'error' : 'unauthenticated',
        outcome === 'unconfirmed' ? 'logout-unconfirmed' : null, outcome)
      return Object.freeze({ local: true, provider: outcome })
    }).finally(() => { signingOut = undefined })
    return signingOut
  }
  const controller = Object.freeze({
    getSnapshot: () => state, refresh, logout,
    subscribe(listener) {
      listeners.add(listener)
      if (listeners.size === 1) {
        let alive = true
        try {
          if (!locked) publish('restoring')
          const { data } = auth.onAuthStateChange((event, session) => {
            if (!alive) return
            revision++
            if (event === 'SIGNED_OUT') {
              cancelCredentialRequests(client)
              locked = true; invalidate()
              if (!signingOut) publish('unauthenticated')
              return
            }
            if (signingOut || (locked && !['SIGNED_IN', 'PASSWORD_RECOVERY'].includes(event))) return
            // Pinned SDK MFA event emits token response data, not the saved Session wrapper.
            if (event === 'MFA_CHALLENGE_VERIFIED') {
              if (!userId || session?.user?.id !== userId || !Number.isSafeInteger(session?.expires_in) || session.expires_in <= 0) {
                rejectSession({ status: 400 }); return
              }
              session = { ...session, expires_at: Math.floor(Date.now()/1000) + session.expires_in }
              assuranceRevision++
            }
            if (['SIGNED_IN', 'PASSWORD_RECOVERY', 'TOKEN_REFRESHED'].includes(event)) cancelCredentialRequests(client)
            locked = false
            try { accept(session) } catch (error) { rejectSession(error) }
          })
          subscription = () => { alive = false; data.subscription.unsubscribe() }
          if (!locked && state.status === 'restoring') restore()
        } catch (error) { rejectSession(error) }
      }
      return () => {
        listeners.delete(listener)
        if (!listeners.size) {
          subscription?.(); subscription = undefined
          invalidate()
          if (!locked) publish('unauthenticated')
        }
      }
    },
    // Trusted API bridge only; never place this controller/lease in React context.
    async withAccess(operation) {
      const epoch = fence
      if (restoring) await waitFor(restoring, epoch.signal)
      if (refreshing) await waitFor(refreshing, epoch.signal)
      if (token && expiresAt <= Date.now() / 1000) await waitFor(refresh(), epoch.signal)
      if (epoch !== fence || epoch.signal.aborted) throw changed()
      if (!listeners.size || locked || !token || signingOut) throw failed()
      const subject = userId
      const assertCurrent = () => {
        if (epoch !== fence || epoch.signal.aborted || locked || userId !== subject || !listeners.size) throw changed()
      }
      const lease = Object.freeze({ authorization: 'Bearer ' + token, userId: subject,
        expiresAt, signal: epoch.signal, assertCurrent })
      try { const value = await operation(lease); assertCurrent(); return value }
      catch (error) { assertCurrent(); throw error }
    },
  })
  controllers.set(client, controller)
  return controller
}

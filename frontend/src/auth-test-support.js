import assert from 'node:assert/strict'
import { getSessionController } from './auth-session.js'

export const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
export const tick = () => new Promise(resolve => setImmediate(resolve))
export const value = (id = 'user-a', expires = Date.now()/1000 + 600) => ({
  access_token: 'synthetic-access-' + id, refresh_token: 'synthetic-refresh', expires_at: expires, user: { id },
})
export function fixture() {
  const load = deferred(), renewal = deferred(), exit = deferred(), handlers = new Set()
  const counts = { restore: 0, refresh: 0, logout: 0, subscriptions: 0, cleanup: 0 }
  const client = { auth: {
    getSession: () => { counts.restore++; return load.promise },
    refreshSession: () => { counts.refresh++; return renewal.promise },
    signOut: options => { assert.deepEqual(options, { scope: 'local' }); counts.logout++; return exit.promise },
    onAuthStateChange(fn) {
      counts.subscriptions++; handlers.add(fn)
      return { data: { subscription: { unsubscribe() { counts.cleanup++; handlers.delete(fn) } } } }
    },
  } }
  return { session: getSessionController(client), client, counts, load, renewal, exit,
    emit: (event, session) => { for (const fn of handlers) fn(event, session) } }
}

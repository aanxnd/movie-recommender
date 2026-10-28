const KEY = 'movelle.identity.v1'
let current = null

export function parseIdentity(value) {
  if (!value || !Number.isSafeInteger(value.id) || value.id < 1 || !/^[A-Za-z0-9_-]{43}$/.test(value.token)) return null
  return { id: value.id, token: value.token }
}

export function readIdentity(storage = globalThis.localStorage) {
  try { current = parseIdentity(JSON.parse(storage.getItem(KEY))); return current } catch { return null }
}

export function saveIdentity(value, storage = globalThis.localStorage) {
  current = parseIdentity(value)
  if (!current) throw new Error('Invalid profile credential.')
  try { storage.setItem(KEY, JSON.stringify(current)) } catch {
    throw new Error('Browser storage is unavailable. Keep your recovery code before closing this page.')
  }
  return current
}

export function identityToken() { return current?.token }
export function clearIdentity(storage = globalThis.localStorage) {
  current = null
  try { storage.removeItem(KEY) } catch { /* In-memory identity still cleared. */ }
}

export function parseRecoveryCode(code) {
  const [id, token, extra] = code.trim().split(':')
  const value = !extra && parseIdentity({ id: Number(id), token })
  if (!value) throw new Error('Enter the private recovery code (ID:credential), not just a numeric ID.')
  return value
}

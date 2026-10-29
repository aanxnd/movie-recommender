export const IDENTITY_KEY = 'movelle.identity.v1'

export function parseIdentity(value) {
  if (!value || !Number.isSafeInteger(value.id) || value.id < 1 || !/^[A-Za-z0-9_-]{43}$/.test(value.token)) return null
  return { id: value.id, token: value.token }
}

export function readIdentity(storage) {
  try { return parseIdentity(JSON.parse((storage ?? globalThis.localStorage).getItem(IDENTITY_KEY))) } catch { return null }
}

export function saveIdentity(value, storage) {
  const next = parseIdentity(value)
  if (!next) throw new Error('Invalid profile credential.')
  try { (storage ?? globalThis.localStorage).setItem(IDENTITY_KEY, JSON.stringify(next)) } catch {
    throw new Error('Browser storage is unavailable. Keep your recovery code before closing this page.')
  }
  return next
}

export function clearIdentity(storage) {
  (storage ?? globalThis.localStorage).removeItem(IDENTITY_KEY)
}

export function sameIdentity(left, right) {
  return left?.id === right?.id && left?.token === right?.token
}

export function parseRecoveryCode(code) {
  const [id, token, extra] = code.trim().split(':')
  const value = !extra && parseIdentity({ id: Number(id), token })
  if (!value) throw new Error('Enter the private recovery code (ID:credential), not just a numeric ID.')
  return value
}

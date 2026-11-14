// Temporary provider credentials only. Never persist, log, interpolate HTML or send to a QR service.
import { denyMfa } from './mfa-evidence.js'

export function validateSetup(data, browser) {
  const secret = data?.totp?.secret, raw = data?.totp?.qr_code, uri = data?.totp?.uri
  if (typeof secret !== 'string' || !/^[A-Z2-7]{16,128}$/.test(secret) ||
      typeof raw !== 'string' || raw.length > 1048576 || !raw.startsWith('data:image/svg+xml;utf-8,') ||
      typeof uri !== 'string' || uri.length > 2048) denyMfa('unavailable')
  const otp = new URL(uri)
  if (otp.protocol !== 'otpauth:' || otp.hostname !== 'totp' || otp.hash || otp.username || otp.password ||
      otp.searchParams.get('secret') !== secret ||
      [...otp.searchParams.keys()].some(k => !['secret', 'issuer', 'algorithm', 'digits', 'period'].includes(k)) ||
      [...new Set(otp.searchParams.keys())].some(k => otp.searchParams.getAll(k).length !== 1) ||
      (otp.searchParams.has('algorithm') && otp.searchParams.get('algorithm') !== 'SHA1') ||
      (otp.searchParams.has('digits') && otp.searchParams.get('digits') !== '6') ||
      (otp.searchParams.has('period') && otp.searchParams.get('period') !== '30')) denyMfa('unavailable')
  const xml = raw.slice('data:image/svg+xml;utf-8,'.length)
  if (/<!DOCTYPE|<!ENTITY/i.test(xml) || (xml.match(/<[^!?/\s>]/g)?.length ?? 0) > 10000) denyMfa('unavailable')
  const doc = new browser.DOMParser().parseFromString(xml, 'image/svg+xml')
  if (doc.documentElement.localName !== 'svg' || doc.querySelector('parsererror')) denyMfa('unavailable')
  for (const element of doc.querySelectorAll('*')) {
    if (!['svg', 'g', 'path', 'rect'].includes(element.localName) || element.namespaceURI !== 'http://www.w3.org/2000/svg') denyMfa('unavailable')
    for (const attr of element.attributes) {
      const valid = attr.name === 'xmlns' ? attr.value === 'http://www.w3.org/2000/svg' :
        attr.name === 'xmlns:xlink' ? element === doc.documentElement && attr.value === 'http://www.w3.org/1999/xlink' :
        attr.name === 'style' ? element.localName === 'rect' && /^(fill:black;stroke:none|fill:white;stroke:none)$/.test(attr.value) :
        ['width', 'height', 'viewBox', 'x', 'y', 'rx', 'ry'].includes(attr.name) ? /^[0-9.,\s-]{1,100}$/.test(attr.value) :
        attr.name === 'fill' ? /^(#[0-9a-f]{3,8}|black|white|none)$/i.test(attr.value) :
        attr.name === 'd' && /^[MmLlHhVvZz0-9.,\s-]+$/.test(attr.value)
      if (!valid) denyMfa('unavailable')
    }
  }
  return { secret, qr: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml) }
}

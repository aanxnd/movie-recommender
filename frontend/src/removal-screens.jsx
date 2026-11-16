import { useEffect, useId, useState } from 'react'
import { AuthFrame, AuthNotice, Password } from './account-screens.jsx'
import { useFormScope } from './password-screens.jsx'
import { pendingDeletion, pendingFactorRemoval } from './removal-contract.js'
import { nativeUuid } from './auth-identifiers.js'

export function AccountRemovalScreen({ service = pendingDeletion, factor = false }) {
  const f = useFormScope(), id = useId(), [inventory, setInventory] = useState(null)
  const available = service.available === true && f.auth.status === 'authenticated'
  useEffect(() => {
    let alive = true; setInventory(null)
    if (available) Promise.resolve().then(() => service.inspect()).then(value => { if (alive) setInventory(value) }, () => { if (alive) setInventory({ status: 'unavailable' }) })
    return () => { alive = false }
  }, [available, service, f.auth.generation])
  const factors = Array.isArray(inventory?.factors) ? inventory.factors.filter(x => x.status === 'verified') : []
  const supported = Array.isArray(inventory?.factors) && inventory.factors.every(x => x && nativeUuid(x.id) && typeof x.label === 'string') &&
    (inventory.status === 'not-enrolled' ? inventory.factors.length === 0 : ['verified', 'challenge-required'].includes(inventory.status) && factors.length > 0)
  const confirmation = factor ? 'REMOVE EVEN IF MFA IS DISABLED' : 'PERMANENTLY DELETE MY ACCOUNT'
  async function submit(event) {
    event.preventDefault()
    if (!available || !supported || !f.form.current.reportValidity()) return
    const data = new FormData(f.form.current), scope = f.begin()
    if (!scope) return
    f.form.current.reset()
    try {
      const selected = data.get('authenticator')
      const outcome = factor ? await service.remove({ factorId: data.get('target'), authenticatingFactorId: selected,
        code: data.get('code'), confirmation: data.get('confirmation') }, { signal: scope.signal }) :
        await service.deleteAccount({ password: data.get('password'), confirmation: data.get('confirmation'),
          requestId: crypto.randomUUID(), ...(selected ? { factorId: selected, code: data.get('code') } : {}) }, { signal: scope.signal })
      scope.report(['pending', 'removed', 'rate-limited', 'cancelled'].includes(outcome?.status) ? outcome.status : 'uncertain')
    } catch { scope.report('uncertain') } finally { scope.finish() }
  }
  return <AuthFrame title={factor ? 'Remove an authenticator.' : 'Delete your account.'} description="Review irreversible consequences before continuing.">
    <AuthNotice error>{factor ? 'Every removal can disable MFA, even if another device showed more factors. No backup-retention guarantee is available.' :
      'Once accepted, deletion blocks personal access and may permanently erase your identity, profile, ratings and invitations. Processing can be delayed or partially complete; cancellation is not promised.'}</AuthNotice>
    {!available ? <AuthNotice>Execution is disabled pending security and operational review. No account change will be sent.</AuthNotice> :
      f.status === 'pending' ? <><AuthNotice>Deletion is pending. Personal access is blocked; this does not confirm erasure.</AuthNotice>
        <button onClick={() => f.auth.logout()}>Sign out</button></> :
      !supported || (factor && !factors.length) ? <AuthNotice>Fresh authenticator evidence is unavailable. This operation cannot continue.</AuthNotice> :
      <form ref={f.form} onSubmit={submit} aria-busy={f.busy}>
        {factor ? <label htmlFor={id+'-target'}>Authenticator to remove<select id={id+'-target'} name="target" required disabled={f.busy}>
          {factors.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label> :
          <Password id={id+'-password'} name="password" label="Current password" autoComplete="current-password" disabled={f.busy} />}
        {factors.length > 0 && <><label htmlFor={id+'-factor'}>Accessible authenticator<select id={id+'-factor'} name="authenticator" required disabled={f.busy}>
          {factors.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
          <label htmlFor={id+'-code'}>Fresh six-digit code<input id={id+'-code'} name="code" type="password" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required disabled={f.busy} /></label></>}
        <label htmlFor={id+'-confirm'}>Type {confirmation}<input id={id+'-confirm'} name="confirmation" required pattern={confirmation} autoComplete="off" disabled={f.busy} /></label>
        {f.status && <AuthNotice error>The operation could not be confirmed. It may have reached the service. Recheck before another explicit request.</AuthNotice>}
        <button className="button-primary" disabled={f.busy}>{factor ? 'Remove with possible MFA opt-out' : 'Request permanent deletion'}</button>
      </form>}
  </AuthFrame>
}

export function FactorRemovalScreen({ service = pendingFactorRemoval }) {
  return <AccountRemovalScreen service={service} factor />
}

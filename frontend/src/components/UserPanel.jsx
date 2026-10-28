import { useEffect, useState } from 'react'
import { UserRound, Plus } from 'lucide-react'
import { request } from '../api.js'
import { identityToken, parseRecoveryCode, saveIdentity } from '../identity.js'

export default function UserPanel({ user, onSelect }) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [code, setCode] = useState('')
  const [invitation, setInvitation] = useState('')
  useEffect(() => {
    if (user && identityToken()) setCode(`${user.id}:${identityToken()}`)
    else setCode('')
    setInvitation('')
  }, [user?.id])

  async function select(create) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const next = create ? await request('/users', { method: 'POST' }) : parseRecoveryCode(input)
      setCode(`${next.id}:${next.token}`)
      if (!create) await request(`/users/${next.id}`, { token: next.token })
      saveIdentity(next)
      onSelect(next)
      setInput('')
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <aside className="border-b border-stone-200 bg-stone-100/70 p-6 lg:border-b-0 lg:border-r lg:p-8">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-stone-500"><UserRound size={15} aria-hidden="true" /> Application user</div>
    <p role="status" className="mt-4 text-2xl font-semibold text-stone-900">{user ? `User ${user.id}` : 'No user selected'}</p>
    <p className="mt-2 text-sm leading-relaxed text-stone-600">{user ? 'This browser remembers your private profile credential.' : 'Create a profile or restore your private recovery code.'}</p>
    <button onClick={() => select(true)} disabled={busy} className="button-primary mt-5 w-full"><Plus size={16} aria-hidden="true" />{busy ? 'Please wait…' : 'Create new user'}</button>
    <form onSubmit={(event) => { event.preventDefault(); select(false) }} className="mt-6">
      <label htmlFor="user-id" className="text-sm font-medium">Private recovery code</label>
      <div className="mt-2 flex gap-2"><input id="user-id" type="password" autoComplete="off" placeholder="ID:credential" value={input} onChange={(event) => setInput(event.target.value)} className="min-w-0 flex-1" disabled={busy} /><button className="button-secondary" disabled={busy}>Load</button></div>
    </form>
    {code && <label className="mt-4 block text-xs">Private recovery code: save securely; never share for groups<input className="mt-2 w-full" type="password" readOnly value={code} onFocus={(event) => event.target.select()} /></label>}
    {user && <div className="mt-4"><button className="button-secondary" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { const result = await request(`/users/${user.id}/group-invitation`, { method: 'POST' }); setInvitation(result.code) } catch (e) { setError(e.message) } finally { setBusy(false) } }}>Create 10-minute group invitation</button>{invitation && <input aria-label="Group invitation" className="mt-2 w-full" readOnly value={invitation} onFocus={(event) => event.target.select()} />}<button className="button-secondary mt-2" disabled={busy} onClick={async () => { setBusy(true); try { await request(`/users/${user.id}/group-invitation`, { method: 'DELETE' }); setInvitation('') } catch (e) { setError(e.message) } finally { setBusy(false) } }}>Revoke invitation</button></div>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <p className="mt-6 border-t border-stone-200 pt-4 text-xs leading-relaxed text-stone-500">Your number is not a password. Keep your recovery code private. Group invitations grant temporary recommendation access only.</p>
  </aside>
}

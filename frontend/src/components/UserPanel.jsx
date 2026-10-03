import { useState } from 'react'
import { UserRound, Plus } from 'lucide-react'
import { parseUserId, request } from '../api.js'

export default function UserPanel({ user, onSelect }) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function select(create) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const next = create ? await request('/users', { method: 'POST' }) : await request(`/users/${parseUserId(input)}`)
      onSelect(next)
      setInput(String(next.id))
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <aside className="border-b border-stone-200 bg-stone-100/70 p-6 lg:border-b-0 lg:border-r lg:p-8">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-stone-500"><UserRound size={15} aria-hidden="true" /> Application user</div>
    <p role="status" className="mt-4 text-2xl font-semibold text-stone-900">{user ? `User ${user.id}` : 'No user selected'}</p>
    <p className="mt-2 text-sm leading-relaxed text-stone-600">{user ? 'Keep this ID to load your saved ratings next time.' : 'Create a user or load an existing ID to start rating.'}</p>
    <button onClick={() => select(true)} disabled={busy} className="button-primary mt-5 w-full"><Plus size={16} aria-hidden="true" />{busy ? 'Please wait…' : 'Create new user'}</button>
    <form onSubmit={(event) => { event.preventDefault(); select(false) }} className="mt-6">
      <label htmlFor="user-id" className="text-sm font-medium">Existing user ID</label>
      <div className="mt-2 flex gap-2"><input id="user-id" inputMode="numeric" placeholder="e.g. 1" value={input} onChange={(event) => setInput(event.target.value)} className="min-w-0 flex-1" disabled={busy} /><button className="button-secondary" disabled={busy}>Load</button></div>
    </form>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <p className="mt-6 border-t border-stone-200 pt-4 text-xs leading-relaxed text-stone-500">Users are saved rating profiles identified by a number. No sign-in is required.</p>
  </aside>
}

import { useEffect, useRef, useState } from 'react'
import { useAuth } from './auth-context.js'
import ArtworkProvider from './components/ArtworkProvider.jsx'
import Library from './components/Library.jsx'
import Recommendations from './components/Recommendations.jsx'

const modes = { recommendations: Object.freeze({ mode: 'personal' }), groups: Object.freeze({ mode: 'group' }) }

// A display-only numeric profile comes from /users/me, never SDK metadata/storage.
export function StagingMovies({ api, onProfile }) {
  const auth = useAuth()
  return <MovieWorkspace key={auth.generation + ':' + auth.status} api={api} onProfile={onProfile} />
}

function MovieWorkspace({ api, onProfile }) {
  const auth = useAuth(), [page, setPage] = useState('search'), [reload, setReload] = useState(0)
  const [owner, setOwner] = useState(null), [rows, setRows] = useState([]), [error, setError] = useState('')
  const [pending, setPending] = useState(new Set()), [notice, setNotice] = useState(''), [grant, setGrant] = useState('')
  const [total, setTotal] = useState(0), [cursor, setCursor] = useState(null), [busy, setBusy] = useState(false)
  const [inviting, setInviting] = useState(false), [findRequest, setFindRequest] = useState(null)
  const active = useRef(false), writes = useRef(new Set()), loading = useRef(false), reading = useRef(null)
  const authenticated = auth.status === 'authenticated'
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  useEffect(() => {
    const scope = new AbortController()
    reading.current = scope
    setOwner(null); setRows([]); setTotal(0); setCursor(null); setError(''); setGrant(''); setBusy(authenticated)
    if (authenticated) (async () => {
      try {
        const value = await api('/users/me', { signal: scope.signal })
        if (!Number.isSafeInteger(value?.id) || value.id <= 0 || Object.keys(value).join(',') !== 'id') throw new Error()
        const saved = await api(`/users/${value.id}/ratings/details`, { signal: scope.signal })
        if (!Array.isArray(saved?.items)) throw new Error()
        if (!scope.signal.aborted) { setOwner(value); setRows(saved.items); setTotal(saved.total); setCursor(saved.next_after) }
      } catch { if (!scope.signal.aborted) setError('Personal access requires a confirmed email, supported MFA evidence and completed profile setup.') }
      finally { if (!scope.signal.aborted) setBusy(false) }
    })()
    return () => scope.abort()
  }, [api, auth.generation, authenticated, reload])
  useEffect(() => {
    if (!grant) return
    const timer = setTimeout(() => setGrant(''), 600000)
    return () => clearTimeout(timer)
  }, [grant])
  async function more() {
    if (!owner || cursor === null || loading.current === reading.current || busy) return
    const scope = reading.current
    loading.current = scope; setBusy(true)
    try {
      const saved = await api(`/users/${owner.id}/ratings/details?after=${cursor}`, { signal: scope.signal })
      if (!scope.signal.aborted) { setRows(previous => [...previous, ...saved.items]); setTotal(saved.total); setCursor(saved.next_after) }
    } catch { if (!scope.signal.aborted) setNotice('Saved ratings could not be loaded. Try again when available.') }
    finally { if (loading.current === scope) loading.current = null; if (!scope.signal.aborted) setBusy(false) }
  }
  async function rate(movie, rating) {
    const id = movie?.movie_id
    if (!Number.isSafeInteger(id) || id <= 0) return
    const key = `${owner?.id}:${id}`
    if (!owner || writes.current.has(key)) return
    writes.current.add(key); setPending(previous => new Set(previous).add(key)); setNotice('')
    try {
      await api(`/users/${owner.id}/ratings/${id}`, { method: 'PUT', body: { rating } })
      if (active.current) setReload(value => value + 1)
    } catch { if (active.current) setNotice('The rating could not be confirmed and may have saved. Check your profile before retrying.') }
    finally { writes.current.delete(key); if (active.current) setPending(previous => { const next = new Set(previous); next.delete(key); return next }) }
  }
  async function invite() {
    if (!owner || writes.current.has('invitation')) return
    writes.current.add('invitation'); setInviting(true); setGrant('')
    try { const value = await api(`/users/${owner.id}/group-invitation`, { method: 'POST' }); if (active.current) setGrant(value.code) }
    catch { if (active.current) setNotice('The invitation could not be confirmed. Check again before creating another.') }
    finally { writes.current.delete('invitation'); if (active.current) setInviting(false) }
  }
  return <ArtworkProvider api={api} onFind={movie => { setPage('search'); setFindRequest({ movie }) }}>
    <main className="app-main"><h1>Movelle staging movies</h1>
      <nav aria-label="Movie sections" style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {['search', 'ratings', 'recommendations', 'groups'].map(value => <button key={value} onClick={() => setPage(value)}>{value}</button>)}
        <button onClick={() => setReload(value => value + 1)}>Check personal access</button>
        {owner && <button onClick={invite} disabled={inviting}>Create group invitation</button>}
      </nav>
      {error && <p role="status">{error}</p>}{notice && <p role="status">{notice}</p>}
      {grant && <label>Temporary group invitation<input readOnly value={grant} /></label>}
      {modes[page] ? <Recommendations api={api} user={owner} revision={reload} requestedMode={modes[page]} onProfile={onProfile} /> :
        <Library api={api} user={owner} ratings={rows} pendingRatings={pending} ratingsBusy={busy} ratingsError=""
          ratingsTotal={total} nextAfter={cursor} onMore={more} onReload={() => setReload(value => value + 1)} onRate={rate}
          onProfile={onProfile} requestedView={page} findRequest={findRequest} ratingsRevision={reload} />}
    </main>
  </ArtworkProvider>
}

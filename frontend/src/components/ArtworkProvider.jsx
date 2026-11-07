import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { request } from '../api.js'
import FilmDialog from './FilmDialog.jsx'
import { ArtworkContext } from '../artwork.js'

export default function ArtworkProvider({ children, onFind, user }) {
  const [items, setItems] = useState(new Map())
  const [film, setFilm] = useState(null)
  const [preference, setPreference] = useState(null)
  const personalKey = preference?.owner === user?.token ? preference?.key || '' : ''
  const personalOwner = personalKey ? user?.token : undefined
  const session = useMemo(() => ({
    controller: new AbortController(), known: new Set(), queue: new Set(), timer: null,
    personalKey, token: personalOwner,
  }), [personalKey, personalOwner])
  const current = useRef(session)
  current.current = session
  useLayoutEffect(() => {
    session.controller = new AbortController()
    session.known.clear()
    session.queue.clear()
    setItems(new Map())
    return () => { session.controller.abort(); clearTimeout(session.timer) }
  }, [session])
  // Drop the raw key when its owner changes, even if the previous owner returns.
  useEffect(() => setPreference(null), [user?.token])

  const load = useCallback(async (batch, details = false) => {
    const controller = session.controller
    let rows = []
    try {
      rows = (await request('/movies/artwork', {
        method: 'POST', token: session.personalKey ? session.token : undefined,
        body: { movie_ids: batch, ...(session.personalKey ? { personal_key: session.personalKey } : {}), ...(details ? { include_credits: true } : {}) },
        signal: controller.signal, timeoutMs: 30000,
      })).items || []
    } catch { if (controller.signal.aborted) return }
    if (controller.signal.aborted || current.current !== session) return
    setItems(previous => {
      const next = new Map(previous)
      for (const id of batch) {
        const row = rows.find(item => item.movie_id === id)
        if (row) {
          const existing = previous.get(id)
          const merged = { ...existing, ...row }
          if (existing?.credits_loaded && !row.credits_loaded) {
            merged.director = existing.director
            merged.credits_loaded = true
          }
          next.set(id, merged)
        }
        else if (!details) next.set(id, null)
      }
      return next
    })
  }, [session])
  const enqueue = useCallback(movie => {
    if (session.known.has(movie.movie_id)) return
    session.known.add(movie.movie_id)
    session.queue.add(movie.movie_id)
    clearTimeout(session.timer)
    session.timer = setTimeout(async () => {
      const ids = [...session.queue]; session.queue.clear()
      for (let offset = 0; offset < ids.length; offset += 8) {
        if (session.controller.signal.aborted) return
        await load(ids.slice(offset, offset + 8))
      }
    }, 15)
  }, [session, load])
  const openFilm = useCallback(movie => { setFilm(movie); load([movie.movie_id], true) }, [load])
  return (
    <ArtworkContext.Provider value={{ items, enqueue, openFilm, personalKeySet: Boolean(personalKey), canSetPersonalKey: Boolean(user), setPersonalKey: key => setPreference(key && user ? { owner: user.token, key } : null) }}>
      {children}
      <FilmDialog movie={film} onClose={() => setFilm(null)} onFind={movie => { setFilm(null); onFind(movie) }} />
    </ArtworkContext.Provider>
  )
}

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { request } from '../api.js'
import FilmDialog from './FilmDialog.jsx'
import { ArtworkContext } from '../artwork.js'

export default function ArtworkProvider({ children, onFind, user, api = request }) {
  const [items, setItems] = useState(new Map())
  const [selectedCovers, setSelectedCovers] = useState(new Map())
  const reportCover = useCallback((id, choice) => setSelectedCovers(previous => {
    if (previous.get(id)?.url === choice.url) return previous
    return new Map(previous).set(id, choice)
  }), [])
  const [film, setFilm] = useState(null)
  const [preference, setPreference] = useState(null)
  const personalKey = preference?.owner === user?.token ? preference?.key || '' : ''
  const personalOwner = personalKey ? user?.token : undefined
  const session = useMemo(() => ({
    controller: new AbortController(), known: new Set(), queue: new Set(), timer: null, running: false,
    personalKey, token: personalOwner,
  }), [personalKey, personalOwner, api])
  const current = useRef(session)
  current.current = session
  useLayoutEffect(() => {
    session.controller = new AbortController()
    session.known.clear()
    session.queue.clear()
    session.running = false
    setItems(new Map())
    setSelectedCovers(new Map())
    return () => { session.controller.abort(); clearTimeout(session.timer) }
  }, [session])
  // Drop the raw key when its owner changes, even if the previous owner returns.
  useEffect(() => setPreference(null), [user?.token])

  const load = useCallback(async (batch, details = false) => {
    const controller = session.controller
    let rows = []
    try {
      const reply = await api('/movies/artwork', {
        method: 'POST', token: session.personalKey ? session.token : undefined,
        body: { movie_ids: batch, ...(session.personalKey ? { personal_key: session.personalKey } : {}), ...(details ? { include_credits: true } : {}) },
        signal: controller.signal, timeoutMs: 30000,
      })
      rows = reply.provider === 'trakt+fanart.tv' && Array.isArray(reply.items) ? reply.items : []
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
  }, [session, api])
  const enqueue = useCallback(movie => {
    if (session.known.has(movie.movie_id)) return
    session.known.add(movie.movie_id)
    session.queue.add(movie.movie_id)
    clearTimeout(session.timer)
    session.timer = setTimeout(async () => {
      if (session.running) return
      session.running = true
      try {
        while (session.queue.size && !session.controller.signal.aborted) {
          const ids = [...session.queue].slice(0, 8)
          for (const id of ids) session.queue.delete(id)
          await load(ids)
        }
      } finally {
        session.running = false
      }
    }, 15)
  }, [session, load])
  const openFilm = useCallback(movie => { setFilm(movie); load([movie.movie_id], true) }, [load])
  return (
    <ArtworkContext.Provider value={{ items, enqueue, openFilm, selectedCovers, reportCover, personalKeySet: Boolean(personalKey), canSetPersonalKey: Boolean(user), setPersonalKey: key => setPreference(key && user ? { owner: user.token, key } : null) }}>
      {children}
      <FilmDialog movie={film} onClose={() => setFilm(null)} onFind={movie => { setFilm(null); onFind(movie) }} />
    </ArtworkContext.Provider>
  )
}

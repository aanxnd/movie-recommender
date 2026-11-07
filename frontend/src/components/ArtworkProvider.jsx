import { useCallback, useEffect, useRef, useState } from 'react'
import { request } from '../api.js'
import FilmDialog from './FilmDialog.jsx'
import { ArtworkContext } from '../artwork.js'

export default function ArtworkProvider({ children, onFind }) {
  const [items, setItems] = useState(new Map())
  const [film, setFilm] = useState(null)
  const known = useRef(new Set())
  const queue = useRef(new Set())
  const timer = useRef(null)
  const lifetime = useRef(null)
  useEffect(() => {
    lifetime.current = new AbortController()
    return () => {
      lifetime.current.abort()
      clearTimeout(timer.current)
      known.current.clear()
      queue.current.clear()
    }
  }, [])
  const enqueue = useCallback((movie) => {
    if (known.current.has(movie.movie_id)) return
    known.current.add(movie.movie_id)
    queue.current.add(movie.movie_id)
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      const ids = [...queue.current]
      queue.current.clear()
      const signal = lifetime.current?.signal
      for (let offset = 0; offset < ids.length; offset += 8) {
        const batch = ids.slice(offset, offset + 8)
        let rows = []
        try {
          rows = (
            await request('/movies/artwork', {
              method: 'POST',
              body: { movie_ids: batch },
              signal,
              timeoutMs: 22000,
            })
          ).items
        } catch {
          if (signal?.aborted) return
        }
        if (signal?.aborted) return
        setItems((previous) => {
          const next = new Map(previous)
          for (const id of batch)
            next.set(id, rows.find((row) => row.movie_id === id) || null)
          return next
        })
      }
    }, 15)
  }, [])
  return (
    <ArtworkContext.Provider value={{ items, enqueue, openFilm: setFilm }}>
      {children}
      <FilmDialog
        movie={film}
        onClose={() => setFilm(null)}
        onFind={(movie) => {
          setFilm(null)
          onFind(movie)
        }}
      />
    </ArtworkContext.Provider>
  )
}

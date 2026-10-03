import { useEffect, useRef, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { parseUserId, request } from '../api.js'
import MovieList from './MovieList.jsx'

const modes = { personal: 'For you', popular: 'Popular', genre: 'By genre', group: 'For a group' }

export default function Recommendations({ user, revision }) {
  const [mode, setMode] = useState('personal')
  const [genre, setGenre] = useState('')
  const [group, setGroup] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef(null)

  useEffect(() => {
    controller.current?.abort()
    setResult(null)
    setError('')
    setBusy(false)
    return () => controller.current?.abort()
  }, [mode, revision])

  async function load(event) {
    event.preventDefault()
    if (busy) return
    setError('')
    setResult(null)
    const current = new AbortController()
    controller.current = current
    try {
      let path, options = {}
      let caption = modes[mode]
      if (mode === 'personal') {
        if (!user) throw new Error('Select a user first.')
        path = `/users/${user.id}/recommendations`
        caption = `Recommendations for User ${user.id}`
      } else if (mode === 'popular') path = '/recommendations/popular'
      else if (mode === 'genre') {
        if (!genre.trim()) throw new Error('Enter a genre, such as Drama or Sci-Fi.')
        path = `/recommendations/genre/${encodeURIComponent(genre.trim())}`
        caption = `${genre.trim()} recommendations`
      } else {
        const parts = group.trim().split(/[\s,]+/).filter(Boolean)
        if (parts.length < 2 || parts.length > 100) throw new Error('Enter between 2 and 100 user IDs, separated by commas or spaces.')
        const ids = parts.map(parseUserId)
        if (new Set(ids).size !== ids.length) throw new Error('Each group member must have a different user ID. Remove duplicate IDs.')
        path = '/recommendations/group'
        options = { method: 'POST', body: { user_ids: ids } }
        caption = `Group · Users ${ids.join(', ')}`
      }
      setBusy(true)
      const movies = await request(path, { ...options, signal: current.signal })
      if (!current.signal.aborted) setResult({ movies, caption })
    } catch (error) {
      if (!current.signal.aborted) setError(error.message)
    } finally {
      if (!current.signal.aborted) setBusy(false)
    }
  }

  return <section aria-labelledby="recommendations-title" className="mt-12 border-t border-stone-300 pt-9">
    <div className="eyebrow">What to watch next</div>
    <h2 id="recommendations-title" className="mt-2 text-2xl font-semibold tracking-tight">A fresh shortlist.</h2>
    <div className="mt-5 flex flex-wrap gap-x-6 border-b border-stone-200">
      {Object.entries(modes).map(([key, label]) => <button key={key} aria-pressed={mode === key} className={`tab ${mode === key ? 'tab-active' : ''}`} onClick={() => setMode(key)}>{label}</button>)}
    </div>
    <p className="mt-4 text-sm leading-relaxed text-stone-600">
      {mode === 'personal' && 'Uses your saved ratings. When no usable predictions are available, the API returns popular movies. It does not identify which method produced a list.'}
      {mode === 'popular' && 'Highest historical average ratings, with at least 20 MovieLens ratings per movie.'}
      {mode === 'genre' && 'Popular movies in a genre, with at least 20 MovieLens ratings per movie.'}
      {mode === 'group' && 'Combines members’ saved ratings and excludes movies rated by any member. Shared ratings are averaged, so disagreements may be hidden.'}
    </p>
    <form onSubmit={load} className="my-5 flex flex-col items-start gap-3 sm:flex-row sm:items-end">
      {mode === 'genre' && <label className="w-full text-sm font-medium sm:max-w-sm">Genre<input value={genre} onChange={(event) => setGenre(event.target.value)} placeholder="e.g. Action, Drama, Sci-Fi" className="mt-2 w-full" /></label>}
      {mode === 'group' && <label className="w-full text-sm font-medium sm:max-w-sm">Application user IDs<input value={group} onChange={(event) => setGroup(event.target.value)} placeholder="e.g. 1, 2" className="mt-2 w-full" /></label>}
      <button className="button-primary" disabled={busy || (mode === 'personal' && !user)}>{busy ? 'Finding movies…' : 'Get recommendations'}<ArrowRight size={16} aria-hidden="true" /></button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {busy && <p className="empty" role="status">Finding your next movies…</p>}
    {!busy && !error && !result && <p className="empty">{mode === 'personal' && !user ? 'Select a user to get recommendations.' : 'Request a shortlist to see ranked movies here.'}</p>}
    {result && <>
      <p role="status" className="mb-3 text-xs text-stone-500">{result.caption} · {result.movies.length} movies</p>
      {result.movies.length ? <MovieList movies={result.movies} ranked scoreLabel={mode === 'popular' || mode === 'genre' ? 'Average' : 'Score'} /> : <p className="empty">No eligible movies found. {mode === 'genre' ? 'Try another MovieLens genre.' : 'Try another recommendation view or adjust your saved ratings.'}</p>}
    </>}
  </section>
}

import { useRef, useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { request } from '../api.js'
import MovieList from './MovieList.jsx'

export default function Library({ user, ratings, pendingRatings, ratingsBusy, ratingsError, onReload, onRate }) {
  const [view, setView] = useState('search')
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef(null)
  useEffect(() => () => controller.current?.abort(), [])

  async function search(event) {
    event.preventDefault()
    controller.current?.abort()
    setError('')
    setResult(null)
    if (!query.trim()) { setBusy(false); return }
    const current = new AbortController()
    controller.current = current
    setBusy(true)
    try {
      const movies = await request(`/movies/search?q=${encodeURIComponent(query.trim())}&limit=30`, { signal: current.signal })
      if (!current.signal.aborted) setResult({ query: query.trim(), movies })
    } catch (error) {
      if (!current.signal.aborted) setError(error.message)
    } finally {
      if (!current.signal.aborted) setBusy(false)
    }
  }

  return <section aria-labelledby="library-title">
    <div className="eyebrow">Your collection</div>
    <h1 id="library-title" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Find it. Rate it.</h1>
    <p className="mt-3 text-sm text-stone-600">Search the MovieLens catalog and build your taste profile.</p>
    <div className="mt-7 flex gap-6 border-b border-stone-200">
      <button className={`tab ${view === 'search' ? 'tab-active' : ''}`} onClick={() => setView('search')} aria-pressed={view === 'search'}>Movie search</button>
      <button className={`tab ${view === 'ratings' ? 'tab-active' : ''}`} onClick={() => setView('ratings')} aria-pressed={view === 'ratings'}>Saved ratings {user && !ratingsBusy && !ratingsError && <span className="ml-1 font-mono text-xs">({ratings.length})</span>}</button>
    </div>
    {view === 'search' ? <>
      <form className="my-6 flex gap-2" onSubmit={search}>
        <label htmlFor="movie-search" className="sr-only">Movie title</label>
        <input id="movie-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by movie title…" className="min-w-0 flex-1" />
        <button className="button-primary" disabled={busy}><Search size={16} aria-hidden="true" /><span>{busy ? 'Searching…' : 'Search'}</span></button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {busy && <p className="empty" role="status">Searching the catalog…</p>}
      {!busy && !error && !result && <p className="empty">Start with a movie you’ve seen. Enter a title above.</p>}
      {result && <>
        <p role="status" className="mb-3 text-xs text-stone-500">{result.movies.length} matches for “{result.query}”{result.movies.length === 30 ? ' · First 30 shown; narrow your search for more specific results.' : ''}</p>
        {!user && <p className="mb-4 text-sm text-stone-600">Select a user to save ratings.</p>}
        {user && ratingsBusy && <p role="status" className="mb-4 text-sm text-stone-500">Loading saved ratings before you can rate these movies…</p>}
        {user && ratingsError && <div className="mb-4"><p role="alert" className="error">{ratingsError}</p><button className="button-secondary mt-2" onClick={onReload}>Retry loading ratings</button></div>}
        {result.movies.length ? <MovieList movies={result.movies} ratings={ratings} userId={user?.id} pendingRatings={pendingRatings} onRate={user && !ratingsBusy && !ratingsError ? onRate : undefined} /> : <p className="empty">No movies found. Try a shorter title or another spelling.</p>}
      </>}
    </> : <div className="mt-6">
      {!user ? <p className="empty">Select a user to see their saved ratings.</p> : ratingsBusy ? <p className="empty" role="status">Loading saved ratings…</p> : ratingsError ? <div><p role="alert" className="error">{ratingsError}</p><button className="button-secondary mt-3" onClick={onReload}>Retry loading ratings</button></div> : ratings.length ? <MovieList movies={ratings} ratings={ratings} userId={user.id} pendingRatings={pendingRatings} onRate={onRate} /> : <p className="empty">No ratings yet. Search for a movie and save your first rating.</p>}
    </div>}
  </section>
}

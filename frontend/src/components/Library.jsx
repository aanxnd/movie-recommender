import { useRef, useState, useEffect } from 'react'
import { ArrowUpRight, Search, X } from 'lucide-react'
import { request } from '../api.js'
import MovieList from './MovieList.jsx'
import { EmptyState, SectionHeading, Skeletons } from './ui.jsx'
import CatalogueExplore from './CatalogueExplore.jsx'

export default function Library({
  api = request,
  user,
  ratings,
  pendingRatings,
  ratingsBusy,
  ratingsError,
  onReload,
  onMore,
  nextAfter,
  ratingsTotal,
  onRate,
  requestedView = 'search',
  onViewChange,
  onProfile,
  headingAs = 'h2',
  focusRequest = 0,
  findRequest,
  ratingsRevision,
}) {
  const [view, setView] = useState(requestedView)
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef(null)
  const searchInput = useRef(null)
  useEffect(() => {
    if (!findRequest) return
    setQuery(findRequest.movie.title)
    findMovies(findRequest.movie.title)
    searchInput.current?.focus()
  }, [findRequest])
  useEffect(() => {
    if (focusRequest) searchInput.current?.focus()
  }, [focusRequest])
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    setView(requestedView)
  }, [requestedView])
  useEffect(() => {
    if (result?.query) findMovies(result.query)
  }, [ratingsRevision]) // Explicit staging refresh; production's undefined value stays unchanged.

  function changeView(next) {
    setView(next)
    onViewChange?.(next)
  }

  async function search(event) {
    event.preventDefault()
    return findMovies(query)
  }

  async function findMovies(title) {
    controller.current?.abort()
    setError('')
    setResult(null)
    if (!title.trim()) {
      setBusy(false)
      return
    }
    const current = new AbortController()
    controller.current = current
    setBusy(true)
    try {
      let movies = await api(
        `/movies/search?q=${encodeURIComponent(title.trim())}&limit=30`,
        { signal: current.signal },
      )
      if (user && movies.length) {
        const saved = await api(`/users/${user.id}/ratings/lookup`, {
          token: user.token,
          method: 'POST',
          body: { movie_ids: movies.map((movie) => movie.movie_id) },
          signal: current.signal,
        })
        const byId = new Map(saved.map((row) => [row.movie_id, row]))
        movies = movies.map((movie) => ({
          ...movie,
          ...byId.get(movie.movie_id),
        }))
      }
      if (!current.signal.aborted) setResult({ query: title.trim(), movies })
    } catch (error) {
      if (!current.signal.aborted) setError(error.message)
    } finally {
      if (!current.signal.aborted) setBusy(false)
    }
  }

  return (
    <section
      id="library"
      aria-labelledby="library-title"
      className="library-section"
    >
      <SectionHeading
        as={headingAs}
        id="library-title"
        title={view === 'search' ? 'Discover films' : 'Your ratings'}
        description={
          view === 'ratings'
            ? 'View and update the films you have rated.'
            : undefined
        }
      >
        {view === 'ratings' && user && (
          <span className="collection-count">
            {ratingsTotal} {ratingsTotal === 1 ? 'film' : 'films'} rated
          </span>
        )}
      </SectionHeading>
      {view === 'search' ? (
        <>
          <form className="search-form" onSubmit={search}>
            <Search
              className="search-leading-icon"
              size={21}
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <label htmlFor="movie-search" className="sr-only">
              Movie title
            </label>
            <input
              id="movie-search"
              ref={searchInput}
              type="search"
              value={query}
              maxLength={120}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search movie titles…"
            />
            {query && (
              <button
                type="button"
                className="icon-button clear-search"
                aria-label="Clear movie search"
                onClick={() => {
                  controller.current?.abort()
                  setQuery('')
                  setResult(null)
                  setError('')
                  setBusy(false)
                  searchInput.current?.focus()
                }}
              >
                <X size={17} aria-hidden="true" />
              </button>
            )}
            <button className="button-primary" disabled={busy}>
              {busy ? 'Searching…' : 'Search'}
              <ArrowUpRight size={16} aria-hidden="true" />
            </button>
          </form>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {busy && <Skeletons label="Searching the catalogue…" />}
          {!busy && !error && !result && (
            <CatalogueExplore
              api={api}
              onPick={(movie) => {
                setQuery(movie.title)
                findMovies(movie.title)
                searchInput.current?.focus()
                document
                  .getElementById('library')
                  ?.scrollIntoView({ block: 'start' })
              }}
            />
          )}
          {result && (
            <>
              <p role="status" className="result-caption">
                {result.movies.length} matches for “{result.query}”
                {result.movies.length === 30
                  ? ' · First 30 shown; narrow your search for more specific results.'
                  : ''}
              </p>
              {!user && (
                <p className="notice">
                  <button className="text-link" onClick={onProfile}>
                    Set up your profile
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </button>
                  <span>to save ratings and build your taste profile.</span>
                </p>
              )}
              {user && ratingsBusy && (
                <p role="status" className="result-caption">
                  Loading saved ratings before you can rate these movies…
                </p>
              )}
              {user && ratingsError && (
                <div className="inline-feedback">
                  <p role="alert" className="error">
                    {ratingsError}
                  </p>
                  <button className="button-secondary" onClick={onReload}>
                    Retry loading ratings
                  </button>
                </div>
              )}
              {result.movies.length ? (
                <MovieList
                  movies={result.movies}
                  ratings={ratings}
                  userId={user?.id}
                  pendingRatings={pendingRatings}
                  onRate={
                    user && !ratingsBusy && !ratingsError ? onRate : undefined
                  }
                />
              ) : (
                <EmptyState title="No matching films">
                  <p>
                    No movies found. Try a shorter title or another spelling.
                  </p>
                </EmptyState>
              )}
            </>
          )}
        </>
      ) : (
        <div className="ratings-content">
          {user && (
            <div className="results-toolbar">
              <p className="result-caption">
                {ratingsTotal} {ratingsTotal === 1 ? 'film' : 'films'} in your
                collection
              </p>
              <button
                className="button-secondary"
                disabled={ratingsBusy}
                onClick={onReload}
              >
                Reload saved ratings
              </button>
            </div>
          )}
          {!user ? (
            <EmptyState
              title="No profile selected"
              action={
                <button className="button-primary" onClick={onProfile}>
                  Set up your profile
                  <ArrowUpRight size={16} aria-hidden="true" />
                </button>
              }
            >
              <p>Select a user to see their saved ratings.</p>
            </EmptyState>
          ) : ratingsBusy ? (
            <Skeletons label="Loading saved ratings…" />
          ) : ratingsError ? (
            <div className="inline-feedback">
              <p role="alert" className="error">
                {ratingsError}
              </p>
              <button className="button-secondary" onClick={onReload}>
                Retry loading ratings
              </button>
            </div>
          ) : ratings.length ? (
            <MovieList
              movies={ratings}
              layout="collection"
              ratings={ratings}
              userId={user.id}
              pendingRatings={pendingRatings}
              onRate={onRate}
            />
          ) : (
            <EmptyState
              title="No ratings yet"
              action={
                <button
                  className="button-secondary"
                  onClick={() => changeView('search')}
                >
                  Find a film to rate
                  <Search size={16} aria-hidden="true" />
                </button>
              }
            >
              <p>
                No ratings yet. Search for a movie and save your first rating.
              </p>
            </EmptyState>
          )}
          {nextAfter !== null && (
            <div className="load-more">
              <button
                className="button-secondary"
                disabled={ratingsBusy}
                onClick={onMore}
              >
                Load more saved ratings
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

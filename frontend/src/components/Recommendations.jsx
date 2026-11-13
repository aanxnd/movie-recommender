import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Film, Users } from 'lucide-react'
import { request } from '../api.js'
import { parseRecoveryCode } from '../identity.js'
import MovieList from './MovieList.jsx'
import { evidenceMessage } from '../evidence.js'
import { EmptyState, SectionHeading, Skeletons } from './ui.jsx'

const modes = {
  personal: 'For you',
  popular: 'Popular',
  genre: 'By genre',
  group: 'For a group',
}

export default function Recommendations({
  api = request,
  user,
  revision,
  requestedMode,
  onModeChange,
  onProfile,
  headingAs = 'h2',
}) {
  const [mode, setMode] = useState('personal')
  const [genre, setGenre] = useState('')
  const [group, setGroup] = useState('')
  const [decade, setDecade] = useState('')
  const [decades, setDecades] = useState([])
  const [decadesBusy, setDecadesBusy] = useState(true)
  const [decadesError, setDecadesError] = useState('')
  const [decadesReload, setDecadesReload] = useState(0)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef(null)
  const inFlight = useRef(false)
  useEffect(() => {
    if (requestedMode) setMode(requestedMode.mode)
  }, [requestedMode])

  useEffect(() => {
    const current = new AbortController()
    setDecadesBusy(true)
    setDecadesError('')
    api('/movies/decades', { signal: current.signal })
      .then((values) => {
        if (!current.signal.aborted) setDecades(values)
      })
      .catch((error) => {
        if (!current.signal.aborted) setDecadesError(error.message)
      })
      .finally(() => {
        if (!current.signal.aborted) setDecadesBusy(false)
      })
    return () => current.abort()
  }, [decadesReload, api])

  useEffect(() => {
    controller.current?.abort()
    inFlight.current = false
    setResult(null)
    setError('')
    setBusy(false)
    return () => controller.current?.abort()
  }, [mode, revision, decade, user?.id, genre, group])

  async function load(event) {
    event.preventDefault()
    if (inFlight.current) return
    setError('')
    setResult(null)
    const current = new AbortController()
    controller.current = current
    try {
      let path,
        options = {}
      let caption = modes[mode]
      if (mode === 'personal') {
        if (!user) throw new Error('Select a user first.')
        path = `/users/${user.id}/recommendations`
        caption = `Recommendations for User ${user.id}`
      } else if (mode === 'popular') path = '/recommendations/popular'
      else if (mode === 'genre') {
        if (!genre.trim())
          throw new Error('Enter a genre, such as Drama or Sci-Fi.')
        path = `/recommendations/genre/${encodeURIComponent(genre.trim())}`
        caption = `${genre.trim()} recommendations`
      } else {
        if (!user) throw new Error('Select your profile first.')
        const members = group
          .trim()
          .split(/[\s,]+/)
          .filter(Boolean)
          .map((code) => {
            try {
              return parseRecoveryCode(code)
            } catch {
              throw new Error(
                'Enter group invitation codes in ID:invitation format. Use temporary invitations, never private recovery codes.',
              )
            }
          })
        const ids = [user.id, ...members.map((member) => member.id)]
        if (
          ids.length < 2 ||
          ids.length > 5 ||
          new Set(ids).size !== ids.length
        )
          throw new Error(
            'Enter distinct invitation codes from other group members.',
          )
        path = '/recommendations/group'
        options = {
          method: 'POST',
          body: {
            user_ids: ids,
            invitations: Object.fromEntries(
              members.map((member) => [member.id, member.token]),
            ),
          },
        }
        caption = `Group: ${ids.length} profiles`
      }
      if (decade) {
        path += `?decade=${encodeURIComponent(decade)}`
        caption += ` · ${decade}–${Number(decade) + 9}`
      }
      setBusy(true)
      inFlight.current = true
      const movies = await api(path, {
        ...options,
        token: user?.token,
        signal: current.signal,
        retry: true,
      })
      if (!current.signal.aborted) setResult({ movies, caption })
    } catch (error) {
      if (!current.signal.aborted) setError(error.message)
    } finally {
      if (!current.signal.aborted) {
        setBusy(false)
        inFlight.current = false
      }
    }
  }

  return (
    <section
      aria-labelledby="recommendations-title"
      className="recommendations-section"
    >
      <SectionHeading
        as={headingAs}
        id="recommendations-title"
        title={
          mode === 'personal'
            ? 'Your recommendations'
            : mode === 'popular'
              ? 'Popular films'
              : mode === 'genre'
                ? 'Explore a genre'
                : 'Group recommendations'
        }
        description={
          mode === 'personal'
            ? 'Find films using your ratings and patterns from similar viewers.'
            : mode === 'popular'
              ? 'Highly rated films from the MovieLens catalogue.'
              : mode === 'genre'
                ? 'Find highly rated films in a genre you love.'
                : 'Combine up to five profiles to find a film to watch together.'
        }
      ></SectionHeading>
      <div className="recommendation-controls">
        {mode !== 'group' && (
          <div
            className="tabs recommendation-tabs"
            aria-label="Recommendation views"
          >
            {Object.entries(modes)
              .filter(([key]) => key !== 'group')
              .map(([key, label]) => (
                <button
                  key={key}
                  aria-pressed={mode === key}
                  className={`tab ${mode === key ? 'tab-active' : ''}`}
                  onClick={() => {
                    setMode(key)
                    onModeChange?.(key)
                  }}
                >
                  {label}
                </button>
              ))}
          </div>
        )}
        <details className="model-help">
          <summary>How these picks work</summary>
          <div>
            <p>
              {mode === 'personal' &&
                'Uses collaborative filtering with a modest genre preference adjustment. When no eligible predictions are available, the API returns a labeled popularity fallback.'}
              {mode === 'popular' &&
                'Highest historical average ratings, with at least 20 MovieLens ratings per movie.'}
              {mode === 'genre' &&
                'Popular movies in a genre, with at least 20 MovieLens ratings per movie.'}
              {mode === 'group' &&
                'Combines members’ saved ratings and excludes movies rated by any member. Shared ratings are averaged, so disagreements may be hidden.'}
            </p>
            {(mode === 'personal' || mode === 'group') && (
              <p>
                Confidence measures recommendation evidence on a 0–1 scale, not
                the probability you’ll like a movie. With the current model
                defaults, the theoretical maximum is about 0.83 (83%). Values
                can be substantially lower because neighbors have imperfect
                similarity, limited shared ratings, or have not rated the
                recommended movie. Popularity fallback has no CF confidence.
              </p>
            )}
          </div>
        </details>
      </div>
      {mode === 'group' && (
        <div className="group-guide">
          <Users size={22} strokeWidth={1.4} aria-hidden="true" />
          <div>
            <h3>Invite your group</h3>
            <p>
              Ask 1-4 friends to create an invitation in Profile. Codes last 10
              minutes. Never share private recovery codes.
            </p>
            <button className="text-link" onClick={onProfile}>
              {user ? 'Manage your group invitation' : 'Set up your profile'}
              <ArrowUpRight size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
      {decadesError && (
        <div className="inline-feedback">
          <p role="alert" className="error">
            Could not load available decades: {decadesError} All decades is
            still available.
          </p>
          <button
            className="button-secondary"
            onClick={() => setDecadesReload((value) => value + 1)}
          >
            Retry loading decades
          </button>
        </div>
      )}
      <form onSubmit={load} className="recommendation-form">
        <label className="field-label">
          Release decade
          <select
            value={decade}
            onChange={(event) => setDecade(event.target.value)}
            disabled={decadesBusy}
          >
            <option value="">
              {decadesBusy ? 'Loading decades…' : 'All decades'}
            </option>
            {decades.map((value) => (
              <option key={value} value={value}>
                {value}–{value + 9}
              </option>
            ))}
          </select>
        </label>
        {mode === 'genre' && (
          <label className="field-label flexible-field">
            Genre
            <input
              value={genre}
              maxLength={40}
              onChange={(event) => setGenre(event.target.value)}
              placeholder="e.g. Action, Drama, Sci-Fi"
            />
          </label>
        )}
        {mode === 'group' && (
          <label className="field-label flexible-field">
            Group invitation codes from other members
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={group}
              onChange={(event) => setGroup(event.target.value)}
              placeholder="ID:invitation, ID:invitation"
            />
          </label>
        )}
        <button
          className="button-primary"
          disabled={
            busy || ((mode === 'personal' || mode === 'group') && !user)
          }
        >
          {busy ? 'Finding movies…' : 'Get recommendations'}
          <ArrowUpRight size={17} aria-hidden="true" />
        </button>
        <span className="recommendation-note">
          {mode === 'personal'
            ? 'Your ratings help improve these picks.'
            : mode === 'group'
              ? 'Invitations expire after 10 minutes.'
              : 'Based on historical MovieLens ratings.'}
        </span>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {busy && <Skeletons />}
      {!busy && !error && !result && (
        <EmptyState
          icon={mode === 'group' ? Users : Film}
          title={
            mode === 'personal' && !user
              ? 'Start with your ratings'
              : mode === 'group'
                ? 'Add invitation codes'
                : 'Request recommendations'
          }
          action={
            (mode === 'personal' || mode === 'group') && !user ? (
              <button className="button-secondary" onClick={onProfile}>
                Set up your profile
                <ArrowUpRight size={15} aria-hidden="true" />
              </button>
            ) : undefined
          }
        >
          <p>
            {mode === 'personal' && !user
              ? 'Create a private profile and rate a few films, or explore Popular for a place to start.'
              : mode === 'group'
                ? user
                  ? 'Add your friends’ invitation codes and request a shared shortlist.'
                  : 'Select your profile first, then invite your fellow film lovers.'
                : 'Choose a release decade, or keep an open mind. Request a shortlist to see ranked movies here.'}
          </p>
        </EmptyState>
      )}
      {result && (
        <>
          {evidenceMessage(result.movies) && (
            <p role="status" className="notice evidence-notice">
              {evidenceMessage(result.movies)}
            </p>
          )}
          <div className="results-toolbar">
            <p role="status" className="result-caption">
              {result.caption} · {result.movies.length} movies
            </p>
            {result.movies.length > 0 && (
              <span className="result-caption">Ranked for discovery</span>
            )}
          </div>
          {result.movies.length ? (
            <MovieList
              movies={result.movies}
              ranked
              showConfidence={mode === 'personal' || mode === 'group'}
              scoreLabel={
                mode === 'popular' || mode === 'genre' ? 'Average' : 'Predicted'
              }
            />
          ) : (
            <EmptyState title="No recommendations found">
              <p>
                No eligible movies found.{' '}
                {decade
                  ? 'Try another decade or All decades.'
                  : mode === 'genre'
                    ? 'Try another MovieLens genre.'
                    : 'Try another recommendation view or adjust your saved ratings.'}
              </p>
            </EmptyState>
          )}
        </>
      )}
    </section>
  )
}

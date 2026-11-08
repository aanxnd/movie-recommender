import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { CheckCircle2, X } from 'lucide-react'
import { request } from './api.js'
import UserPanel from './components/UserPanel.jsx'
import Library from './components/Library.jsx'
import Recommendations from './components/Recommendations.jsx'
import AppHeader from './components/AppHeader.jsx'
import ArtworkProvider from './components/ArtworkProvider.jsx'
import ProfileDialog from './components/ProfileDialog.jsx'
import ThemeDialog from './components/ThemeDialog.jsx'
import { THEME_KEY, getTheme, readTheme, saveTheme, themeProperties } from './themes.js'
import {
  IDENTITY_KEY,
  readIdentity,
  saveIdentity,
  sameIdentity,
} from './identity.js'

export default function App() {
  const [user, setUser] = useState(null)
  const [page, setPage] = useState('discover')
  const [profileOpen, setProfileOpen] = useState(false)
  const [themeOpen, setThemeOpen] = useState(false)
  const [theme, setTheme] = useState(readTheme)
  const [themeSaved, setThemeSaved] = useState(true)
  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    const properties = Array.from({ length: root.style.length }, (_, index) => root.style.item(index))
    for (const name of properties.filter(name => name.startsWith('--theme-'))) {
      root.style.removeProperty(name)
    }
    for (const [name, value] of Object.entries(themeProperties(theme))) {
      root.style.setProperty(name, value)
    }
    document.querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', getTheme(theme).colors[0])
  }, [theme])
  useEffect(() => {
    const changed = event => {
      if (event.key === THEME_KEY || event.key === null) {
        setTheme(readTheme())
        setThemeSaved(true)
      }
    }
    window.addEventListener('storage', changed)
    return () => window.removeEventListener('storage', changed)
  }, [])
  function changeTheme(id) {
    setTheme(id)
    setThemeSaved(saveTheme(id))
  }

  const [libraryView, setLibraryView] = useState('search')
  const [recommendationView, setRecommendationView] = useState(null)
  const mainRef = useRef(null)
  const [searchFocus, setSearchFocus] = useState(0)
  const [filmSearchRequest, setFilmSearchRequest] = useState(null)
  function focusSearch() {
    navigate('discover')
    setSearchFocus((value) => value + 1)
  }
  useEffect(() => {
    function shortcut(event) {
      if (profileOpen || themeOpen) return
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        focusSearch()
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [profileOpen, themeOpen])

  function navigate(next) {
    setPage(next)
    if (next === 'ratings' || next === 'discover')
      setLibraryView(next === 'ratings' ? 'ratings' : 'search')
    if (next === 'for-you' || next === 'groups')
      setRecommendationView({ mode: next === 'groups' ? 'group' : 'personal' })
    // Start each view at its heading and make the navigation change available
    // to keyboard and screen-reader users, without adding credential-bearing URLs.
    mainRef.current?.focus({ preventScroll: true })
    window.scrollTo?.({ top: 0, behavior: 'instant' })
  }
  const [ratings, setRatings] = useState([])
  const [ratingsBusy, setRatingsBusy] = useState(false)
  const [nextAfter, setNextAfter] = useState(null)
  const [ratingsTotal, setRatingsTotal] = useState(0)
  const ratingsController = useRef(null)
  const [ratingsError, setRatingsError] = useState('')
  const [reload, setReload] = useState(0)
  const [revision, setRevision] = useState(0)
  const [selection, setSelection] = useState(0)
  const [notice, setNotice] = useState('')
  const [restoreError, setRestoreError] = useState('')
  const [restoreRetry, setRestoreRetry] = useState(0)
  const [pendingRatings, setPendingRatings] = useState(new Set())
  const [ratingErrors, setRatingErrors] = useState({})
  const pendingWrites = useRef(new Set())
  const identityRevision = useRef(0)
  const restoreController = useRef(null)

  function activateUser(next) {
    identityRevision.current++
    restoreController.current?.abort()
    ratingsController.current?.abort()
    setNotice('')
    setRestoreError('')
    setUser(next)
    setRatings([])
    setNextAfter(null)
    setRatingsTotal(0)
    setRatingsError('')
    setRatingsBusy(next !== null)
    setReload((value) => value + 1)
    setRevision((value) => value + 1)
    setSelection((value) => value + 1)
  }

  function selectUser(next) {
    activateUser(saveIdentity(next))
  }

  useEffect(() => {
    function restore() {
      activateUser(null)
      const revision = identityRevision.current
      const stored = readIdentity()
      if (!stored) return
      const current = new AbortController()
      restoreController.current = current
      function complete(error) {
        if (current.signal.aborted || identityRevision.current !== revision)
          return
        // Storage may have changed before its cross-tab event reaches this tab.
        if (!sameIdentity(stored, readIdentity())) {
          restore()
          return
        }
        if (error)
          setRestoreError(`Could not restore profile: ${error.message}`)
        else activateUser(stored) // Restoration never persists an older snapshot.
      }
      request(`/users/${stored.id}`, {
        token: stored.token,
        signal: current.signal,
      }).then(() => complete(), complete)
    }
    function storageChanged(event) {
      if (event.storageArea && event.storageArea !== window.localStorage) return
      if (event.key === IDENTITY_KEY || event.key === null) restore()
    }
    window.addEventListener('storage', storageChanged)
    restore()
    return () => {
      restoreController.current?.abort()
      window.removeEventListener('storage', storageChanged)
    }
  }, [restoreRetry])

  useEffect(() => {
    if (!user) return
    const controller = new AbortController()
    ratingsController.current = controller
    async function loadRatings() {
      setRatingsBusy(true)
      setRatingsError('')
      try {
        const page = await request(`/users/${user.id}/ratings/details`, {
          token: user.token,
          signal: controller.signal,
        })
        if (!controller.signal.aborted) {
          setRatings(page.items)
          setNextAfter(page.next_after)
          setRatingsTotal(page.total)
        }
      } catch (error) {
        if (!controller.signal.aborted) setRatingsError(error.message)
      } finally {
        if (!controller.signal.aborted) setRatingsBusy(false)
      }
    }
    loadRatings()
    return () => controller.abort()
  }, [user, reload])

  async function rateMovie(movie, rating) {
    const userId = user.id
    const selectedRevision = identityRevision.current
    const key = `${userId}:${movie.movie_id}`
    if (pendingWrites.current.has(key)) return
    pendingWrites.current.add(key)
    setPendingRatings(new Set(pendingWrites.current))
    setNotice('')
    setRatingErrors((previous) => {
      const next = { ...previous }
      delete next[key]
      return next
    })
    try {
      const row = await request(`/users/${userId}/ratings/${movie.movie_id}`, {
        token: user.token,
        method: 'PUT',
        body: { rating },
      })
      if (identityRevision.current !== selectedRevision) return
      ratingsController.current?.abort()
      setRatingsBusy(false)
      setNotice(`Saved ${row.rating} / 5 for ${movie.title}.`)
      setRatings((previous) =>
        [
          ...previous.filter((item) => item.movie_id !== movie.movie_id),
          { ...movie, ...row },
        ].sort((a, b) => a.movie_id - b.movie_id),
      )
      setRevision((value) => value + 1)
      if (
        movie.rating === undefined &&
        !ratings.some((item) => item.movie_id === movie.movie_id)
      )
        setRatingsTotal((value) => value + 1)
    } catch (error) {
      if (identityRevision.current !== selectedRevision) return
      setRatingErrors((previous) => ({
        ...previous,
        [key]: `Could not save ${movie.title}: ${error.message} Retry using Save or Update.`,
      }))
    } finally {
      pendingWrites.current.delete(key)
      setPendingRatings(new Set(pendingWrites.current))
    }
  }

  async function loadMore() {
    if (nextAfter === null || ratingsBusy || !user) return
    const userId = user.id
    const selectedRevision = identityRevision.current
    const current = new AbortController()
    ratingsController.current?.abort()
    ratingsController.current = current
    setRatingsBusy(true)
    setRatingsError('')
    try {
      const page = await request(
        `/users/${userId}/ratings/details?after=${nextAfter}`,
        { token: user.token, signal: current.signal },
      )
      if (
        !current.signal.aborted &&
        identityRevision.current === selectedRevision
      ) {
        setRatings((previous) => [
          ...new Map(
            [...previous, ...page.items].map((row) => [row.movie_id, row]),
          ).values(),
        ])
        setNextAfter(page.next_after)
        setRatingsTotal(page.total)
      }
    } catch (error) {
      if (
        !current.signal.aborted &&
        identityRevision.current === selectedRevision
      )
        setRatingsError(error.message)
    } finally {
      if (
        !current.signal.aborted &&
        identityRevision.current === selectedRevision
      )
        setRatingsBusy(false)
    }
  }

  return (
    <ArtworkProvider
      user={user}
      onFind={(movie) => {
        navigate('discover')
        setFilmSearchRequest({ movie })
      }}
    >
      <div className="app-shell" data-view={page}>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <AppHeader
          page={page}
          user={user}
          onNavigate={navigate}
          onSearch={focusSearch}
          onProfile={() => setProfileOpen(true)}
          onTheme={() => setThemeOpen(true)}
        />
        <main
          id="main-content"
          ref={mainRef}
          tabIndex={-1}
          className="content-wrap"
        >
          {restoreError && (
            <div className="inline-feedback restore-feedback">
              <p role="alert" className="error">
                {restoreError}
              </p>
              <button
                className="button-secondary"
                onClick={() => setRestoreRetry((value) => value + 1)}
              >
                Retry restoring profile
              </button>
            </div>
          )}
          {Object.entries(ratingErrors)
            .filter(([key]) => key.startsWith(`${user?.id}:`))
            .map(([key, message]) => (
              <p key={key} role="alert" className="error">
                {message}
              </p>
            ))}
          <div
            className="page-view"
            hidden={page === 'for-you' || page === 'groups'}
          >
            <Library
              key={`library-${selection}`}
              user={user}
              ratings={ratings}
              pendingRatings={pendingRatings}
              ratingsBusy={ratingsBusy}
              ratingsError={ratingsError}
              onReload={() => setReload((value) => value + 1)}
              onMore={loadMore}
              nextAfter={nextAfter}
              ratingsTotal={ratingsTotal}
              onRate={rateMovie}
              headingAs="h1"
              requestedView={libraryView}
              focusRequest={searchFocus}
              findRequest={filmSearchRequest}
              onViewChange={(view) => {
                setLibraryView(view)
                setPage(view === 'ratings' ? 'ratings' : 'discover')
              }}
              onProfile={() => setProfileOpen(true)}
            />
          </div>
          <div
            className="page-view"
            hidden={page === 'discover' || page === 'ratings'}
          >
            <Recommendations
              key={`recommendations-${selection}`}
              user={user}
              revision={revision}
              headingAs="h1"
              requestedMode={recommendationView}
              onModeChange={(mode) => {
                setRecommendationView({ mode })
                setPage((current) =>
                  mode === 'group'
                    ? 'groups'
                    : current === 'groups'
                      ? 'for-you'
                      : current,
                )
              }}
              onProfile={() => setProfileOpen(true)}
            />
          </div>
        </main>
        <footer className="site-footer content-wrap">
          <span className="footer-brand">Movelle</span>
          <section className="film-credits" aria-label="Credits">
            <h2>Credits</h2>
            <p>Catalogue and ratings: MovieLens.</p>
            <p>Movelle uses <a href="https://trakt.tv/" target="_blank" rel="noreferrer">Trakt</a> but is not endorsed or certified by Trakt.</p>
            <p>Movie artwork is sourced through <a href="https://fanart.tv/" target="_blank" rel="noreferrer">Fanart.tv</a>, which does not endorse Movelle. Recorded artwork credits appear in film details.</p>
          </section>
        </footer>
        {notice && (
          <div role="status" className="notice success">
            <CheckCircle2 size={18} aria-hidden="true" />
            <span>{notice}</span>
            <button
              className="icon-button"
              aria-label="Dismiss notification"
              onClick={() => setNotice('')}
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )}
        <ProfileDialog open={profileOpen} onClose={() => setProfileOpen(false)}>
          <UserPanel
            key={`user-${selection}`}
            user={user}
            onSelect={selectUser}
            open={profileOpen}
          />
        </ProfileDialog>
        <ThemeDialog open={themeOpen} onClose={() => setThemeOpen(false)} theme={theme} onChange={changeTheme} saved={themeSaved} />
      </div>
    </ArtworkProvider>
  )
}

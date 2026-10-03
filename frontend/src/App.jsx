import { useEffect, useRef, useState } from 'react'
import { Film } from 'lucide-react'
import { request } from './api.js'
import UserPanel from './components/UserPanel.jsx'
import Library from './components/Library.jsx'
import Recommendations from './components/Recommendations.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [ratings, setRatings] = useState([])
  const [ratingsBusy, setRatingsBusy] = useState(false)
  const [ratingsError, setRatingsError] = useState('')
  const [reload, setReload] = useState(0)
  const [revision, setRevision] = useState(0)
  const [selection, setSelection] = useState(0)
  const [notice, setNotice] = useState('')
  const [pendingRatings, setPendingRatings] = useState(new Set())
  const [ratingErrors, setRatingErrors] = useState({})
  const pendingWrites = useRef(new Set())
  const activeId = useRef(null)

  function selectUser(next) {
    activeId.current = next.id
    setNotice('')
    setUser(next)
    setRatings([])
    setRatingsError('')
    setRatingsBusy(true)
    setReload((value) => value + 1)
    setRevision((value) => value + 1)
    setSelection((value) => value + 1)
  }

  useEffect(() => {
    if (!user) return
    const controller = new AbortController()
    async function loadRatings() {
      setRatingsBusy(true)
      setRatingsError('')
      try {
        const rows = await request(`/users/${user.id}/ratings`, { signal: controller.signal })
        const movies = await Promise.all(rows.map(async (row) => ({
          ...await request(`/movies/${row.movie_id}`, { signal: controller.signal }), ...row,
        })))
        if (!controller.signal.aborted) setRatings(movies)
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
      const row = await request(`/users/${userId}/ratings/${movie.movie_id}`, { method: 'PUT', body: { rating } })
      if (activeId.current !== userId) return
      setNotice(`Saved ${row.rating} / 5 for ${movie.title}.`)
      setRatings((previous) => [...previous.filter((item) => item.movie_id !== movie.movie_id), { ...movie, ...row }].sort((a, b) => a.movie_id - b.movie_id))
      setRevision((value) => value + 1)
      setReload((value) => value + 1)
    } catch (error) {
      setRatingErrors((previous) => ({ ...previous, [key]: `Could not save ${movie.title}: ${error.message} Retry using Save or Update.` }))
    } finally {
      pendingWrites.current.delete(key)
      setPendingRatings(new Set(pendingWrites.current))
    }
  }

  return <div className="min-h-screen bg-[#faf9f6] text-stone-800">
    <header className="bg-[#182c28] text-[#faf9f6]">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-5 sm:px-8">
        <div className="flex items-center gap-3"><Film size={24} strokeWidth={1.6} aria-hidden="true" /><span className="text-lg font-semibold tracking-tight">Movie Recommender</span></div>
        <span className="hidden text-xs tracking-wide text-stone-300 sm:block">Search · Rate · Discover</span>
      </div>
    </header>
    <div className="mx-auto grid max-w-7xl lg:min-h-[calc(100vh-116px)] lg:grid-cols-[280px_1fr]">
      <UserPanel user={user} onSelect={selectUser} />
      <main className="min-w-0 px-6 py-9 sm:px-8 lg:px-12">
        {notice && <p role="status" className="mb-5 border-l-2 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{notice}</p>}
        {Object.entries(ratingErrors).filter(([key]) => key.startsWith(`${user?.id}:`)).map(([key, message]) => <p key={key} role="alert" className="error mb-5">{message}</p>)}
        <Library key={`library-${selection}`} user={user} ratings={ratings} pendingRatings={pendingRatings} ratingsBusy={ratingsBusy} ratingsError={ratingsError} onReload={() => setReload((value) => value + 1)} onRate={rateMovie} />
        <Recommendations key={`recommendations-${selection}`} user={user} revision={revision} />
      </main>
    </div>
    <footer className="border-t border-stone-200 px-6 py-4 text-center text-xs text-stone-500">MovieLens metadata · Ratings saved locally in SQLite</footer>
  </div>
}

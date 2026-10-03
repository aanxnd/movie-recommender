import { useState } from 'react'
import { Star } from 'lucide-react'

function RatingControl({ movie, savedRating, onRate, pending }) {
  const [value, setValue] = useState(savedRating ?? 3.5)

  function save(event) {
    event.preventDefault()
    if (!pending) onRate(movie, Number(value))
  }

  const values = Array.from({ length: 10 }, (_, index) => (index + 1) / 2)
  if (savedRating !== undefined && !values.includes(savedRating)) values.push(savedRating)
  values.sort((a, b) => a - b)

  return <div className="sm:w-52 sm:shrink-0">
    <form onSubmit={save} className="flex items-end gap-2">
      <label className="flex-1 text-xs text-stone-600">{savedRating === undefined ? 'Your rating' : `Saved: ${savedRating} / 5`}
        <select aria-label={`Rating for ${movie.title}`} value={value} onChange={(event) => setValue(event.target.value)} disabled={pending} className="mt-1 w-full">
          {values.map((rating) => <option key={rating} value={rating}>{rating.toFixed(1)}</option>)}
        </select>
      </label>
      <button className="button-secondary" disabled={pending}>{pending ? 'Saving…' : savedRating === undefined ? 'Save' : 'Update'}</button>
    </form>
  </div>
}

export default function MovieList({ movies, ratings = [], onRate, userId, pendingRatings = new Set(), ranked = false, showConfidence = false, scoreLabel = 'Score' }) {
  return <ol className="divide-y divide-stone-200 border-y border-stone-200">
    {movies.map((movie, index) => {
      const savedRating = ratings.find((row) => row.movie_id === movie.movie_id)?.rating
      return <li key={movie.movie_id} className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 gap-4">
          {ranked && <span className="w-7 shrink-0 pt-1 font-mono text-sm text-stone-400">{String(index + 1).padStart(2, '0')}</span>}
          <div className="min-w-0">
            <h3 className="font-semibold leading-snug text-stone-900">{movie.title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-stone-500">{movie.genres.join(' · ')}</p>
          </div>
        </div>
        {ranked && <div className="shrink-0 text-sm sm:text-right"><div className="flex items-center gap-2 sm:justify-end">
          <Star size={14} aria-hidden="true" className="text-amber-700" />
          <span className="font-mono font-semibold">{movie.score.toFixed(2)} <span className="font-sans font-normal text-stone-500">/ 5</span></span>
          <span className="text-xs text-stone-500">{movie.method === 'popularity_fallback' ? 'Average' : scoreLabel}</span>
        </div>
          {showConfidence && <p className="mt-1 text-xs text-stone-500">Confidence: {movie.confidence === null ? '—' : movie.confidence.toFixed(2)}{movie.method === 'popularity_fallback' ? ' · Popularity fallback' : ''}</p>}
        </div>}
        {onRate && <RatingControl key={`${movie.movie_id}-${savedRating}`} movie={movie} savedRating={savedRating} onRate={onRate} pending={pendingRatings.has(`${userId}:${movie.movie_id}`)} />}
      </li>
    })}
  </ol>
}

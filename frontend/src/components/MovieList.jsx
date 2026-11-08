import { useMemo, useState } from 'react'
import { Check, Star } from 'lucide-react'
import MovieCover, { movieTitle } from './MovieCover.jsx'
import { StarRating } from './ui.jsx'
import { useFilmActions } from '../artwork.js'

function RatingControl({ movie, savedRating, onRate, pending }) {
  const [value, setValue] = useState(savedRating ?? 3.5)
  const values = Array.from({ length: 10 }, (_, index) => (index + 1) / 2)
  if (savedRating !== undefined && !values.includes(savedRating))
    values.push(savedRating)
  values.sort((a, b) => a - b)
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!pending) onRate(movie, Number(value))
      }}
      className="rating-control"
    >
      <div className="rating-control-top">
        <span className="rating-label">
          {savedRating === undefined
            ? 'Your rating'
            : `Saved: ${savedRating} / 5`}
        </span>
        <StarRating value={Number(value)} />
      </div>
      <div className="rating-control-actions">
        <label className="sr-only" htmlFor={`rating-${movie.movie_id}`}>
          Rating for {movie.title}
        </label>
        <select
          id={`rating-${movie.movie_id}`}
          aria-label={`Rating for ${movie.title}`}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          disabled={pending}
        >
          {values.map((rating) => (
            <option key={rating} value={rating}>
              {String(rating)}
            </option>
          ))}
        </select>
        <button className="button-secondary" disabled={pending}>
          {pending ? 'Saving…' : savedRating === undefined ? 'Save' : 'Update'}
          {savedRating !== undefined && !pending && (
            <Check size={14} aria-hidden="true" />
          )}
        </button>
      </div>
    </form>
  )
}

export default function MovieList({
  movies,
  ratings = [],
  onRate,
  userId,
  pendingRatings = new Set(),
  ranked = false,
  showConfidence = false,
  scoreLabel = 'Score',
  layout = 'cards',
  onPick,
  showRank = true,
}) {
  const actions = useFilmActions()
  const ratingMap = useMemo(
    () => new Map(ratings.map((row) => [row.movie_id, row.rating])),
    [ratings],
  )
  return (
    <ol
      className={`movie-grid ${ranked ? 'ranked-grid' : ''} ${layout === 'collection' ? 'collection-list' : layout === 'shelf' ? 'shelf-list' : ''}`}
    >
      {movies.map((movie, index) => {
        const savedRating = ratingMap.get(movie.movie_id) ?? movie.rating
        const { title, year } = movieTitle(movie.title)
        return (
          <li
            key={movie.movie_id}
            className="movie-card"
            data-movie-id={movie.movie_id}
            style={{ '--i': Math.min(index, 8) }}
          >
            <div className="movie-cover-wrap">
              {onPick || actions?.openFilm ? (
                <button
                  className="cover-button"
                  onClick={() =>
                    actions?.openFilm ? actions.openFilm(movie) : onPick(movie)
                  }
                  aria-label={`Details for ${movie.title}`}
                >
                  <MovieCover
                    movie={movie}
                    rank={ranked && showRank ? index + 1 : undefined}
                  />
                </button>
              ) : (
                <MovieCover
                  movie={movie}
                  rank={ranked && showRank ? index + 1 : undefined}
                />
              )}
              {savedRating !== undefined && (
                <span className="rated-badge">
                  <Check size={12} aria-hidden="true" />
                  Rated
                </span>
              )}
            </div>
            <div className="movie-card-body">
              <div className="movie-meta">
                {year && <span>{year}</span>}
                <span>
                  {movie.genres
                    .filter((genre) => genre !== '(no genres listed)')
                    .join(' · ') || 'Genre unavailable'}
                </span>
              </div>
              <h3>{title}</h3>
              {ranked && (
                <div className="movie-score">
                  <div>
                    <Star size={15} fill="currentColor" aria-hidden="true" />
                    <strong>{movie.score.toFixed(2)}</strong>
                    <span>/ 5</span>
                  </div>
                  <span>
                    {movie.method === 'popularity_fallback'
                      ? 'Average · Fallback'
                      : scoreLabel}
                  </span>
                </div>
              )}
              {showConfidence && (
                <p className="confidence">
                  Confidence:{' '}
                  {movie.confidence == null
                    ? 'N/A'
                    : movie.confidence.toFixed(2)}
                  {movie.method === 'popularity_fallback'
                    ? ' · Popularity fallback'
                    : ''}
                </p>
              )}
              {onRate && movie.available !== false && (
                <RatingControl
                  key={`${movie.movie_id}-${savedRating}`}
                  movie={movie}
                  savedRating={savedRating}
                  onRate={onRate}
                  pending={pendingRatings.has(`${userId}:${movie.movie_id}`)}
                />
              )}
              {movie.available === false && (
                <p className="unavailable-label">
                  No longer in the catalogue. Your rating is kept.
                </p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

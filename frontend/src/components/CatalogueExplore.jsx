import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { request } from '../api.js'
import { imageUrl, imageSrcSet, useArtwork, useFilmActions } from '../artwork.js'
import MovieCover, { movieTitle } from './MovieCover.jsx'
import MovieList from './MovieList.jsx'
import { Skeletons } from './ui.jsx'

function FeaturedFilm({ movie, onPick }) {
  const artwork = useArtwork(movie)
  const [failed, setFailed] = useState(false)
  const { title, year } = movieTitle(movie.title)
  useEffect(() => setFailed(false), [movie.movie_id])
  return (
    <article
      className={`featured-film ${!artwork?.backdrop_path || failed ? 'feature-without-backdrop' : ''}`}
    >
      {artwork?.backdrop_path && !failed && (
        <img
          className="feature-backdrop"
          src={imageUrl(artwork.backdrop_path, 'fanart')}
          srcSet={imageSrcSet(artwork.backdrop_path, artwork.backdrop_credit, true)}
          sizes="(max-width: 767px) 100vw, 1280px"
          width="1280"
          height="720"
          fetchPriority="high"
          alt={`Scene from ${title}`}
          onError={() => setFailed(true)}
        />
      )}
      <div className="feature-copy">
        <p className="feature-metadata">
          {year} <span>{movie.genres.slice(0, 2).join(' / ')}</span>
        </p>
        <h2>{title}</h2>
        <p className="feature-description">
          {artwork?.overview ||
            'A community favourite from the MovieLens catalogue.'}
        </p>
        <div className="feature-actions">
          <button className="button-primary" onClick={() => onPick(movie)}>
            Explore film
          </button>
          <span className="feature-score">
            {movie.score.toFixed(2)} <span>/ 5 MovieLens average</span>
          </span>
        </div>
      </div>
      {(!artwork?.backdrop_path || failed) && (
        <div className="feature-poster">
          <MovieCover movie={movie} priority />
        </div>
      )}
    </article>
  )
}

function FilmShelf({ movies, title, onPick }) {
  function scroll(event, direction) {
    const row = event.currentTarget
      .closest('section')
      .querySelector('.movie-grid')
    row.scrollBy({
      left: direction * row.clientWidth * 0.75,
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
    })
  }
  return (
    <section className="film-shelf" aria-label={title}>
      <div className="shelf-heading">
        <h2>{title}</h2>
        <div className="shelf-navigation">
          <button
            className="icon-button"
            aria-label={`Previous films in ${title}`}
            onClick={(e) => scroll(e, -1)}
          >
            <ChevronLeft size={19} aria-hidden="true" />
          </button>
          <button
            className="icon-button"
            aria-label={`More films in ${title}`}
            onClick={(e) => scroll(e, 1)}
          >
            <ChevronRight size={19} aria-hidden="true" />
          </button>
        </div>
      </div>
      <MovieList
        movies={movies}
        ranked
        showRank={false}
        scoreLabel="Average"
        layout="shelf"
        onPick={onPick}
      />
    </section>
  )
}

function GenreShelf({ genre, title, onPick }) {
  const [movies, setMovies] = useState([])
  useEffect(() => {
    const controller = new AbortController()
    request(`/recommendations/genre/${encodeURIComponent(genre)}?limit=10`, {
      signal: controller.signal,
    })
      .then(setMovies)
      .catch(() => {})
    return () => controller.abort()
  }, [genre])
  return movies.length ? (
    <FilmShelf movies={movies} title={title} onPick={onPick} />
  ) : null
}

export default function CatalogueExplore({ onPick }) {
  const [movies, setMovies] = useState([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [genre, setGenre] = useState('')
  const actions = useFilmActions()
  const pick = (movie) =>
    actions?.openFilm ? actions.openFilm(movie) : onPick(movie)
  useEffect(() => {
    const controller = new AbortController()
    setBusy(true)
    setError('')
    const path = genre
      ? `/recommendations/genre/${encodeURIComponent(genre)}?limit=16`
      : '/recommendations/popular?limit=16'
    request(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setMovies(data)
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false)
      })
    return () => controller.abort()
  }, [revision, genre])
  return (
    <div className="catalogue-explore">
      <div className="discovery-genres" aria-label="Discover by genre">
        {['', 'Drama', 'Thriller', 'Sci-Fi', 'Comedy', 'Horror'].map(
          (value) => (
            <button
              key={value}
              className={genre === value ? 'selected' : ''}
              aria-pressed={genre === value}
              onClick={() => setGenre(value)}
            >
              {value || 'All films'}
            </button>
          ),
        )}
      </div>
      {busy ? (
        <Skeletons label="Loading films..." count={8} />
      ) : error ? (
        <div className="explore-error">
          <p role="alert" className="error">
            {error}
          </p>
          <button
            className="button-secondary"
            onClick={() => setRevision((value) => value + 1)}
          >
            <RefreshCw size={15} aria-hidden="true" />
            Retry loading films
          </button>
        </div>
      ) : movies.length ? (
        <>
          <FeaturedFilm movie={movies[0]} onPick={pick} />
          <FilmShelf
            movies={movies.slice(1)}
            title={genre ? `${genre} films` : 'Community favourites'}
            onPick={pick}
          />
          {!genre && (
            <>
              <GenreShelf genre="Thriller" title="Thrillers" onPick={pick} />
              <GenreShelf
                genre="Sci-Fi"
                title="Science fiction"
                onPick={pick}
              />
            </>
          )}
        </>
      ) : (
        <p className="result-caption">
          No films available. Try another genre or search for a title.
        </p>
      )}
    </div>
  )
}

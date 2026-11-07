import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { imageUrl, useArtwork } from '../artwork.js'
import { movieTitle } from './MovieCover.jsx'
import { containDialogFocus } from '../dialog.js'

export default function FilmDialog({ movie, onClose, onFind }) {
  const ref = useRef(null)
  const previous = useRef(null)
  const artwork = useArtwork(movie)
  const [imageFailed, setImageFailed] = useState(false)
  useEffect(() => setImageFailed(false), [movie?.movie_id])
  useEffect(() => {
    if (movie) {
      previous.current = document.activeElement
      ref.current.showModal()
    } else if (ref.current.open) {
      ref.current.close()
      previous.current?.focus()
    }
  }, [movie])
  const info = movie ? movieTitle(movie.title) : {}
  return (
    <dialog
      ref={ref}
      className="film-dialog"
      aria-labelledby="film-detail-title"
      onKeyDown={containDialogFocus}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      {movie && (
        <div className="film-dialog-inner">
          <button
            className="icon-button film-close"
            aria-label="Close film details"
            onClick={onClose}
          >
            <X size={21} aria-hidden="true" />
          </button>
          {artwork?.backdrop_path && !imageFailed && (
            <img
              className="film-detail-backdrop"
              src={imageUrl(artwork.backdrop_path, 'w780')}
              alt={`Scene from ${info.title}`}
              width="780"
              height="439"
              onError={() => setImageFailed(true)}
            />
          )}
          <div className="film-detail-copy">
            <p className="film-detail-meta">
              {info.year}
              {artwork?.runtime ? ` / ${artwork.runtime} min` : ''}
            </p>
            <h2 id="film-detail-title">{info.title}</h2>
            <p className="film-detail-genres">
              {movie.genres
                .filter((g) => g !== '(no genres listed)')
                .join(', ')}
            </p>
            {artwork?.director && (
              <p className="film-director">Directed by {artwork.director}</p>
            )}
            {artwork?.overview && (
              <p className="film-overview">{artwork.overview}</p>
            )}
            {movie.score != null && (
              <p className="film-score">
                {movie.score.toFixed(2)} / 5{' '}
                <span>
                  {movie.method === 'collaborative_filtering'
                    ? 'Predicted rating'
                    : 'MovieLens average'}
                </span>
              </p>
            )}
            <button className="button-primary" onClick={() => onFind(movie)}>
              Find and rate this film
            </button>
            {artwork && (
              <p className="film-source">Film metadata and images from TMDB.</p>
            )}
          </div>
        </div>
      )}
    </dialog>
  )
}

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { imageUrl, imageSrcSet, useArtwork } from '../artwork.js'
import { movieTitle } from './MovieCover.jsx'
import { containDialogFocus } from '../dialog.js'

export default function FilmDialog({ movie, onClose, onFind }) {
  const ref = useRef(null)
  const previous = useRef(null)
  const artwork = useArtwork(movie)
  const backdrop = imageUrl(artwork?.backdrop_path, 'fanart')
  const [imageFailed, setImageFailed] = useState(false)
  useEffect(() => setImageFailed(false), [movie?.movie_id, backdrop])
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
          {backdrop && !imageFailed && (
            <img
              className="film-detail-backdrop"
              src={imageUrl(artwork.backdrop_path, 'fanart')}
              srcSet={imageSrcSet(artwork.backdrop_path, artwork.backdrop_credit, true)}
              sizes="(max-width: 767px) 100vw, 900px"
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
            {artwork?.released && <p className="field-hint">Released {artwork.released}</p>}
            <h2 id="film-detail-title">{info.title}</h2>
            <p className="film-detail-genres">
              {movie.genres
                .filter((g) => g !== '(no genres listed)')
                .join(', ') || artwork?.metadata_genres?.join(', ')}
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
              <div className="film-source">
                <p>Metadata: <a href="https://trakt.tv/" target="_blank" rel="noreferrer">Trakt</a>. Artwork: <a href="https://fanart.tv/" target="_blank" rel="noreferrer">Fanart.tv</a>.</p>
                {[['Poster', artwork.poster_credit], ['Backdrop', artwork.backdrop_credit]].map(([label, credit]) => credit && (
                  <p key={label}>{label} copyright: {credit.copyright || 'Unknown'}.
                    {safeCreditLink(credit.copyright_link) && <> <a href={credit.copyright_link} target="_blank" rel="noreferrer">Recorded source</a>.</>}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </dialog>
  )
}

function safeCreditLink(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash
  } catch { return false }
}

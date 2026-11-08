import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { imageUrl, imageSrcSet, useArtwork, useImageCandidate, useFilmActions } from '../artwork.js'
import { movieTitle } from './MovieCover.jsx'
import { containDialogFocus } from '../dialog.js'

export default function FilmDialog({ movie, onClose, onFind }) {
  const ref = useRef(null)
  const previous = useRef(null)
  const artwork = useArtwork(movie)
  const { choice, loaded, onLoad, onError } = useImageCandidate(artwork, 'backdrop')
  const backdrop = imageUrl(choice?.url, 'fanart')
  const selectedCover = useFilmActions()?.selectedCovers?.get(movie?.movie_id)
  const displayed = [selectedCover, loaded ? choice : null].filter((row, index, rows) =>
    row && rows.findIndex(other => other?.url === row.url) === index)
  const providers = [...new Set(displayed.map(row => row.provider))]
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
          {backdrop && (
            <img
              className="film-detail-backdrop"
              key={backdrop}
              src={backdrop}
              srcSet={imageSrcSet(choice.url, choice.credit, true)}
              sizes="(max-width: 767px) 100vw, 900px"
              alt={`Scene from ${info.title}`}
              width="780"
              height="439"
              onLoad={onLoad}
              onError={onError}
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
                <p>Metadata: <a href="https://trakt.tv/" target="_blank" rel="noreferrer">Trakt</a>.
                  {providers.length > 0 && <> Artwork: {providers.map((provider, index) => <span key={provider}>{index > 0 && ', '}<a href={provider === 'trakt' ? 'https://trakt.tv/' : 'https://fanart.tv/'} target="_blank" rel="noreferrer">{provider === 'trakt' ? 'Trakt' : 'Fanart.tv'}</a></span>)}.</>}
                </p>
                {displayed.map(({ url, kind, credit }) => credit && (
                  <p key={url}>{kind === 'poster' ? 'Poster' : 'Background'} copyright: {credit.copyright || 'Unknown'}.
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

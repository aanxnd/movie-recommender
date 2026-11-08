import { useState } from 'react'
import { Film } from 'lucide-react'
import { imageUrl, imageSrcSet, useArtwork } from '../artwork.js'

export function movieTitle(title) {
  const match = title.match(/\s*\((\d{4})\)\s*$/)
  const original = match ? title.slice(0, match.index) : title
  const primary = original.replace(/\s*\(a\.k\.a\..*?\)/gi, '').trim()
  const article = primary.match(/^(.*),\s*(The|An|A)$/)
  return {
    title: article ? `${article[2]} ${article[1]}` : primary,
    year: match ? match[1] : null,
  }
}

function PosterImage({ movie, path, credit, priority, pending }) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const { title } = movieTitle(movie.title)
  return (
    <div
      className={`movie-cover ${loaded ? 'image-ready' : ''}`}
      data-artwork={
        failed || (!pending && !path)
          ? 'unavailable'
          : loaded
            ? 'loaded'
            : 'loading'
      }
    >
      {path && !failed ? (
        <img
          ref={(image) => {
            if (image?.complete && image.naturalWidth > 0 && !loaded)
              setLoaded(true)
          }}
          src={imageUrl(path)}
          srcSet={imageSrcSet(path, credit)}
          sizes="(max-width: 600px) 40vw, (max-width: 1100px) 20vw, 160px"
          width="342"
          height="513"
          loading={priority ? 'eager' : 'lazy'}
          decoding="async"
          alt={`${title} poster`}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="poster-unavailable">
          <Film size={23} strokeWidth={1.3} aria-hidden="true" />
          <span>{pending ? 'Loading poster' : 'Poster unavailable'}</span>
        </div>
      )}
    </div>
  )
}

export default function MovieCover({ movie, priority = false }) {
  const artwork = useArtwork(movie)
  const path = imageUrl(artwork?.poster_path, 'fanart')
  // A new source owns a fresh loading state; cached onLoad cannot race a reset effect.
  return (
    <PosterImage
      key={path || 'missing'}
      movie={movie}
      path={path}
      credit={artwork?.poster_credit}
      priority={priority}
      pending={artwork === undefined}
    />
  )
}

import { Film } from 'lucide-react'
import { imageUrl, imageSrcSet, useArtwork, useImageCandidate, useFilmActions } from '../artwork.js'

export function movieTitle(title) {
  const match = title.match(/\s*\((\d{4})\)\s*$/)
  const original = match ? title.slice(0, match.index) : title
  const primary = original.replace(/\s*\(a\.k\.a\..*?\)/gi, '').trim()
  const article = primary.match(/^(.*),\s*(The|An|A)$/)
  return { title: article ? `${article[2]} ${article[1]}` : primary, year: match ? match[1] : null }
}

export default function MovieCover({ movie, priority = false }) {
  const artwork = useArtwork(movie)
  const { reportCover } = useFilmActions() || {}
  const { choice, loaded, onLoad, onError } = useImageCandidate(artwork)
  const { title } = movieTitle(movie.title)
  const background = choice?.kind === 'background'
  const ready = () => { onLoad(); reportCover?.(movie.movie_id, choice) }
  return (
    <div className={`movie-cover ${loaded ? 'image-ready' : ''}`}
      data-kind={choice?.kind}
      data-artwork={loaded ? 'loaded' : choice || artwork === undefined ? 'loading' : 'unavailable'}>
      {choice ? <>
        <img key={choice.url}
          ref={image => { if (image?.complete && image.naturalWidth > 0 && !loaded) ready() }}
          src={imageUrl(choice.url)} srcSet={imageSrcSet(choice.url, choice.credit)}
          sizes="(max-width: 600px) 40vw, (max-width: 1100px) 20vw, 160px"
          width="342" height="513" loading={priority ? 'eager' : 'lazy'} decoding="async"
          alt={`${title} ${background ? 'background' : 'poster'}`} onLoad={ready} onError={onError} />
        {background && loaded && <span className="cover-kind">Film still</span>}
      </> : <div className="poster-unavailable">
        <Film size={23} strokeWidth={1.3} aria-hidden="true" />
        <span>{artwork === undefined ? 'Loading poster' : 'Poster unavailable'}</span>
      </div>}
    </div>
  )
}

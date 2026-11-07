import { createContext, useContext, useEffect } from 'react'

export const ArtworkContext = createContext(null)
export const imageUrl = (path, size = 'w342') =>
  /^\/[A-Za-z0-9_-]+\.(jpg|png|webp)$/.test(path || '')
    ? `https://image.tmdb.org/t/p/${size}${path}`
    : null

export function useArtwork(movie) {
  const context = useContext(ArtworkContext)
  useEffect(() => {
    if (movie) context?.enqueue(movie)
  }, [context?.enqueue, movie?.movie_id])
  return context?.items.get(movie?.movie_id)
}
export const useFilmActions = () => useContext(ArtworkContext)

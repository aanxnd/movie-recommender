import { createContext, useContext, useEffect } from 'react'

export const ArtworkContext = createContext(null)
export function imageUrl(path, size = 'bigpreview') {
  if (typeof path === 'string' && /^\/movies\/artwork-image\/[1-9][0-9]*$/.test(path)) return path.startsWith('/') ? `${import.meta.env?.VITE_API_BASE_URL?.replace(/\/+$/, '') || '/api'}${path}` : null
  if (typeof path !== 'string' || !/^https:\/\/assets\.fanart\.tv\/fanart\/[A-Za-z0-9/_-]+\.(jpg|png|webp)$/.test(path) || path.includes('..')) return null
  const variant = ['preview', 'bigpreview', 'fanart'].includes(size) ? size : 'bigpreview'
  return path.replace('/fanart/', `/${variant}/`)
}

export function imageSrcSet(path, credit, full = false) {
  if (!imageUrl(path) || path.startsWith('/')) return undefined
  const width = Number(credit?.width), height = Number(credit?.height)
  if (!(width >= 100 && height >= 100)) return undefined
  const variants = [['preview', 200], ['bigpreview', 400]]
  const entries = variants.map(([name, maximum]) => `${imageUrl(path, name)} ${Math.max(1, Math.round(width * Math.min(1, maximum / Math.max(width, height))))}w`)
  if (full) entries.push(`${imageUrl(path, 'fanart')} ${width}w`)
  return entries.join(', ')
}

export function useArtwork(movie) {
  const context = useContext(ArtworkContext)
  useEffect(() => {
    if (movie) context?.enqueue(movie)
  }, [context?.enqueue, movie?.movie_id])
  return context?.items.get(movie?.movie_id)
}
export const useFilmActions = () => useContext(ArtworkContext)

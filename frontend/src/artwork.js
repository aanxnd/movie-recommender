import { createContext, useContext, useEffect, useState } from 'react'
import { apiUrl } from './api.js'

export const ArtworkContext = createContext(null)
export function imageUrl(path, size = 'bigpreview') {
  if (typeof path !== 'string') return null
  const cached = /^\/movies\/artwork-image\/[1-9][0-9]*\/(poster|backdrop)$/
  try {
    if (cached.test(path)) return apiUrl(path)
    const base = apiUrl('')
    if (path.startsWith(base) && cached.test(path.slice(base.length))) return path
  } catch { return null }
  if (!/^https:\/\/assets\.fanart\.tv\/(fanart|preview|bigpreview)\/[A-Za-z0-9/_-]+\.(jpg|png|webp)$/.test(path) || path.includes('..')) return null
  const variant = ['preview', 'bigpreview', 'fanart'].includes(size) ? size : 'bigpreview'
  return path.replace(/\/(fanart|preview|bigpreview)\//, `/${variant}/`)
}

export function imageSrcSet(path, credit, full = false) {
  if (!imageUrl(path) || !path.startsWith('https://assets.fanart.tv/')) return undefined
  const width = Number(credit?.width), height = Number(credit?.height)
  if (!(width >= 100 && height >= 100)) return undefined
  const variants = [['preview', 200], ['bigpreview', 400]]
  const entries = variants.map(([name, maximum]) => `${imageUrl(path, name)} ${Math.max(1, Math.round(width * Math.min(1, maximum / Math.max(width, height))))}w`)
  if (full) entries.push(`${imageUrl(path, 'fanart')} ${width}w`)
  return entries.join(', ')
}

export function imageCandidates(artwork, role = 'cover') {
  if (!artwork) return []
  const supplied = artwork[role === 'cover' ? 'cover_candidates' : 'backdrop_candidates']
  const credit = artwork[role === 'cover' ? 'poster_credit' : 'backdrop_credit']
  const fallback = { url: artwork[role === 'cover' ? 'poster_path' : 'backdrop_path'], credit,
    provider: credit?.provider || 'fanart.tv',
    kind: role !== 'cover' || credit?.kind === 'backdrop' || Number(credit?.width) > Number(credit?.height) ? 'background' : 'poster' }
  const seen = new Set()
  return (Array.isArray(supplied) ? supplied : [fallback]).filter(row => {
    if (!row || !imageUrl(row.url) || seen.has(row.url)) return false
    seen.add(row.url)
    return true
  })
}

export function useImageCandidate(artwork, role = 'cover') {
  const candidates = imageCandidates(artwork, role)
  const key = JSON.stringify(candidates)
  const [state, setState] = useState({ key, index: 0, loaded: false })
  const current = state.key === key ? state : { key, index: 0, loaded: false }
  return {
    choice: candidates[current.index], loaded: current.loaded,
    onLoad: () => setState({ ...current, loaded: true }),
    onError: () => setState({ key, index: current.index + 1, loaded: false }),
  }
}

export function useArtwork(movie) {
  const context = useContext(ArtworkContext)
  useEffect(() => {
    if (movie) context?.enqueue(movie)
  }, [context?.enqueue, movie?.movie_id])
  return context?.items.get(movie?.movie_id)
}
export const useFilmActions = () => useContext(ArtworkContext)

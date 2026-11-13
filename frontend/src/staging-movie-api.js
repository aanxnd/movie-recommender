// Trusted staging bridge for existing movie UI; never restores legacy identity.
import { ApiError } from './api.js'
import { createAuthenticatedApi } from './auth-api.js'

export function createStagingMovieApi(config) {
  const native = createAuthenticatedApi(config)
  return (path, options = {}) => {
    const { token, retry, ...safe } = options
    if (token !== undefined || safe.headers !== undefined || safe.access !== undefined)
      return Promise.reject(new ApiError('Staging accepts only native session credentials.'))
    // Shared components pass an undefined legacy token and a retry preference.
    // Discard both; native transport never automatically replays mutations.
    const route = path.split('?')[0], method = (safe.method ?? 'GET').toUpperCase()
    const publicRead = method === 'GET' && (/^\/movies\//.test(route) ||
      route === '/recommendations/popular' || route.startsWith('/recommendations/genre/'))
    const publicArtwork = method === 'POST' && route === '/movies/artwork' && !safe.body?.personal_key
    return native(path, { ...safe, access: publicRead || publicArtwork ? 'public' : 'authenticated' })
  }
}

// Synthetic test pixel; never presented as real film artwork outside this intercepted test.
const pixel = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3ioAAAAASUVORK5CYII=', 'base64')

export async function artworkCandidates(page, mode) {
  await page.route('**/api/movies/artwork', async route => {
    const { movie_ids } = route.request().postDataJSON()
    const items = movie_ids.map(movie_id => {
      const choice = (url, provider, kind) => ({ url, provider, kind, credit: { provider, kind, copyright: 'Unknown' } })
      const cover_candidates = [
        choice(`https://assets.fanart.tv/fanart/test-poster-${movie_id}.jpg`, 'fanart.tv', 'poster'),
        choice(`/movies/artwork-image/${movie_id}/poster`, 'trakt', 'poster'),
        choice(`https://assets.fanart.tv/fanart/test-background-${movie_id}.jpg`, 'fanart.tv', 'background'),
        choice(`/movies/artwork-image/${movie_id}/backdrop`, 'trakt', 'background'),
      ]
      return { movie_id, cover_candidates, backdrop_candidates: cover_candidates.slice(2), source: 'trakt+fanart.tv' }
    })
    await route.fulfill({ json: { provider: 'trakt+fanart.tv', configured: true, items } })
  })
  const requests = []
  await page.route(/\/(?:api\/movies\/artwork-image\/\d+\/(?:poster|backdrop)|(?:bigpreview|fanart|preview)\/test-(?:poster|background)-\d+\.jpg)$/, async route => {
    const url = route.request().url()
    requests.push(url)
    const success = mode === 'available' ? true : mode === 'background' ? url.includes('test-background') : mode === 'trakt' ? url.endsWith('/poster') : mode === 'trakt-background' ? url.endsWith('/backdrop') : false
    await route.fulfill(success ? { contentType: 'image/png', body: pixel } : { status: 404, body: 'Unavailable' })
  })
  await page.goto('/')
  return requests
}


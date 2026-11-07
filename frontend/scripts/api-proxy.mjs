export function localApiTarget(value = 'http://127.0.0.1:8000') {
  let url
  try {
    url = new URL(value.trim() || 'http://127.0.0.1:8000')
  } catch {
    /* fixed error below */
  }
  if (
    !url ||
    !['http:', 'https:'].includes(url.protocol) ||
    !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== '/'
  ) {
    throw new Error(
      'API_PROXY_TARGET must be a loopback HTTP(S) origin without credentials, a path, or query parameters.'
    )
  }
  return url.origin
}

export function apiProxy(value) {
  return {
    target: localApiTarget(value),
    rewrite: (path) => path.replace(/^\/api(?=\/|$)/, ''),
    configure(proxy) {
      proxy.on('error', (_error, _request, response) => {
        if (
          !response ||
          typeof response.writeHead !== 'function' ||
          response.headersSent ||
          response.writableEnded
        )
          return
        response.writeHead(502, {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store'
        })
        response.end(
          JSON.stringify({
            detail:
              'The local API is unavailable. Run npm run dev to start both services. With dev:frontend, start the API separately and check API_PROXY_TARGET.'
          })
        )
      })
    }
  }
}

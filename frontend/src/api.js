export function apiUrl(path, base = import.meta.env?.VITE_API_BASE_URL) {
  return `${(base || '/api').replace(/\/+$/, '')}${path}`
}

export async function request(path, { body, ...options } = {}) {
  let response
  try {
    response = await fetch(apiUrl(path), {
      ...options,
      ...(body === undefined ? {} : {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot reach the API. Check that FastAPI is running and try again.')
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status >= 500) throw new Error('The API could not complete this request. Please try again.')
    if (response.status === 404) {
      throw new Error(data?.detail === 'Movie not found' ? 'Movie not found.' : 'User not found. Check the application user ID.')
    }
    if (response.status === 422) {
      const details = Array.isArray(data?.detail) ? data.detail : []
      const messages = details.map((item) => {
        const field = (item.loc || []).filter((part) => part !== 'body' && part !== 'query').join(' ')
        return `${field || 'Input'}: ${item.msg || 'Invalid value'}`
      })
      throw new Error(messages.length ? messages.join('. ') : 'Check the values and try again.')
    }
    throw new Error('The request failed. Please try again.')
  }
  if (data === null) throw new Error('The API returned an unreadable response. Please try again.')
  return data
}

export function parseUserId(value) {
  const text = value.trim()
  if (!/^\d+$/.test(text) || !Number.isSafeInteger(Number(text)) || Number(text) < 1) {
    throw new Error('Enter a positive whole-number user ID within the browser’s supported integer range.')
  }
  return Number(text)
}

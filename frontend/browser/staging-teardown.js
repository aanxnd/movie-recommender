import { readFile } from 'node:fs/promises'

// Request Python's normal finally/owned-schema cleanup before Playwright kills processes on Windows.
export default async function teardown() {
  try { await fetch('http://127.0.0.1:19002/_fixture/shutdown', { method: 'POST', signal: AbortSignal.timeout(3000) }) } catch {}
  const deadline = Date.now() + 15000
  while (Date.now() < deadline) {
    try {
      const result = await readFile(new URL('../../.pytest-tmp/staging-fixture.done', import.meta.url), 'utf8')
      if (result === 'clean') return
      throw new Error('Offline staging cleanup failed')
    } catch (error) { if (error.code !== 'ENOENT') throw error }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('Offline staging did not shut down')
}

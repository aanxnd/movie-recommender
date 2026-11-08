import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { once } from 'node:events'
import { setTimeout as pause } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'

const cwd = fileURLToPath(new URL('../', import.meta.url))
const frontendPort = 5181,
  apiPort = 8011

async function occupied(port, expected) {
  const listener = createServer()
  listener.listen(port, '127.0.0.1')
  await once(listener, 'listening')
  try {
    const worker = launch()
    const code = await worker.exited
    assert.equal(code, 1)
    assert.match(worker.output(), expected)
    assert.doesNotMatch(worker.output(), /Started server process|READY:/)
  } finally {
    listener.close()
  }
}

function launch() {
  let output = ''
  const worker = spawn(
    process.execPath,
    ['scripts/dev.mjs', '--port', String(frontendPort)],
    {
      cwd,
      windowsHide: true,
      env: {
        ...process.env,
        MOVELLE_DEV_API_PORT: String(apiPort),
        MOVELLE_DEV_INSTANCE: 'lifecycle-qa',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  worker.stdout.on('data', (chunk) => {
    output += chunk
  })
  worker.stderr.on('data', (chunk) => {
    output += chunk
  })
  return {
    worker,
    output: () => output,
    exited: once(worker, 'exit').then(([code]) => code),
  }
}

async function until(check, message, timeout = 45000) {
  const end = Date.now() + timeout
  while (Date.now() < end) {
    if (await check()) return
    await pause(100)
  }
  throw new Error(message)
}

await occupied(frontendPort, /Frontend port 5181 is occupied/)
await occupied(apiPort, /API port 8011 is occupied/)
console.log(
  'PASS: both occupied ports fail before starting a backend or showing READY.',
)

const running = launch()
let apiPid
try {
  await until(
    () => running.output().includes('READY:'),
    'The isolated launcher never became ready.',
  )
  apiPid = Number(
    running.output().match(/Started server process \[(\d+)\]/)?.[1],
  )
  assert.ok(Number.isInteger(apiPid) && apiPid > 0)
  for (const [origin, path] of [
    [`http://127.0.0.1:${apiPort}`, '/health'],
    [`http://127.0.0.1:${apiPort}`, '/ready'],
    [`http://127.0.0.1:${frontendPort}`, '/api/movies/decades'],
  ]) {
    const reply = await fetch(origin + path)
    assert.equal(reply.status, 200)
    const data = await reply.json()
    path.endsWith('decades')
      ? assert.ok(data.length && data.every(Number.isInteger))
      : assert.equal(data.status, 'ok')
  }
  // This PID comes only from our freshly spawned child's startup output.
  process.kill(apiPid)
  const code = await Promise.race([
    running.exited,
    pause(10000).then(() => {
      throw new Error('The launcher ignored its stopped API.')
    }),
  ])
  assert.equal(code, 1)
  assert.match(running.output(), /The local API stopped. Stopping the frontend/)
  await until(
    async () => {
      try {
        await fetch(`http://127.0.0.1:${frontendPort}`, {
          signal: AbortSignal.timeout(500),
        })
        return false
      } catch {
        return true
      }
    },
    'Vite remained available after its API stopped.',
    10000,
  )
  console.log(
    'PASS: verified HTTP startup, killed only the owned test API, launcher exited 1 and its frontend stopped.',
  )
} finally {
  if (running.worker.exitCode === null) running.worker.kill()
}

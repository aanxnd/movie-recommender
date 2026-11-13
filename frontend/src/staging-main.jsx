import React from 'react'
import { createRoot } from 'react-dom/client'
import { createStagingRuntime } from './staging-runtime.js'
import { StagingApp } from './staging-app.jsx'
import './styles.css'
import './staging.css'

const root = createRoot(document.getElementById('root'))
try {
  const runtime = createStagingRuntime({ projectUrl: import.meta.env.VITE_STAGING_SUPABASE_URL,
    publishableKey: import.meta.env.VITE_STAGING_SUPABASE_PUBLISHABLE_KEY,
    appOrigin: 'http://127.0.0.1:5173', base: '/api' })
  addEventListener('beforeunload', () => runtime.stop(), { once: true })
  root.render(<React.StrictMode><StagingApp runtime={runtime} /></React.StrictMode>)
} catch {
  history.replaceState(null, '', '/')
  root.render(<main><h1>Staging configuration unavailable</h1><p>Use the reviewed isolated launcher and public development configuration.</p></main>)
}

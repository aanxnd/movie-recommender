import React from 'react'
import { createRoot } from 'react-dom/client'
import { createPrivateRuntime } from './private-runtime.js'
import { StagingApp } from './staging-app.jsx'
import './styles.css'
import './staging.css'

const root = createRoot(document.getElementById('root'))
try {
  const runtime = createPrivateRuntime({ mode: 'private-stage23',
    projectUrl: __MOVELLE_PRIVATE_PUBLIC__.supabase_url, publishableKey: __MOVELLE_PRIVATE_KEY__,
    appOrigin: __MOVELLE_PRIVATE_PUBLIC__.frontend_origin, base: '/api' }, __MOVELLE_PRIVATE_PUBLIC__)
  addEventListener('beforeunload', () => runtime.stop(), { once: true })
  root.render(<React.StrictMode><StagingApp runtime={runtime} /></React.StrictMode>)
} catch {
  history.replaceState(null, '', '/')
  root.render(<main><h1>Private preview unavailable</h1><p>Approved configuration is required.</p></main>)
}

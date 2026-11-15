import React from 'react'
import { createRoot } from 'react-dom/client'
import { createNativeRuntime } from './native-runtime.js'
import { NativeApp } from './native-app.jsx'
import './styles.css'
import './native.css'

const root = createRoot(document.getElementById('root'))
try {
  const targets = __MOVELLE_NATIVE_PUBLIC__
  const runtime = createNativeRuntime({ projectUrl: targets.supabase_url, publishableKey: __MOVELLE_NATIVE_KEY__,
    appOrigin: targets.frontend_origin, base: targets.api_origin }, targets)
  addEventListener('beforeunload', () => runtime.stop(), { once: true })
  root.render(<React.StrictMode><NativeApp runtime={runtime} /></React.StrictMode>)
} catch {
  history.replaceState(null, '', '/')
  root.render(<main><h1>Movelle is unavailable.</h1><p>Please try again when the service is ready.</p></main>)
}

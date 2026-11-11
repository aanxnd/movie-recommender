import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import { fixture, tick } from './auth-test-support.js'

// Isolated DOM + the actual JSX modules; no production mount or hosted transport.
export async function mountAccount(t, filename, name, props = {}, authenticated = false) {
  const dom = new JSDOM('<div id="root"></div>', { url: 'https://movelle.test' })
  globalThis.window = dom.window; globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const previousFormData = globalThis.FormData; globalThis.FormData = dom.window.FormData
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom',
    optimizeDeps: { noDiscovery: true, include: [] } })
  const screens = await server.ssrLoadModule('/src/' + filename)
  const { AuthProvider } = await server.ssrLoadModule('/src/auth-context.js')
  const f = fixture(), root = createRoot(document.getElementById('root'))
  t.after(async () => {
    await act(async () => root.unmount()); await server.close(); dom.window.close()
    globalThis.FormData = previousFormData
    delete globalThis.window; delete globalThis.document; delete globalThis.IS_REACT_ACT_ENVIRONMENT
  })
  await act(async () => {
    root.render(React.createElement(React.StrictMode, null,
      React.createElement(AuthProvider, { session: f.session }, React.createElement(screens[name], props))))
    f.load.resolve({ data: { session: authenticated ? { access_token: 'synthetic', expires_at: Date.now()/1000+600, user: { id: 'a' } } : null } })
    await tick()
  })
  return { ...f, dom, root, text: () => document.body.textContent,
    input: (name, value) => { document.querySelector(`[name="${name}"]`).value = value },
    submit: () => act(async () => { document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })); await tick() }),
    click: selector => act(async () => { document.querySelector(selector).click(); await tick() }),
  }
}

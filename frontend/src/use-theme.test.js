import test from 'node:test'
import assert from 'node:assert/strict'
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import { useTheme } from './use-theme.js'
import { THEME_KEY } from './themes.js'

async function setup(t, stored) {
  const dom = new JSDOM('<meta name="theme-color"><div id="root"></div>', { url: 'https://movelle.test' })
  globalThis.window = dom.window; globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  if (stored) dom.window.localStorage.setItem(THEME_KEY, stored)
  dom.window.localStorage.setItem('movelle.identity.v1', 'legacy-private')
  const root = createRoot(document.getElementById('root')), values = []
  function View({ index }) { values[index] = useTheme(); return React.createElement('span', null, values[index].theme) }
  const mount = async () => act(async () => root.render(React.createElement(React.StrictMode, null,
    React.createElement(View, { index: 0 }), React.createElement(View, { index: 1 }))))
  t.after(async () => { await act(async () => root.unmount()); dom.window.close(); delete globalThis.window;
    delete globalThis.document; delete globalThis.IS_REACT_ACT_ENVIRONMENT })
  await mount()
  return { values, dom, root, mount }
}
test('saved palette applies on first layout and synchronizes consumers without touching identity', async t => {
  const f = await setup(t, 'forest-wine')
  assert.equal(document.documentElement.dataset.theme, 'forest-wine')
  assert.equal(document.documentElement.style.getPropertyValue('--theme-bg'), '#10271e')
  await act(async () => f.values[0].changeTheme('midnight-copper'))
  assert.equal(f.values[1].theme, 'midnight-copper')
  assert.equal(window.localStorage.getItem(THEME_KEY), 'midnight-copper')
  assert.equal(window.localStorage.getItem('movelle.identity.v1'), 'legacy-private')
  await act(async () => f.root.render(null)); await f.mount()
  assert.equal(f.values[0].theme, 'midnight-copper')
  assert.equal(document.documentElement.dataset.theme, 'midnight-copper')
})
test('cross-tab updates/clear and blocked storage keep the existing safe fallback', async t => {
  const f = await setup(t)
  window.localStorage.setItem(THEME_KEY, 'grayscale')
  await act(async () => window.dispatchEvent(new window.StorageEvent('storage', { key: THEME_KEY })))
  assert.equal(f.values[1].theme, 'grayscale')
  window.localStorage.clear()
  await act(async () => window.dispatchEvent(new window.StorageEvent('storage', { key: null })))
  assert.equal(f.values[0].theme, 'cinema')
  assert.equal(document.documentElement.style.getPropertyValue('--theme-bg'), '')
  t.mock.method(f.dom.window.Storage.prototype, 'setItem', () => { throw new Error('blocked') })
  await act(async () => f.values[0].changeTheme('pine-petrol'))
  assert.equal(f.values[0].saved, false); assert.equal(f.values[1].theme, 'pine-petrol')
  await act(async () => f.root.render(null)); await f.mount()
  assert.equal(f.values[0].theme, 'pine-petrol'); assert.equal(f.values[1].saved, false)
})

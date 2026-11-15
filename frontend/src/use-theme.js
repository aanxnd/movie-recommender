import { useEffect, useLayoutEffect, useState } from 'react'
import { THEME_KEY, getTheme, readTheme, saveTheme, themeProperties } from './themes.js'

const CHANGED = 'movelle:theme-change'
const visits = new WeakMap()
function currentPreference() {
  if (typeof window === 'undefined') return { theme: 'cinema', saved: false }
  if (!visits.has(window)) visits.set(window, { theme: readTheme(), saved: true })
  return visits.get(window)
}

// Shared by product and account screens; theme state never owns auth/identity state.
export function useTheme() {
  const [theme, setTheme] = useState(() => currentPreference().theme), [saved, setSaved] = useState(() => currentPreference().saved)
  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    const properties = Array.from({ length: root.style.length }, (_, i) => root.style.item(i))
    for (const name of properties.filter(name => name.startsWith('--theme-'))) root.style.removeProperty(name)
    for (const [name, value] of Object.entries(themeProperties(theme))) root.style.setProperty(name, value)
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', getTheme(theme).colors[0])
    // Do not clear root on unmount: login/logout/navigation must retain the palette.
  }, [theme])
  useEffect(() => {
    const changed = event => {
      if (event.type === CHANGED || event.key === THEME_KEY || event.key === null) {
        const next = { theme: event.type === CHANGED ? getTheme(event.detail?.id).id : readTheme(),
          saved: event.type === CHANGED ? event.detail?.saved === true : true }
        visits.set(window, next); setTheme(next.theme); setSaved(next.saved)
      }
    }
    window.addEventListener('storage', changed); window.addEventListener(CHANGED, changed)
    return () => { window.removeEventListener('storage', changed); window.removeEventListener(CHANGED, changed) }
  }, [])
  function changeTheme(id) {
    const next = getTheme(id).id, persisted = saveTheme(next)
    visits.set(window, { theme: next, saved: persisted })
    setTheme(next); setSaved(persisted)
    window.dispatchEvent(new window.CustomEvent(CHANGED, { detail: { id: next, saved: persisted } }))
  }
  return { theme, saved, changeTheme }
}

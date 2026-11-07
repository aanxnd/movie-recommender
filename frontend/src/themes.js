export const THEME_KEY = 'movelle.theme.v1'

// Dark tints keep hue relationships visible without competing with film imagery.
export const THEMES = [
  { id: 'cinema', name: 'Original cinema', colors: ['#0c1715', '#451b29', '#19364f'], description: 'Forest, oxblood and midnight', kind: 'Three colors' },
  { id: 'forest-wine', name: 'Forest & wine', colors: ['#10271e', '#351722'], description: 'Deep green with a wine-red counterpoint', kind: 'Two colors', harmony: 'Complementary', surface: '#1a2c24', raised: '#2a4034', header: '#0a1711', accent: '#c2ac89', muted: '#c3c8b9', text: '#f0e9de', ink: '#152018' },
  { id: 'midnight-copper', name: 'Midnight & copper', colors: ['#122436', '#382319'], description: 'Cool blue balanced by warm copper', kind: 'Two colors', harmony: 'Complementary', surface: '#1d2e3c', raised: '#304451', header: '#0b1824', accent: '#d0ab87', muted: '#c3c4bd', text: '#f0e9de', ink: '#17212a' },
  { id: 'aubergine-olive', name: 'Aubergine & olive', colors: ['#25172f', '#272e1b'], description: 'Dark violet with muted yellow-green', kind: 'Two colors', harmony: 'Complementary', surface: '#302437', raised: '#45364a', header: '#19101f', accent: '#c3bf95', muted: '#c7c0c5', text: '#eee9df', ink: '#231a29' },
  { id: 'pine-petrol', name: 'Pine, petrol & midnight', colors: ['#102b30', '#132d24', '#142039'], description: 'Neighboring greens and blues', kind: 'Three colors', harmony: 'Analogous', surface: '#1b3135', raised: '#30474a', header: '#0b1c20', accent: '#b9c5b1', muted: '#bdc8c5', text: '#ecebe2', ink: '#17272a' },
  { id: 'midnight-wine-olive', name: 'Midnight, wine & olive', colors: ['#142039', '#351925', '#252e1a'], description: 'A subdued blue, red and green triad', kind: 'Three colors', harmony: 'Triadic', surface: '#202d42', raised: '#354459', header: '#0d1628', accent: '#c6b58f', muted: '#c3c3bc', text: '#f0e9de', ink: '#182235' },
  { id: 'grayscale', name: 'Grayscale', colors: ['#111111', '#272727', '#ececec'], description: 'Black, charcoal and off-white', kind: 'Three tones', harmony: 'Achromatic', surface: '#242424', raised: '#393939', header: '#0c0c0c', accent: '#c9c9c9', muted: '#c0c0c0', text: '#ececec', ink: '#171717' },
]

export function getTheme(id) {
  return THEMES.find(theme => theme.id === id) || THEMES[0]
}

export function readTheme(storage) {
  try { return getTheme((storage || window.localStorage).getItem(THEME_KEY)).id }
  catch { return 'cinema' }
}

export function saveTheme(id, storage) {
  try { (storage || window.localStorage).setItem(THEME_KEY, getTheme(id).id); return true }
  catch { return false }
}

export function themeProperties(id) {
  const theme = getTheme(id)
  if (theme.id === 'cinema') return {}
  // Grayscale's off-white is text, never a background stop.
  const stops = theme.id === 'grayscale' ? theme.colors.slice(0, 2) : theme.colors
  return {
    '--theme-bg': stops[0],
    '--theme-backdrop': `linear-gradient(125deg, ${stops.join(', ')})`,
    '--theme-surface': theme.surface,
    '--theme-raised': theme.raised,
    '--theme-header': theme.header,
    '--theme-accent': theme.accent,
    '--theme-muted': theme.muted,
    '--theme-text': theme.text,
    '--theme-ink': theme.ink,
    '--theme-feature': stops[1],
  }
}

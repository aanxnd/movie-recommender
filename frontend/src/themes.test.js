import assert from 'node:assert/strict'
import test from 'node:test'
import { THEMES, THEME_KEY, readTheme, saveTheme, themeProperties } from './themes.js'

function luminance(hex) {
  const channels = hex.slice(1).match(/../g).map(channel => {
    const value = parseInt(channel, 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
}
function contrast(a, b) {
  const values = [luminance(a), luminance(b)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}

test('theme text meets WCAG AA against every background and control surface', () => {
  for (const theme of THEMES.filter(theme => theme.id !== 'cinema')) {
    const backgrounds = theme.id === 'grayscale' ? theme.colors.slice(0, 2) : theme.colors
    for (const background of [...backgrounds, theme.surface, theme.raised, theme.header]) {
      for (const foreground of [theme.text, theme.muted, theme.accent]) {
        assert.ok(contrast(background, foreground) >= 4.5,
          `${theme.name}: ${foreground} on ${background} is ${contrast(background, foreground).toFixed(2)}:1`)
      }
    }
    assert.ok(contrast(theme.text, theme.ink) >= 4.5, `${theme.name}: primary button`)
    assert.notEqual(theme.text.toLowerCase(), '#ffffff')
  }
})

test('grayscale is neutral, stays dark and uses off-white only as a foreground', () => {
  const theme = THEMES.find(theme => theme.id === 'grayscale')
  for (const color of [...theme.colors, theme.surface, theme.raised, theme.header, theme.accent, theme.muted, theme.ink]) {
    assert.equal(color.slice(1, 3), color.slice(3, 5))
    assert.equal(color.slice(3, 5), color.slice(5, 7))
  }
  assert.equal(theme.text, '#ececec')
  assert.ok(!themeProperties('grayscale')['--theme-backdrop'].includes(theme.text))
})

test('theme preference is separate from identity and survives reloads', () => {
  const values = new Map([['movelle.identity.v1', 'existing-profile']])
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }
  assert.equal(saveTheme('forest-wine', storage), true)
  assert.equal(values.get(THEME_KEY), 'forest-wine')
  assert.equal(readTheme(storage), 'forest-wine')
  assert.equal(values.get('movelle.identity.v1'), 'existing-profile')
})

test('unknown preferences and unavailable browser storage fail safely', () => {
  assert.equal(readTheme({ getItem: () => 'unknown' }), 'cinema')
  assert.deepEqual(themeProperties('unknown'), {})
  const storage = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  assert.equal(readTheme(storage), 'cinema')
  assert.equal(saveTheme('grayscale', storage), false)
})

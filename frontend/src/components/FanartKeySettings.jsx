import { useContext, useEffect, useState } from 'react'
import { ArtworkContext } from '../artwork.js'

export default function FanartKeySettings({ open }) {
  const artwork = useContext(ArtworkContext)
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { if (!open) { setInput(''); setError('') } }, [open])
  if (!artwork) return null
  return (
    <section className="fanart-settings" aria-labelledby="fanart-key-title">
      <h3 id="fanart-key-title">Artwork access</h3>
      <p className="field-hint">Fanart.tv works without a personal key. An optional <a href="https://fanart.tv/get-an-api-key/" target="_blank" rel="noreferrer">personal key</a> can give earlier access to new images.</p>
      <p className="field-hint" id="fanart-key-privacy">Kept in this tab's memory only. Sent securely through Movelle to Fanart.tv alongside the project key. Cleared on reload or profile change.</p>
      {!artwork.canSetPersonalKey && <p className="field-hint">Create or restore a profile to use a personal key.</p>}
      <form onSubmit={event => {
        event.preventDefault()
        if (!/^[a-fA-F0-9]{32}$/.test(input.trim())) { setError('Enter the 32-character personal key from Fanart.tv.'); return }
        artwork.setPersonalKey(input.trim()); setInput(''); setError('')
      }}>
        <label htmlFor="fanart-personal-key">Personal Fanart.tv key (optional)</label>
        <input id="fanart-personal-key" type="password" autoComplete="off" spellCheck={false} maxLength={32} value={input} disabled={!artwork.canSetPersonalKey} aria-describedby="fanart-key-privacy" onChange={event => setInput(event.target.value)} />
        <div className="recovery-actions">
          <button className="button-secondary" disabled={!artwork.canSetPersonalKey || !input} type="submit">Use personal key</button>
          {artwork.personalKeySet && <button className="button-quiet" type="button" onClick={() => { artwork.setPersonalKey(''); setInput(''); setError('') }}>Remove personal key</button>}
        </div>
      </form>
      {error && <p role="alert" className="error">{error}</p>}
      <p role="status" className="field-hint">{artwork.personalKeySet ? 'Personal key set for this tab. This confirms its format, not provider acceptance.' : 'Using standard project access.'}</p>
    </section>
  )
}

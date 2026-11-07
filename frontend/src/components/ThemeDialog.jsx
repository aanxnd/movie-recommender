import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { containDialogFocus } from '../dialog.js'
import { THEMES } from '../themes.js'

export default function ThemeDialog({ open, onClose, theme, onChange, saved }) {
  const dialog = useRef(null)
  const previous = useRef(null)
  useEffect(() => {
    if (open) { previous.current = document.activeElement; dialog.current.showModal() }
    else if (dialog.current.open) { dialog.current.close(); previous.current?.focus() }
  }, [open])
  return <dialog ref={dialog} id="theme-dialog" className="theme-dialog" aria-labelledby="theme-title" onKeyDown={containDialogFocus} onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <div className="theme-dialog-inner">
      <button className="icon-button theme-close" aria-label="Close themes" onClick={onClose}><X size={20} aria-hidden="true" /></button>
      <h2 id="theme-title">Website theme</h2>
      <p className="theme-intro">Dark palettes in two or three colors. Select one to preview it.</p>
      <fieldset className="theme-options"><legend className="sr-only">Background color theme</legend>{THEMES.map(option => <label className={`theme-option ${option.id === 'cinema' ? 'theme-original' : ''}`} key={option.id}>
        <span className="theme-swatches" aria-hidden="true">{option.colors.map(color => <span key={color} style={{ backgroundColor: color }} />)}</span>
        <span className="theme-option-copy"><span className="theme-option-name">{option.name}</span><span className="theme-option-description">{option.description}</span><span className="theme-option-kind">{option.kind}</span></span>
        <input type="radio" name="website-theme" aria-label={option.name} value={option.id} checked={theme === option.id} onChange={() => onChange(option.id)} />
      </label>)}</fieldset>
      <div className="theme-dialog-footer"><p role="status">{saved ? 'Saved on this browser.' : 'Applied for this visit. Browser storage is unavailable.'}</p><button className="button-primary" onClick={onClose}>Done</button></div>
    </div>
  </dialog>
}

import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { containDialogFocus } from '../dialog.js'

export default function ProfileDialog({ open, onClose, children }) {
  const ref = useRef(null)
  const returnFocus = useRef(null)
  useEffect(() => {
    const dialog = ref.current
    if (open) {
      returnFocus.current = document.activeElement
      dialog.showModal()
    } else if (dialog.open) {
      dialog.close()
      returnFocus.current?.focus()
    }
  }, [open])
  return (
    <dialog
      ref={ref}
      id="profile-dialog"
      className="profile-dialog"
      aria-labelledby="profile-title"
      onKeyDown={containDialogFocus}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="profile-dialog-inner">
        <button
          className="icon-button dialog-close"
          aria-label="Close profile"
          onClick={onClose}
        >
          <X size={20} aria-hidden="true" />
        </button>
        {children}
      </div>
    </dialog>
  )
}

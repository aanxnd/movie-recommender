import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from './auth-context.js'
import { AuthNotice } from './account-screens.jsx'
import { containDialogFocus } from './dialog.js'

const copy = {
  disable: { title: 'Review account disabling', warning: 'A supported disable operation would pause personal features while keeping your data. Login and session restrictions still need an approved design.',
    button: 'Disabling unavailable' },
  delete: { title: 'Review account deletion', warning: 'Deletion could permanently remove your profile, ratings and shared invitations. Retention, recovery and identity cleanup rules still need approval.',
    button: 'Deletion unavailable' },
}

// Deliberately no destructive service/handler prop: previewing consequences cannot execute an operation.
export function AccountLifecycleControls() {
  const auth = useAuth(), id = useId(), dialog = useRef(null), [kind, setKind] = useState(null)
  const signedIn = auth.status === 'authenticated'
  useEffect(() => { setKind(null) }, [auth.generation, signedIn])
  useEffect(() => {
    if (!kind) return
    const element = dialog.current, previous = document.activeElement
    element.showModal(); element.querySelector('[data-cancel]').focus()
    return () => { if (element.open) element.close(); if (previous?.isConnected) previous.focus() }
  }, [kind])
  return <section className="account-section" aria-labelledby={id + '-heading'}>
    <h2 id={id + '-heading'}>Account access</h2>
    <p>Disabling and deletion need a trusted backend. Signing out does not disable or delete an account.</p>
    <div className="account-review-actions">
      <button className="button-secondary" disabled={!signedIn} onClick={() => setKind('disable')}>Review disabling</button>
      <button className="button-secondary" disabled={!signedIn} onClick={() => setKind('delete')}>Review deletion</button>
    </div>
    <dialog ref={dialog} className="account-lifecycle-dialog" aria-labelledby={id + '-title'} aria-describedby={id + '-warning'}
      onKeyDown={containDialogFocus} onCancel={event => { event.preventDefault(); setKind(null) }}
      onClick={event => { if (event.target === event.currentTarget) setKind(null) }}>
      {kind && <>
        <p className="eyebrow">ACCOUNT CARE</p><h2 id={id + '-title'}>{copy[kind].title}</h2>
        <p id={id + '-warning'}>{copy[kind].warning}</p>
        <AuthNotice focus={false}>This operation is unavailable. No account or data change will be performed here.</AuthNotice>
        <label className="account-acknowledgement"><input type="checkbox" /> I understand that the account and data consequences require review.</label>
        <div className="account-review-actions"><button className="button-secondary" data-cancel onClick={() => setKind(null)}>Cancel</button>
          <button className="button-primary" disabled>{copy[kind].button}</button></div>
      </>}
    </dialog>
  </section>
}

import { useEffect, useRef, useState } from 'react'
import {
  UserRound,
  Plus,
  Copy,
  ShieldCheck,
  Users,
  Eye,
  EyeOff,
} from 'lucide-react'
import { request } from '../api.js'
import { parseRecoveryCode, readIdentity, sameIdentity } from '../identity.js'

function RecoveryCode({ code, unsaved, open }) {
  const [visible, setVisible] = useState(false)
  const [copyStatus, setCopyStatus] = useState('')
  useEffect(() => {
    if (!open) setVisible(false)
  }, [open])

  async function copy() {
    setCopyStatus('copying')
    try {
      await window.navigator.clipboard.writeText(code)
      setCopyStatus('copied')
    } catch {
      // Browser errors may contain sensitive details; show only fixed text.
      setCopyStatus('error')
    }
  }

  return (
    <div className="recovery-card">
      <label htmlFor="profile-recovery-code">
        {unsaved
          ? 'Unsaved new profile recovery code: save securely'
          : 'Private recovery code: save securely; never share for groups'}
      </label>
      <input
        id="profile-recovery-code"
        aria-describedby="recovery-code-warning"
        className="credential-input"
        type={visible ? 'text' : 'password'}
        autoComplete="off"
        spellCheck={false}
        readOnly
        value={code}
        onFocus={(event) => event.target.select()}
      />
      <div className="recovery-actions">
        <button
          type="button"
          className="button-secondary"
          disabled={copyStatus === 'copying'}
          onClick={copy}
          aria-label="Copy recovery code"
        >
          <Copy size={14} aria-hidden="true" />
          Copy code
        </button>
        <button
          type="button"
          className="button-secondary"
          aria-label={visible ? 'Hide recovery code' : 'Show recovery code'}
          aria-controls="profile-recovery-code"
          aria-pressed={visible}
          onClick={() => setVisible((value) => !value)}
        >
          {visible ? (
            <EyeOff size={14} aria-hidden="true" />
          ) : (
            <Eye size={14} aria-hidden="true" />
          )}
          {visible ? 'Hide code' : 'Show code'}
        </button>
      </div>
      <p role="status" aria-atomic="true" className="copy-status">
        {copyStatus === 'copied'
          ? 'Recovery code copied.'
          : copyStatus === 'copying'
            ? 'Copying recovery code...'
            : ''}
      </p>
      {copyStatus === 'error' && (
        <p role="alert" className="error">
          Could not copy recovery code. Show it, then select and copy it
          manually.
        </p>
      )}
      <p id="recovery-code-warning" className="security-note">
        <ShieldCheck size={16} aria-hidden="true" />
        Your recovery code grants access to your account. Store it securely and
        never share it.
      </p>
    </div>
  )
}

export default function UserPanel({ user, onSelect, open = true }) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [errorArea, setErrorArea] = useState('invite')
  const [invitationVisible, setInvitationVisible] = useState(false)
  useEffect(() => {
    if (!open) setInvitationVisible(false)
  }, [open])
  const [unsavedCode, setUnsavedCode] = useState('')
  const [invitation, setInvitation] = useState('')
  const [invitationExpiresAt, setInvitationExpiresAt] = useState(null)
  const [invitationStatus, setInvitationStatus] = useState('')
  const pending = useRef(null)
  const code = unsavedCode || (user ? `${user.id}:${user.token}` : '')
  useEffect(() => () => pending.current?.abort(), [])
  useEffect(() => {
    if (!invitation || !Number.isFinite(invitationExpiresAt)) return
    const expire = () => {
      setInvitation('')
      setInvitationExpiresAt(null)
      setInvitationStatus(
        'This invitation expired. Create a new invitation to share with your group.',
      )
    }
    const remaining = invitationExpiresAt * 1000 - Date.now()
    if (remaining <= 0) {
      expire()
      return
    }
    const timer = setTimeout(expire, remaining)
    return () => clearTimeout(timer)
  }, [invitation, invitationExpiresAt])

  async function perform(action, area = 'invite') {
    setErrorArea(area)
    if (pending.current) return
    const current = new AbortController()
    pending.current = current
    setBusy(true)
    setError('')
    try {
      await action(current.signal)
    } catch (error) {
      if (!current.signal.aborted) setError(error.message)
    } finally {
      if (!current.signal.aborted) {
        pending.current = null
        setBusy(false)
      }
    }
  }

  function select(create) {
    return perform(
      async (signal) => {
        const previous = readIdentity()
        const next = create
          ? await request('/users', { method: 'POST', signal })
          : parseRecoveryCode(input)
        if (!create)
          await request(`/users/${next.id}`, { token: next.token, signal })
        signal.throwIfAborted()
        if (!sameIdentity(previous, readIdentity()))
          throw new Error(
            'The profile changed in another tab. Please try again.',
          )
        if (create) setUnsavedCode(`${next.id}:${next.token}`)
        onSelect(next) // App alone persists and activates the selection.
        setInput('')
      },
      create ? 'create' : 'restore',
    )
  }

  return (
    <aside className="user-panel">
      <p className="eyebrow">
        <UserRound size={14} aria-hidden="true" />
        Your account
      </p>
      <h2 id="profile-title">Your profile</h2>
      <p role="status" className="profile-status">
        <span className={`status-dot ${user ? 'connected' : ''}`} />
        {user ? `User ${user.id}` : 'No user selected'}
      </p>
      <p className="profile-intro">
        {user
          ? 'Your ratings are saved to this profile. Keep its recovery code to use it on another browser.'
          : 'Create a private profile to save ratings and get recommendations. Keep the recovery code so you can return.'}
      </p>
      <button
        onClick={() => select(true)}
        disabled={busy}
        className="button-primary profile-create"
        aria-label="Create new user"
      >
        <Plus size={16} aria-hidden="true" />
        {busy ? 'Please wait…' : 'Create profile'}
      </button>
      {error && errorArea === 'create' && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          select(false)
        }}
        className="restore-form"
      >
        <label htmlFor="user-id" className="field-label">
          Private recovery code
        </label>
        <p className="field-hint">
          Already have a profile? Paste your saved code to restore it.
        </p>
        <div className="restore-actions">
          <input
            id="user-id"
            type="password"
            autoComplete="off"
            placeholder="ID:credential"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={busy}
          />
          <button className="button-secondary" disabled={busy}>
            Load
          </button>
        </div>
      </form>
      {error && errorArea === 'restore' && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {code && (
        <RecoveryCode
          key={unsavedCode ? `unsaved-${code.split(':')[0]}` : 'selected'}
          code={code}
          unsaved={Boolean(unsavedCode)}
          open={open}
        />
      )}
      {user && (
        <div className="invitation-panel">
          <h3>
            <Users size={17} aria-hidden="true" />
            Group invitations
          </h3>
          <p className="field-hint">
            Create an invitation for group recommendations. It grants temporary
            recommendation access only.
          </p>
          <div className="invitation-actions">
            <button
              className="button-secondary"
              disabled={busy}
              onClick={() =>
                perform(async (signal) => {
                  const result = await request(
                    `/users/${user.id}/group-invitation`,
                    { token: user.token, method: 'POST', signal },
                  )
                  setInvitation(result.code)
                  setInvitationExpiresAt(result.expires_at)
                  setInvitationStatus(
                    'Invitation created. Valid for 10 minutes; creating another replaces it.',
                  )
                })
              }
            >
              Create 10-minute group invitation
            </button>
            <button
              className="button-quiet"
              disabled={busy}
              onClick={() =>
                perform(async (signal) => {
                  await request(`/users/${user.id}/group-invitation`, {
                    token: user.token,
                    method: 'DELETE',
                    signal,
                  })
                  setInvitation('')
                  setInvitationExpiresAt(null)
                  setInvitationStatus('Invitation revoked.')
                })
              }
            >
              Revoke invitation
            </button>
          </div>
          {invitation && (
            <div className="invitation-code">
              <label className="field-label" htmlFor="group-invitation">
                Share this temporary invitation
              </label>
              <input
                id="group-invitation"
                type={invitationVisible ? 'text' : 'password'}
                aria-label="Group invitation"
                autoComplete="off"
                spellCheck={false}
                readOnly
                value={invitation}
                onFocus={(event) => event.target.select()}
              />
              <div className="recovery-actions">
                <button
                  className="button-secondary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(invitation)
                      setInvitationStatus(
                        'Invitation copied. Share it with your group.',
                      )
                    } catch {
                      setErrorArea('invite')
                      setError(
                        'Could not copy. Show the invitation and copy it manually.',
                      )
                    }
                  }}
                >
                  Copy invitation
                </button>
                <button
                  className="button-secondary"
                  aria-pressed={invitationVisible}
                  onClick={() => setInvitationVisible((value) => !value)}
                >
                  {invitationVisible ? 'Hide invitation' : 'Show invitation'}
                </button>
              </div>
            </div>
          )}
          {invitationStatus && (
            <p role="status" className="field-hint">
              {invitationStatus}
            </p>
          )}
        </div>
      )}
      {error && errorArea === 'invite' && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!user && (
        <p className="security-note profile-security">
          <ShieldCheck size={17} aria-hidden="true" />
          Your number is not a password. Keep your recovery code private. Group
          invitations grant temporary recommendation access only.
        </p>
      )}
    </aside>
  )
}

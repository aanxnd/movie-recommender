import { useRef, useState } from 'react'
import { Search, UserRound, Menu, X, Palette } from 'lucide-react'
import { Brand } from './ui.jsx'

const links = [
  ['discover', 'Discover'],
  ['ratings', 'My ratings'],
  ['for-you', 'For you'],
  ['groups', 'Groups'],
]
export default function AppHeader({
  page,
  user,
  onNavigate,
  onSearch,
  onProfile,
  onTheme,
}) {
  const [open, setOpen] = useState(false)
  const menuButton = useRef(null)
  return (
    <header
      className="site-header"
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          setOpen(false)
          menuButton.current?.focus()
        }
      }}
    >
      <div className="header-inner">
        <button
          className="brand-button"
          aria-label="Movelle home"
          onClick={() => {
            setOpen(false)
            onNavigate('discover')
          }}
        >
          <Brand />
        </button>
        <nav
          id="main-navigation"
          className={`main-nav ${open ? 'menu-open' : ''}`}
          aria-label="Main navigation"
        >
          {links.map(([key, label]) => (
            <button
              key={key}
              className={`nav-link ${page === key ? 'active' : ''}`}
              aria-current={page === key ? 'page' : undefined}
              onClick={() => {
                setOpen(false)
                onNavigate(key)
              }}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="header-actions">
          <button
            className="theme-trigger"
            aria-label="Change color theme"
            aria-haspopup="dialog"
            aria-controls="theme-dialog"
            onClick={() => {
              setOpen(false)
              onTheme()
            }}
          >
            <Palette size={18} aria-hidden="true" />
            <span>Theme</span>
          </button>
          <button
            className="header-search"
            aria-label="Search films"
            onClick={() => {
              setOpen(false)
              onSearch()
            }}
          >
            <Search size={18} aria-hidden="true" />
            <span>Search</span>
            <kbd>Ctrl K</kbd>
          </button>
          <button
            className="profile-trigger"
            aria-label="Your profile"
            aria-haspopup="dialog"
            aria-controls="profile-dialog"
            onClick={() => {
              setOpen(false)
              onProfile()
            }}
          >
            <UserRound size={18} aria-hidden="true" />
            <span>{user ? `User ${user.id}` : 'Profile'}</span>
          </button>
          <button
            ref={menuButton}
            className="mobile-menu icon-button"
            aria-label="Navigation menu"
            aria-expanded={open}
            aria-controls="main-navigation"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? (
              <X size={23} aria-hidden="true" />
            ) : (
              <Menu size={23} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}

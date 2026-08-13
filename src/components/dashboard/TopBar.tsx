import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Role } from './Sidebar'
import Logo from '../ui/Logo'
import { useProfile } from '../../context/ProfileContext'
import { useProfileStats } from '../../hooks/useProfileStats'

interface TopBarProps {
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  role: Role
  onOpenMobileNav?: () => void
  onNavigate?: (item: string) => void
  onLogout?: () => void
}

export default function TopBar({
  theme,
  onToggleTheme,
  role,
  onOpenMobileNav,
  onNavigate,
  onLogout,
}: TopBarProps) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [notifOpen, setNotifOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const { profile } = useProfile()
  const stats = useProfileStats()

  const studentNotifications = [
    {
      id: 1,
      text: 'Quiz results ready: Biology Chapter 8',
      time: '2m ago',
      icon: '📋',
      unread: true,
    },
    {
      id: 2,
      text: 'Streak milestone: 21 days 🔥',
      time: '1h ago',
      icon: '🏆',
      unread: true,
    },
    {
      id: 3,
      text: 'New AI Tutor feature available',
      time: '3h ago',
      icon: '🤖',
      unread: true,
    },
    {
      id: 4,
      text: 'Weekly report ready to view',
      time: '1d ago',
      icon: '📊',
      unread: false,
    },
  ]

  const doctorNotifications = [
    {
      id: 1,
      text: '5 new students enrolled in CS201',
      time: '5m ago',
      icon: '👥',
      unread: true,
    },
    {
      id: 2,
      text: '3 students flagged as at-risk this week',
      time: '2h ago',
      icon: '⚠️',
      unread: true,
    },
    {
      id: 3,
      text: 'New course material uploaded',
      time: '4h ago',
      icon: '📚',
      unread: true,
    },
    {
      id: 4,
      text: 'Weekly engagement report generated',
      time: '1d ago',
      icon: '📊',
      unread: false,
    },
  ]

  const notifications = role === 'doctor' ? doctorNotifications : studentNotifications
  const unreadCount = notifications.filter((n) => n.unread).length

  const studentResults = [
    { label: 'Biology Chapter 7 Notes', type: 'File', icon: '📄' },
    { label: 'Calculus Study Plan', type: 'Planner', icon: '📅' },
    { label: 'Physics Mock Test #3', type: 'Quiz', icon: '❓' },
  ]

  const doctorResults = [
    { label: 'CS201 — Data Structures', type: 'Course', icon: '📚' },
    { label: 'CS310 — Database Systems', type: 'Course', icon: '📚' },
    { label: 'Amelia Torres', type: 'Student', icon: '👤' },
  ]

  const results = role === 'doctor' ? doctorResults : studentResults

  return (
    <>
      <header
        className="flex items-center gap-3 sm:gap-4 px-4 sm:px-6 py-3.5 sm:py-4 border-b backdrop-blur-xl"
        style={{
          background: 'var(--header-bg)',
          borderColor: 'var(--border-subtle)',
          position: 'sticky',
          top: 0,
          zIndex: 30,
        }}
      >
        {/* Mobile menu toggle */}
        <button
          onClick={onOpenMobileNav}
          className="lg:hidden w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 input-field"
          style={{ color: 'var(--muted-foreground)' }}
          aria-label="Open menu"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Compact logo — mobile header only, hidden once the sidebar is visible */}
        <Logo variant="symbol" size="xs" className="lg:hidden flex-shrink-0" />

        {/* Search bar */}
        <button
          onClick={() => setSearchOpen(true)}
          className="input-field flex-1 max-w-md flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all"
          style={{ color: 'var(--muted-foreground)' }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <span className="hidden sm:inline">
            {role === 'doctor' ? 'Search courses, students...' : 'Search anything...'}
          </span>
          <span className="sm:hidden">Search...</span>
          <span
            className="ml-auto text-xs px-2 py-0.5 rounded hidden sm:inline-block"
            style={{
              background: 'var(--surface-hover)',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            ⌘K
          </span>
        </button>

        <div className="flex items-center gap-3 ml-auto">
          {/* Theme toggle */}
          <button
            onClick={onToggleTheme}
            className="w-9 h-9 rounded-xl flex items-center justify-center transition-all hover:scale-110 input-field"
            style={{ color: 'var(--muted-foreground)' }}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="5" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            ) : (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => {
                setNotifOpen((v) => !v)
                setProfileOpen(false)
              }}
              className="relative w-9 h-9 rounded-xl flex items-center justify-center transition-all hover:scale-110 input-field"
              style={{ color: 'var(--muted-foreground)' }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {unreadCount > 0 && (
                <span
                  className="absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{
                    background: 'var(--accent)',
                    color: 'var(--accent-foreground)',
                    fontSize: 9,
                  }}
                >
                  {unreadCount}
                </span>
              )}
            </button>

            <AnimatePresence>
              {notifOpen && (
                <motion.div
                  className="surface-popover absolute right-0 mt-2 w-80 rounded-2xl overflow-hidden"
                  style={{ top: '100%', zIndex: 50 }}
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                >
                  <div
                    className="px-4 py-3 border-b"
                    style={{ borderColor: 'var(--border-subtle)' }}
                  >
                    <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                      Notifications
                    </p>
                  </div>
                  {notifications.map((n) => (
                    <div
                      key={n.id}
                      className="flex items-start gap-3 px-4 py-3 transition-colors"
                      style={{ borderBottom: '1px solid var(--border-subtle)' }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background = 'var(--surface-hover)')
                      }
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <span className="text-lg flex-shrink-0">{n.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p
                          className="text-xs leading-relaxed"
                          style={{
                            color: n.unread ? 'var(--foreground)' : 'var(--muted-foreground)',
                          }}
                        >
                          {n.text}
                        </p>
                        <p
                          className="text-xs mt-0.5"
                          style={{
                            color: 'var(--muted-foreground)',
                            opacity: 0.7,
                          }}
                        >
                          {n.time}
                        </p>
                      </div>
                      {n.unread && (
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0 mt-1"
                          style={{ background: 'var(--primary)' }}
                        />
                      )}
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* XP Badge (student) / Status badge (doctor) */}
          {role === 'student' ? (
            <div
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full"
              style={{
                background: 'rgba(255,126,54,0.12)',
                border: '1px solid rgba(255,126,54,0.25)',
              }}
            >
              <span
                className="text-xs font-black"
                style={{
                  color: 'var(--accent)',
                  fontFamily: 'Orbitron, sans-serif',
                }}
              >
                LVL {stats.level.level}
              </span>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                ·
              </span>
              <span
                className="text-xs font-mono"
                style={{
                  color: 'var(--accent)',
                  fontFamily: 'JetBrains Mono, monospace',
                }}
              >
                {stats.xp.toLocaleString()} XP
              </span>
            </div>
          ) : (
            <div
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full"
              style={{
                background: 'rgba(45,212,191,0.1)',
                border: '1px solid rgba(45,212,191,0.22)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--primary)' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--primary)' }}>
                4 courses active
              </span>
            </div>
          )}

          {/* Avatar */}
          <div className="relative">
            <button
              onClick={() => {
                setProfileOpen((v) => !v)
                setNotifOpen(false)
              }}
              className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all hover:scale-110 overflow-hidden"
              style={{
                background:
                  role === 'student' && profile?.avatarDataUrl
                    ? undefined
                    : 'linear-gradient(135deg, var(--primary), var(--secondary))',
                color: 'var(--primary-foreground)',
              }}
            >
              {role === 'student' && profile?.avatarDataUrl ? (
                <img
                  src={profile.avatarDataUrl}
                  alt={profile.fullName}
                  className="w-full h-full object-cover"
                />
              ) : role === 'doctor' ? (
                'DR'
              ) : (
                (profile?.fullName || 'A').charAt(0).toUpperCase()
              )}
            </button>

            <AnimatePresence>
              {profileOpen && (
                <motion.div
                  className="surface-popover absolute right-0 mt-2 w-56 rounded-2xl overflow-hidden"
                  style={{ top: '100%', zIndex: 50 }}
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                >
                  <div
                    className="px-4 py-4 border-b"
                    style={{ borderColor: 'var(--border-subtle)' }}
                  >
                    <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                      {role === 'doctor' ? 'Dr. Sarah Novak' : profile?.fullName || 'Student'}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      {role === 'doctor'
                        ? 'sarah.novak@university.edu'
                        : profile?.email || 'student@university.edu'}
                    </p>
                  </div>
                  {(role === 'student'
                    ? [
                        { label: 'My Profile', item: 'profile' },
                        { label: 'Achievements', item: 'gamification' },
                        { label: 'Certificates', item: 'gamification' },
                        { label: 'Settings', item: 'settings' },
                        { label: `Theme: ${theme === 'dark' ? 'Dark' : 'Light'}`, item: 'theme' },
                        { label: 'Log Out', item: 'logout' },
                      ]
                    : [
                        { label: 'Profile', item: 'settings' },
                        { label: 'Preferences', item: 'settings' },
                        { label: `Theme: ${theme === 'dark' ? 'Dark' : 'Light'}`, item: 'theme' },
                        { label: 'Log Out', item: 'logout' },
                      ]
                  ).map(({ label, item }) => (
                    <button
                      key={label}
                      onClick={() => {
                        setProfileOpen(false)
                        if (item === 'theme') {
                          onToggleTheme()
                          return
                        }
                        if (item === 'logout') {
                          onLogout?.()
                          return
                        }
                        onNavigate?.(item)
                      }}
                      className="w-full text-left px-4 py-2.5 text-sm transition-colors"
                      style={{
                        color: item === 'logout' ? 'var(--danger)' : 'var(--muted-foreground)',
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background = 'var(--surface-hover)')
                      }
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      {label}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </header>

      {/* Command palette */}
      <AnimatePresence>
        {searchOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-start justify-center pt-32 px-4"
            style={{
              background: 'var(--overlay-bg)',
              backdropFilter: 'blur(8px)',
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSearchOpen(false)}
          >
            <motion.div
              className="surface-popover w-full max-w-lg rounded-2xl overflow-hidden"
              initial={{ opacity: 0, y: -20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 380, damping: 28 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                className="flex items-center gap-3 px-5 py-4 border-b"
                style={{ borderColor: 'var(--border-subtle)' }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--primary)"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={
                    role === 'doctor'
                      ? 'Search courses, students...'
                      : 'Search files, quizzes, topics...'
                  }
                  className="flex-1 bg-transparent outline-none text-sm"
                  style={{ color: 'var(--foreground)' }}
                />
                <kbd
                  className="text-xs px-2 py-0.5 rounded"
                  style={{
                    background: 'var(--surface-hover)',
                    color: 'var(--muted-foreground)',
                  }}
                >
                  ESC
                </kbd>
              </div>
              <div className="py-2">
                {results.map((r) => (
                  <button
                    key={r.label}
                    className="w-full flex items-center gap-3 px-5 py-3 text-sm transition-colors text-left"
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = 'var(--surface-hover)')
                    }
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <span>{r.icon}</span>
                    <span style={{ color: 'var(--foreground)' }}>{r.label}</span>
                    <span
                      className="ml-auto text-xs px-2 py-0.5 rounded"
                      style={{
                        background: 'rgba(45,212,191,0.1)',
                        color: 'var(--primary)',
                      }}
                    >
                      {r.type}
                    </span>
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

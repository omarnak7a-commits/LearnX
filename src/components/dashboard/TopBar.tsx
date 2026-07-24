import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface TopBarProps {
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

export default function TopBar({ theme, onToggleTheme }: TopBarProps) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [notifOpen, setNotifOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const notifications = [
    { id: 1, text: 'Quiz results ready: Biology Chapter 8', time: '2m ago', icon: '📋', unread: true },
    { id: 2, text: 'Streak milestone: 21 days 🔥', time: '1h ago', icon: '🏆', unread: true },
    { id: 3, text: 'New AI Tutor feature available', time: '3h ago', icon: '🤖', unread: true },
    { id: 4, text: 'Weekly report ready to view', time: '1d ago', icon: '📊', unread: false },
  ]

  const results = [
    { label: 'Biology Chapter 7 Notes', type: 'File', icon: '📄' },
    { label: 'Calculus Study Plan', type: 'Planner', icon: '📅' },
    { label: 'Physics Mock Test #3', type: 'Quiz', icon: '❓' },
  ]

  return (
    <>
      <header
        className="flex items-center gap-4 px-6 py-4 border-b"
        style={{ background: '#0a0d14', borderColor: 'rgba(45,212,191,0.1)', position: 'sticky', top: 0, zIndex: 30 }}
      >
        {/* Search bar */}
        <button
          onClick={() => setSearchOpen(true)}
          className="flex-1 max-w-md flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all hover:border-teal-400/30"
          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(45,212,191,0.1)', color: '#64748B' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <span>Search anything...</span>
          <span
            className="ml-auto text-xs px-2 py-0.5 rounded"
            style={{ background: 'rgba(255,255,255,0.06)', fontFamily: 'JetBrains Mono, monospace' }}
          >
            ⌘K
          </span>
        </button>

        <div className="flex items-center gap-3 ml-auto">
          {/* Theme toggle */}
          <button
            onClick={onToggleTheme}
            className="w-9 h-9 rounded-xl flex items-center justify-center transition-all hover:scale-110"
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(45,212,191,0.1)', color: '#94A3B8' }}
          >
            {theme === 'dark' ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="5"/>
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => { setNotifOpen(v => !v); setProfileOpen(false) }}
              className="relative w-9 h-9 rounded-xl flex items-center justify-center transition-all hover:scale-110"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(45,212,191,0.1)', color: '#94A3B8' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              <span
                className="absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold"
                style={{ background: '#FF7E36', color: '#0A0D14', fontSize: 9 }}
              >
                4
              </span>
            </button>

            <AnimatePresence>
              {notifOpen && (
                <motion.div
                  className="absolute right-0 mt-2 w-80 rounded-2xl overflow-hidden"
                  style={{ background: '#111827', border: '1px solid rgba(45,212,191,0.15)', top: '100%', zIndex: 50 }}
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                >
                  <div className="px-4 py-3 border-b" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
                    <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>Notifications</p>
                  </div>
                  {notifications.map(n => (
                    <div
                      key={n.id}
                      className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-white/5"
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                    >
                      <span className="text-lg flex-shrink-0">{n.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs leading-relaxed" style={{ color: n.unread ? '#F8FAFC' : '#64748B' }}>{n.text}</p>
                        <p className="text-xs mt-0.5" style={{ color: '#475569' }}>{n.time}</p>
                      </div>
                      {n.unread && <div className="w-2 h-2 rounded-full flex-shrink-0 mt-1" style={{ background: '#2DD4BF' }} />}
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* XP Badge */}
          <div
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full"
            style={{ background: 'rgba(255,126,54,0.12)', border: '1px solid rgba(255,126,54,0.25)' }}
          >
            <span className="text-xs font-black" style={{ color: '#FF7E36', fontFamily: 'Orbitron, sans-serif' }}>
              LVL 12
            </span>
            <span className="text-xs" style={{ color: '#94A3B8' }}>·</span>
            <span className="text-xs font-mono" style={{ color: '#FF7E36', fontFamily: 'JetBrains Mono, monospace' }}>4,820 XP</span>
          </div>

          {/* Avatar */}
          <div className="relative">
            <button
              onClick={() => { setProfileOpen(v => !v); setNotifOpen(false) }}
              className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all hover:scale-110"
              style={{ background: 'linear-gradient(135deg, #2DD4BF, #14B8A6)', color: '#0A0D14' }}
            >
              A
            </button>

            <AnimatePresence>
              {profileOpen && (
                <motion.div
                  className="absolute right-0 mt-2 w-56 rounded-2xl overflow-hidden"
                  style={{ background: '#111827', border: '1px solid rgba(45,212,191,0.15)', top: '100%', zIndex: 50 }}
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                >
                  <div className="px-4 py-4 border-b" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
                    <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>Alex Chen</p>
                    <p className="text-xs" style={{ color: '#64748B' }}>alex@university.edu</p>
                  </div>
                  {['Profile', 'Preferences', 'Billing', 'Sign out'].map(item => (
                    <button
                      key={item}
                      className="w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-white/5"
                      style={{ color: item === 'Sign out' ? '#ef4444' : '#94A3B8' }}
                    >
                      {item}
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
            style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSearchOpen(false)}
          >
            <motion.div
              className="w-full max-w-lg rounded-2xl overflow-hidden"
              style={{ background: '#111827', border: '1px solid rgba(45,212,191,0.2)' }}
              initial={{ opacity: 0, y: -20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 380, damping: 28 }}
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center gap-3 px-5 py-4 border-b" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2DD4BF" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <input
                  autoFocus
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search files, quizzes, topics..."
                  className="flex-1 bg-transparent outline-none text-sm"
                  style={{ color: 'var(--foreground)' }}
                />
                <kbd className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.06)', color: '#64748B' }}>ESC</kbd>
              </div>
              <div className="py-2">
                {results.map(r => (
                  <button
                    key={r.label}
                    className="w-full flex items-center gap-3 px-5 py-3 text-sm transition-colors hover:bg-white/5 text-left"
                  >
                    <span>{r.icon}</span>
                    <span style={{ color: 'var(--foreground)' }}>{r.label}</span>
                    <span className="ml-auto text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(45,212,191,0.1)', color: '#2DD4BF' }}>{r.type}</span>
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

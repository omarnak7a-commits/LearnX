import { motion, AnimatePresence } from 'framer-motion'
import LogoMark from '../ui/LogoMark'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  activeItem: string
  onNavigate: (item: string) => void
  onBack: () => void
}

const navItems = [
  { id: 'dashboard', icon: '⊞', label: 'Dashboard', badge: null },
  { id: 'files', icon: '📂', label: 'My Files', badge: null },
  { id: 'tutor', icon: '🤖', label: 'AI Tutor', badge: 'NEW' },
  { id: 'planner', icon: '📅', label: 'Smart Planner', badge: null },
  { id: 'quizzes', icon: '❓', label: 'Quizzes', badge: '3' },
  { id: 'gamification', icon: '🏆', label: 'Gamification', badge: null },
  { id: 'analytics', icon: '📊', label: 'Analytics', badge: null },
  { id: 'settings', icon: '⚙️', label: 'Settings', badge: null },
]

export default function Sidebar({ collapsed, onToggle, activeItem, onNavigate, onBack }: SidebarProps) {
  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 240 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="relative flex flex-col overflow-hidden border-r scrollbar-thin"
      style={{
        background: '#090c13',
        borderColor: 'rgba(45,212,191,0.1)',
        minHeight: '100vh',
      }}
    >
      {/* Logo header */}
      <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
        <button onClick={onBack} className="flex-shrink-0 transition-all hover:scale-110" aria-label="Back to landing">
          <LogoMark size={30} color="#2DD4BF" />
        </button>
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              className="font-bold text-base whitespace-nowrap overflow-hidden"
              style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.2 }}
            >
              LearnX
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map(item => {
          const isActive = activeItem === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 relative group"
              style={{
                background: isActive ? 'rgba(45,212,191,0.1)' : 'transparent',
                color: isActive ? '#2DD4BF' : '#64748B',
                borderLeft: isActive ? '2px solid #2DD4BF' : '2px solid transparent',
              }}
            >
              <span className="text-base flex-shrink-0">{item.icon}</span>

              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    className="whitespace-nowrap overflow-hidden"
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>

              {item.badge && !collapsed && (
                <span
                  className="ml-auto text-xs px-1.5 py-0.5 rounded-full font-mono"
                  style={{
                    background: item.badge === 'NEW' ? 'rgba(45,212,191,0.15)' : 'rgba(255,126,54,0.2)',
                    color: item.badge === 'NEW' ? '#2DD4BF' : '#FF7E36',
                  }}
                >
                  {item.badge}
                </span>
              )}

              {/* Tooltip when collapsed */}
              {collapsed && (
                <div
                  className="absolute left-full ml-3 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50"
                  style={{ background: '#1a2235', color: '#F8FAFC', border: '1px solid rgba(45,212,191,0.2)' }}
                >
                  {item.label}
                </div>
              )}
            </button>
          )
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="p-3 border-t" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center p-2.5 rounded-xl transition-all hover:bg-white/5"
          style={{ color: '#64748B' }}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <motion.div animate={{ rotate: collapsed ? 180 : 0 }} transition={{ duration: 0.25 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
          </motion.div>
        </button>
      </div>
    </motion.aside>
  )
}

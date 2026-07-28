import { motion, AnimatePresence } from 'framer-motion'
import Logo from '../ui/Logo'

export type Role = 'student' | 'doctor'

interface NavItem {
  id: string
  icon: string
  label: string
  badge?: string | null
}

const studentNav: NavItem[] = [
  { id: 'dashboard', icon: '⊞', label: 'Dashboard' },
  { id: 'courses', icon: '📚', label: 'My Courses', badge: 'NEW' },
  { id: 'tutor', icon: '🤖', label: 'AI Workspace' },
  { id: 'files', icon: '📂', label: 'My Files' },
  { id: 'calendar', icon: '📅', label: 'Calendar' },
  { id: 'planner', icon: '📅', label: 'Study Planner' },
  { id: 'analytics', icon: '📊', label: 'Analytics' },
  { id: 'gamification', icon: '🏆', label: 'Achievements' },
  { id: 'settings', icon: '⚙️', label: 'Settings' },
  { id: 'video', icon: '🎬', label: 'Video Intelligence', badge: 'NEW' },
  { id: 'quizzes', icon: '❓', label: 'Quizzes', badge: '3' },
]

const doctorNav: NavItem[] = [
  { id: 'dashboard', icon: '⊞', label: 'Dashboard' },
  { id: 'courses', icon: '📚', label: 'Courses' },
  { id: 'course-builder', icon: '🧩', label: 'Course Builder', badge: 'NEW' },
  { id: 'materials', icon: '🗂️', label: 'Materials' },
  { id: 'students', icon: '👥', label: 'Students' },
  { id: 'assignments', icon: '📝', label: 'Assignments' },
  { id: 'exams', icon: '🧾', label: 'Exams' },
  { id: 'analytics', icon: '📊', label: 'Analytics' },
  { id: 'revenue', icon: '💰', label: 'Revenue' },
  { id: 'messages', icon: '💬', label: 'Messages', badge: '2' },
  { id: 'calendar', icon: '📅', label: 'Calendar' },
  { id: 'announcements', icon: '📣', label: 'Announcements' },
  { id: 'ai', icon: '✨', label: 'AI Assistant' },
  { id: 'settings', icon: '⚙️', label: 'Settings' },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  activeItem: string
  onNavigate: (item: string) => void
  onBack: () => void
  role: Role
  onRoleChange: (role: Role) => void
  mobileOpen?: boolean
  onCloseMobile?: () => void
}

export default function Sidebar({
  collapsed,
  onToggle,
  activeItem,
  onNavigate,
  onBack,
  role,
  onRoleChange,
  mobileOpen = false,
  onCloseMobile,
}: SidebarProps) {
  const navItems = role === 'doctor' ? doctorNav : studentNav

  return (
    <>
      {/* Mobile scrim */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-40 lg:hidden"
            style={{ background: 'var(--overlay-bg)', backdropFilter: 'blur(4px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCloseMobile}
          />
        )}
      </AnimatePresence>

      <motion.aside
        animate={{
          width: collapsed ? 76 : 252,
          x: 0,
        }}
        initial={false}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className={`flex flex-col overflow-hidden border-r scrollbar-thin fixed lg:relative inset-y-0 left-0 z-50 transition-transform duration-300 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          background: 'var(--surface-0)',
          borderColor: 'var(--border-subtle)',
          minHeight: '100vh',
        }}
      >
        {/* Logo header */}
        <div
          className="flex items-center gap-3 px-4 py-5 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <button
            onClick={onBack}
            className="flex-shrink-0 transition-transform hover:scale-110"
            aria-label="Back to landing"
          >
            <Logo variant="symbol" size="sm" />
          </button>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                className="overflow-hidden"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.2 }}
              >
                <span
                  className="font-bold text-base whitespace-nowrap"
                  style={{
                    fontFamily: 'Orbitron, sans-serif',
                    color: 'var(--foreground)',
                    letterSpacing: '0.04em',
                  }}
                >
                  LearnX
                </span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Mobile close button */}
          <button
            onClick={onCloseMobile}
            className="ml-auto lg:hidden w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ color: 'var(--muted-foreground)' }}
            aria-label="Close menu"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Role switcher (demo/preview convenience — Student workspace vs. Doctor workspace) */}
        <div className="px-3 pt-3">
          {!collapsed ? (
            <div
              className="relative flex rounded-xl p-1 text-xs font-semibold"
              style={{ background: 'var(--muted)' }}
            >
              {(['student', 'doctor'] as Role[]).map((r) => (
                <button
                  key={r}
                  onClick={() => onRoleChange(r)}
                  className="relative flex-1 py-1.5 rounded-lg z-10 transition-colors capitalize"
                  style={{
                    color: role === r ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                  }}
                >
                  {role === r && (
                    <motion.span
                      layoutId="role-pill"
                      className="absolute inset-0 rounded-lg -z-10"
                      style={{ background: 'var(--primary)' }}
                      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                    />
                  )}
                  {r === 'student' ? 'Student' : 'Doctor'}
                </button>
              ))}
            </div>
          ) : (
            <button
              onClick={() => onRoleChange(role === 'student' ? 'doctor' : 'student')}
              className="w-full flex items-center justify-center py-1.5 rounded-lg text-xs font-bold"
              style={{ background: 'var(--muted)', color: 'var(--primary)' }}
              aria-label="Switch role"
            >
              {role === 'student' ? '🎓' : '🩺'}
            </button>
          )}
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto scrollbar-thin">
          {navItems.map((item) => {
            const isActive = activeItem === item.id
            return (
              <button
                key={item.id}
                onClick={() => {
                  onNavigate(item.id)
                  onCloseMobile?.()
                }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 relative group"
                style={{
                  background: isActive ? 'rgba(45,212,191,0.1)' : 'transparent',
                  color: isActive ? 'var(--primary)' : 'var(--muted-foreground)',
                  borderLeft: isActive ? '2px solid var(--primary)' : '2px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'var(--surface-hover)'
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent'
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
                      background:
                        item.badge === 'NEW' ? 'rgba(45,212,191,0.15)' : 'rgba(255,126,54,0.2)',
                      color: item.badge === 'NEW' ? 'var(--primary)' : 'var(--accent)',
                    }}
                  >
                    {item.badge}
                  </span>
                )}

                {/* Tooltip when collapsed */}
                {collapsed && (
                  <div className="surface-tooltip absolute left-full ml-3 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
                    {item.label}
                  </div>
                )}
              </button>
            )
          })}
        </nav>

        {/* Profile snippet + collapse toggle */}
        <div className="p-3 border-t space-y-2" style={{ borderColor: 'var(--border-subtle)' }}>
          {!collapsed && (
            <div
              className="flex items-center gap-2.5 px-1.5 py-1.5 rounded-xl"
              style={{ background: 'var(--surface-hover)' }}
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{
                  background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
                  color: 'var(--primary-foreground)',
                }}
              >
                {role === 'doctor' ? 'DR' : 'AC'}
              </div>
              <div className="min-w-0">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {role === 'doctor' ? 'Dr. Sarah Novak' : 'Alex Chen'}
                </p>
                <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                  {role === 'doctor' ? 'Professor · CS Dept.' : 'Comp Sci · Year 2'}
                </p>
              </div>
            </div>
          )}
          <button
            onClick={onToggle}
            className="hidden lg:flex w-full items-center justify-center p-2.5 rounded-xl transition-all"
            style={{ color: 'var(--muted-foreground)' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <motion.div animate={{ rotate: collapsed ? 180 : 0 }} transition={{ duration: 0.25 }}>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </motion.div>
          </button>
        </div>
      </motion.aside>
    </>
  )
}

import { useState, useEffect, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import IntroAnimation from './components/IntroAnimation'
import LandingPage from './components/landing/LandingPage'
import LoginPage from './components/auth/LoginPage'
import OnboardingFlow from './components/auth/OnboardingFlow'
import GoogleCallbackPage from './components/auth/GoogleCallbackPage'
import DashboardPage from './components/dashboard/DashboardPage'
import { ProfileProvider, useProfile } from './context/ProfileContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import { NotificationsProvider } from './context/NotificationsContext'
import type { AuthUser } from './types/auth'

type View = 'landing' | 'login' | 'onboarding' | 'dashboard'

function dashboardPathFor(role: string): string {
  return role === 'doctor' ? '/doctor/dashboard' : '/student/dashboard'
}

function AppShell() {
  const [introComplete, setIntroComplete] = useState(false)
  const [view, setView] = useState<View>('landing')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [pendingEmail, setPendingEmail] = useState('student@university.edu')
  const { user } = useAuth()
  const { recordDailyActivity } = useProfile()
  const [isGoogleCallback, setIsGoogleCallback] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.location.pathname.startsWith('/auth/callback/google')
  )

  useEffect(() => {
    document.documentElement.className = theme === 'light' ? 'light' : ''
  }, [theme])

  useEffect(() => {
    if (view === 'dashboard') recordDailyActivity()
  }, [view, recordDailyActivity])

  function toggleTheme() {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }

  const handleGoogleAuthenticated = useCallback(() => {
    setIsGoogleCallback(false)
    setIntroComplete(true)
    
    try {
      const savedUserStr = localStorage.getItem('learnx_user')
      const saved = savedUserStr ? JSON.parse(savedUserStr) : null
      const roleStr = saved?.role?.value || saved?.role || user?.role || 'student'
      window.history.replaceState({}, '', dashboardPathFor(roleStr))
    } catch {
      window.history.replaceState({}, '', '/student/dashboard')
    }
    
    setView('dashboard')
  }, [user])

  function handleLogin(emailOrUser?: any) {
    setIntroComplete(true)
    let roleStr = 'student'
    if (typeof emailOrUser === 'string') {
      setPendingEmail(emailOrUser)
    } else if (emailOrUser && typeof emailOrUser === 'object') {
      roleStr = emailOrUser.role?.value || emailOrUser.role || 'student'
    } else if (user?.role) {
      roleStr = user.role
    }
    
    window.history.replaceState({}, '', dashboardPathFor(roleStr))
    setView('dashboard')
  }

  function handleEnter() {
    setIntroComplete(true)
    const roleStr = user?.role || 'student'
    window.history.replaceState({}, '', dashboardPathFor(roleStr))
    setView('dashboard')
  }

  if (isGoogleCallback) {
    return (
      <div style={{ background: 'var(--background)', minHeight: '100vh' }}>
        <GoogleCallbackPage
          onAuthenticated={handleGoogleAuthenticated}
          onDone={handleGoogleAuthenticated}
        />
      </div>
    )
  }

  return (
    <div style={{ background: 'var(--background)', minHeight: '100vh' }}>
      {/* Cinematic intro overlay */}
      <AnimatePresence>
        {!introComplete && (
          <IntroAnimation
            onComplete={() => {
              setIntroComplete(true)
              if (typeof window !== 'undefined' && localStorage.getItem('learnx_user')) {
                try {
                  const saved = JSON.parse(localStorage.getItem('learnx_user')!)
                  const roleStr = saved.role?.value || saved.role || 'student'
                  window.history.replaceState({}, '', dashboardPathFor(roleStr))
                } catch {}
                setView('dashboard')
              }
            }}
          />
        )}
      </AnimatePresence>

      {/* Main views */}
      {introComplete && (
        <AnimatePresence mode="wait">
          {view === 'landing' ? (
            <motion.div
              key="landing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
            >
              <LandingPage
                onEnter={handleEnter}
                onLogin={() => setView('login')}
                theme={theme}
                onToggleTheme={toggleTheme}
              />
            </motion.div>
          ) : view === 'login' ? (
            <motion.div
              key="login"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <LoginPage
                onLogin={handleLogin}
                onBackToLanding={() => setView('landing')}
                theme={theme}
                onToggleTheme={toggleTheme}
              />
            </motion.div>
          ) : view === 'onboarding' ? (
            <motion.div
              key="onboarding"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <OnboardingFlow
                email={pendingEmail}
                onComplete={(savedUser: AuthUser) => {
                  setIntroComplete(true)
                  const targetRole = savedUser.role === 'doctor' ? 'doctor' : 'student'
                  window.history.replaceState({}, '', dashboardPathFor(targetRole))
                  setView('dashboard')
                }}
              />
            </motion.div>
          ) : (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <DashboardPage
                onBack={() => setView('landing')}
                theme={theme}
                onToggleTheme={toggleTheme}
                onLogout={() => {
                  try {
                    localStorage.removeItem('learnx_user')
                    setToken(null)
                  } catch {}
                  window.history.replaceState({}, '', '/')
                  setView('landing')
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ProfileProvider>
        <NotificationsProvider>
          <AppShell />
        </NotificationsProvider>
      </ProfileProvider>
    </AuthProvider>
  )
}

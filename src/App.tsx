import { useState, useEffect, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import IntroAnimation from './components/IntroAnimation'
import LandingPage from './components/landing/LandingPage'
import LoginPage from './components/auth/LoginPage'
import OnboardingFlow from './components/auth/OnboardingFlow'
import GoogleCallbackPage from './components/auth/GoogleCallbackPage'
import DashboardPage from './components/dashboard/DashboardPage'
import { ProfileProvider, useProfile } from './context/ProfileContext'
import { AuthProvider } from './context/AuthContext'
import { NotificationsProvider } from './context/NotificationsContext'

type View = 'landing' | 'login' | 'onboarding' | 'dashboard'

function AppShell() {
  const [introComplete, setIntroComplete] = useState(false)
  const [view, setView] = useState<View>('landing')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [pendingEmail, setPendingEmail] = useState('student@university.edu')
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

  const handleGoogleAuthenticated = useCallback((onboardingComplete: boolean = true) => {
    setIsGoogleCallback(false)
    setIntroComplete(true)
    window.history.replaceState({}, '', '/')
    setView('dashboard')
  }, [])

  function handleLogin(emailOrUser?: any) {
    if (typeof emailOrUser === 'string') {
      setPendingEmail(emailOrUser)
    }
    setIntroComplete(true)
    setView('dashboard')
  }

  function handleEnter() {
    setIntroComplete(true)
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
                onEnter={() => setView('login')}
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
                onAuthenticated={handleLogin}
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
                onComplete={() => {
                  setIntroComplete(true)
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
                    localStorage.removeItem('learnx_access_token')
                  } catch {}
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

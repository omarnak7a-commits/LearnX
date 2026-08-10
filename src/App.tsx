import { useEffect, useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import IntroAnimation from './components/IntroAnimation'
import LandingPage from './components/landing/LandingPage'
import LoginPage from './components/auth/LoginPage'
import ForgotPasswordPage from './components/auth/ForgotPasswordPage'
import ResetPasswordPage from './components/auth/ResetPasswordPage'
import VerifyEmailPage from './components/auth/VerifyEmailPage'
import GoogleCallbackPage from './components/auth/GoogleCallbackPage'
import OnboardingFlow from './components/auth/OnboardingFlow'
import DashboardPage from './components/dashboard/DashboardPage'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ProfileProvider, useProfile } from './context/ProfileContext'
import { NotificationsProvider } from './context/NotificationsContext'
import type { AuthUser } from './types/auth'

type View =
  | 'landing'
  | 'login'
  | 'forgot-password'
  | 'reset-password'
  | 'verify-email'
  | 'google-callback'
  | 'onboarding'
  | 'dashboard'

function dashboardPathFor(role: 'student' | 'doctor'): string {
  return role === 'doctor' ? '/doctor/dashboard' : '/student/dashboard'
}

function parseInitialRoute(): {
  view: View | null
  token: string | null
  code: string | null
  state: string | null
  dashboardIntent: 'student' | 'doctor' | null
} {
  const path = window.location.pathname
  const params = new URLSearchParams(window.location.search)

  if (path === '/reset-password') {
    return { view: 'reset-password', token: params.get('token'), code: null, state: null, dashboardIntent: null }
  }
  if (path === '/verify-email') {
    return { view: 'verify-email', token: params.get('token'), code: null, state: null, dashboardIntent: null }
  }
  if (path.startsWith('/auth/callback/google')) {
    return { view: 'google-callback', token: null, code: params.get('code'), state: params.get('state'), dashboardIntent: null }
  }
  if (path === '/student/dashboard') {
    return { view: null, token: null, code: null, state: null, dashboardIntent: 'student' }
  }
  if (path === '/doctor/dashboard') {
    return { view: null, token: null, code: null, state: null, dashboardIntent: 'doctor' }
  }
  return { view: null, token: null, code: null, state: null, dashboardIntent: null }
}

function AppShell() {
  const initialRoute = useState(() => parseInitialRoute())[0]
  const [introComplete, setIntroComplete] = useState(() => {
    return (
      typeof window !== 'undefined' &&
      (Boolean(initialRoute.view) ||
        window.location.pathname.startsWith('/auth/callback/google') ||
        Boolean(localStorage.getItem('learnx_user')))
    )
  })
  const [view, setView] = useState<View>(() => {
    if (initialRoute.view) return initialRoute.view
    try {
      const savedUserStr = localStorage.getItem('learnx_user')
      if (savedUserStr) {
        const saved = JSON.parse(savedUserStr)
        if (saved && (saved.onboardingComplete || saved.onboarding_complete) && (saved.universityId || saved.university_id)) {
          return 'dashboard'
        }
        return 'onboarding'
      }
    } catch {}
    return 'landing'
  })
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const { user, loading, logout } = useAuth()
  const { loading: profileLoading, recordDailyActivity } = useProfile()

  useEffect(() => {
    document.documentElement.className = theme === 'light' ? 'light' : ''
  }, [theme])

  useEffect(() => {
    if (view === 'dashboard') recordDailyActivity()
  }, [view, recordDailyActivity])

  useEffect(() => {
    if (loading || profileLoading) return
    if (initialRoute.view && initialRoute.view !== 'google-callback') return

    if (!user) {
      if (initialRoute.dashboardIntent || view === 'dashboard' || view === 'onboarding') {
        window.history.replaceState({}, '', '/')
        setView('landing')
      }
      return
    }

    const isOnboarded = Boolean(
      (user.onboardingComplete || (user as any).onboarding_complete) &&
      (user.universityId || (user as any).university_id)
    )

    const correctView: View = isOnboarded ? 'dashboard' : 'onboarding'
    const targetRole = user.role === 'doctor' ? 'doctor' : 'student'
    const correctPath = isOnboarded ? dashboardPathFor(targetRole) : null

    if (initialRoute.dashboardIntent) {
      if (initialRoute.dashboardIntent !== targetRole || !isOnboarded) {
        if (correctPath) window.history.replaceState({}, '', correctPath)
        setView(correctView)
      } else {
        setView('dashboard')
      }
      return
    }

    if (view === 'landing' || view === 'login' || view === 'google-callback') {
      if (correctPath) window.history.replaceState({}, '', correctPath)
      setView(correctView)
    }
  }, [loading, profileLoading, user, initialRoute, view])

  function toggleTheme() {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }

  function goToAppRoute(next: View) {
    window.history.replaceState({}, '', '/')
    setView(next)
  }

  const handleAuthenticated = useCallback((freshUser: AuthUser) => {
    const isOnboarded = Boolean(
      (freshUser.onboardingComplete || (freshUser as any).onboarding_complete) &&
      (freshUser.universityId || (freshUser as any).university_id)
    )
    if (!isOnboarded) {
      goToAppRoute('onboarding')
    } else {
      const targetRole = freshUser.role === 'doctor' ? 'doctor' : 'student'
      window.history.replaceState({}, '', dashboardPathFor(targetRole))
      setView('dashboard')
    }
  }, [])

  const handleOnboardingComplete = useCallback((freshUser: AuthUser) => {
    const targetRole = freshUser.role === 'doctor' ? 'doctor' : 'student'
    window.history.replaceState({}, '', dashboardPathFor(targetRole))
    setView('dashboard')
  }, [])

  async function handleLogout() {
    await logout()
    goToAppRoute('landing')
  }

  return (
    <div style={{ background: 'var(--background)', minHeight: '100vh' }}>
      <AnimatePresence>
        {!introComplete && <IntroAnimation onComplete={() => setIntroComplete(true)} />}
      </AnimatePresence>

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
                onAuthenticated={handleAuthenticated}
                onForgotPassword={() => setView('forgot-password')}
                onBackToLanding={() => setView('landing')}
                theme={theme}
                onToggleTheme={toggleTheme}
              />
            </motion.div>
          ) : view === 'forgot-password' ? (
            <motion.div
              key="forgot"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <ForgotPasswordPage onBackToLogin={() => setView('login')} />
            </motion.div>
          ) : view === 'reset-password' ? (
            <motion.div
              key="reset"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <ResetPasswordPage
                token={initialRoute.token ?? ''}
                onBackToLogin={() => goToAppRoute('login')}
              />
            </motion.div>
          ) : view === 'verify-email' ? (
            <motion.div
              key="verify"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <VerifyEmailPage
                token={initialRoute.token}
                onContinue={() => {
                  if (user) handleAuthenticated(user)
                  else goToAppRoute('login')
                }}
              />
            </motion.div>
          ) : view === 'google-callback' ? (
            <motion.div
              key="google"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <GoogleCallbackPage
                code={initialRoute.code}
                state={initialRoute.state}
                onAuthenticated={(isOnboarded) => {
                  if (isOnboarded) setView('dashboard')
                  else setView('onboarding')
                }}
                onDone={handleAuthenticated}
                onCancel={() => goToAppRoute('login')}
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
              <OnboardingFlow onComplete={handleOnboardingComplete} />
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
                onLogout={handleLogout}
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

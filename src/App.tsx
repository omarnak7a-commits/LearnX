import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import IntroAnimation from './components/IntroAnimation'
import LandingPage from './components/landing/LandingPage'
import LoginPage from './components/auth/LoginPage'
import DashboardPage from './components/dashboard/DashboardPage'

type View = 'landing' | 'login' | 'dashboard'

export default function App() {
  const [introComplete, setIntroComplete] = useState(false)
  const [view, setView] = useState<View>('landing')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')

  useEffect(() => {
    document.documentElement.className = theme === 'light' ? 'light' : ''
  }, [theme])

  function toggleTheme() {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }

  return (
    <div style={{ background: 'var(--background)', minHeight: '100vh' }}>
      {/* Cinematic intro overlay — AnimatePresence lets it fade out while
          the landing page mounts underneath, avoiding a hard cut. */}
      <AnimatePresence>
        {!introComplete && (
          <IntroAnimation onComplete={() => setIntroComplete(true)} />
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
                onEnter={() => setView('dashboard')}
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
                onLogin={() => setView('dashboard')}
                onBackToLanding={() => setView('landing')}
                theme={theme}
                onToggleTheme={toggleTheme}
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
              />
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  )
}


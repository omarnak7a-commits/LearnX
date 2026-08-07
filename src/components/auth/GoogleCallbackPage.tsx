/**
 * GoogleCallbackPage — receives the JWT from the backend after the
 * Google OAuth Authorization Code Flow completes.
 *
 * The backend redirects to:
 *   {APP_BASE_URL}/auth/callback/google?token=<jwt>
 *
 * This page (mounted at that route in the SPA) extracts the token,
 * finishes the session and forwards the user into the app.
 */

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import Logo from '../ui/Logo'
import { useAuth } from '../../context/AuthContext'

interface GoogleCallbackPageProps {
  onAuthenticated: (onboardingComplete: boolean) => void
}

export default function GoogleCallbackPage({ onAuthenticated }: GoogleCallbackPageProps) {
  const { completeGoogleAuth } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const token = useMemo(() => new URLSearchParams(window.location.search).get('token'), [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!token) {
        setError('Missing authentication token.')
        return
      }
      try {
        const user = await completeGoogleAuth(token)
        if (cancelled) return
        if (user) {
          // Clean the token out of the URL bar.
          window.history.replaceState({}, document.title, window.location.pathname)
          onAuthenticated(user.onboarding_complete)
        } else {
          setError('Google sign-in failed.')
        }
      } catch {
        if (!cancelled) setError('Google sign-in failed. Please try again.')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, completeGoogleAuth, onAuthenticated])

  return (
    <div
      className="relative min-h-screen flex items-center justify-center px-6"
      style={{ background: 'var(--section-dark)' }}
    >
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <motion.div
        className="glass-card w-full max-w-sm p-8 relative z-10 flex flex-col items-center text-center"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Logo variant="symbol" size="lg" className="mb-4" />
        {error ? (
          <>
            <h1 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>
              Sign-in issue
            </h1>
            <p className="text-sm mt-2" style={{ color: 'var(--muted-foreground)' }}>
              {error}
            </p>
            <a
              href="/"
              className="mt-6 px-5 py-2.5 rounded-xl text-sm font-bold"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Back to LearnX
            </a>
          </>
        ) : (
          <>
            <h1 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>
              Signing you in…
            </h1>
            <p className="text-sm mt-2" style={{ color: 'var(--muted-foreground)' }}>
              Connecting your Google account.
            </p>
            <div className="mt-6 w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent' }} />
          </>
        )}
      </motion.div>
    </div>
  )
}

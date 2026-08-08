import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import Logo from '../ui/Logo'
import RoleSelectCards from './RoleSelectCards'
import { useAuth } from '../../context/AuthContext'
import { apiCompleteGoogleSignup, apiExchangeGoogleCode } from '../../lib/auth/apiClient'
import type { AuthUser, UserRole } from '../../types/auth'
import { describeError } from './LoginPage'

interface GoogleCallbackPageProps {
  code: string | null
  state: string | null
  onDone: (user: AuthUser) => void
  onCancel: () => void
}

export default function GoogleCallbackPage({
  code,
  state,
  onDone,
  onCancel,
}: GoogleCallbackPageProps) {
  const { setUserFromAuthResponse } = useAuth()
  const [status, setStatus] = useState<'exchanging' | 'needs-role' | 'error'>('exchanging')
  const [error, setError] = useState<string | null>(null)
  const [pendingToken, setPendingToken] = useState<string | null>(null)
  const [role, setRole] = useState<UserRole | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authCode = code || params.get('code')
    const authState = state || params.get('state')

    if (!authCode || !authState) {
      setStatus('error')
      setError('Missing Google authorization details. Please try signing in again.')
      return
    }

    ;(async () => {
      try {
        const outcome = await apiExchangeGoogleCode({ code: authCode, state: authState })
        if (outcome.status === 'authenticated') {
          setUserFromAuthResponse(outcome.user)
          onDone(outcome.user)
        } else {
          setPendingToken(outcome.pendingToken)
          setStatus('needs-role')
        }
      } catch (err) {
        setStatus('error')
        setError(describeError(err))
      }
    })()
  }, [code, state, onDone, setUserFromAuthResponse])

  async function handleCompleteSignup() {
    if (!role || !pendingToken) return
    setSubmitting(true)
    try {
      const result = await apiCompleteGoogleSignup({ pendingToken, role })
      setUserFromAuthResponse(result.user)
      onDone(result.user)
    } catch (err) {
      setStatus('error')
      setError(describeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="relative min-h-screen flex items-center justify-center px-6 py-12 overflow-hidden"
      style={{ background: 'var(--section-dark)' }}
    >
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <div className="absolute top-6 inset-x-0 px-6 flex items-center justify-center">
        <Logo variant="full" size="sm" />
      </div>

      <motion.div
        className={`glass-card w-full p-8 relative z-10 text-center transition-[max-width] duration-300 ${
          status === 'needs-role' ? 'max-w-xl' : 'max-w-md'
        }`}
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <Logo variant="symbol" size="lg" className="mb-4 mx-auto" />

        {status === 'exchanging' && (
          <>
            <div
              className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin mx-auto mb-4"
              style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent' }}
            />
            <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
              Completing sign-in with Google…
            </p>
          </>
        )}

        {status === 'needs-role' && (
          <div className="text-left">
            <h1
              className="text-lg font-bold mb-1 text-center"
              style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
            >
              How will you use LearnX?
            </h1>
            <p className="text-xs mb-5 text-center" style={{ color: 'var(--muted-foreground)' }}>
              Choose your account type to finish creating your LearnX account.
            </p>
            <RoleSelectCards value={role} onChange={setRole} showFeatures />
            <motion.button
              onClick={handleCompleteSignup}
              disabled={!role || submitting}
              className="w-full py-3 rounded-xl text-sm font-bold mt-5"
              style={{
                background: 'var(--primary)',
                color: 'var(--primary-foreground)',
                opacity: !role || submitting ? 0.5 : 1,
              }}
              whileHover={!role || submitting ? undefined : { scale: 1.02 }}
              whileTap={!role || submitting ? undefined : { scale: 0.98 }}
            >
              {submitting ? 'Creating account…' : 'Continue'}
            </motion.button>
          </div>
        )}

        {status === 'error' && (
          <>
            <div
              className="w-14 h-14 rounded-full mx-auto flex items-center justify-center text-2xl mb-4"
              style={{ background: 'var(--danger-soft)' }}
            >
              ⚠️
            </div>
            <h1
              className="text-lg font-bold mb-1"
              style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
            >
              Google sign-in failed
            </h1>
            <p className="text-xs mb-6" style={{ color: 'var(--muted-foreground)' }}>
              {error}
            </p>
            <button
              onClick={onCancel}
              className="w-full py-3 rounded-xl text-sm font-bold"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Back to sign in
            </button>
          </>
        )}
      </motion.div>
    </div>
  )
}

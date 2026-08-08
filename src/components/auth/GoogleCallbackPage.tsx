import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { apiCompleteGoogleSignup, apiExchangeGoogleCode } from '../../lib/auth/apiClient'
import type { AuthUser, UserRole } from '../../types/auth'

interface GoogleCallbackPageProps {
  code: string | null
  state: string | null
  onDone: (user: AuthUser) => void
  onCancel: () => void
}

function describeError(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'An error occurred during Google authentication. Please try again.'
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
      style={{ background: 'var(--section-dark, #0A0D14)' }}
    >
      <div className="glass-card w-full max-w-md p-8 relative z-10 text-center rounded-2xl border border-white/10 bg-slate-900/80 shadow-2xl">
        <div className="w-12 h-12 rounded-xl bg-teal-500/20 text-teal-400 flex items-center justify-center text-xl font-bold mx-auto mb-4 border border-teal-500/30">
          LX
        </div>

        {status === 'exchanging' && (
          <div>
            <div className="w-10 h-10 rounded-full border-2 border-teal-400 border-t-transparent animate-spin mx-auto mb-4" />
            <h2 className="text-lg font-bold text-white mb-1">Connecting to Google...</h2>
            <p className="text-xs text-slate-400">Authenticating your LearnX account.</p>
          </div>
        )}

        {status === 'needs-role' && (
          <div className="text-left">
            <h2 className="text-lg font-bold text-white text-center mb-1">Choose Account Type</h2>
            <p className="text-xs text-slate-400 text-center mb-6">How will you be using LearnX?</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
              <button
                type="button"
                onClick={() => setRole('student')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  role === 'student'
                    ? 'border-teal-400 bg-teal-500/10 shadow-lg shadow-teal-500/10'
                    : 'border-white/10 bg-slate-800/50 hover:border-white/20'
                }`}
              >
                <div className="text-2xl mb-1">🎓</div>
                <div className="font-bold text-white text-sm">Student</div>
                <div className="text-xs text-slate-400 mt-1">Study, take quizzes & track progress</div>
              </button>

              <button
                type="button"
                onClick={() => setRole('doctor')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  role === 'doctor'
                    ? 'border-teal-400 bg-teal-500/10 shadow-lg shadow-teal-500/10'
                    : 'border-white/10 bg-slate-800/50 hover:border-white/20'
                }`}
              >
                <div className="text-2xl mb-1">👨‍🏫</div>
                <div className="font-bold text-white text-sm">Doctor</div>
                <div className="text-xs text-slate-400 mt-1">Create courses & manage lectures</div>
              </button>
            </div>

            <button
              onClick={handleCompleteSignup}
              disabled={!role || submitting}
              className="w-full py-3 rounded-xl text-sm font-bold bg-teal-400 text-slate-950 disabled:opacity-50 hover:bg-teal-300 transition-all"
            >
              {submitting ? 'Creating account...' : 'Continue to LearnX'}
            </button>
          </div>
        )}

        {status === 'error' && (
          <div>
            <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center text-xl mx-auto mb-3">
              ⚠️
            </div>
            <h2 className="text-lg font-bold text-white mb-1">Google Sign-in Issue</h2>
            <p className="text-xs text-slate-400 mb-6">{error}</p>
            <button
              onClick={onCancel}
              className="w-full py-3 rounded-xl text-sm font-bold bg-teal-400 text-slate-950 hover:bg-teal-300 transition-all"
            >
              Back to Sign In
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

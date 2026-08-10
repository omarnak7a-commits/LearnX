import { useEffect, useState } from 'react'

interface GoogleCallbackPageProps {
  code?: string | null
  state?: string | null
  onAuthenticated?: (onboardingComplete: boolean) => void
  onDone?: (user: any) => void
  onCancel?: () => void
}

export default function GoogleCallbackPage({
  code,
  state,
  onAuthenticated,
  onCancel,
}: GoogleCallbackPageProps) {
  const [status, setStatus] = useState<'exchanging' | 'error'>('exchanging')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authCode = code || params.get('code')
    const authState = state || params.get('state')

    if (!authCode) {
      setStatus('error')
      setError('Missing Google authorization details. Please try signing in again.')
      return
    }

    ;(async () => {
      try {
        let res = await fetch('/api/v1/auth/google/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ code: authCode, state: authState }),
        })

        if (res.status === 404 || res.status === 405) {
          res = await fetch('/api/v1/auth/google', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ code: authCode, state: authState }),
          })
        }

        const text = await res.text()
        let data: any = {}
        try {
          data = JSON.parse(text)
        } catch {
          throw new Error(`Server returned: ${text.substring(0, 100)}`)
        }

        if (!res.ok) {
          throw new Error(data.detail || data.message || 'Google sign-in exchange failed')
        }

        const rawUser = data.user || data
        const isAlreadyOnboarded = Boolean(
          (rawUser.onboardingComplete || rawUser.onboarding_complete) &&
          (rawUser.universityId || rawUser.university_id)
        )

        const authUser = {
          ...rawUser,
          role: rawUser.role?.value || rawUser.role || 'student',
          onboardingComplete: isAlreadyOnboarded,
        }

        try {
          localStorage.setItem('learnx_user', JSON.stringify(authUser))
          if (data.access_token) localStorage.setItem('learnx_access_token', data.access_token)
        } catch {}

        if (typeof onAuthenticated === 'function') {
          onAuthenticated(isAlreadyOnboarded)
          return
        }

        if (isAlreadyOnboarded) {
          window.location.href = authUser.role === 'doctor' ? '/doctor/dashboard' : '/student/dashboard'
        } else {
          window.location.href = '/'
        }
      } catch (err) {
        setStatus('error')
        setError(err instanceof Error ? err.message : 'Google authentication failed.')
      }
    })()
  }, [code, state, onAuthenticated])

  function handleCancelClick() {
    if (typeof onCancel === 'function') {
      try { onCancel(); return; } catch {}
    }
    window.location.href = '/'
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

        {status === 'error' && (
          <div>
            <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center text-xl mx-auto mb-3">
              ⚠️
            </div>
            <h2 className="text-lg font-bold text-white mb-1">Google Sign-in Issue</h2>
            <p className="text-xs text-slate-400 mb-6">{error}</p>
            <button
              onClick={handleCancelClick}
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

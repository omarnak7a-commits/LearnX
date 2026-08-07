import { useState } from 'react'
import { motion } from 'framer-motion'
import Logo from '../ui/Logo'
import { login as apiLogin, register as apiRegister, forgotPassword } from '../../lib/auth/apiClient'

interface LoginPageProps {
  onLogin: (email: string) => void
  onBackToLanding: () => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

/**
 * LearnX authentication screen. Same visual language as the rest of the
 * marketing site (glass-card, gradient text, grid background, spring
 * transitions) — the full wordmark is used here per brand guidance for
 * marketing-adjacent surfaces.
 */
export default function LoginPage({
  onLogin,
  onBackToLanding,
  theme,
  onToggleTheme,
}: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      if (mode === 'signin') {
        await apiLogin(email.trim(), password)
      } else {
        const resp = await apiRegister({
          email: email.trim(),
          password,
          full_name: fullName.trim() || email.trim().split('@')[0],
        })
        if (resp.requires_email_verification) {
          setNotice('Account created! Check your inbox to verify your email.')
        }
      }
      onLogin(email.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleForgotPassword() {
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError('Enter your email address first.')
      return
    }
    setError(null)
    try {
      await forgotPassword(email.trim())
      setNotice('Password reset link sent — check your inbox.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send reset link.')
    }
  }

  function handleGoogle() {
    window.location.href = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1/auth/google`
  }

  return (
    <div
      className="relative min-h-screen flex items-center justify-center px-6 py-12 overflow-hidden"
      style={{ background: 'var(--section-dark)' }}
    >
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <div
        className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none"
        style={{
          background:
            'radial-gradient(circle at 70% 30%, rgba(45,212,191,0.08) 0%, transparent 65%)',
        }}
      />

      {/* Top bar: logo + theme toggle */}
      <div className="absolute top-6 inset-x-0 px-6 flex items-center justify-between">
        <button onClick={onBackToLanding} aria-label="Back to landing">
          <Logo variant="full" size="sm" />
        </button>
        <button
          onClick={onToggleTheme}
          className="w-9 h-9 rounded-xl flex items-center justify-center input-field"
          style={{ color: 'var(--muted-foreground)' }}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          ) : (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
      </div>

      <motion.div
        className="glass-card w-full max-w-md p-8 relative z-10"
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="flex flex-col items-center mb-8">
          <Logo variant="symbol" size="lg" className="mb-4" />
          <h1
            className="text-xl font-bold"
            style={{
              fontFamily: 'Orbitron, sans-serif',
              color: 'var(--foreground)',
              letterSpacing: '-0.01em',
            }}
          >
            {mode === 'signin' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="text-xs mt-1.5 text-center" style={{ color: 'var(--muted-foreground)' }}>
            {mode === 'signin'
              ? 'Sign in to continue to your workspace'
              : 'Less stress. More success. Start free.'}
          </p>
        </div>

        {/* Mode switch */}
        <div
          className="flex items-center gap-1 p-1 rounded-xl mb-6"
          style={{ background: 'var(--muted)' }}
        >
          {(['signin', 'signup'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className="relative flex-1 py-2 rounded-lg text-xs font-semibold transition-colors z-0"
              style={{
                color: mode === m ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              {mode === m && (
                <motion.span
                  layoutId="auth-mode-pill"
                  className="absolute inset-0 rounded-lg -z-10"
                  style={{ background: 'var(--primary)' }}
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                />
              )}
              {m === 'signin' ? 'Sign in' : 'Sign up'}
            </button>
          ))}
        </div>

        {error && (
          <div
            className="mb-4 px-4 py-2.5 rounded-xl text-xs font-medium"
            style={{ background: 'rgba(248,113,113,0.12)', color: '#f87171', border: '1px solid rgba(248,113,113,0.3)' }}
          >
            {error}
          </div>
        )}
        {notice && (
          <div
            className="mb-4 px-4 py-2.5 rounded-xl text-xs font-medium"
            style={{ background: 'rgba(45,212,191,0.12)', color: '#2DD4BF', border: '1px solid rgba(45,212,191,0.3)' }}
          >
            {notice}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              className="text-xs font-medium mb-1.5 block"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@university.edu"
              className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
            />
          </div>
          {mode === 'signup' && (
            <div>
              <label
                className="text-xs font-medium mb-1.5 block"
                style={{ color: 'var(--muted-foreground)' }}
              >
                Full name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Alex Chen"
                className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
              />
            </div>
          )}
          <div>
            <label
              className="text-xs font-medium mb-1.5 block"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
            />
          </div>

          {mode === 'signin' && (
            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleForgotPassword}
                className="text-xs hover:underline"
                style={{ color: 'var(--muted-foreground)' }}
              >
                Forgot password?
              </button>
            </div>
          )}

          <motion.button
            type="submit"
            disabled={busy}
            className="w-full py-3 rounded-xl text-sm font-bold mt-2 disabled:opacity-60"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            whileHover={{ scale: 1.02, boxShadow: '0 0 32px rgba(45,212,191,0.4)' }}
            whileTap={{ scale: 0.98 }}
          >
            {busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </motion.button>
        </form>

        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px" style={{ background: 'var(--border-subtle)' }} />
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            or continue with
          </span>
          <div className="flex-1 h-px" style={{ background: 'var(--border-subtle)' }} />
        </div>

        <div className="grid grid-cols-1 gap-3">
          <button
            type="button"
            onClick={handleGoogle}
            className="flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium input-field"
          >
            <span>🔵</span> Continue with Google
          </button>
        </div>
      </motion.div>
    </div>
  )
}

import { useState } from 'react'
import { motion } from 'framer-motion'
import Logo from '../ui/Logo'

interface LoginPageProps {
  onLogin: () => void
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
export default function LoginPage({ onLogin, onBackToLanding, theme, onToggleTheme }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onLogin()
  }

  return (
    <div
      className="relative min-h-screen flex items-center justify-center px-6 py-12 overflow-hidden"
      style={{ background: 'var(--section-dark)' }}
    >
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <div
        className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none"
        style={{ background: 'radial-gradient(circle at 70% 30%, rgba(45,212,191,0.08) 0%, transparent 65%)' }}
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
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
            style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)', letterSpacing: '-0.01em' }}
          >
            {mode === 'signin' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="text-xs mt-1.5 text-center" style={{ color: 'var(--muted-foreground)' }}>
            {mode === 'signin' ? 'Sign in to continue to your workspace' : 'Less stress. More success. Start free.'}
          </p>
        </div>

        {/* Mode switch */}
        <div className="flex items-center gap-1 p-1 rounded-xl mb-6" style={{ background: 'var(--muted)' }}>
          {(['signin', 'signup'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className="relative flex-1 py-2 rounded-lg text-xs font-semibold transition-colors z-0"
              style={{ color: mode === m ? 'var(--primary-foreground)' : 'var(--muted-foreground)' }}
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

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-medium mb-1.5 block" style={{ color: 'var(--muted-foreground)' }}>
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
          <div>
            <label className="text-xs font-medium mb-1.5 block" style={{ color: 'var(--muted-foreground)' }}>
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
            />
          </div>

          <motion.button
            type="submit"
            className="w-full py-3 rounded-xl text-sm font-bold mt-2"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            whileHover={{ scale: 1.02, boxShadow: '0 0 32px rgba(45,212,191,0.4)' }}
            whileTap={{ scale: 0.98 }}
          >
            {mode === 'signin' ? 'Sign in' : 'Create account'}
          </motion.button>
        </form>

        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px" style={{ background: 'var(--border-subtle)' }} />
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            or continue with
          </span>
          <div className="flex-1 h-px" style={{ background: 'var(--border-subtle)' }} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            className="flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium input-field"
          >
            <span>🔵</span> Google
          </button>
          <button
            type="button"
            className="flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium input-field"
          >
            <span>🍎</span> Apple
          </button>
        </div>
      </motion.div>
    </div>
  )
}

import { useState } from 'react'
import { motion } from 'framer-motion'
import Logo from '../ui/Logo'

const cols = {
  Product: ['Features', 'Pricing', 'Changelog', 'Roadmap'],
  Company: ['About', 'Blog', 'Careers', 'Press'],
  Support: ['Help Center', 'Discord', 'Status', 'Contact'],
}

const socials = [
  {
    name: 'X',
    path: 'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.258 5.63 5.906-5.63Zm-1.161 17.52h1.833L7.084 4.126H5.117z',
  },
  {
    name: 'GitHub',
    path: 'M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z',
  },
  {
    name: 'Discord',
    path: 'M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057c.002.022.015.043.03.056a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z',
  },
]

export default function Footer() {
  const [email, setEmail] = useState('')
  const [subscribed, setSubscribed] = useState(false)

  return (
    <footer
      style={{
        background: 'var(--section-deep)',
        borderTop: '1px solid var(--border-subtle)',
      }}
    >
      {/* Large tagline row */}
      <div className="max-w-7xl mx-auto px-8 pt-20 pb-10">
        <div
          className="flex flex-col md:flex-row items-start md:items-end justify-between gap-8 pb-16 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <div className="mb-5">
              <Logo variant="full" size="md" />
            </div>
            <p
              className="text-3xl md:text-4xl font-light leading-snug max-w-lg"
              style={{ color: 'var(--foreground)', letterSpacing: '-0.02em' }}
            >
              Less stress.{' '}
              <span className="text-gradient" style={{ fontWeight: 700 }}>
                More success.
              </span>
            </p>
          </div>

          {/* Newsletter */}
          <div className="min-w-[280px]">
            <p className="text-sm font-medium mb-3" style={{ color: 'var(--foreground)' }}>
              Stay updated
            </p>
            {subscribed ? (
              <motion.p
                className="text-sm"
                style={{ color: 'var(--primary)' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                ✓ You're on the list.
              </motion.p>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  if (email) setSubscribed(true)
                }}
                className="flex gap-2"
              >
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="flex-1 px-3 py-2 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--border)',
                    color: 'var(--foreground)',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'rgba(45,212,191,0.35)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                  required
                />
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
                  style={{
                    background: 'var(--primary)',
                    color: 'var(--primary-foreground)',
                  }}
                >
                  Join
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Links + copyright */}
        <div className="flex flex-col md:flex-row gap-12 pt-10 pb-4">
          {/* Link columns */}
          <div className="flex gap-12 flex-wrap">
            {Object.entries(cols).map(([group, items]) => (
              <div key={group}>
                <p
                  className="text-xs tracking-[0.2em] uppercase mb-4"
                  style={{
                    color: 'var(--primary)',
                    fontFamily: 'JetBrains Mono, monospace',
                  }}
                >
                  {group}
                </p>
                <ul className="space-y-2.5">
                  {items.map((item) => (
                    <li key={item}>
                      <a
                        href="#"
                        className="text-sm transition-colors duration-200"
                        style={{ color: 'var(--muted-foreground)' }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--foreground)')}
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.color = 'var(--muted-foreground)')
                        }
                      >
                        {item}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div
          className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-8 border-t"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            © 2026 LearnX Technologies Inc. All rights reserved.
          </p>

          <div className="flex items-center gap-3">
            {socials.map((s) => (
              <a
                key={s.name}
                href="#"
                aria-label={s.name}
                className="w-7 h-7 rounded-lg flex items-center justify-center transition-all hover:scale-110"
                style={{ color: 'var(--muted-foreground)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted-foreground)')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d={s.path} />
                </svg>
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}

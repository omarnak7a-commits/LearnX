import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Logo from '../ui/Logo'

interface NavbarProps {
  onEnter: () => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

const links = ['Features', 'Roles', 'Pricing', 'Analytics']

export default function Navbar({ onEnter, theme, onToggleTheme }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 48)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  return (
    <>
      <motion.nav
        className="fixed top-0 inset-x-0 z-50 px-6 py-4"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div
          className="max-w-7xl mx-auto flex items-center justify-between transition-all duration-500"
          style={
            scrolled
              ? {
                  background: 'var(--header-bg)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  borderRadius: 20,
                  border: '1px solid var(--border)',
                  padding: '10px 24px',
                  boxShadow: 'var(--shadow-md)',
                }
              : { padding: '4px 0' }
          }
        >
          {/* Logo */}
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="group py-1"
            aria-label="LearnX — back to top"
          >
            <Logo variant="full" size="md" />
          </button>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-1">
            {links.map((link) => (
              <a
                key={link}
                href={`#${link.toLowerCase()}`}
                className="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                style={{ color: 'var(--muted-foreground)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--foreground)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted-foreground)')}
              >
                {link}
              </a>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={onToggleTheme}
              className="hidden sm:flex w-8 h-8 items-center justify-center rounded-lg transition-all hover:scale-110"
              style={{ color: 'var(--muted-foreground)' }}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                >
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              ) : (
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                >
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>

            <motion.button
              onClick={onEnter}
              className="hidden md:flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium transition-all"
              style={{
                background: 'rgba(45,212,191,0.1)',
                border: '1px solid rgba(45,212,191,0.22)',
                color: 'var(--primary)',
              }}
              whileHover={{
                background: 'rgba(45,212,191,1)',
                color: '#050709',
                scale: 1.03,
              }}
              whileTap={{ scale: 0.97 }}
            >
              Try free
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </motion.button>

            {/* Hamburger */}
            <button
              className="md:hidden flex flex-col justify-center items-center w-8 h-8 gap-1"
              onClick={() => setMobileOpen((v) => !v)}
            >
              <motion.span
                className="block w-5 h-0.5 rounded-full"
                style={{ background: 'var(--foreground)' }}
                animate={{ rotate: mobileOpen ? 45 : 0, y: mobileOpen ? 5 : 0 }}
              />
              <motion.span
                className="block w-5 h-0.5 rounded-full"
                style={{ background: 'var(--foreground)' }}
                animate={{ opacity: mobileOpen ? 0 : 1 }}
              />
              <motion.span
                className="block w-5 h-0.5 rounded-full"
                style={{ background: 'var(--foreground)' }}
                animate={{
                  rotate: mobileOpen ? -45 : 0,
                  y: mobileOpen ? -5 : 0,
                }}
              />
            </button>
          </div>
        </div>
      </motion.nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-40 flex flex-col items-center justify-center"
            style={{
              background: 'var(--overlay-bg)',
              backdropFilter: 'blur(24px)',
            }}
            initial={{ opacity: 0, clipPath: 'inset(0 0 100% 0)' }}
            animate={{ opacity: 1, clipPath: 'inset(0 0 0% 0)' }}
            exit={{ opacity: 0, clipPath: 'inset(0 0 100% 0)' }}
            transition={{ duration: 0.4, ease: [0.76, 0, 0.24, 1] }}
          >
            <nav className="flex flex-col items-center gap-8">
              {links.map((link, i) => (
                <motion.a
                  key={link}
                  href={`#${link.toLowerCase()}`}
                  className="text-3xl font-light tracking-wide"
                  style={{ color: 'var(--foreground)' }}
                  onClick={() => setMobileOpen(false)}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    delay: 0.1 + i * 0.07,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                >
                  {link}
                </motion.a>
              ))}
              <motion.button
                onClick={() => {
                  setMobileOpen(false)
                  onEnter()
                }}
                className="mt-6 px-8 py-3 rounded-full text-base font-semibold"
                style={{
                  background: 'var(--primary)',
                  color: 'var(--primary-foreground)',
                }}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                Try LearnX Free
              </motion.button>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

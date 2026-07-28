import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import logoLockupLightInk from '../assets/brand/logo-lockup-light-ink.png'

interface IntroAnimationProps {
  onComplete: () => void
}

/**
 * Native pixel dimensions of the official lockup crop (icon + "LearnX"
 * wordmark, cropped directly from src/imports/logo2.png — the official
 * dark-background brand asset — with the tagline row removed so it can be
 * animated in separately). Used to reserve layout space up front so the
 * logo never shifts or pops in late.
 */
const LOGO_WIDTH = 943
const LOGO_HEIGHT = 169

export default function IntroAnimation({ onComplete }: IntroAnimationProps) {
  const [phase, setPhase] = useState<'converge' | 'reveal' | 'glow' | 'exit'>('converge')
  const [showShockwave, setShowShockwave] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('reveal'), 900)
    const t2 = setTimeout(() => setShowShockwave(true), 1100)
    const t3 = setTimeout(() => setPhase('glow'), 1500)
    const t4 = setTimeout(() => setPhase('exit'), 2200)
    const t5 = setTimeout(() => onComplete(), 3000)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(t3)
      clearTimeout(t4)
      clearTimeout(t5)
    }
  }, [onComplete])

  return (
    <AnimatePresence>
      {phase !== 'exit' ? (
        <motion.div
          key="intro"
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black"
          exit={{ scale: 1.08, opacity: 0 }}
          transition={{ duration: 0.8, ease: [0.76, 0, 0.24, 1] }}
        >
          {/* Subtle grid */}
          <div className="absolute inset-0 bg-grid opacity-30" />

          {/* Soft ambient particles */}
          {[...Array(12)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-teal-400/30"
              style={{
                left: `${10 + i * 7.5}%`,
                top: `${15 + (i % 5) * 18}%`,
              }}
              animate={{ y: [-6, 6, -6], opacity: [0.2, 0.6, 0.2] }}
              transition={{ duration: 3 + i * 0.4, repeat: Infinity, ease: 'easeInOut', delay: i * 0.3 }}
            />
          ))}

          {/* Small glowing fragments converging toward the center */}
          {phase === 'converge' &&
            [...Array(8)].map((_, i) => {
              const angle = (i / 8) * Math.PI * 2
              const distance = 140
              return (
                <motion.div
                  key={`fragment-${i}`}
                  className="absolute w-1.5 h-1.5 rounded-full"
                  style={{ background: '#10E5C9' }}
                  initial={{
                    x: Math.cos(angle) * distance,
                    y: Math.sin(angle) * distance,
                    opacity: 0,
                    scale: 1.4,
                  }}
                  animate={{ x: 0, y: 0, opacity: [0, 0.9, 0], scale: 0.4 }}
                  transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: i * 0.03 }}
                />
              )
            })}

          {/* Shockwave ring */}
          {showShockwave && (
            <motion.div
              className="absolute rounded-full border border-teal-400/60"
              style={{ width: 120, height: 120 }}
              animate={{ scale: [1, 10], opacity: [0.7, 0] }}
              transition={{ duration: 1.2, ease: 'easeOut' }}
            />
          )}
          {showShockwave && (
            <motion.div
              className="absolute rounded-full border border-teal-300/30"
              style={{ width: 80, height: 80 }}
              animate={{ scale: [1, 14], opacity: [0.5, 0] }}
              transition={{ duration: 1.5, ease: 'easeOut', delay: 0.1 }}
            />
          )}

          {/* Official LearnX logo — exact brand asset, never redrawn */}
          <div className="relative flex flex-col items-center gap-6 px-6">
            <div
              className="relative flex items-center justify-center"
              style={{
                width: 'clamp(200px, 45vw, 480px)',
                aspectRatio: `${LOGO_WIDTH} / ${LOGO_HEIGHT}`,
              }}
            >
              {/* Subtle glow behind the logo — soft, not neon */}
              <motion.div
                className="absolute inset-0 -z-10 rounded-full"
                style={{
                  background: 'radial-gradient(ellipse 65% 65% at center, rgba(16,229,201,0.35), transparent 70%)',
                  filter: 'blur(28px)',
                }}
                initial={{ opacity: 0 }}
                animate={{
                  opacity: phase === 'reveal' ? 0.5 : phase === 'glow' ? [0.4, 0.65, 0.4] : 0,
                }}
                transition={{ duration: 2.4, ease: 'easeInOut', repeat: phase === 'glow' ? Infinity : 0 }}
              />

              <motion.img
                src={logoLockupLightInk}
                alt="LearnX"
                width={LOGO_WIDTH}
                height={LOGO_HEIGHT}
                className="relative h-full w-full object-contain"
                draggable={false}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={phase === 'converge' ? { opacity: 0, scale: 0.95 } : { opacity: 1, scale: 1 }}
                transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>

            {/* Tagline */}
            <motion.span
              className="text-sm text-teal-300/70 tracking-[0.3em] uppercase text-center"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: phase !== 'converge' ? 1 : 0, y: phase !== 'converge' ? 0 : 10 }}
              transition={{ delay: 0.5, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              Less Stress · More Success
            </motion.span>
          </div>
        </motion.div>
      ) : (
        <motion.div
          key="exit-overlay"
          className="fixed inset-0 z-[9998] bg-black"
          initial={{ opacity: 1 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 0.8, ease: 'easeInOut' }}
        />
      )}
    </AnimatePresence>
  )
}

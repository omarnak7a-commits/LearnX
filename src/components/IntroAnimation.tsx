import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import LogoMark from './ui/LogoMark'

interface IntroAnimationProps {
  onComplete: () => void
}

export default function IntroAnimation({ onComplete }: IntroAnimationProps) {
  const [phase, setPhase] = useState<'draw' | 'glow' | 'exit'>('draw')
  const [showShockwave, setShowShockwave] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('glow'), 1200)
    const t2 = setTimeout(() => setShowShockwave(true), 1600)
    const t3 = setTimeout(() => setPhase('exit'), 2200)
    const t4 = setTimeout(() => onComplete(), 3000)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4) }
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

          {/* Floating particles */}
          {[...Array(12)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-teal-400/30"
              style={{
                left: `${10 + (i * 7.5)}%`,
                top: `${15 + (i % 5) * 18}%`,
              }}
              animate={{ y: [-6, 6, -6], opacity: [0.2, 0.6, 0.2] }}
              transition={{ duration: 3 + i * 0.4, repeat: Infinity, ease: 'easeInOut', delay: i * 0.3 }}
            />
          ))}

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

          {/* Logo mark */}
          <motion.div
            className="relative flex flex-col items-center gap-6"
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          >
            <motion.div
              animate={phase === 'glow' ? {
                filter: ['drop-shadow(0 0 8px #2DD4BF)', 'drop-shadow(0 0 32px #2DD4BF)', 'drop-shadow(0 0 16px #2DD4BF)'],
              } : {}}
              transition={{ duration: 0.8, ease: 'easeInOut' }}
            >
              <LogoMark size={120} animated color="#2DD4BF" />
            </motion.div>

            <motion.div
              className="flex flex-col items-center gap-1"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.0, duration: 0.5 }}
            >
              <span
                className="text-4xl font-bold text-white tracking-wider"
                style={{ fontFamily: 'Orbitron, sans-serif' }}
              >
                LearnX
              </span>
              <span className="text-sm text-teal-400/70 tracking-[0.3em] uppercase">
                Less Stress · More Success
              </span>
            </motion.div>
          </motion.div>
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

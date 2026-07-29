import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import logoSymbolLightInk from '../assets/brand/logo-symbol-light-ink.png'

interface IntroAnimationProps {
  onComplete: () => void
}

/**
 * Native pixel dimensions of the official LearnX symbol asset
 * (src/assets/brand/logo-symbol-light-ink.png — the double-chevron + teal
 * diamond mark, cropped directly from the official brand artwork and
 * never redrawn or approximated). Reserved up front so the mark never
 * shifts, pops, or lays out late.
 */
const SYMBOL_WIDTH = 253
const SYMBOL_HEIGHT = 280

type Phase = 'dark' | 'gather' | 'reveal' | 'tagline' | 'transition' | 'done'

/** Once-per-browser-session guard — the intro auto-plays only the first time within a session. */
const SESSION_KEY = 'learnx-intro-played'

/**
 * Deterministic "knowledge fragment" field: documents, notes, equations,
 * and small geometric pieces drifting in the dark before they gather.
 */
const FRAGMENTS = Array.from({ length: 16 }, (_, i) => {
  const angle = (i / 16) * Math.PI * 2 + (i % 2 === 0 ? 0.18 : -0.12)
  const radius = 30 + ((i * 37) % 46)
  const kind = i % 4 // 0=doc, 1=note-line, 2=equation-glyph, 3=geometric chip
  const size = kind === 3 ? 5 + (i % 3) * 2 : 10 + (i % 3) * 4
  return {
    id: i,
    angle,
    radius,
    kind,
    size,
    driftDelay: (i * 0.14) % 1.6,
    gatherDelay: (i * 0.045) % 0.5,
  }
})

function FragmentGlyph({ kind, size }: { kind: number; size: number }) {
  const stroke = 'rgba(180, 214, 214, 0.55)'

  if (kind === 0) {
    // Document — small rounded rectangle with two "text" lines.
    return (
      <svg width={size * 1.6} height={size * 2} viewBox="0 0 16 20" fill="none">
        <rect x="1" y="1" width="14" height="18" rx="1.5" stroke={stroke} strokeWidth="1" />
        <line x1="4" y1="7" x2="12" y2="7" stroke={stroke} strokeWidth="1" />
        <line x1="4" y1="11" x2="12" y2="11" stroke={stroke} strokeWidth="1" />
        <line x1="4" y1="15" x2="9" y2="15" stroke={stroke} strokeWidth="1" />
      </svg>
    )
  }

  if (kind === 1) {
    // Note fragment — a short handwritten-style line.
    return (
      <svg width={size * 2} height={size} viewBox="0 0 20 10" fill="none">
        <line x1="1" y1="5" x2="19" y2="5" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    )
  }

  if (kind === 2) {
    // Equation glyph — a small sigma-like mark.
    return (
      <svg width={size * 1.4} height={size * 1.4} viewBox="0 0 16 16" fill="none">
        <path d="M3 2h10l-5 6 5 6H3l4-6-4-6z" stroke={stroke} strokeWidth="1" strokeLinejoin="round" />
      </svg>
    )
  }

  // Small geometric chip.
  return (
    <div
      style={{
        width: size,
        height: size,
        border: `1px solid ${stroke}`,
        transform: 'rotate(45deg)',
      }}
    />
  )
}

export default function IntroAnimation({ onComplete }: IntroAnimationProps) {
  const prefersReducedMotion = useReducedMotion()
  const skippedRef = useRef(false)

  const alreadyPlayed = useMemo(() => {
    try {
      return sessionStorage.getItem(SESSION_KEY) === '1'
    } catch {
      return false
    }
  }, [])

  const [phase, setPhase] = useState<Phase>(alreadyPlayed ? 'done' : 'dark')

  function finish() {
    if (skippedRef.current) return
    skippedRef.current = true
    try {
      sessionStorage.setItem(SESSION_KEY, '1')
    } catch {
      /* sessionStorage unavailable — safe to ignore, intro just replays */
    }
    onComplete()
  }

  useEffect(() => {
    if (alreadyPlayed) {
      onComplete()
      return
    }

    if (prefersReducedMotion) {
      // Simple fade-in of the symbol + tagline only, per accessibility requirement.
      setPhase('reveal')
      const t1 = setTimeout(() => setPhase('tagline'), 500)
      const t2 = setTimeout(finish, 1400)
      return () => {
        clearTimeout(t1)
        clearTimeout(t2)
      }
    }

    // Full cinematic timeline — approximately 7 seconds total.
    const timers = [
      setTimeout(() => setPhase('gather'), 1500), // 0.0–1.5s: dark environment + particles
      setTimeout(() => setPhase('reveal'), 3500), // 1.5–3.5s: fragments gather
      setTimeout(() => setPhase('tagline'), 5000), // 3.5–5.0s: symbol revealed
      setTimeout(() => setPhase('transition'), 6500), // 5.0–6.5s: tagline shown
      setTimeout(finish, 7500), // 6.5–7.5s: transition into landing page
    ]
    return () => timers.forEach(clearTimeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (phase === 'done') return null

  const isGathering = phase === 'gather'
  const symbolVisible = phase === 'reveal' || phase === 'tagline' || phase === 'transition'
  const showTagline = phase === 'tagline' || phase === 'transition'
  const isTransitioning = phase === 'transition'

  return (
    <motion.div
      key="intro"
      className="fixed inset-0 z-[9999] flex items-center justify-center overflow-hidden"
      style={{ background: '#080E1A' }}
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.9, ease: [0.4, 0, 0.2, 1] }}
    >
      {/* Skip control */}
      {phase !== 'transition' && (
        <button
          onClick={finish}
          className="absolute bottom-8 right-8 z-10 text-xs tracking-[0.2em] uppercase transition-opacity"
          style={{ color: 'rgba(180, 200, 210, 0.4)' }}
          aria-label="Skip intro"
        >
          Skip
        </button>
      )}

      {/* Almost-invisible animated texture */}
      <div className="absolute inset-0 bg-noise" style={{ opacity: 0.4 }} />
      <motion.div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 45%, rgba(45,212,191,0.05), transparent 70%)',
        }}
        animate={{ opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Ambient drifting knowledge fragments (documents, notes, equations, chips) */}
      {!prefersReducedMotion &&
        FRAGMENTS.map((f) => {
          const startX = Math.cos(f.angle) * f.radius
          const startY = Math.sin(f.angle) * f.radius
          return (
            <motion.div
              key={f.id}
              className="absolute flex items-center justify-center"
              style={{ left: '50%', top: '50%' }}
              initial={{
                x: `calc(${startX}vmin - 50%)`,
                y: `calc(${startY}vmin - 50%)`,
                opacity: 0,
                rotate: (f.id * 23) % 360,
              }}
              animate={
                isGathering || symbolVisible
                  ? {
                      x: '-50%',
                      y: '-50%',
                      opacity: [0, 0.8, 0],
                      scale: [1, 0.7, 0.3],
                      rotate: ((f.id * 23) % 360) + (f.id % 2 === 0 ? 140 : -140),
                    }
                  : {
                      x: [
                        `calc(${startX}vmin - 50%)`,
                        `calc(${startX + (f.id % 2 === 0 ? 2 : -2)}vmin - 50%)`,
                        `calc(${startX}vmin - 50%)`,
                      ],
                      y: [
                        `calc(${startY}vmin - 50%)`,
                        `calc(${startY - 2}vmin - 50%)`,
                        `calc(${startY}vmin - 50%)`,
                      ],
                      opacity: [0, 0.5, 0.5, 0],
                      rotate: ((f.id * 23) % 360) + 8,
                    }
              }
              transition={
                isGathering || symbolVisible
                  ? { duration: 1.1, ease: [0.6, 0.05, 0.15, 1], delay: f.gatherDelay }
                  : { duration: 5 + (f.id % 4), ease: 'easeInOut', repeat: Infinity, delay: f.driftDelay }
              }
            >
              <FragmentGlyph kind={f.kind} size={f.size} />
            </motion.div>
          )
        })}

      {/* Symbol + tagline group — this is what eases into the navbar position */}
      <motion.div
        className="relative flex flex-col items-center"
        animate={
          isTransitioning
            ? { scale: 0.28, y: '-42vh', x: 'calc(-46vw + 3rem)' }
            : { scale: 1, y: 0, x: 0 }
        }
        transition={{ duration: 1.0, ease: [0.65, 0, 0.35, 1] }}
      >
        <div
          className="relative flex items-center justify-center"
          style={{
            width: 'clamp(84px, 14vw, 148px)',
            aspectRatio: `${SYMBOL_WIDTH} / ${SYMBOL_HEIGHT}`,
          }}
        >
          {/* Soft ambient glow behind the symbol */}
          <motion.div
            className="absolute inset-0 -z-10 rounded-full"
            style={{
              background: 'radial-gradient(ellipse 60% 60% at center, rgba(45,212,191,0.28), transparent 72%)',
              filter: 'blur(24px)',
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: symbolVisible ? [0.35, 0.55, 0.35] : 0 }}
            transition={{ duration: 3.2, ease: 'easeInOut', repeat: symbolVisible ? Infinity : 0 }}
          />

          {/* The official symbol, exact asset — never redrawn */}
          <motion.img
            src={logoSymbolLightInk}
            alt="LearnX"
            width={SYMBOL_WIDTH}
            height={SYMBOL_HEIGHT}
            draggable={false}
            className="relative h-full w-full object-contain"
            initial={{ opacity: 0, scale: 0.92 }}
            animate={
              symbolVisible
                ? {
                    opacity: 1,
                    scale: phase === 'reveal' ? [0.92, 1.0] : 1,
                    y: showTagline && !isTransitioning ? [0, -3, 0] : 0,
                  }
                : { opacity: 0, scale: 0.92 }
            }
            transition={
              phase === 'reveal'
                ? { duration: 1.3, ease: [0.16, 1, 0.3, 1] }
                : showTagline
                  ? { y: { duration: 4, repeat: Infinity, ease: 'easeInOut' }, opacity: { duration: 0.4 } }
                  : { duration: 0.6 }
            }
          />

          {/* Aqua light sweep through the icon, once, right after reveal */}
          {phase === 'tagline' && (
            <motion.div
              className="absolute inset-0 pointer-events-none"
              style={{
                background: 'linear-gradient(115deg, transparent 30%, rgba(180,255,245,0.55) 48%, transparent 66%)',
                mixBlendMode: 'screen',
              }}
              initial={{ x: '-120%', opacity: 0 }}
              animate={{ x: '120%', opacity: [0, 1, 0] }}
              transition={{ duration: 1.1, ease: [0.4, 0, 0.2, 1], delay: 0.1 }}
            />
          )}

          {/* Teal diamond flare — brief glow, natural fade */}
          {phase === 'tagline' && (
            <motion.div
              className="absolute rounded-full pointer-events-none"
              style={{
                left: '49.8%',
                top: '50%',
                width: '22%',
                height: '22%',
                background: 'radial-gradient(circle, rgba(16,229,201,0.9), transparent 70%)',
                transform: 'translate(-50%, -50%)',
              }}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: [0, 0.9, 0], scale: [0.6, 1.6, 2.1] }}
              transition={{ duration: 1.3, ease: 'easeOut', delay: 0.55 }}
            />
          )}
        </div>

        {/* Tagline */}
        <motion.p
          className="mt-7 text-center whitespace-nowrap"
          style={{
            fontFamily: "'Inter', sans-serif",
            fontWeight: 300,
            fontSize: 'clamp(0.8rem, 1.6vw, 1rem)',
            letterSpacing: '0.28em',
            textTransform: 'uppercase',
            color: 'rgba(210, 224, 226, 0.75)',
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: showTagline && !isTransitioning ? 1 : 0 }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
        >
          Less Stress&nbsp;&nbsp;|&nbsp;&nbsp;More Success
        </motion.p>
      </motion.div>
    </motion.div>
  )
}

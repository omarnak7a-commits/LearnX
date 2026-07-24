import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'

interface HeroSectionProps {
  onEnter: () => void
}

const tickerItems = [
  '94 avg. focus score',
  '21-day active streaks',
  '+1,240 XP earned today',
  '247k students worldwide',
  '4.2h saved per week',
  'AI-powered spaced repetition',
  'RAG document indexing',
  'Physics · Biology · Maths · Chemistry',
]

const headlineLines = [
  { text: 'Study Smarter,', gradient: true },
  { text: 'Not Harder.', gradient: false },
]

function DashboardFragment() {
  return (
    <div
      className="glass-card overflow-hidden w-full max-w-sm"
      style={{ background: 'rgba(10,14,24,0.75)', borderColor: 'rgba(45,212,191,0.18)' }}
    >
      {/* Top bar */}
      <div
        className="flex items-center justify-between px-4 py-3.5 border-b"
        style={{ borderColor: 'rgba(45,212,191,0.08)' }}
      >
        <div>
          <p className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
            Good morning ☀️
          </p>
          <p className="text-base font-bold" style={{ color: 'var(--foreground)' }}>
            Alex Chen
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Imperial College London
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Exam in</p>
          <p
            className="text-xl font-black"
            style={{ color: '#FF7E36', fontFamily: 'Orbitron, sans-serif', lineHeight: 1 }}
          >
            12
          </p>
          <p className="text-xs" style={{ color: '#FF7E36' }}>days</p>
        </div>
      </div>

      {/* Focus score row */}
      <div
        className="flex items-center gap-4 px-4 py-4 border-b"
        style={{ borderColor: 'rgba(45,212,191,0.08)' }}
      >
        <FocusRing value={94} />
        <div className="flex-1">
          <div className="flex items-baseline gap-1 mb-1">
            <span
              className="text-3xl font-black"
              style={{ color: '#2DD4BF', fontFamily: 'Orbitron, sans-serif' }}
            >
              94
            </span>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>/100</span>
          </div>
          <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>Focus Score</p>
          <p className="text-xs" style={{ color: 'rgba(45,212,191,0.7)' }}>↑ +6 pts this week</p>
        </div>
        <div className="text-right">
          <p
            className="text-sm font-black"
            style={{ color: '#FF7E36', fontFamily: 'JetBrains Mono, monospace' }}
          >
            +1,240
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>XP today</p>
        </div>
      </div>

      {/* Today label */}
      <div className="px-4 pt-3 pb-1.5 flex items-center justify-between">
        <p
          className="text-xs font-semibold tracking-widest uppercase"
          style={{ color: 'var(--muted-foreground)', fontFamily: 'JetBrains Mono, monospace' }}
        >
          Today · Mon 21 Jul
        </p>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(45,212,191,0.1)', color: '#2DD4BF' }}
        >
          2/5
        </span>
      </div>

      {/* Tasks */}
      <div className="px-4 pb-4 space-y-2">
        {[
          { subject: 'MATHS', task: 'Derive Euler-Lagrange equation', done: true, xp: 120 },
          { subject: 'BIO', task: 'Krebs cycle intermediates', done: true, xp: 80 },
          { subject: 'PHYS', task: "Newton's Laws practice", done: false, xp: 200 },
        ].map(item => (
          <div key={item.task} className="flex items-center gap-2.5">
            <div
              className="w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center"
              style={{
                background: item.done ? 'rgba(45,212,191,0.15)' : 'transparent',
                border: `1.5px solid ${item.done ? '#2DD4BF' : 'rgba(255,255,255,0.15)'}`,
              }}
            >
              {item.done && (
                <svg width="7" height="7" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5l2.5 2.5 4-4" stroke="#2DD4BF" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              )}
            </div>
            <span
              className="text-xs px-1.5 py-0.5 rounded font-mono font-semibold"
              style={{ background: 'rgba(45,212,191,0.08)', color: '#2DD4BF', fontSize: 9 }}
            >
              {item.subject}
            </span>
            <span
              className="text-xs flex-1 truncate"
              style={{
                color: item.done ? 'var(--muted-foreground)' : 'var(--foreground)',
                textDecoration: item.done ? 'line-through' : 'none',
              }}
            >
              {item.task}
            </span>
            <span
              className="text-xs"
              style={{ color: item.done ? 'rgba(255,126,54,0.5)' : '#FF7E36', fontFamily: 'JetBrains Mono, monospace', fontSize: 9 }}
            >
              +{item.xp}
            </span>
          </div>
        ))}
      </div>

      {/* XP footer */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-t"
        style={{ borderColor: 'rgba(45,212,191,0.08)' }}
      >
        <span className="text-base">⚡</span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.07)' }}>
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg, #FF7E36, #ffa06b)' }}
            initial={{ width: 0 }}
            animate={{ width: '68%' }}
            transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1], delay: 1.2 }}
          />
        </div>
        <span className="text-xs font-mono" style={{ color: '#FF7E36', fontFamily: 'JetBrains Mono, monospace' }}>
          LVL 12
        </span>
      </div>
    </div>
  )
}

function FocusRing({ value }: { value: number }) {
  const r = 20
  const circ = 2 * Math.PI * r
  return (
    <svg width="48" height="48" viewBox="0 0 48 48">
      <circle cx="24" cy="24" r={r} fill="none" stroke="rgba(45,212,191,0.1)" strokeWidth="4" />
      <motion.circle
        cx="24" cy="24" r={r}
        fill="none" stroke="#2DD4BF" strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circ}
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ * (1 - value / 100) }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 1.0 }}
        transform="rotate(-90 24 24)"
      />
    </svg>
  )
}

export default function HeroSection({ onEnter }: HeroSectionProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ['start start', 'end start'] })
  const fragmentY = useTransform(scrollYProgress, [0, 1], [0, -40])
  const textY = useTransform(scrollYProgress, [0, 1], [0, 60])

  return (
    <section
      ref={containerRef}
      className="relative min-h-screen flex items-center px-6 pt-24 pb-12 overflow-hidden"
      style={{ background: 'var(--section-dark)' }}
    >
      {/* Fine grid */}
      <div className="absolute inset-0 bg-grid opacity-50 pointer-events-none" />

      {/* Radial ambient */}
      <div
        className="absolute top-0 right-0 w-[600px] h-[600px] pointer-events-none"
        style={{
          background: 'radial-gradient(circle at 70% 30%, rgba(45,212,191,0.07) 0%, transparent 65%)',
        }}
      />

      <div className="max-w-7xl mx-auto w-full">
        <div className="grid lg:grid-cols-[1fr_420px] gap-16 items-center">
          {/* Left: Text */}
          <motion.div style={{ y: textY }}>
            {/* Eyebrow */}
            <motion.div
              className="flex items-center gap-2.5 mb-8"
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="w-6 h-px" style={{ background: '#2DD4BF' }} />
              <span
                className="text-xs tracking-[0.25em] uppercase font-medium"
                style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}
              >
                AI-Powered Learning
              </span>
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(45,212,191,0.1)', color: 'rgba(45,212,191,0.7)', fontFamily: 'JetBrains Mono, monospace' }}
              >
                Private Beta
              </span>
            </motion.div>

            {/* Headline */}
            <h1 style={{ lineHeight: 0.95 }}>
              {headlineLines.map((line, i) => (
                <motion.span
                  key={line.text}
                  className={`block ${line.gradient ? 'text-gradient' : ''}`}
                  style={{
                    fontFamily: 'Orbitron, sans-serif',
                    fontWeight: 900,
                    fontSize: 'clamp(3rem, 7.5vw, 7.5rem)',
                    letterSpacing: '-0.025em',
                    color: line.gradient ? undefined : 'var(--foreground)',
                    filter: 'blur(12px)',
                  }}
                  initial={{ filter: 'blur(12px)', opacity: 0, y: 20 }}
                  animate={{ filter: 'blur(0px)', opacity: 1, y: 0 }}
                  transition={{ duration: 0.75, delay: 0.25 + i * 0.18, ease: [0.16, 1, 0.3, 1] }}
                >
                  {line.text}
                </motion.span>
              ))}
            </h1>

            {/* Sub */}
            <motion.p
              className="mt-7 text-lg max-w-lg leading-relaxed"
              style={{ color: 'var(--muted-foreground)', fontWeight: 400 }}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.64, ease: [0.16, 1, 0.3, 1] }}
            >
              The AI workspace where focus lives. Upload your materials, get a personalised study plan, and watch your grades improve — week by week.
            </motion.p>

            {/* CTAs */}
            <motion.div
              className="flex flex-wrap items-center gap-4 mt-10"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.8, ease: [0.16, 1, 0.3, 1] }}
            >
              <motion.button
                onClick={onEnter}
                className="flex items-center gap-2.5 px-7 py-3.5 rounded-full text-sm font-bold"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                whileHover={{ scale: 1.04, boxShadow: '0 0 36px rgba(45,212,191,0.5), 0 0 80px rgba(45,212,191,0.15)' }}
                whileTap={{ scale: 0.97 }}
              >
                Try LearnX Free
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </motion.button>

              <motion.button
                className="flex items-center gap-2 px-6 py-3.5 text-sm font-medium rounded-full transition-all"
                style={{
                  color: 'var(--muted-foreground)',
                  border: '1px solid var(--border-subtle)',
                }}
                whileHover={{ color: 'var(--foreground)', borderColor: 'rgba(45,212,191,0.25)' }}
                whileTap={{ scale: 0.97 }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none"/>
                </svg>
                Watch demo
              </motion.button>
            </motion.div>
          </motion.div>

          {/* Right: Dashboard Fragment */}
          <motion.div
            className="relative hidden lg:block"
            style={{ y: fragmentY }}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.45, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Glow behind card */}
            <div
              className="absolute -inset-8 rounded-3xl pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at center, rgba(45,212,191,0.12) 0%, transparent 70%)' }}
            />
            <DashboardFragment />
          </motion.div>
        </div>
      </div>

      {/* Ticker */}
      <motion.div
        className="absolute bottom-0 left-0 right-0 overflow-hidden border-t"
        style={{ borderColor: 'rgba(45,212,191,0.07)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.1, duration: 0.6 }}
      >
        <div className="flex animate-marquee py-3 gap-0" style={{ width: 'max-content' }}>
          {[...tickerItems, ...tickerItems].map((item, i) => (
            <span
              key={i}
              className="flex items-center gap-4 px-6 text-xs font-medium whitespace-nowrap"
              style={{
                color: 'var(--muted-foreground)',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              {item}
              <span style={{ color: 'rgba(45,212,191,0.3)' }}>·</span>
            </span>
          ))}
        </div>
      </motion.div>
    </section>
  )
}

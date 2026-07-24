import { motion, useInView } from 'framer-motion'
import { useRef } from 'react'

/* ── RAG Knowledge Graph SVG ── */
function KnowledgeGraph() {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  const nodes = [
    { id: 'doc', cx: 60, cy: 180, r: 36, label: 'PDF', color: '#2DD4BF', delay: 0 },
    { id: 'notes', cx: 240, cy: 80, r: 28, label: 'Notes', color: '#5eead4', delay: 0.35 },
    { id: 'quiz', cx: 330, cy: 160, r: 32, label: 'Quiz', color: '#FF7E36', delay: 0.5 },
    { id: 'summary', cx: 280, cy: 270, r: 26, label: 'Summary', color: '#2DD4BF', delay: 0.65 },
    { id: 'ai', cx: 170, cy: 310, r: 22, label: 'Ask AI', color: '#5eead4', delay: 0.8 },
  ]

  const edges = [
    { x1: 96, y1: 170, x2: 212, y2: 90, delay: 0.2 },
    { x1: 96, y1: 185, x2: 298, y2: 162, delay: 0.32 },
    { x1: 96, y1: 200, x2: 254, y2: 268, delay: 0.44 },
    { x1: 96, y1: 208, x2: 148, y2: 306, delay: 0.56 },
    { x1: 268, y1: 80, x2: 298, y2: 144, delay: 0.7 },
    { x1: 330, y1: 192, x2: 292, y2: 244, delay: 0.82 },
  ]

  return (
    <svg ref={ref} viewBox="0 0 400 360" fill="none" className="w-full max-w-sm mx-auto">
      {/* Edges */}
      {edges.map((e, i) => (
        <motion.line
          key={i}
          x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
          stroke="rgba(45,212,191,0.22)"
          strokeWidth="1.2"
          strokeDasharray="4 3"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={inView ? { pathLength: 1, opacity: 1 } : {}}
          transition={{ duration: 0.7, delay: e.delay, ease: 'easeOut' }}
        />
      ))}

      {/* Nodes */}
      {nodes.map(n => (
        <g key={n.id}>
          <motion.circle
            cx={n.cx} cy={n.cy} r={n.r}
            fill={`${n.color}12`}
            stroke={n.color}
            strokeWidth="1.2"
            initial={{ scale: 0, opacity: 0 }}
            animate={inView ? { scale: 1, opacity: 1 } : {}}
            transition={{ duration: 0.45, delay: n.delay, ease: [0.34, 1.56, 0.64, 1] }}
            style={{ transformOrigin: `${n.cx}px ${n.cy}px` }}
          />
          <motion.text
            x={n.cx} y={n.cy + 4}
            textAnchor="middle"
            fontSize="10"
            fontWeight="600"
            fill={n.color}
            fontFamily="JetBrains Mono, monospace"
            initial={{ opacity: 0 }}
            animate={inView ? { opacity: 1 } : {}}
            transition={{ duration: 0.3, delay: n.delay + 0.2 }}
          >
            {n.label}
          </motion.text>
        </g>
      ))}

      {/* Query bar at bottom */}
      <motion.g
        initial={{ opacity: 0, y: 10 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5, delay: 1.0 }}
      >
        <rect x="60" y="336" width="280" height="22" rx="11" fill="rgba(45,212,191,0.07)" stroke="rgba(45,212,191,0.2)" strokeWidth="1"/>
        <text x="78" y="351" fontSize="9" fill="rgba(45,212,191,0.6)" fontFamily="JetBrains Mono, monospace">
          Summarise Krebs cycle in 5 bullet points →
        </text>
      </motion.g>
    </svg>
  )
}

/* ── Pomodoro Timer Visual ── */
function PomodoroVisual() {
  const r = 80
  const circ = 2 * Math.PI * r
  const progress = 0.63

  return (
    <div className="flex flex-col items-center gap-6">
      {/* Timer ring */}
      <div className="relative flex items-center justify-center">
        <svg width="200" height="200" viewBox="0 0 200 200">
          <circle cx="100" cy="100" r={r} fill="none" stroke="rgba(255,126,54,0.08)" strokeWidth="8" />
          <motion.circle
            cx="100" cy="100" r={r}
            fill="none" stroke="#FF7E36" strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            whileInView={{ strokeDashoffset: circ * (1 - progress) }}
            viewport={{ once: true }}
            transition={{ duration: 1.8, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
            transform="rotate(-90 100 100)"
          />
        </svg>

        <div className="absolute text-center">
          <p
            className="text-4xl font-black leading-none"
            style={{ fontFamily: 'Orbitron, sans-serif', color: '#FF7E36' }}
          >
            23:47
          </p>
          <p className="text-xs mt-1" style={{ color: 'rgba(255,126,54,0.6)', fontFamily: 'JetBrains Mono, monospace' }}>
            FOCUS SESSION
          </p>
        </div>
      </div>

      {/* Waveform */}
      <div className="flex items-end gap-1 h-10">
        {[3, 5, 7, 4, 8, 6, 9, 7, 5, 8, 10, 7, 6, 9, 8, 6, 4, 7, 5, 8].map((h, i) => (
          <motion.div
            key={i}
            className="w-1.5 rounded-full"
            style={{ background: i < 13 ? '#FF7E36' : 'rgba(255,126,54,0.3)' }}
            animate={{ height: [h * 3.5, h * 3.5 * 1.4, h * 3.5] }}
            transition={{
              duration: 1.2 + (i % 4) * 0.2,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: i * 0.06,
            }}
          />
        ))}
      </div>

      <p className="text-xs text-center" style={{ color: 'rgba(255,126,54,0.6)', fontFamily: 'JetBrains Mono, monospace' }}>
        forest-rain.ambient · playing
      </p>
    </div>
  )
}

/* ── Feature Story component ── */
interface StoryProps {
  number: string
  eyebrow: string
  title: string
  body: string
  bullets: string[]
  visual: React.ReactNode
  flip?: boolean
  bg: string
  accentColor: string
}

function FeatureStory({ number, eyebrow, title, body, bullets, visual, flip = false, bg, accentColor }: StoryProps) {
  return (
    <section className="relative py-24 lg:py-32 overflow-hidden" style={{ background: bg }}>
      {/* Watermark number */}
      <div
        className="absolute pointer-events-none select-none"
        style={{
          fontFamily: 'Orbitron, sans-serif',
          fontSize: 'clamp(8rem, 20vw, 18rem)',
          fontWeight: 900,
          color: accentColor,
          opacity: 0.03,
          top: '50%',
          transform: 'translateY(-50%)',
          right: flip ? undefined : '-2rem',
          left: flip ? '-2rem' : undefined,
          lineHeight: 1,
          userSelect: 'none',
        }}
      >
        {number}
      </div>

      <div className="max-w-7xl mx-auto px-8">
        <div className={`grid lg:grid-cols-2 gap-16 lg:gap-24 items-center ${flip ? 'lg:grid-flow-dense' : ''}`}>
          {/* Text */}
          <div className={flip ? 'lg:col-start-2' : ''}>
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-center gap-3 mb-5">
                <div className="w-6 h-px" style={{ background: accentColor }} />
                <span
                  className="text-xs tracking-[0.2em] uppercase font-semibold"
                  style={{ color: accentColor, fontFamily: 'JetBrains Mono, monospace' }}
                >
                  {eyebrow}
                </span>
              </div>

              <h2
                className="mb-5 leading-tight"
                style={{
                  fontFamily: 'Orbitron, sans-serif',
                  fontSize: 'clamp(1.75rem, 4vw, 3rem)',
                  fontWeight: 900,
                  color: 'var(--foreground)',
                  letterSpacing: '-0.02em',
                }}
              >
                {title}
              </h2>

              <p className="text-base leading-relaxed mb-8" style={{ color: 'var(--muted-foreground)', fontWeight: 400 }}>
                {body}
              </p>

              <ul className="space-y-3">
                {bullets.map(b => (
                  <li key={b} className="flex items-start gap-3 text-sm" style={{ color: 'var(--foreground)' }}>
                    <svg
                      className="flex-shrink-0 mt-0.5"
                      width="14" height="14" viewBox="0 0 16 16" fill="none"
                    >
                      <path d="M3 8l3.5 3.5L13 4" stroke={accentColor} strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    {b}
                  </li>
                ))}
              </ul>
            </motion.div>
          </div>

          {/* Visual */}
          <motion.div
            className={flip ? 'lg:col-start-1' : ''}
            initial={{ opacity: 0, x: flip ? -30 : 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          >
            <div
              className="rounded-2xl overflow-hidden p-8 relative"
              style={{
                background: `${accentColor}07`,
                border: `1px solid ${accentColor}20`,
              }}
            >
              <div
                className="absolute inset-0 bg-grid-fine opacity-60 pointer-events-none"
              />
              <div className="relative z-10">{visual}</div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}

/* ── Capsule cards ── */
const capsules = [
  {
    icon: '🤖',
    label: 'AI Tutor',
    description: 'Switch between Socratic, Direct, and Mentor modes. Your AI adapts to how you learn best.',
    tag: 'Adaptive',
    color: '#2DD4BF',
  },
  {
    icon: '🔄',
    label: 'Spaced Repetition',
    description: 'SM-2 algorithm surfaces flashcards exactly when you\'re about to forget. Zero wasted reviews.',
    tag: 'Memory Science',
    color: '#2DD4BF',
  },
  {
    icon: '🏆',
    label: 'Gamification',
    description: 'XP, levels, badges, and a live class leaderboard. Every session earns progress.',
    tag: 'Engagement',
    color: '#FF7E36',
  },
]

function CapsuleCards() {
  return (
    <section
      className="py-20 px-8"
      style={{ background: 'var(--section-dark)' }}
    >
      <div className="max-w-5xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {capsules.map((c, i) => (
            <motion.div
              key={c.label}
              className="glass-card p-6 relative overflow-hidden group"
              initial={{ opacity: 0, y: 20, scale: 0.97 }}
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              whileHover={{ y: -4 }}
              style={{ minHeight: i === 1 ? 200 : 180 }}
            >
              <div
                className="absolute top-0 inset-x-0 h-px"
                style={{ background: `linear-gradient(90deg, transparent, ${c.color}60, transparent)` }}
              />
              <div className="flex items-center justify-between mb-4">
                <span className="text-2xl">{c.icon}</span>
                <span
                  className="text-xs px-2.5 py-1 rounded-full font-mono"
                  style={{ background: `${c.color}15`, color: c.color, fontFamily: 'JetBrains Mono, monospace' }}
                >
                  {c.tag}
                </span>
              </div>
              <h3 className="text-base font-bold mb-2" style={{ color: 'var(--foreground)' }}>{c.label}</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{c.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Main export ── */
export default function FeaturesGrid() {
  return (
    <div id="features">
      <FeatureStory
        number="01"
        eyebrow="AI Document Engine"
        title="Upload anything. Understand everything."
        body="Drop in any PDF, lecture recording, or DOCX. LearnX's RAG engine parses, indexes, and connects concepts across all your materials — then lets you query them, generate quizzes, and get instant summaries."
        bullets={[
          'Supports PDF, DOCX, PPTX, and web URLs',
          'Semantic search across all your files at once',
          'Auto-generates flashcards and quizzes per chapter',
          'Knowledge graph visualises how concepts connect',
        ]}
        visual={<KnowledgeGraph />}
        bg="var(--section-deep)"
        accentColor="#2DD4BF"
      />

      <FeatureStory
        number="02"
        eyebrow="Focus Architecture"
        title="Never lose your flow state again."
        body="Intelligent Pomodoro sessions with adaptive break scheduling, ambient soundscapes hand-picked for cognitive performance, and a real-time focus meter that learns when you're at your sharpest."
        bullets={[
          '25/5 or custom session lengths with smart nudges',
          '12 ambient soundscapes: lo-fi, forest, rain, café',
          'Focus score tracked per session and over time',
          'Auto-pause detection when you go idle',
        ]}
        visual={<PomodoroVisual />}
        flip
        bg="var(--section-blue)"
        accentColor="#FF7E36"
      />

      <CapsuleCards />
    </div>
  )
}

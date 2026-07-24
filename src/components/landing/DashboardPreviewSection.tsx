import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'

interface DashboardPreviewSectionProps {
  onEnter: () => void
}

/* Mini chart for the preview */
function SparkLine({ data, color }: { data: number[]; color: string }) {
  const w = 180, h = 48
  const max = Math.max(...data)
  const min = Math.min(...data)
  const xs = data.map((_, i) => (i / (data.length - 1)) * w)
  const ys = data.map(v => h - ((v - min) / (max - min)) * (h - 8) - 4)
  const d = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x},${ys[i]}`).join(' ')
  const area = `${d} L${w},${h} L0,${h} Z`

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none">
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill="url(#sg)"/>
      <path d={d} stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function RingMini({ pct, color, size = 44 }: { pct: number; color: string; size?: number }) {
  const r = size / 2 - 5
  const circ = 2 * Math.PI * r
  return (
    <svg width={size} height={size}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="4"/>
      <motion.circle
        cx={size/2} cy={size/2} r={r}
        fill="none" stroke={color} strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circ}
        initial={{ strokeDashoffset: circ }}
        whileInView={{ strokeDashoffset: circ * (1 - pct / 100) }}
        viewport={{ once: true }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.8 }}
        transform={`rotate(-90 ${size/2} ${size/2})`}
      />
      <text x={size/2} y={size/2 + 4} textAnchor="middle" fontSize="9" fontWeight="800" fill={color} fontFamily="Orbitron, sans-serif">
        {pct}%
      </text>
    </svg>
  )
}

export default function DashboardPreviewSection({ onEnter }: DashboardPreviewSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start end', 'center center'],
  })

  const rotateX = useTransform(scrollYProgress, [0, 1], [14, 0])
  const scale = useTransform(scrollYProgress, [0, 1], [0.88, 1])
  const opacity = useTransform(scrollYProgress, [0, 0.25], [0, 1])
  const y = useTransform(scrollYProgress, [0, 1], [60, 0])

  return (
    <section
      id="analytics"
      ref={sectionRef}
      className="py-28 px-6 relative overflow-hidden"
      style={{ background: 'var(--section-deep)' }}
    >
      {/* Ambient glow */}
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(45,212,191,0.2), transparent)' }}
      />
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[80%] h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(45,212,191,0.12), transparent)' }}
      />

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex items-center justify-center gap-3 mb-5">
            <div className="w-10 h-px" style={{ background: 'var(--border)' }} />
            <span
              className="text-xs tracking-[0.25em] uppercase font-semibold"
              style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}
            >
              Your workspace
            </span>
            <div className="w-10 h-px" style={{ background: 'var(--border)' }} />
          </div>
          <h2
            className="leading-tight mb-4"
            style={{
              fontFamily: 'Orbitron, sans-serif',
              fontSize: 'clamp(2rem, 5vw, 3.5rem)',
              fontWeight: 900,
              color: 'var(--foreground)',
              letterSpacing: '-0.02em',
            }}
          >
            A dashboard designed for flow
          </h2>
          <p className="text-base max-w-lg mx-auto" style={{ color: 'var(--muted-foreground)' }}>
            Every widget is connected. Every metric has context. No noise — just the data that moves your studies forward.
          </p>
        </motion.div>

        {/* Dashboard mockup — scroll-driven perspective */}
        <motion.div
          style={{ rotateX, scale, opacity, y, perspective: 1000 }}
          className="mx-auto max-w-5xl relative"
        >
          {/* Glow beneath */}
          <div
            className="absolute -inset-8 rounded-3xl pointer-events-none"
            style={{ background: 'radial-gradient(ellipse 70% 40% at 50% 90%, rgba(45,212,191,0.18) 0%, transparent 70%)' }}
          />

          {/* Dashboard frame */}
          <div
            className="relative rounded-2xl overflow-hidden"
            style={{
              background: '#090c14',
              border: '1px solid rgba(45,212,191,0.16)',
              boxShadow: '0 40px 120px rgba(0,0,0,0.7)',
            }}
          >
            {/* Window chrome */}
            <div
              className="flex items-center gap-3 px-5 py-3 border-b"
              style={{ background: '#060810', borderColor: 'rgba(45,212,191,0.08)' }}
            >
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#ff5f57' }} />
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#ffbd2e' }} />
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#28c840' }} />
              </div>
              <div
                className="flex-1 mx-8 h-5 rounded-md flex items-center px-3"
                style={{ background: 'rgba(255,255,255,0.04)' }}
              >
                <span
                  className="text-xs"
                  style={{ color: 'rgba(255,255,255,0.25)', fontFamily: 'JetBrains Mono, monospace', fontSize: 9 }}
                >
                  app.learnx.io/dashboard
                </span>
              </div>
            </div>

            {/* App layout */}
            <div className="flex" style={{ minHeight: 420 }}>
              {/* Sidebar */}
              <div
                className="w-12 flex flex-col items-center gap-3 py-5 border-r flex-shrink-0"
                style={{ background: '#060810', borderColor: 'rgba(45,212,191,0.07)' }}
              >
                {['⊞', '📂', '🤖', '📅', '❓', '🏆', '📊'].map((icon, i) => (
                  <div
                    key={i}
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
                    style={{
                      background: i === 0 ? 'rgba(45,212,191,0.12)' : 'transparent',
                      borderLeft: i === 0 ? '2px solid #2DD4BF' : '2px solid transparent',
                      fontSize: 13,
                    }}
                  >
                    {icon}
                  </div>
                ))}
              </div>

              {/* Main content */}
              <div className="flex-1 p-4 grid grid-cols-12 gap-3">
                {/* Greeting + Goal */}
                <div
                  className="col-span-4 rounded-xl p-4"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <p className="text-xs mb-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>Good morning ☀️</p>
                  <p className="text-sm font-bold mb-3" style={{ color: '#F0F4F8' }}>Alex Chen</p>
                  <div className="flex items-center gap-3">
                    <RingMini pct={68} color="#2DD4BF" size={48} />
                    <div>
                      <p className="text-xs font-semibold" style={{ color: '#F0F4F8' }}>Daily Goal</p>
                      <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>2h 18m left</p>
                    </div>
                  </div>
                  {/* AI insight */}
                  <div
                    className="mt-3 p-2.5 rounded-lg"
                    style={{ background: 'rgba(45,212,191,0.06)', border: '1px solid rgba(45,212,191,0.15)' }}
                  >
                    <p className="text-xs leading-relaxed" style={{ color: 'rgba(45,212,191,0.8)', fontSize: 9 }}>
                      💡 Review Newton's Laws again — retention at 61%
                    </p>
                  </div>
                </div>

                {/* Focus chart */}
                <div
                  className="col-span-8 rounded-xl p-4"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-xs font-semibold" style={{ color: '#F0F4F8' }}>Focus Score</p>
                      <p style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>7-day trend</p>
                    </div>
                    <p
                      className="text-2xl font-black"
                      style={{ color: '#2DD4BF', fontFamily: 'Orbitron, sans-serif', lineHeight: 1 }}
                    >
                      94
                    </p>
                  </div>
                  <SparkLine data={[71, 83, 68, 90, 87, 94, 89]} color="#2DD4BF" />
                </div>

                {/* Study plan */}
                <div
                  className="col-span-8 rounded-xl p-4"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <p className="text-xs font-semibold mb-2.5" style={{ color: '#F0F4F8' }}>Today's Study Plan</p>
                  <div className="space-y-2">
                    {[
                      { task: 'Derive Euler-Lagrange equation', done: true, subj: 'MATHS', xp: 120 },
                      { task: 'Krebs cycle intermediates', done: true, subj: 'BIO', xp: 80 },
                      { task: "Newton's Laws practice", done: false, subj: 'PHYS', xp: 200 },
                    ].map(t => (
                      <div key={t.task} className="flex items-center gap-2">
                        <div
                          className="w-3.5 h-3.5 rounded-full flex-shrink-0 flex items-center justify-center"
                          style={{
                            background: t.done ? 'rgba(45,212,191,0.15)' : 'transparent',
                            border: `1px solid ${t.done ? '#2DD4BF' : 'rgba(255,255,255,0.15)'}`,
                          }}
                        >
                          {t.done && (
                            <svg width="6" height="6" viewBox="0 0 10 10" fill="none">
                              <path d="M2 5l2.5 2.5 4-4" stroke="#2DD4BF" strokeWidth="2" strokeLinecap="round"/>
                            </svg>
                          )}
                        </div>
                        <span
                          className="text-xs rounded px-1 font-mono"
                          style={{ background: 'rgba(45,212,191,0.07)', color: '#2DD4BF', fontSize: 8 }}
                        >
                          {t.subj}
                        </span>
                        <span className="text-xs flex-1 truncate" style={{ color: t.done ? 'rgba(255,255,255,0.3)' : '#F0F4F8', fontSize: 10 }}>
                          {t.task}
                        </span>
                        <span style={{ fontSize: 9, color: '#FF7E36', fontFamily: 'JetBrains Mono, monospace' }}>
                          +{t.xp}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Streak */}
                <div
                  className="col-span-4 rounded-xl p-4"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs font-semibold" style={{ color: '#F0F4F8' }}>Streak</p>
                    <span className="text-base">🔥</span>
                  </div>
                  <p
                    className="text-3xl font-black"
                    style={{ color: '#FF7E36', fontFamily: 'Orbitron, sans-serif', lineHeight: 1 }}
                  >
                    21
                  </p>
                  <p style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>day streak</p>
                  <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.07)' }}>
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: '#FF7E36' }}
                      initial={{ width: 0 }}
                      whileInView={{ width: '68%' }}
                      viewport={{ once: true }}
                      transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 1.0 }}
                    />
                  </div>
                  <p style={{ fontSize: 8, color: 'rgba(255,126,54,0.5)', marginTop: 4 }}>Level 12 · 68% to Level 13</p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          className="text-center mt-14"
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.55, delay: 0.3 }}
        >
          <motion.button
            onClick={onEnter}
            className="px-10 py-4 rounded-full text-sm font-bold"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            whileHover={{ scale: 1.04, boxShadow: '0 0 36px rgba(45,212,191,0.5)' }}
            whileTap={{ scale: 0.97 }}
          >
            Open your dashboard →
          </motion.button>
          <p className="mt-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
            No credit card required · Free forever for students
          </p>
        </motion.div>
      </div>
    </section>
  )
}

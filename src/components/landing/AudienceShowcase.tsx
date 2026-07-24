import { useState } from 'react'
import { motion } from 'framer-motion'

const personas = [
  {
    id: 'students',
    label: 'University Students',
    ageRange: '18–25',
    icon: '🎓',
    quote: "I went from averaging 58% to 79% in one semester. The spaced repetition alone changed everything.",
    author: 'Priya K. · 2nd Year Medicine',
    highlights: [
      { stat: '+22%', label: 'avg. grade improvement' },
      { stat: '4.2h', label: 'saved per week' },
    ],
    features: [
      'AI flashcards generated from your own notes',
      'Personalised study schedule around your timetable',
      'Exam countdown with daily targets',
      'Gamified XP — studying feels like progress',
    ],
    accent: '#2DD4BF',
    height: 'auto',
  },
  {
    id: 'exam',
    label: 'Exam Candidates',
    ageRange: 'All ages',
    icon: '📋',
    quote: "Uploaded 6 past papers on Sunday. By Friday I had a targeted revision plan and mock test scores improving daily.",
    author: 'James T. · A-Level student',
    highlights: [
      { stat: '+34%', label: 'pass rate lift' },
      { stat: '91%', label: 'of students pass on first attempt' },
    ],
    features: [
      'Past paper analysis → personalised practice',
      'Weak area identification and targeted drills',
      'AI explains every wrong answer in plain English',
      'Mock test generator with timed conditions',
    ],
    accent: '#FF7E36',
    height: 'auto',
  },
  {
    id: 'educators',
    label: 'Teachers & Parents',
    ageRange: '',
    icon: '👨‍🏫',
    quote: "I can finally see exactly where each student is struggling before they even ask for help.",
    author: 'Ms. Chen · Secondary school teacher',
    highlights: [
      { stat: '91%', label: 'parent engagement rate' },
      { stat: '6h', label: 'saved per week' },
    ],
    features: [
      'Real-time class progress dashboard',
      'Weekly AI-written reports per student',
      'Set goals and track completion rates',
      'Classroom leaderboard for healthy competition',
    ],
    accent: '#2DD4BF',
    height: 'auto',
  },
]

export default function AudienceShowcase() {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  return (
    <section
      id="roles"
      className="py-28 px-8 relative"
      style={{ background: 'var(--section-mid)' }}
    >
      <div className="max-w-7xl mx-auto">
        {/* Section header */}
        <motion.div
          className="mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-6 h-px" style={{ background: 'var(--primary)' }} />
            <span
              className="text-xs tracking-[0.25em] uppercase font-semibold"
              style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}
            >
              Who it's for
            </span>
          </div>
          <h2
            className="leading-tight"
            style={{
              fontFamily: 'Orbitron, sans-serif',
              fontSize: 'clamp(2rem, 5vw, 4rem)',
              fontWeight: 900,
              color: 'var(--foreground)',
              letterSpacing: '-0.02em',
              maxWidth: '22ch',
            }}
          >
            Built for every kind of learner
          </h2>
        </motion.div>

        {/* Three columns — intentionally staggered heights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-start">
          {personas.map((p, i) => {
            const isHovered = hoveredId === p.id
            const offsets = [0, 40, 0]

            return (
              <motion.div
                key={p.id}
                style={{ marginTop: offsets[i] }}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: offsets[i] }}
                viewport={{ once: true }}
                transition={{ duration: 0.7, delay: i * 0.12, ease: [0.16, 1, 0.3, 1] }}
                onMouseEnter={() => setHoveredId(p.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <motion.div
                  className="rounded-2xl overflow-hidden cursor-pointer"
                  animate={{
                    boxShadow: isHovered
                      ? `0 20px 60px rgba(0,0,0,0.4), 0 0 0 1px ${p.accent}30`
                      : '0 4px 24px rgba(0,0,0,0.2)',
                  }}
                  transition={{ duration: 0.3 }}
                  style={{
                    background: 'var(--card)',
                    border: `1px solid ${isHovered ? p.accent + '28' : 'var(--border)'}`,
                    transition: 'border-color 0.3s ease',
                  }}
                >
                  {/* Top accent line */}
                  <div
                    className="h-0.5"
                    style={{ background: `linear-gradient(90deg, ${p.accent}, ${p.accent}50, transparent)` }}
                  />

                  <div className="p-7">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-6">
                      <div>
                        <span className="text-3xl block mb-3">{p.icon}</span>
                        <h3
                          className="text-lg font-bold"
                          style={{ color: 'var(--foreground)', fontFamily: 'Orbitron, sans-serif', letterSpacing: '-0.01em' }}
                        >
                          {p.label}
                        </h3>
                        {p.ageRange && (
                          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)', fontFamily: 'JetBrains Mono, monospace' }}>
                            Aged {p.ageRange}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Quote */}
                    <blockquote
                      className="text-sm leading-relaxed mb-1 italic"
                      style={{ color: 'var(--foreground)', borderLeft: `2px solid ${p.accent}`, paddingLeft: 14 }}
                    >
                      "{p.quote}"
                    </blockquote>
                    <p className="text-xs mb-6 pl-4" style={{ color: 'var(--muted-foreground)' }}>
                      — {p.author}
                    </p>

                    {/* Stats */}
                    <div className="flex gap-6 mb-6 py-4 border-t border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                      {p.highlights.map(h => (
                        <div key={h.label}>
                          <p
                            className="text-2xl font-black"
                            style={{ color: p.accent, fontFamily: 'Orbitron, sans-serif' }}
                          >
                            {h.stat}
                          </p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                            {h.label}
                          </p>
                        </div>
                      ))}
                    </div>

                    {/* Features — revealed on hover */}
                    <motion.ul
                      className="space-y-2.5 overflow-hidden"
                      animate={{ height: isHovered ? 'auto' : '0px', opacity: isHovered ? 1 : 0 }}
                      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                    >
                      {p.features.map(f => (
                        <li key={f} className="flex items-start gap-2.5 text-xs" style={{ color: 'var(--foreground)' }}>
                          <svg className="flex-shrink-0 mt-0.5" width="12" height="12" viewBox="0 0 14 14" fill="none">
                            <path d="M2.5 7l3 3 5.5-5.5" stroke={p.accent} strokeWidth="2" strokeLinecap="round"/>
                          </svg>
                          {f}
                        </li>
                      ))}
                    </motion.ul>
                  </div>
                </motion.div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

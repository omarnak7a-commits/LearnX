import { motion } from 'framer-motion'

const lines = [
  { words: ['Your', 'notes.', 'Your', 'lectures.'], dim: false },
  { words: ['Your', 'syllabus.', 'Your', 'deadlines.'], dim: true },
  null,
  { words: ['Finally', 'understood.'], dim: false, accent: true },
]

export default function StatementSection() {
  return (
    <section
      className="relative py-36 px-8 overflow-hidden"
      style={{ background: 'var(--section-deep)' }}
    >
      {/* Vertical rule accent */}
      <motion.div
        className="absolute left-12 top-1/2 -translate-y-1/2 w-px h-24"
        style={{ background: 'linear-gradient(to bottom, transparent, #2DD4BF, transparent)' }}
        initial={{ scaleY: 0, opacity: 0 }}
        whileInView={{ scaleY: 1, opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
      />

      <div className="max-w-5xl mx-auto">
        <div className="space-y-2">
          {lines.map((line, i) => {
            if (!line) return <div key={i} className="h-8" />
            return (
              <div key={i} className="overflow-hidden">
                <motion.p
                  className="leading-none tracking-tight"
                  style={{
                    fontSize: 'clamp(2.5rem, 6vw, 5.5rem)',
                    fontFamily: line.accent ? 'Orbitron, sans-serif' : 'Inter, sans-serif',
                    fontWeight: line.accent ? 900 : 300,
                    color: line.accent ? 'var(--primary)' : line.dim ? 'var(--muted-foreground)' : 'var(--foreground)',
                    letterSpacing: line.accent ? '-0.02em' : '-0.01em',
                  }}
                  initial={{ clipPath: 'inset(0 100% 0 0)' }}
                  whileInView={{ clipPath: 'inset(0 0% 0 0)' }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.9, delay: i * 0.16, ease: [0.76, 0, 0.24, 1] }}
                >
                  {line.words.join(' ')}
                </motion.p>
              </div>
            )
          })}
        </div>

        {/* Subtext beneath */}
        <motion.p
          className="mt-12 text-base max-w-md leading-relaxed"
          style={{ color: 'var(--muted-foreground)', fontWeight: 400 }}
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, delay: 0.8 }}
        >
          LearnX connects every document, note, and deadline you own — then builds an AI-powered study system around your specific goals.
        </motion.p>
      </div>
    </section>
  )
}

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { SummaryContent } from '../../../../types/video'

interface SummaryPanelProps {
  summaries: SummaryContent[]
}

export default function SummaryPanel({ summaries }: SummaryPanelProps) {
  const [active, setActive] = useState(summaries[0]?.level)
  const current = summaries.find((s) => s.level === active) ?? summaries[0]

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-4 flex-wrap">
        {summaries.map((s) => (
          <button
            key={s.level}
            onClick={() => setActive(s.level)}
            className="relative px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
            style={{
              background: active === s.level ? 'var(--primary)' : 'var(--tint-2)',
              color: active === s.level ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {current && (
          <motion.div
            key={current.level}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="space-y-2.5"
          >
            {current.points.map((p, i) => (
              <div key={i} className="flex items-start gap-2.5 text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
                <span
                  className="w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0"
                  style={{ background: 'var(--primary)' }}
                />
                {p}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

import { motion } from 'framer-motion'
import type { StudyRecommendation } from '../../../../types/planner'

interface RecommendationsPanelProps {
  recommendations: StudyRecommendation[]
}

export default function RecommendationsPanel({ recommendations }: RecommendationsPanelProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {recommendations.map((r, i) => (
        <motion.div
          key={r.id}
          className="p-3.5 rounded-xl flex items-start gap-3"
          style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06 }}
          whileHover={{ y: -2 }}
        >
          <span className="text-lg flex-shrink-0">{r.icon}</span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
              {r.title}
            </p>
            <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              {r.body}
            </p>
            <button className="text-xs font-semibold mt-2" style={{ color: 'var(--primary)' }}>
              {r.actionLabel} →
            </button>
          </div>
        </motion.div>
      ))}
    </div>
  )
}

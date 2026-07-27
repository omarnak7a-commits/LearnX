import { motion } from 'framer-motion'
import Badge from '../../ui/Badge'

interface Recommendation {
  icon: string
  title: string
  body: string
  action: string
  tone: 'primary' | 'accent' | 'warning'
}

const recommendations: Recommendation[] = [
  {
    icon: '🔁',
    title: 'Suggested revision',
    body: "Newton's Laws retention dropped to 61% — review before Friday's quiz.",
    action: 'Review now',
    tone: 'primary',
  },
  {
    icon: '⚠️',
    title: 'Weak topic detected',
    body: 'SN1/SN2 mechanisms — 3 incorrect attempts this week in Organic Chemistry.',
    action: 'Practice topic',
    tone: 'warning',
  },
  {
    icon: '❓',
    title: 'Recommended quiz',
    body: "Cellular Respiration — you're ready for the Chapter 11 checkpoint quiz.",
    action: 'Start quiz',
    tone: 'accent',
  },
  {
    icon: '💡',
    title: 'Study tip',
    body: 'Your focus peaks 10am–12pm. Schedule hard topics in that window.',
    action: 'Adjust planner',
    tone: 'primary',
  },
]

/** AI Recommendations feed — revision, weak topics, quizzes, and tips. */
export default function AIRecommendations() {
  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center gap-2 mb-5">
        <span className="text-base">✨</span>
        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          AI Recommendations
        </h3>
        <Badge tone="primary" size="xs" pulse>
          Live
        </Badge>
      </div>

      <div className="space-y-2.5">
        {recommendations.map((r, i) => (
          <motion.div
            key={r.title}
            className="flex items-start gap-3 p-3.5 rounded-xl group"
            style={{
              background: 'var(--tint-1)',
              border: '1px solid var(--border-subtle)',
            }}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 + i * 0.08 }}
            whileHover={{ x: 2 }}
          >
            <span className="text-lg flex-shrink-0">{r.icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
                {r.title}
              </p>
              <p
                className="text-xs mt-0.5 leading-relaxed"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {r.body}
              </p>
            </div>
            <button
              className="text-xs font-semibold px-2.5 py-1.5 rounded-lg flex-shrink-0 transition-transform group-hover:scale-105"
              style={{
                background:
                  r.tone === 'primary'
                    ? 'rgba(45,212,191,0.12)'
                    : r.tone === 'accent'
                      ? 'rgba(255,126,54,0.12)'
                      : 'var(--warning-soft)',
                color:
                  r.tone === 'primary'
                    ? 'var(--primary)'
                    : r.tone === 'accent'
                      ? 'var(--accent)'
                      : 'var(--warning)',
              }}
            >
              {r.action}
            </button>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

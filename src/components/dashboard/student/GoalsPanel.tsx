import { motion } from 'framer-motion'

interface Goal {
  label: string
  progress: number
  target: string
  color: string
}

const dailyGoals: Goal[] = [
  {
    label: 'Study 2 hours',
    progress: 85,
    target: '1h 42m / 2h',
    color: '#2DD4BF',
  },
  {
    label: 'Complete 1 quiz',
    progress: 100,
    target: '1 / 1',
    color: '#22c55e',
  },
]

const weeklyGoals: Goal[] = [
  {
    label: 'Study 15 hours',
    progress: 62,
    target: '9.3h / 15h',
    color: '#a855f7',
  },
  {
    label: 'Review 4 weak topics',
    progress: 50,
    target: '2 / 4',
    color: '#f59e0b',
  },
]

function GoalBar({ goal, delay }: { goal: Goal; delay: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>
          {goal.label}
        </p>
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          {goal.target}
        </p>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
        <motion.div
          className="h-full rounded-full"
          style={{ background: goal.color }}
          initial={{ width: 0 }}
          animate={{ width: `${goal.progress}%` }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay }}
        />
      </div>
    </div>
  )
}

/** Daily Goals, Weekly Goals, XP progress, and streak recap. */
export default function GoalsPanel() {
  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <h3 className="text-sm font-bold mb-5" style={{ color: 'var(--foreground)' }}>
        🎯 Goals
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <div>
          <p
            className="text-xs font-semibold mb-3 uppercase tracking-wide"
            style={{
              color: 'var(--muted-foreground)',
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 10,
            }}
          >
            Daily Goals
          </p>
          <div className="space-y-3.5">
            {dailyGoals.map((g, i) => (
              <GoalBar key={g.label} goal={g} delay={0.2 + i * 0.1} />
            ))}
          </div>
        </div>
        <div>
          <p
            className="text-xs font-semibold mb-3 uppercase tracking-wide"
            style={{
              color: 'var(--muted-foreground)',
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 10,
            }}
          >
            Weekly Goals
          </p>
          <div className="space-y-3.5">
            {weeklyGoals.map((g, i) => (
              <GoalBar key={g.label} goal={g} delay={0.2 + i * 0.1} />
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

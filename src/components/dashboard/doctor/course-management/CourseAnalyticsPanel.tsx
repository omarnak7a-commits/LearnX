import { motion } from 'framer-motion'
import type { Course } from '../../../../types/course'
import ProgressRing from '../../../ui/ProgressRing'

interface CourseAnalyticsPanelProps {
  course: Course
}

/** Per-course Doctor analytics: KPIs, "most studied / most difficult /
 * struggling with" callouts, and AI insight cards — per the spec. */
export default function CourseAnalyticsPanel({ course }: CourseAnalyticsPanelProps) {
  const a = course.analytics

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi
          icon="👥"
          label="Total Students"
          value={a.totalStudents.toLocaleString()}
          color="#2DD4BF"
          delay={0}
        />
        <Kpi
          icon="🟢"
          label="Active Students"
          value={a.activeStudents.toLocaleString()}
          color="#22c55e"
          delay={0.05}
        />
        <Kpi
          icon="✅"
          label="Completion Rate"
          value={`${a.completionRate}%`}
          color="#FF7E36"
          delay={0.1}
        />
        <Kpi
          icon="⏱️"
          label="Avg. Watch Time"
          value={`${a.avgWatchTimeMinutes}m`}
          color="#38bdf8"
          delay={0.15}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <motion.div
          className="glass-card p-5"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
            📈 Most students studied
          </p>
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            {a.mostViewedLessonTitle}
          </p>
        </motion.div>

        <motion.div
          className="glass-card p-5"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
            ⚠️ Most difficult topic
          </p>
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            {a.strugglingTopic}
          </p>
        </motion.div>

        <motion.div
          className="glass-card p-5"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
            🚧 Drop-off point
          </p>
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            {a.dropOffLessonTitle}
          </p>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-5 items-center glass-card p-6">
        <ProgressRing pct={a.quizAvgScore} color="var(--primary)" size={88} label="quiz avg" />
        <div>
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Quiz Performance
          </p>
          <p className="text-xs mt-1 max-w-md" style={{ color: 'var(--muted-foreground)' }}>
            {a.strugglingPct}% of students struggled with {a.strugglingTopic}. Consider adding a
            recap lesson or extra practice quiz before the next module.
          </p>
        </div>
      </div>

      {a.aiInsights.length > 0 && (
        <motion.div
          className="glass-card p-6"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <p
            className="text-sm font-bold mb-3 flex items-center gap-2"
            style={{ color: 'var(--foreground)' }}
          >
            ✨ AI Insights
          </p>
          <div className="space-y-2.5">
            {a.aiInsights.map((insight, i) => (
              <div
                key={i}
                className="p-3 rounded-xl text-xs leading-relaxed"
                style={{
                  background: 'rgba(45,212,191,0.06)',
                  border: '1px solid rgba(45,212,191,0.15)',
                  color: 'rgba(45,212,191,0.9)',
                }}
              >
                💡 {insight}
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}

function Kpi({
  icon,
  label,
  value,
  color,
  delay,
}: {
  icon: string
  label: string
  value: string
  color: string
  delay: number
}) {
  return (
    <motion.div
      className="glass-card p-4"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className="w-7 h-7 rounded-lg flex items-center justify-center text-xs flex-shrink-0"
          style={{ background: `${color}18` }}
        >
          {icon}
        </span>
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          {label}
        </p>
      </div>
      <p className="text-xl font-black" style={{ fontFamily: 'Orbitron, sans-serif', color }}>
        {value}
      </p>
    </motion.div>
  )
}

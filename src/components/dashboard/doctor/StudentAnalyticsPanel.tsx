import { motion } from 'framer-motion'
import { LineChart, Line, XAxis, ResponsiveContainer, Tooltip, CartesianGrid } from 'recharts'
import HeatmapGrid from '../shared/HeatmapGrid'
import Badge from '../../ui/Badge'

const topStudents = [
  { name: 'Amelia Torres', score: 97, sessions: 42 },
  { name: 'Ravi Malhotra', score: 94, sessions: 39 },
  { name: 'Lucia Fernandez', score: 91, sessions: 36 },
  { name: 'Noah Kim', score: 89, sessions: 34 },
]

const atRisk = [
  {
    name: 'Jordan Blake',
    reason: 'No activity in 9 days',
    severity: 'high' as const,
  },
  {
    name: 'Priya Nair',
    reason: 'Quiz average dropped 22%',
    severity: 'medium' as const,
  },
  {
    name: "Sam O'Connor",
    reason: 'Missed 2 assignments',
    severity: 'medium' as const,
  },
]

const engagementTrend = [
  { week: 'W1', engagement: 62 },
  { week: 'W2', engagement: 68 },
  { week: 'W3', engagement: 71 },
  { week: 'W4', engagement: 66 },
  { week: 'W5', engagement: 78 },
  { week: 'W6', engagement: 82 },
]

// 7 columns (weeks) x 5 rows — synthetic engagement heatmap
const heatmapData = Array.from({ length: 12 }, () => Array.from({ length: 5 }, () => Math.random()))

const knowledgeGaps = [
  { topic: 'Recursion & Backtracking', course: 'CS201', gap: 38 },
  { topic: 'Normalization (3NF)', course: 'CS310', gap: 27 },
  { topic: 'Graph Traversal', course: 'CS201', gap: 22 },
]

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value: number }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="surface-popover px-3 py-2 rounded-lg text-xs">
      <p style={{ color: 'var(--muted-foreground)' }}>{label}</p>
      <p className="font-bold" style={{ color: 'var(--primary)' }}>
        {payload[0]?.value}% engagement
      </p>
    </div>
  )
}

/** Doctor-facing student analytics: top students, engagement, attendance, quiz performance, heatmap, gaps, at-risk, AI insights. */
export default function StudentAnalyticsPanel() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
      {/* Most active students */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          🌟 Most Active Students
        </h3>
        <div className="space-y-2.5">
          {topStudents.map((s, i) => (
            <div key={s.name} className="flex items-center gap-3">
              <span className="w-6 text-xs font-bold" style={{ color: 'var(--muted-foreground)' }}>
                #{i + 1}
              </span>
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{
                  background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
                  color: 'var(--primary-foreground)',
                }}
              >
                {s.name
                  .split(' ')
                  .map((n) => n[0])
                  .join('')}
              </div>
              <div className="min-w-0 flex-1">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {s.name}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {s.sessions} sessions
                </p>
              </div>
              <span className="text-xs font-bold" style={{ color: 'var(--primary)' }}>
                {s.score}%
              </span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Engagement trend */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--foreground)' }}>
          📈 Engagement & Attendance
        </h3>
        <p className="text-xs mb-3" style={{ color: 'var(--muted-foreground)' }}>
          Weekly average across all courses
        </p>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={engagementTrend} margin={{ left: -30 }}>
            <CartesianGrid strokeDasharray="2 4" stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="week"
              tick={{ fill: 'var(--chart-tick)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="engagement"
              stroke="var(--primary)"
              strokeWidth={2.5}
              dot={{ r: 3, fill: 'var(--primary)' }}
            />
          </LineChart>
        </ResponsiveContainer>
        <div
          className="flex items-center justify-between mt-3 pt-3 border-t"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              Attendance rate
            </p>
            <p
              className="text-lg font-black"
              style={{
                fontFamily: 'Orbitron, sans-serif',
                color: 'var(--foreground)',
              }}
            >
              91%
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              Quiz performance
            </p>
            <p
              className="text-lg font-black"
              style={{
                fontFamily: 'Orbitron, sans-serif',
                color: 'var(--primary)',
              }}
            >
              83%
            </p>
          </div>
        </div>
      </motion.div>

      {/* At-risk students */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h3
          className="text-sm font-bold mb-4 flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          ⚠️ At-Risk Students
        </h3>
        <div className="space-y-2.5">
          {atRisk.map((s) => (
            <div
              key={s.name}
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: 'var(--danger-soft)' }}
            >
              <span
                className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                style={{ background: 'var(--danger)' }}
              />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
                  {s.name}
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                  {s.reason}
                </p>
              </div>
              <Badge tone={s.severity === 'high' ? 'danger' : 'warning'} size="xs">
                {s.severity}
              </Badge>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Learning heatmap */}
      <motion.div
        className="glass-card p-6 xl:col-span-2"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--foreground)' }}>
          🔥 Learning Heatmap
        </h3>
        <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
          Student activity intensity across the last 12 weeks
        </p>
        <HeatmapGrid data={heatmapData} color="#2DD4BF" />
        <div
          className="flex items-center gap-2 mt-4 text-xs"
          style={{ color: 'var(--muted-foreground)' }}
        >
          <span>Less</span>
          <div className="flex gap-1">
            {[0.1, 0.3, 0.55, 0.8, 1].map((v) => (
              <div
                key={v}
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  background: `color-mix(in srgb, #2DD4BF ${Math.round((0.15 + v * 0.75) * 100)}%, transparent)`,
                }}
              />
            ))}
          </div>
          <span>More</span>
        </div>
      </motion.div>

      {/* Knowledge gaps */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          🧩 Knowledge Gaps
        </h3>
        <div className="space-y-3">
          {knowledgeGaps.map((g) => (
            <div key={g.topic}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>
                  {g.topic}
                </p>
                <span className="text-xs" style={{ color: 'var(--warning)' }}>
                  {g.gap}% gap
                </span>
              </div>
              <div
                className="h-1.5 rounded-full overflow-hidden"
                style={{ background: 'var(--tint-3)' }}
              >
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: 'var(--warning)' }}
                  initial={{ width: 0 }}
                  animate={{ width: `${g.gap}%` }}
                  transition={{ duration: 1 }}
                />
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                {g.course}
              </p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* AI insights */}
      <motion.div
        className="glass-card p-6 xl:col-span-3"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <h3
          className="text-sm font-bold mb-4 flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          ✨ AI Insights
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            {
              icon: '💡',
              text: 'Recursion is the weakest topic across CS201 — consider an extra workshop before the midterm.',
            },
            {
              icon: '📊',
              text: 'Engagement rose 20% after switching Lecture 9 to video format — consider more video content.',
            },
            {
              icon: '🎯',
              text: '3 students are trending toward at-risk status. Early outreach could improve retention by ~15%.',
            },
          ].map((t, i) => (
            <div
              key={i}
              className="p-3.5 rounded-xl flex items-start gap-2.5"
              style={{
                background: 'rgba(45,212,191,0.06)',
                border: '1px solid rgba(45,212,191,0.14)',
              }}
            >
              <span className="text-base flex-shrink-0">{t.icon}</span>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--foreground)' }}>
                {t.text}
              </p>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

import { motion } from 'framer-motion'
import type { Course } from '../../../../types/course'
import DataTable, { type Column } from '../../shared/DataTable'
import Badge from '../../../ui/Badge'
import ProgressRing from '../../../ui/ProgressRing'

interface CourseStudent {
  id: number
  name: string
  progress: number
  lastActive: string
  quizAvg: number
  status: 'excellent' | 'good' | 'at-risk'
}

const rosterNames = [
  'Amelia Torres',
  'Ravi Malhotra',
  'Lucia Fernandez',
  'Noah Kim',
  'Jordan Blake',
  'Priya Nair',
  "Sam O'Connor",
  'Emeka Obi',
]

function buildRoster(course: Course): CourseStudent[] {
  const count = Math.min(8, Math.max(3, Math.round(course.studentsCount / 20)))
  return rosterNames.slice(0, count).map((name, i) => {
    const progress = Math.max(
      12,
      Math.min(100, course.completionRate + (i % 3 === 0 ? 14 : -10 * i))
    )
    const quizAvg = Math.max(
      20,
      Math.min(100, course.analytics.quizAvgScore + (i % 2 === 0 ? 8 : -12))
    )
    const status: CourseStudent['status'] =
      progress > 80 ? 'excellent' : progress > 50 ? 'good' : 'at-risk'
    return {
      id: i + 1,
      name,
      progress,
      lastActive: i === 0 ? 'Today' : `${i + 1}d ago`,
      quizAvg,
      status,
    }
  })
}

const statusTone: Record<CourseStudent['status'], 'success' | 'warning' | 'danger'> = {
  excellent: 'success',
  good: 'warning',
  'at-risk': 'danger',
}

const columns: Column<CourseStudent>[] = [
  {
    key: 'name',
    header: 'Student',
    render: (s) => (
      <div className="flex items-center gap-2.5">
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
        <span className="font-medium">{s.name}</span>
      </div>
    ),
  },
  {
    key: 'progress',
    header: 'Progress',
    render: (s) => (
      <div className="flex items-center gap-2 w-28">
        <div
          className="flex-1 h-1.5 rounded-full overflow-hidden"
          style={{ background: 'var(--tint-3)' }}
        >
          <div
            className="h-full rounded-full"
            style={{ width: `${s.progress}%`, background: 'var(--primary)' }}
          />
        </div>
        <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          {s.progress}%
        </span>
      </div>
    ),
    hideOnMobile: true,
  },
  {
    key: 'quizAvg',
    header: 'Quiz Avg',
    render: (s) => <span className="font-semibold">{s.quizAvg}%</span>,
  },
  {
    key: 'lastActive',
    header: 'Last Active',
    render: (s) => <span style={{ color: 'var(--muted-foreground)' }}>{s.lastActive}</span>,
    hideOnMobile: true,
  },
  {
    key: 'status',
    header: 'Status',
    render: (s) => (
      <Badge tone={statusTone[s.status]} size="xs">
        {s.status}
      </Badge>
    ),
  },
]

/** Per-course "View Students" roster — same visual language as the global
 * Students page, filtered to just this course's enrollees. */
export default function CourseStudentsPanel({ course }: { course: Course }) {
  const roster = buildRoster(course)
  const avgProgress = roster.length
    ? Math.round(roster.reduce((sum, s) => sum + s.progress, 0) / roster.length)
    : 0

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Kpi
          label="Enrolled"
          value={course.studentsCount.toLocaleString()}
          color="var(--primary)"
          delay={0}
        />
        <Kpi
          label="Excellent"
          value={roster.filter((s) => s.status === 'excellent').length.toString()}
          color="var(--success)"
          delay={0.05}
        />
        <Kpi
          label="At-risk"
          value={roster.filter((s) => s.status === 'at-risk').length.toString()}
          color="var(--danger)"
          delay={0.1}
        />
        <Kpi label="Avg. progress" value={`${avgProgress}%`} color="var(--accent)" delay={0.15} />
      </div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            {course.title} — Roster
          </h3>
          <input
            placeholder="Search students..."
            className="input-field px-3.5 py-2 rounded-lg text-xs w-48"
          />
        </div>
        <DataTable columns={columns} rows={roster} rowKey={(s) => s.id} />
      </motion.div>

      <motion.div
        className="glass-card p-6 flex items-center gap-6 flex-wrap"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <ProgressRing
          pct={course.completionRate}
          color="var(--primary)"
          size={72}
          label="completion"
        />
        <div>
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Course completion rate
          </p>
          <p className="text-xs mt-1 max-w-md" style={{ color: 'var(--muted-foreground)' }}>
            {course.completionRate}% of enrolled students have finished {course.title}. See the
            Analytics tab for drop-off points and AI-suggested interventions.
          </p>
        </div>
      </motion.div>
    </div>
  )
}

function Kpi({
  label,
  value,
  color,
  delay,
}: {
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
      <p className="text-2xl font-black" style={{ fontFamily: 'Orbitron, sans-serif', color }}>
        {value}
      </p>
      <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
    </motion.div>
  )
}

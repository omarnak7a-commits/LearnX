import { motion } from 'framer-motion'
import Badge from '../../ui/Badge'

interface Item {
  title: string
  course: string
  due: string
  urgent?: boolean
  color: string
}

const assignments: Item[] = [
  {
    title: 'Lab Report — Kinematics',
    course: 'Classical Mechanics',
    due: 'Due tomorrow',
    urgent: true,
    color: '#2DD4BF',
  },
  {
    title: 'Problem Set 6',
    course: 'Calculus & Analysis',
    due: 'Due in 3 days',
    color: '#a855f7',
  },
  {
    title: 'Reaction Mechanism Essay',
    course: 'Organic Chemistry II',
    due: 'Due in 5 days',
    color: '#f59e0b',
  },
]

const exams: Item[] = [
  {
    title: 'Midterm Exam',
    course: 'Classical Mechanics',
    due: 'In 12 days',
    urgent: true,
    color: '#2DD4BF',
  },
  {
    title: 'Chapter 11 Checkpoint',
    course: 'Cell Biology',
    due: 'In 18 days',
    color: '#22c55e',
  },
]

function ListPanel({ title, icon, items }: { title: string; icon: string; items: Item[] }) {
  return (
    <div className="flex-1 min-w-0">
      <p
        className="text-xs font-bold mb-3 flex items-center gap-1.5"
        style={{ color: 'var(--foreground)' }}
      >
        <span>{icon}</span>
        {title}
      </p>
      <div className="space-y-2">
        {items.map((it, i) => (
          <motion.div
            key={it.title}
            className="flex items-center gap-3 p-3 rounded-xl"
            style={{
              background: 'var(--tint-1)',
              border: '1px solid var(--border-subtle)',
            }}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + i * 0.07 }}
          >
            <span
              className="w-1.5 h-8 rounded-full flex-shrink-0"
              style={{ background: it.color }}
            />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold truncate" style={{ color: 'var(--foreground)' }}>
                {it.title}
              </p>
              <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                {it.course}
              </p>
            </div>
            <Badge tone={it.urgent ? 'accent' : 'neutral'} size="xs">
              {it.due}
            </Badge>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

/** Upcoming Assignments + Upcoming Exams side-by-side panel. */
export default function UpcomingWork() {
  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex flex-col sm:flex-row gap-6">
        <ListPanel title="Upcoming Assignments" icon="📝" items={assignments} />
        <div
          className="hidden sm:block w-px self-stretch"
          style={{ background: 'var(--border-subtle)' }}
        />
        <ListPanel title="Upcoming Exams" icon="🧾" items={exams} />
      </div>
    </motion.div>
  )
}

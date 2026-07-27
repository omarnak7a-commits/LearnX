import { motion } from 'framer-motion'
import Badge from '../../ui/Badge'

interface Quiz {
  title: string
  subject: string
  questions: number
  status: 'new' | 'in-progress' | 'done'
  score?: number
  color: string
}

const quizzes: Quiz[] = [
  {
    title: "Newton's Laws Practice",
    subject: 'Physics',
    questions: 15,
    status: 'new',
    color: '#2DD4BF',
  },
  {
    title: 'SN1 vs SN2 Mechanisms',
    subject: 'Chemistry',
    questions: 12,
    status: 'in-progress',
    color: '#f59e0b',
  },
  {
    title: 'Cellular Respiration Checkpoint',
    subject: 'Biology',
    questions: 20,
    status: 'done',
    score: 84,
    color: '#22c55e',
  },
  {
    title: 'Variational Calculus',
    subject: 'Mathematics',
    questions: 10,
    status: 'done',
    score: 96,
    color: '#a855f7',
  },
]

const statusLabel: Record<
  Quiz['status'],
  {
    label: string
    tone: 'primary' | 'warning' | 'success'
  }
> = {
  new: { label: 'Not started', tone: 'primary' },
  'in-progress': { label: 'In progress', tone: 'warning' },
  done: { label: 'Completed', tone: 'success' },
}

export default function QuizzesPage() {
  return (
    <div className="space-y-5">
      <motion.div
        className="glass-card p-6 flex flex-col sm:flex-row items-center justify-between gap-4"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Generate a new quiz
          </h3>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            Pick a topic and let AI build a quiz from your uploaded materials.
          </p>
        </div>
        <button
          className="px-5 py-2.5 rounded-full text-sm font-semibold flex-shrink-0"
          style={{
            background: 'var(--primary)',
            color: 'var(--primary-foreground)',
          }}
        >
          ✨ Generate Quiz
        </button>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {quizzes.map((q, i) => (
          <motion.div
            key={q.title}
            className="glass-card p-5"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 * i }}
            whileHover={{ y: -3 }}
          >
            <div className="flex items-start justify-between mb-3">
              <span
                className="text-xs px-2 py-0.5 rounded-md font-mono"
                style={{
                  background: `${q.color}18`,
                  color: q.color,
                  fontFamily: 'JetBrains Mono, monospace',
                }}
              >
                {q.subject}
              </span>
              <Badge tone={statusLabel[q.status].tone} size="xs">
                {statusLabel[q.status].label}
              </Badge>
            </div>
            <p className="text-sm font-semibold mb-1" style={{ color: 'var(--foreground)' }}>
              {q.title}
            </p>
            <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
              {q.questions} questions
            </p>
            {q.status === 'done' ? (
              <div className="flex items-center gap-2">
                <div
                  className="flex-1 h-1.5 rounded-full overflow-hidden"
                  style={{ background: 'var(--tint-3)' }}
                >
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: q.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${q.score}%` }}
                    transition={{ duration: 1 }}
                  />
                </div>
                <span className="text-xs font-bold" style={{ color: q.color }}>
                  {q.score}%
                </span>
              </div>
            ) : (
              <button
                className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                style={{ background: `${q.color}18`, color: q.color }}
              >
                {q.status === 'new' ? 'Start quiz →' : 'Resume →'}
              </button>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  )
}

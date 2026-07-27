import { motion } from 'framer-motion'
import ProgressRing from '../../ui/ProgressRing'
import Badge from '../../ui/Badge'

interface Course {
  id: number
  name: string
  instructor: string
  color: string
  progress: number
  lastLesson: string
  remainingLessons: number
  icon: string
}

const courses: Course[] = [
  {
    id: 1,
    name: 'Classical Mechanics',
    instructor: 'Dr. Sarah Novak',
    color: '#2DD4BF',
    progress: 72,
    lastLesson: 'Rotational Dynamics',
    remainingLessons: 5,
    icon: '⚛️',
  },
  {
    id: 2,
    name: 'Organic Chemistry II',
    instructor: 'Dr. Michael Osei',
    color: '#f59e0b',
    progress: 48,
    lastLesson: 'SN1 vs SN2 Reactions',
    remainingLessons: 9,
    icon: '🧪',
  },
  {
    id: 3,
    name: 'Calculus & Analysis',
    instructor: 'Prof. Lena Kraus',
    color: '#a855f7',
    progress: 91,
    lastLesson: 'Variational Calculus',
    remainingLessons: 1,
    icon: '📐',
  },
  {
    id: 4,
    name: 'Cell Biology',
    instructor: 'Dr. Amara Diallo',
    color: '#22c55e',
    progress: 33,
    lastLesson: 'Cellular Respiration',
    remainingLessons: 12,
    icon: '🧬',
  },
]

/** "My Courses" grid — continue learning, progress ring, instructor, remaining lessons. */
export default function MyCourses() {
  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            My Courses
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            4 active · continue where you left off
          </p>
        </div>
        <button className="text-xs font-semibold" style={{ color: 'var(--primary)' }}>
          View all →
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {courses.map((c, i) => (
          <motion.div
            key={c.id}
            className="rounded-2xl p-4 flex items-center gap-4 transition-all cursor-pointer group"
            style={{
              background: 'var(--tint-1)',
              border: '1px solid var(--border-subtle)',
            }}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + i * 0.07, duration: 0.4 }}
            whileHover={{ borderColor: `${c.color}44`, y: -2 }}
          >
            <ProgressRing pct={c.progress} color={c.color} size={58} strokeWidth={5} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="text-sm">{c.icon}</span>
                <p
                  className="text-sm font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {c.name}
                </p>
              </div>
              <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                {c.instructor}
              </p>
              <p className="text-xs mt-1 truncate" style={{ color: c.color }}>
                ▸ {c.lastLesson}
              </p>
              <div className="flex items-center gap-2 mt-1.5">
                <Badge size="xs" tone="neutral">
                  {c.remainingLessons} lessons left
                </Badge>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

import { motion } from 'framer-motion'
import DropZone from '../shared/DropZone'
import Badge from '../../ui/Badge'

interface CourseCard {
  id: number
  name: string
  code: string
  students: number
  materials: number
  color: string
  icon: string
  progress: number
}

const courses: CourseCard[] = [
  {
    id: 1,
    name: 'Data Structures & Algorithms',
    code: 'CS201',
    students: 148,
    materials: 34,
    color: '#2DD4BF',
    icon: '💻',
    progress: 68,
  },
  {
    id: 2,
    name: 'Discrete Mathematics',
    code: 'MATH210',
    students: 96,
    materials: 21,
    color: '#a855f7',
    icon: '📐',
    progress: 54,
  },
  {
    id: 3,
    name: 'Database Systems',
    code: 'CS310',
    students: 112,
    materials: 28,
    color: '#f59e0b',
    icon: '🗄️',
    progress: 81,
  },
  {
    id: 4,
    name: 'Intro to AI',
    code: 'CS420',
    students: 56,
    materials: 19,
    color: '#38bdf8',
    icon: '🤖',
    progress: 45,
  },
]

/** Course management: drag-and-drop uploads for materials + course cards. */
export default function CourseManagement() {
  return (
    <div className="space-y-5">
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
              Upload course materials
            </h3>
            <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
              PDFs, PPTs, DOCX, videos, assignments, and exams — organized automatically by course.
            </p>
          </div>
        </div>
        <DropZone
          title="Drag & drop lecture materials"
          subtitle="PDF, PPT, DOCX, video, assignment, or exam files"
          accept=".pdf,.ppt,.pptx,.doc,.docx,.mp4,.mov"
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            My Courses
          </h3>
          <button
            className="text-xs font-semibold px-4 py-2 rounded-full"
            style={{
              background: 'var(--primary)',
              color: 'var(--primary-foreground)',
            }}
          >
            + New Course
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {courses.map((c, i) => (
            <motion.div
              key={c.id}
              className="glass-card p-5"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 * i }}
              whileHover={{ y: -3 }}
            >
              <div className="flex items-start justify-between mb-3">
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
                  style={{ background: `${c.color}18` }}
                >
                  {c.icon}
                </span>
                <Badge tone="neutral" size="xs" mono>
                  {c.code}
                </Badge>
              </div>
              <p className="text-sm font-semibold mb-1" style={{ color: 'var(--foreground)' }}>
                {c.name}
              </p>
              <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
                {c.students} students · {c.materials} materials
              </p>
              <div
                className="h-1.5 rounded-full overflow-hidden mb-1.5"
                style={{ background: 'var(--tint-3)' }}
              >
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: c.color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${c.progress}%` }}
                  transition={{ duration: 1, delay: 0.3 }}
                />
              </div>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {c.progress}% syllabus complete
              </p>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

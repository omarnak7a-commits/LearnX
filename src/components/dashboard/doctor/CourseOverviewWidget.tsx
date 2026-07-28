import { motion } from 'framer-motion'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import Badge from '../../ui/Badge'
import { statusTone, statusLabel } from '../doctor/course-management/courseMeta'

interface CourseOverviewWidgetProps {
  onManageCourses: () => void
  onOpenCourse?: (courseId: string) => void
}

/**
 * Compact "My Courses" summary for the Doctor dashboard home — replaces
 * the old static mock course grid with the real, shared course catalog
 * (the same data the full Courses / Course Builder / Analytics pages use)
 * and deep-links into the full Course Management workspace.
 */
export default function CourseOverviewWidget({
  onManageCourses,
  onOpenCourse,
}: CourseOverviewWidgetProps) {
  const { courses } = useCourseCatalog()
  const visible = courses.filter((c) => c.status !== 'archived').slice(0, 4)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            My Courses
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            {courses.length} total · manage content, students, and analytics
          </p>
        </div>
        <button
          onClick={onManageCourses}
          className="text-xs font-semibold px-4 py-2 rounded-full"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Manage Courses →
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {visible.map((c, i) => (
          <motion.button
            key={c.id}
            onClick={() => onOpenCourse?.(c.id)}
            className="glass-card p-5 text-left"
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
              <Badge tone={statusTone[c.status]} size="xs">
                {statusLabel[c.status]}
              </Badge>
            </div>
            <p className="text-sm font-semibold mb-1" style={{ color: 'var(--foreground)' }}>
              {c.title}
            </p>
            <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
              {c.studentsCount} students · {c.modules.length} modules
            </p>
            <div
              className="h-1.5 rounded-full overflow-hidden mb-1.5"
              style={{ background: 'var(--tint-3)' }}
            >
              <motion.div
                className="h-full rounded-full"
                style={{ background: c.color }}
                initial={{ width: 0 }}
                animate={{ width: `${c.completionRate}%` }}
                transition={{ duration: 1, delay: 0.3 }}
              />
            </div>
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {c.completionRate}% avg. completion
            </p>
          </motion.button>
        ))}
      </div>
    </motion.div>
  )
}

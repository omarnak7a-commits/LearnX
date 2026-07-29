import { motion } from 'framer-motion'
import type { Course } from '../../../../types/course'
import Badge from '../../../ui/Badge'
import CourseThumbnail from '../../shared/CourseThumbnail'
import { statusTone, statusLabel } from './courseMeta'

interface DoctorCourseCardProps {
  course: Course
  delay?: number
  onEdit: () => void
  onManageContent: () => void
  onViewStudents: () => void
  onAnalytics: () => void
  onSubmitForReview: () => void
  onPublish: () => void
  onArchive: () => void
  onRestore: () => void
}

/** Full course card for the Doctor "My Courses" workspace — thumbnail,
 * status, KPIs, and the complete action set from the spec. */
export default function DoctorCourseCard({
  course,
  delay = 0,
  onEdit,
  onManageContent,
  onViewStudents,
  onAnalytics,
  onSubmitForReview,
  onPublish,
  onArchive,
  onRestore,
}: DoctorCourseCardProps) {
  return (
    <motion.div
      className="glass-card overflow-hidden group"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      whileHover={{ y: -3 }}
    >
      <CourseThumbnail icon={course.icon} color={course.color} />

      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <p className="text-sm font-semibold leading-snug" style={{ color: 'var(--foreground)' }}>
            {course.title}
          </p>
          <Badge tone={statusTone[course.status]} size="xs" className="flex-shrink-0">
            {statusLabel[course.status]}
          </Badge>
        </div>
        <p className="text-xs mb-3" style={{ color: 'var(--muted-foreground)' }}>
          {course.department}
        </p>

        <div className="grid grid-cols-3 gap-2 mb-3">
          <Kpi label="Students" value={course.studentsCount.toLocaleString()} />
          <Kpi label="Completion" value={`${course.completionRate}%`} />
          <Kpi label="Rating" value={course.rating > 0 ? `★ ${course.rating}` : '—'} />
        </div>

        <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
          Updated {course.lastUpdated}
        </p>

        <div className="flex flex-wrap gap-1.5">
          <ActionButton onClick={onEdit}>Edit</ActionButton>
          <ActionButton onClick={onManageContent}>Manage Content</ActionButton>
          <ActionButton onClick={onViewStudents}>View Students</ActionButton>
          <ActionButton onClick={onAnalytics}>Analytics</ActionButton>
          {course.status === 'draft' && (
            <ActionButton onClick={onSubmitForReview} primary>
              Submit for Review
            </ActionButton>
          )}
          {course.status === 'pending-review' && (
            <ActionButton onClick={onPublish} primary>
              Publish
            </ActionButton>
          )}
          {course.status !== 'archived' && <ActionButton onClick={onArchive}>Archive</ActionButton>}
          {course.status === 'archived' && (
            <ActionButton onClick={onRestore}>Restore to Draft</ActionButton>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg px-2 py-1.5 text-center" style={{ background: 'var(--tint-1)' }}>
      <p className="text-xs font-bold" style={{ color: 'var(--foreground)' }}>
        {value}
      </p>
      <p className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
    </div>
  )
}

function ActionButton({
  children,
  onClick,
  primary = false,
}: {
  children: React.ReactNode
  onClick: () => void
  primary?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className="text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all"
      style={
        primary
          ? { background: 'var(--primary)', color: 'var(--primary-foreground)' }
          : { background: 'var(--tint-2)', color: 'var(--foreground)' }
      }
    >
      {children}
    </button>
  )
}

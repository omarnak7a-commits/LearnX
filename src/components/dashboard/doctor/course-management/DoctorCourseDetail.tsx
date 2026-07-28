import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Course } from '../../../../types/course'
import { totalLessons } from '../../../../types/course'
import { useCourseCatalog } from '../../../../context/CourseCatalogContext'
import Tabs from '../../shared/Tabs'
import Badge from '../../../ui/Badge'
import CourseThumbnail from '../../shared/CourseThumbnail'
import CourseBuilder from './CourseBuilder'
import CourseAnalyticsPanel from './CourseAnalyticsPanel'
import CourseStudentsPanel from './CourseStudentsPanel'
import { statusTone, statusLabel, courseTypeLabel } from './courseMeta'

interface DoctorCourseDetailProps {
  course: Course
  initialTab?: 'Content' | 'Students' | 'Analytics'
  onBack: () => void
}

const tabs = ['Content', 'Students', 'Analytics'] as const

/** Doctor's full course workspace — header with course meta + status
 * actions, and a tabbed view: Course Builder (content), Students
 * (per-course roster), and Analytics (per-course insights). */
export default function DoctorCourseDetail({
  course,
  initialTab = 'Content',
  onBack,
}: DoctorCourseDetailProps) {
  const [tab, setTab] = useState<(typeof tabs)[number]>(initialTab)
  const { publishCourse, archiveCourse } = useCourseCatalog()

  return (
    <div className="space-y-5">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs font-semibold"
        style={{ color: 'var(--muted-foreground)' }}
      >
        ← Back to My Courses
      </button>

      <motion.div
        className="glass-card p-6 flex flex-col sm:flex-row gap-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <CourseThumbnail
          icon={course.icon}
          color={course.color}
          size="sm"
          className="sm:w-28 sm:h-28 w-full"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-1.5">
                <h2
                  className="text-lg font-bold"
                  style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
                >
                  {course.title}
                </h2>
                <Badge tone={statusTone[course.status]} size="xs">
                  {statusLabel[course.status]}
                </Badge>
                <Badge tone="neutral" size="xs" mono>
                  {courseTypeLabel[course.courseType]}
                </Badge>
              </div>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {course.department} · {course.academicLevel} · {totalLessons(course)} lessons across{' '}
                {course.modules.length} modules
              </p>
            </div>
            <div className="flex gap-2 flex-shrink-0">
              {course.status !== 'published' && course.status !== 'archived' && (
                <button
                  onClick={() => publishCourse(course.id)}
                  className="text-xs font-semibold px-4 py-2 rounded-full"
                  style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                >
                  Publish
                </button>
              )}
              {course.status !== 'archived' && (
                <button
                  onClick={() => archiveCourse(course.id)}
                  className="text-xs font-semibold px-4 py-2 rounded-full"
                  style={{ background: 'var(--tint-2)', color: 'var(--foreground)' }}
                >
                  Archive
                </button>
              )}
            </div>
          </div>
          <p className="text-sm mt-3 max-w-2xl" style={{ color: 'var(--muted-foreground)' }}>
            {course.description}
          </p>
          <div className="flex items-center gap-4 mt-3 flex-wrap">
            <Stat label="Students" value={course.studentsCount.toLocaleString()} />
            <Stat label="Completion" value={`${course.completionRate}%`} />
            <Stat label="Rating" value={course.rating > 0 ? `★ ${course.rating}` : '—'} />
            <Stat label="Updated" value={course.lastUpdated} />
          </div>
        </div>
      </motion.div>

      <Tabs tabs={[...tabs]} active={tab} onChange={(t) => setTab(t as (typeof tabs)[number])} />

      {tab === 'Content' && <CourseBuilder course={course} />}
      {tab === 'Students' && <CourseStudentsPanel course={course} />}
      {tab === 'Analytics' && <CourseAnalyticsPanel course={course} />}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
        {value}
      </p>
      <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
    </div>
  )
}

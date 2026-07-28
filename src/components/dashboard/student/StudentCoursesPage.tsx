import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Course } from '../../../types/course'
import { totalLessons, remainingLessons } from '../../../types/course'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import CourseThumbnail from '../shared/CourseThumbnail'
import Badge from '../../ui/Badge'
import Tabs from '../shared/Tabs'
import EmptyState from '../shared/EmptyState'
import StudentCourseDetail from './course-library/StudentCourseDetail'

const tabs = ['Enrolled', 'Recently Viewed', 'Continue Learning', 'Completed', 'Saved'] as const

function courseGroup(courses: Course[], tab: (typeof tabs)[number]): Course[] {
  switch (tab) {
    case 'Enrolled':
      return courses.filter((c) => c.enrolled)
    case 'Recently Viewed':
      return courses
        .filter((c) => c.lastViewedAt)
        .sort((a, b) => (a.lastViewedAt! > b.lastViewedAt! ? -1 : 1))
    case 'Continue Learning':
      return courses.filter((c) => c.enrolled && c.progressPct > 0 && c.progressPct < 100)
    case 'Completed':
      return courses.filter((c) => c.progressPct === 100 || c.completedAt)
    case 'Saved':
      return courses.filter((c) => c.saved)
  }
}

/**
 * Student Course Library — the hub connecting Doctor-uploaded courses to
 * the student learning experience. Every published (non-archived) course
 * in the shared catalog is discoverable here; students can enroll, save
 * for later, and jump straight into the full course detail workspace.
 */
export default function StudentCoursesPage() {
  const { courses, toggleEnroll, toggleSaved } = useCourseCatalog()
  const [tab, setTab] = useState<(typeof tabs)[number]>('Continue Learning')
  const [openCourseId, setOpenCourseId] = useState<string | null>(null)

  const discoverable = courses.filter((c) => c.status === 'published')
  const openCourse = courses.find((c) => c.id === openCourseId)

  if (openCourse) {
    return <StudentCourseDetail course={openCourse} onBack={() => setOpenCourseId(null)} />
  }

  const group = courseGroup(discoverable, tab)

  return (
    <div className="space-y-6">
      <Tabs tabs={[...tabs]} active={tab} onChange={(t) => setTab(t as (typeof tabs)[number])} />

      {group.length === 0 ? (
        <div className="glass-card">
          <EmptyState
            icon="📚"
            title={`No courses in "${tab}" yet`}
            body={
              tab === 'Continue Learning'
                ? 'Enroll in a course below to start tracking your progress here.'
                : 'Browse the full catalog and enroll to see it here.'
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {group.map((course, i) => (
            <StudentCourseCard
              key={course.id}
              course={course}
              delay={i * 0.05}
              onOpen={() => setOpenCourseId(course.id)}
              onToggleEnroll={() => toggleEnroll(course.id)}
              onToggleSaved={() => toggleSaved(course.id)}
            />
          ))}
        </div>
      )}

      {/* Full catalog — discover courses not yet in this tab's filter */}
      <div>
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          📖 Browse All Courses
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {discoverable.map((course, i) => (
            <StudentCourseCard
              key={course.id}
              course={course}
              delay={i * 0.04}
              onOpen={() => setOpenCourseId(course.id)}
              onToggleEnroll={() => toggleEnroll(course.id)}
              onToggleSaved={() => toggleSaved(course.id)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function StudentCourseCard({
  course,
  delay,
  onOpen,
  onToggleEnroll,
  onToggleSaved,
}: {
  course: Course
  delay: number
  onOpen: () => void
  onToggleEnroll: () => void
  onToggleSaved: () => void
}) {
  const remaining = remainingLessons(course)
  const total = totalLessons(course)

  return (
    <motion.div
      className="glass-card overflow-hidden group"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      whileHover={{ y: -3 }}
    >
      <div className="relative cursor-pointer" onClick={onOpen}>
        <CourseThumbnail icon={course.icon} color={course.color} />
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggleSaved()
          }}
          className="absolute top-2.5 right-2.5 w-8 h-8 rounded-full flex items-center justify-center text-sm"
          style={{ background: 'rgba(0,0,0,0.4)', color: course.saved ? '#FF7E36' : '#fff' }}
          aria-label={course.saved ? 'Remove from saved' : 'Save course'}
        >
          {course.saved ? '★' : '☆'}
        </button>
        {course.enrolled && (
          <div
            className="absolute bottom-0 left-0 right-0 px-3 py-2 flex items-center gap-2"
            style={{ background: 'rgba(0,0,0,0.5)' }}
          >
            <div
              className="flex-1 h-1.5 rounded-full overflow-hidden"
              style={{ background: 'rgba(255,255,255,0.25)' }}
            >
              <div
                className="h-full rounded-full"
                style={{ width: `${course.progressPct}%`, background: course.color }}
              />
            </div>
            <span className="text-xs font-semibold" style={{ color: '#fff' }}>
              {course.progressPct}%
            </span>
          </div>
        )}
      </div>

      <div className="p-4">
        <div className="flex items-center gap-1.5 mb-1.5">
          <p
            className="text-sm font-semibold flex-1 min-w-0 truncate cursor-pointer"
            style={{ color: 'var(--foreground)' }}
            onClick={onOpen}
          >
            {course.title}
          </p>
          {course.progressPct === 100 && (
            <Badge tone="success" size="xs">
              Completed
            </Badge>
          )}
        </div>
        <p className="text-xs mb-3" style={{ color: 'var(--muted-foreground)' }}>
          {course.doctorName}
        </p>

        {course.enrolled ? (
          <>
            <p className="text-xs mb-3 truncate" style={{ color: course.color }}>
              ▸ {course.lastLessonTitle ?? 'Not started yet'}
            </p>
            <div className="flex items-center justify-between gap-2">
              <Badge size="xs" tone="neutral">
                {remaining} of {total} lessons left
              </Badge>
              <button
                onClick={onOpen}
                className="text-xs font-semibold"
                style={{ color: 'var(--primary)' }}
              >
                Continue →
              </button>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {course.studentsCount.toLocaleString()} students · ★ {course.rating}
            </span>
            <button
              onClick={onToggleEnroll}
              className="text-xs font-semibold px-3 py-1.5 rounded-full flex-shrink-0"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Enroll
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

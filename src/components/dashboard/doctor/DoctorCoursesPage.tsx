import { useState } from 'react'
import { motion } from 'framer-motion'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import type { Course, CourseStatus } from '../../../types/course'
import DoctorCourseCard from './course-management/DoctorCourseCard'
import CreateCourseModal from './course-management/CreateCourseModal'
import EditCourseModal from './course-management/EditCourseModal'
import DoctorCourseDetail from './course-management/DoctorCourseDetail'
import EmptyState from '../shared/EmptyState'

const statusGroups: { status: CourseStatus; label: string; icon: string }[] = [
  { status: 'published', label: 'Published Courses', icon: '✅' },
  { status: 'draft', label: 'Draft Courses', icon: '📝' },
  { status: 'pending-review', label: 'Pending Review', icon: '⏳' },
  { status: 'archived', label: 'Archived Courses', icon: '🗄️' },
]

interface DoctorCoursesPageProps {
  initialCourseId?: string | null
}

/**
 * Doctor "My Courses" workspace — the entry point for the whole course
 * management system. Lists every course grouped by status (Published /
 * Draft / Pending Review / Archived), each with the full action set, and
 * hosts the "Create New Course" flow. Selecting a course opens its full
 * detail workspace (Builder / Students / Analytics tabs). Accepts an
 * optional `initialCourseId` so other pages (e.g. the dashboard home's
 * course widget) can deep-link straight into a specific course.
 */
export default function DoctorCoursesPage({ initialCourseId = null }: DoctorCoursesPageProps) {
  const { courses, createCourse, updateCourseInfo, publishCourse, archiveCourse } =
    useCourseCatalog()
  const [createOpen, setCreateOpen] = useState(false)
  const [editCourseId, setEditCourseId] = useState<string | null>(null)
  const [openCourseId, setOpenCourseId] = useState<string | null>(initialCourseId)
  const [initialTab, setInitialTab] = useState<'Content' | 'Students' | 'Analytics'>('Content')

  const openCourse = courses.find((c) => c.id === openCourseId)
  const editCourse = courses.find((c) => c.id === editCourseId) ?? null

  function openDetail(course: Course, tab: 'Content' | 'Students' | 'Analytics' = 'Content') {
    setOpenCourseId(course.id)
    setInitialTab(tab)
  }

  if (openCourse) {
    return (
      <DoctorCourseDetail
        course={openCourse}
        initialTab={initialTab}
        onBack={() => setOpenCourseId(null)}
      />
    )
  }

  return (
    <div className="space-y-8">
      <motion.div
        className="glass-card p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div>
          <h2
            className="text-base font-bold"
            style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
          >
            Course Management
          </h2>
          <p className="text-xs mt-1 max-w-lg" style={{ color: 'var(--muted-foreground)' }}>
            Create courses, build structured content, and track every student's journey — all in one
            professional teaching workspace.
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="text-sm font-semibold px-5 py-2.5 rounded-full flex-shrink-0"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          + Create New Course
        </button>
      </motion.div>

      {statusGroups.map(({ status, label, icon }) => {
        const group = courses.filter((c) => c.status === status)
        if (group.length === 0) return null
        return (
          <div key={status}>
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
                {icon} {label}
              </h3>
              <span
                className="text-xs px-2 py-0.5 rounded-full font-mono"
                style={{ background: 'var(--tint-2)', color: 'var(--muted-foreground)' }}
              >
                {group.length}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {group.map((course, i) => (
                <DoctorCourseCard
                  key={course.id}
                  course={course}
                  delay={i * 0.05}
                  onEdit={() => setEditCourseId(course.id)}
                  onManageContent={() => openDetail(course, 'Content')}
                  onViewStudents={() => openDetail(course, 'Students')}
                  onAnalytics={() => openDetail(course, 'Analytics')}
                  onPublish={() => publishCourse(course.id)}
                  onArchive={() => archiveCourse(course.id)}
                />
              ))}
            </div>
          </div>
        )
      })}

      {courses.length === 0 && (
        <div className="glass-card">
          <EmptyState
            icon="📚"
            title="No courses yet"
            body="Create your first course to start building your teaching workspace."
            action={
              <button
                onClick={() => setCreateOpen(true)}
                className="text-sm font-semibold px-5 py-2.5 rounded-full"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                + Create New Course
              </button>
            }
          />
        </div>
      )}

      <CreateCourseModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreate={(input) => {
          const created = createCourse(input)
          openDetail(created, 'Content')
        }}
      />

      <EditCourseModal
        course={editCourse}
        onClose={() => setEditCourseId(null)}
        onSave={(input) => {
          if (editCourse) updateCourseInfo(editCourse.id, input)
        }}
      />
    </div>
  )
}

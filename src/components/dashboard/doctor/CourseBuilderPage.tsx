import { useState } from 'react'
import { motion } from 'framer-motion'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import { totalLessons } from '../../../types/course'
import CourseThumbnail from '../shared/CourseThumbnail'
import Badge from '../../ui/Badge'
import CourseBuilder from './course-management/CourseBuilder'
import { statusTone, statusLabel } from './course-management/courseMeta'

/**
 * Standalone "Course Builder" workspace (its own sidebar entry, separate
 * from the "Courses" management list) — pick any course you own and jump
 * straight into its structured Module → Lesson → Resource editor with
 * drag-and-drop reordering.
 */
export default function CourseBuilderPage() {
  const { courses } = useCourseCatalog()
  const [selectedId, setSelectedId] = useState<string | null>(courses[0]?.id ?? null)
  const selected = courses.find((c) => c.id === selectedId)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5">
      {/* Course picker */}
      <motion.div
        className="glass-card p-4 h-fit"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <p className="text-xs font-semibold mb-3 px-1" style={{ color: 'var(--muted-foreground)' }}>
          Select a course to edit
        </p>
        <div className="space-y-1.5 max-h-[70vh] overflow-y-auto scrollbar-thin">
          {courses.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedId(c.id)}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-left transition-all"
              style={{
                background: selectedId === c.id ? 'rgba(45,212,191,0.1)' : 'transparent',
                borderLeft:
                  selectedId === c.id ? '2px solid var(--primary)' : '2px solid transparent',
              }}
            >
              <span className="text-base flex-shrink-0">{c.icon}</span>
              <div className="min-w-0 flex-1">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {c.title}
                </p>
                <p className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                  {c.modules.length} modules · {totalLessons(c)} lessons
                </p>
              </div>
            </button>
          ))}
        </div>
      </motion.div>

      {/* Builder */}
      <div>
        {selected ? (
          <>
            <motion.div
              className="glass-card p-5 mb-4 flex items-center gap-4"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <CourseThumbnail icon={selected.icon} color={selected.color} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <h3 className="text-sm font-bold truncate" style={{ color: 'var(--foreground)' }}>
                    {selected.title}
                  </h3>
                  <Badge tone={statusTone[selected.status]} size="xs">
                    {statusLabel[selected.status]}
                  </Badge>
                </div>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  Drag modules and lessons to reorder. Changes save instantly.
                </p>
              </div>
            </motion.div>
            <CourseBuilder course={selected} />
          </>
        ) : (
          <div
            className="glass-card p-10 text-center text-sm"
            style={{ color: 'var(--muted-foreground)' }}
          >
            Select a course from the left to start building.
          </div>
        )}
      </div>
    </div>
  )
}

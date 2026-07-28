import { useState } from 'react'
import { motion, AnimatePresence, Reorder } from 'framer-motion'
import type { Course, Lesson, LessonType } from '../../../../types/course'
import { useCourseCatalog } from '../../../../context/CourseCatalogContext'
import Badge from '../../../ui/Badge'

interface CourseBuilderProps {
  course: Course
}

const lessonTypeIcon: Record<LessonType, string> = {
  video: '🎬',
  pdf: '📄',
  notes: '📝',
  quiz: '❓',
  assignment: '📋',
}

const lessonTypeLabel: Record<LessonType, string> = {
  video: 'Video',
  pdf: 'PDF',
  notes: 'Notes',
  quiz: 'Quiz',
  assignment: 'Assignment',
}

/**
 * Structured course editor: Course → Modules → Lessons → Resources.
 * Drag-and-drop reordering for both modules and, within an expanded
 * module, its lessons — powered by framer-motion's <Reorder.Group>, the
 * same animation library already used everywhere else in the app.
 */
export default function CourseBuilder({ course }: CourseBuilderProps) {
  const {
    addModule,
    addLesson,
    updateModuleTitle,
    updateLessonTitle,
    deleteLesson,
    deleteModule,
    reorderModules,
    reorderLessons,
    publishCourse,
  } = useCourseCatalog()
  const [expanded, setExpanded] = useState<Record<string, boolean>>(
    Object.fromEntries(course.modules.map((m, i) => [m.id, i === 0]))
  )
  const [addingLessonTo, setAddingLessonTo] = useState<string | null>(null)
  const [newLessonTitle, setNewLessonTitle] = useState('')
  const [newLessonType, setNewLessonType] = useState<LessonType>('video')
  const [newModuleTitle, setNewModuleTitle] = useState('')
  const [addingModule, setAddingModule] = useState(false)
  const [editingModuleId, setEditingModuleId] = useState<string | null>(null)
  const [editingModuleTitle, setEditingModuleTitle] = useState('')
  const [editingLessonId, setEditingLessonId] = useState<string | null>(null)
  const [editingLessonTitle, setEditingLessonTitle] = useState('')
  const [publishedFlash, setPublishedFlash] = useState(false)

  function toggle(id: string) {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  function submitNewModule() {
    if (!newModuleTitle.trim()) return
    addModule(course.id, newModuleTitle.trim())
    setNewModuleTitle('')
    setAddingModule(false)
  }

  function submitNewLesson(moduleId: string) {
    if (!newLessonTitle.trim()) return
    addLesson(course.id, moduleId, newLessonTitle.trim(), newLessonType)
    setNewLessonTitle('')
    setNewLessonType('video')
    setAddingLessonTo(null)
  }

  function startEditModule(moduleId: string, title: string) {
    setEditingModuleId(moduleId)
    setEditingModuleTitle(title)
  }

  function saveModuleEdit(moduleId: string) {
    if (editingModuleTitle.trim()) updateModuleTitle(course.id, moduleId, editingModuleTitle.trim())
    setEditingModuleId(null)
  }

  function startEditLesson(lessonId: string, title: string) {
    setEditingLessonId(lessonId)
    setEditingLessonTitle(title)
  }

  function saveLessonEdit(moduleId: string, lessonId: string) {
    if (editingLessonTitle.trim())
      updateLessonTitle(course.id, moduleId, lessonId, editingLessonTitle.trim())
    setEditingLessonId(null)
  }

  function handlePublishUpdates() {
    publishCourse(course.id)
    setPublishedFlash(true)
    setTimeout(() => setPublishedFlash(false), 2400)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          Drag modules and lessons to reorder. All edits save instantly.
        </p>
        <AnimatePresence mode="wait">
          {publishedFlash ? (
            <motion.span
              key="flash"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="text-xs font-semibold px-3.5 py-2 rounded-full flex items-center gap-1.5"
              style={{ background: 'var(--success-soft)', color: 'var(--success)' }}
            >
              ✓ Updates published
            </motion.span>
          ) : (
            <motion.button
              key="publish"
              onClick={handlePublishUpdates}
              className="text-xs font-semibold px-3.5 py-2 rounded-full"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Publish Updates
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      <Reorder.Group
        axis="y"
        values={course.modules}
        onReorder={(modules) => reorderModules(course.id, modules)}
        className="space-y-3"
      >
        {course.modules.map((mod, mi) => (
          <Reorder.Item
            key={mod.id}
            value={mod}
            className="glass-card overflow-hidden"
            whileDrag={{ scale: 1.01, boxShadow: '0 12px 32px rgba(0,0,0,0.25)' }}
          >
            {/* Module header */}
            <div
              className="flex items-center gap-3 px-4 py-3.5 cursor-pointer select-none"
              onClick={() => toggle(mod.id)}
            >
              <span
                className="text-sm cursor-grab active:cursor-grabbing flex-shrink-0"
                style={{ color: 'var(--muted-foreground)' }}
                title="Drag to reorder"
              >
                ⠿
              </span>
              <span
                className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{ background: 'rgba(45,212,191,0.12)', color: 'var(--primary)' }}
              >
                {mi + 1}
              </span>
              <div className="flex-1 min-w-0">
                {editingModuleId === mod.id ? (
                  <input
                    autoFocus
                    value={editingModuleTitle}
                    onChange={(e) => setEditingModuleTitle(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.key === 'Enter' && saveModuleEdit(mod.id)}
                    onBlur={() => saveModuleEdit(mod.id)}
                    className="input-field w-full px-2 py-1 rounded-md text-sm"
                  />
                ) : (
                  <p
                    className="text-sm font-semibold truncate"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {mod.title}
                  </p>
                )}
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {mod.lessons.length} lesson{mod.lessons.length === 1 ? '' : 's'}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  startEditModule(mod.id, mod.title)
                }}
                className="text-xs px-2 py-1 rounded-lg flex-shrink-0"
                style={{ color: 'var(--primary)' }}
              >
                Edit
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  deleteModule(course.id, mod.id)
                }}
                className="text-xs px-2 py-1 rounded-lg flex-shrink-0"
                style={{ color: 'var(--danger)' }}
              >
                Delete
              </button>
              <motion.span
                animate={{ rotate: expanded[mod.id] ? 90 : 0 }}
                className="flex-shrink-0"
                style={{ color: 'var(--muted-foreground)' }}
              >
                ›
              </motion.span>
            </div>

            {/* Lessons */}
            <AnimatePresence>
              {expanded[mod.id] && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="border-t"
                  style={{ borderColor: 'var(--border-subtle)' }}
                >
                  <Reorder.Group
                    axis="y"
                    values={mod.lessons}
                    onReorder={(lessons: Lesson[]) => reorderLessons(course.id, mod.id, lessons)}
                    className="px-4 py-2 space-y-1.5"
                  >
                    {mod.lessons.map((lesson) => (
                      <Reorder.Item
                        key={lesson.id}
                        value={lesson}
                        className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg"
                        style={{ background: 'var(--tint-1)' }}
                        whileDrag={{ scale: 1.01 }}
                      >
                        <span
                          className="text-xs cursor-grab active:cursor-grabbing flex-shrink-0"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          ⠿
                        </span>
                        <span className="text-sm flex-shrink-0">{lessonTypeIcon[lesson.type]}</span>
                        {editingLessonId === lesson.id ? (
                          <input
                            autoFocus
                            value={editingLessonTitle}
                            onChange={(e) => setEditingLessonTitle(e.target.value)}
                            onKeyDown={(e) =>
                              e.key === 'Enter' && saveLessonEdit(mod.id, lesson.id)
                            }
                            onBlur={() => saveLessonEdit(mod.id, lesson.id)}
                            className="input-field flex-1 min-w-0 px-2 py-1 rounded-md text-sm"
                          />
                        ) : (
                          <span
                            className="text-sm flex-1 min-w-0 truncate"
                            style={{ color: 'var(--foreground)' }}
                          >
                            {lesson.title}
                          </span>
                        )}
                        <Badge tone="neutral" size="xs">
                          {lessonTypeLabel[lesson.type]}
                        </Badge>
                        {lesson.resources.length > 0 && (
                          <span
                            className="text-xs flex-shrink-0"
                            style={{ color: 'var(--muted-foreground)' }}
                            title={lesson.resources.map((r) => r.name).join(', ')}
                          >
                            📎 {lesson.resources.length}
                          </span>
                        )}
                        {lesson.durationMinutes !== undefined && (
                          <span
                            className="text-xs flex-shrink-0 font-mono"
                            style={{ color: 'var(--muted-foreground)' }}
                          >
                            {lesson.durationMinutes}m
                          </span>
                        )}
                        <button
                          onClick={() => startEditLesson(lesson.id, lesson.title)}
                          className="text-xs flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center"
                          style={{ color: 'var(--primary)' }}
                          aria-label="Edit lesson"
                        >
                          ✎
                        </button>
                        <button
                          onClick={() => deleteLesson(course.id, mod.id, lesson.id)}
                          className="text-xs flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center"
                          style={{ color: 'var(--muted-foreground)' }}
                          aria-label="Delete lesson"
                        >
                          ✕
                        </button>
                      </Reorder.Item>
                    ))}
                  </Reorder.Group>

                  {/* Add lesson */}
                  <div className="px-4 pb-3.5 pt-1">
                    {addingLessonTo === mod.id ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          autoFocus
                          value={newLessonTitle}
                          onChange={(e) => setNewLessonTitle(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && submitNewLesson(mod.id)}
                          placeholder="Lesson title"
                          className="input-field flex-1 min-w-[140px] px-3 py-1.5 rounded-lg text-xs"
                        />
                        <select
                          value={newLessonType}
                          onChange={(e) => setNewLessonType(e.target.value as LessonType)}
                          className="input-field px-2 py-1.5 rounded-lg text-xs"
                        >
                          {(Object.keys(lessonTypeLabel) as LessonType[]).map((t) => (
                            <option key={t} value={t}>
                              {lessonTypeLabel[t]}
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => submitNewLesson(mod.id)}
                          className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                          style={{
                            background: 'var(--primary)',
                            color: 'var(--primary-foreground)',
                          }}
                        >
                          Add
                        </button>
                        <button
                          onClick={() => setAddingLessonTo(null)}
                          className="text-xs px-2 py-1.5"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setAddingLessonTo(mod.id)}
                        className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                        style={{ background: 'var(--tint-2)', color: 'var(--primary)' }}
                      >
                        + Add Lesson
                      </button>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Reorder.Item>
        ))}
      </Reorder.Group>

      {/* Add module */}
      <div className="glass-card p-4">
        {addingModule ? (
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={newModuleTitle}
              onChange={(e) => setNewModuleTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitNewModule()}
              placeholder="Module title (e.g. Advanced Topics)"
              className="input-field flex-1 px-3.5 py-2 rounded-lg text-sm"
            />
            <button
              onClick={submitNewModule}
              className="text-sm font-semibold px-4 py-2 rounded-lg"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Add
            </button>
            <button
              onClick={() => setAddingModule(false)}
              className="text-sm px-2"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAddingModule(true)}
            className="w-full text-sm font-semibold py-1.5"
            style={{ color: 'var(--primary)' }}
          >
            + Add Module
          </button>
        )}
      </div>
    </div>
  )
}

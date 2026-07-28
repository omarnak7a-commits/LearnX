import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Course, Lesson, LessonType } from '../../../../types/course'
import { totalLessons, completedLessons } from '../../../../types/course'
import { useCourseCatalog } from '../../../../context/CourseCatalogContext'
import CourseThumbnail from '../../shared/CourseThumbnail'
import ProgressRing from '../../../ui/ProgressRing'
import CourseAIPanel, { type AITool } from './CourseAIPanel'

interface StudentCourseDetailProps {
  course: Course
  onBack: () => void
}

const lessonTypeIcon: Record<LessonType, string> = {
  video: '🎬',
  pdf: '📄',
  notes: '📝',
  quiz: '❓',
  assignment: '📋',
}

/**
 * Student-facing course detail — header (thumbnail, doctor profile,
 * description, progress), the full module/lesson content tree, and the
 * AI action bar (Ask AI / Generate Quiz / Create Flashcards / Create
 * Summary / Download Materials) that opens the shared CourseAIPanel.
 */
export default function StudentCourseDetail({ course, onBack }: StudentCourseDetailProps) {
  const { toggleEnroll, markLessonComplete } = useCourseCatalog()
  const [aiTool, setAiTool] = useState<AITool | null>(null)
  const [expandedModule, setExpandedModule] = useState<string | null>(course.modules[0]?.id ?? null)
  const [downloadState, setDownloadState] = useState<'idle' | 'preparing' | 'ready'>('idle')

  const total = totalLessons(course)
  const done = completedLessons(course)
  const allResources = course.modules.flatMap((m) => m.lessons.flatMap((l) => l.resources))

  function findNextLesson(): Lesson | null {
    for (const m of course.modules) {
      const next = m.lessons.find((l) => !l.completed)
      if (next) return next
    }
    return null
  }

  const nextLesson = findNextLesson()

  function handleDownload() {
    if (downloadState !== 'idle') return
    setDownloadState('preparing')
    setTimeout(() => setDownloadState('ready'), 1400)
  }

  return (
    <div className="space-y-5">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs font-semibold"
        style={{ color: 'var(--muted-foreground)' }}
      >
        ← Back to My Courses
      </button>

      {/* Course header */}
      <motion.div
        className="glass-card p-6 flex flex-col sm:flex-row gap-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <CourseThumbnail
          icon={course.icon}
          color={course.color}
          size="sm"
          className="sm:w-32 sm:h-32 w-full"
        />
        <div className="flex-1 min-w-0">
          <h2
            className="text-lg font-bold mb-1.5"
            style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
          >
            {course.title}
          </h2>
          <div className="flex items-center gap-2.5 mb-3">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
              style={{
                background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
                color: 'var(--primary-foreground)',
              }}
            >
              {course.doctorInitials}
            </div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {course.doctorName} · {course.department}
            </span>
          </div>
          <p className="text-sm mb-4 max-w-2xl" style={{ color: 'var(--muted-foreground)' }}>
            {course.description}
          </p>

          <div className="flex items-center gap-4 flex-wrap">
            {course.enrolled ? (
              <div className="flex items-center gap-3">
                <ProgressRing
                  pct={course.progressPct}
                  color={course.color}
                  size={52}
                  strokeWidth={5}
                />
                <div>
                  <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
                    {done} of {total} lessons complete
                  </p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    {course.progressPct === 100 ? 'Course completed 🎉' : 'Keep going!'}
                  </p>
                </div>
              </div>
            ) : (
              <button
                onClick={() => toggleEnroll(course.id)}
                className="text-sm font-semibold px-5 py-2.5 rounded-full"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                Enroll in this course
              </button>
            )}
          </div>
        </div>
      </motion.div>

      {/* Action bar */}
      <div className="flex flex-wrap gap-2">
        {course.enrolled && nextLesson && (
          <ActionChip
            icon="▶️"
            label="Continue Learning"
            primary
            onClick={() => markLessonComplete(course.id, nextLesson.id)}
          />
        )}
        <ActionChip icon="⬇️" label="Download Materials" onClick={handleDownload} />
        <ActionChip icon="✨" label="Ask AI About Course" onClick={() => setAiTool('chat')} />
        <ActionChip icon="❓" label="Generate Quiz" onClick={() => setAiTool('quiz')} />
        <ActionChip icon="🗂️" label="Create Flashcards" onClick={() => setAiTool('flashcards')} />
        <ActionChip icon="💡" label="Create Summary" onClick={() => setAiTool('summary')} />
        <ActionChip icon="🧠" label="Mind Map" onClick={() => setAiTool('mindmap')} />
        <ActionChip icon="⭐" label="Important Questions" onClick={() => setAiTool('important')} />
        <ActionChip icon="📅" label="Study Plan" onClick={() => setAiTool('plan')} />
      </div>

      <AnimatePresence>
        {downloadState !== 'idle' && (
          <motion.div
            className="glass-card px-4 py-3 flex items-center gap-3"
            initial={{ opacity: 0, y: -8, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            {downloadState === 'preparing' ? (
              <>
                <div
                  className="w-4 h-4 rounded-full border-2 border-t-transparent animate-spin flex-shrink-0"
                  style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent' }}
                />
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  Preparing {allResources.length > 0 ? allResources.length : total} file
                  {allResources.length === 1 ? '' : 's'} for download…
                </p>
              </>
            ) : (
              <>
                <span className="text-sm flex-shrink-0" style={{ color: 'var(--success)' }}>
                  ✓
                </span>
                <p className="text-xs" style={{ color: 'var(--foreground)' }}>
                  {allResources.length > 0
                    ? `${allResources.length} material${allResources.length === 1 ? '' : 's'} ready — ${allResources.map((r) => r.name).join(', ')}`
                    : `All ${total} lesson materials for ${course.title} are ready.`}
                </p>
                <button
                  onClick={() => setDownloadState('idle')}
                  className="ml-auto text-xs font-semibold flex-shrink-0"
                  style={{ color: 'var(--primary)' }}
                >
                  Dismiss
                </button>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content tree */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          Course Content
        </h3>
        <div className="space-y-2">
          {course.modules.map((m, mi) => (
            <div
              key={m.id}
              className="rounded-xl overflow-hidden"
              style={{ border: '1px solid var(--border-subtle)' }}
            >
              <button
                onClick={() => setExpandedModule((e) => (e === m.id ? null : m.id))}
                className="w-full flex items-center gap-3 px-4 py-3 text-left"
                style={{ background: 'var(--tint-1)' }}
              >
                <span
                  className="w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                  style={{ background: 'rgba(45,212,191,0.12)', color: 'var(--primary)' }}
                >
                  {mi + 1}
                </span>
                <span
                  className="text-sm font-semibold flex-1"
                  style={{ color: 'var(--foreground)' }}
                >
                  {m.title}
                </span>
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {m.lessons.filter((l) => l.completed).length}/{m.lessons.length}
                </span>
                <motion.span
                  animate={{ rotate: expandedModule === m.id ? 90 : 0 }}
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  ›
                </motion.span>
              </button>
              <AnimatePresence>
                {expandedModule === m.id && (
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: 'auto' }}
                    exit={{ height: 0 }}
                    transition={{ duration: 0.2 }}
                    style={{ overflow: 'hidden' }}
                  >
                    <div className="p-2 space-y-1">
                      {m.lessons.map((l) => (
                        <button
                          key={l.id}
                          onClick={() =>
                            course.enrolled && !l.completed && markLessonComplete(course.id, l.id)
                          }
                          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-colors"
                          style={{
                            background: l.completed ? 'rgba(45,212,191,0.06)' : 'transparent',
                          }}
                          disabled={!course.enrolled}
                        >
                          <span
                            className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center"
                            style={{
                              background: l.completed ? 'rgba(45,212,191,0.15)' : 'transparent',
                              border: `1.5px solid ${l.completed ? 'var(--primary)' : 'var(--border)'}`,
                            }}
                          >
                            {l.completed && (
                              <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
                                <path
                                  d="M2 5l2.5 2.5 4-4"
                                  stroke="#2DD4BF"
                                  strokeWidth="1.5"
                                  strokeLinecap="round"
                                />
                              </svg>
                            )}
                          </span>
                          <span className="text-sm flex-shrink-0">{lessonTypeIcon[l.type]}</span>
                          <span
                            className="text-sm flex-1 min-w-0 truncate"
                            style={{
                              color: l.completed ? 'var(--muted-foreground)' : 'var(--foreground)',
                              textDecoration: l.completed ? 'line-through' : 'none',
                            }}
                          >
                            {l.title}
                          </span>
                          {l.resources.length > 0 && (
                            <span
                              className="text-xs flex-shrink-0 flex items-center gap-1"
                              style={{ color: 'var(--muted-foreground)' }}
                              title={l.resources.map((r) => r.name).join(', ')}
                            >
                              📎 {l.resources.length}
                            </span>
                          )}
                          {l.durationMinutes !== undefined && (
                            <span
                              className="text-xs flex-shrink-0 font-mono"
                              style={{ color: 'var(--muted-foreground)' }}
                            >
                              {l.durationMinutes}m
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </motion.div>

      <AnimatePresence>
        {aiTool && (
          <CourseAIPanel course={course} initialTool={aiTool} onClose={() => setAiTool(null)} />
        )}
      </AnimatePresence>
    </div>
  )
}

function ActionChip({
  icon,
  label,
  onClick,
  primary = false,
}: {
  icon: string
  label: string
  onClick: () => void
  primary?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-full transition-all"
      style={
        primary
          ? { background: 'var(--primary)', color: 'var(--primary-foreground)' }
          : { background: 'var(--tint-2)', color: 'var(--foreground)' }
      }
    >
      <span>{icon}</span>
      {label}
    </button>
  )
}

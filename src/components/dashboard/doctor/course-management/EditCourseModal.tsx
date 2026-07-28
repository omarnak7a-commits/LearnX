import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Course, CourseType } from '../../../../types/course'
import { courseTypeLabel } from './courseMeta'

interface EditCourseModalProps {
  course: Course | null
  onClose: () => void
  onSave: (input: {
    title: string
    description: string
    category: string
    faculty: string
    academicLevel: string
    courseType: CourseType
  }) => void
}

const categories = [
  'Computer Science',
  'Mathematics',
  'Physics',
  'Chemistry',
  'Biology',
  'Business',
  'Design',
]

const academicLevels = [
  'Undergraduate · Year 1',
  'Undergraduate · Year 2',
  'Undergraduate · Year 3',
  'Undergraduate · Year 4',
  'Postgraduate',
]

/** "Edit Course" — updates a course's basic info (title, description,
 * category, faculty, academic level, type) without touching its content
 * tree (that lives in the Course Builder). Reuses the same field style as
 * the Create Course flow for visual/interaction consistency. */
export default function EditCourseModal({ course, onClose, onSave }: EditCourseModalProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState(categories[0])
  const [faculty, setFaculty] = useState('Faculty of Engineering')
  const [academicLevel, setAcademicLevel] = useState(academicLevels[0])
  const [courseType, setCourseType] = useState<CourseType>('university')

  useEffect(() => {
    if (!course) return
    setTitle(course.title)
    setDescription(course.description)
    setCategory(course.category)
    setFaculty(course.faculty)
    setAcademicLevel(course.academicLevel)
    setCourseType(course.courseType)
  }, [course])

  function handleSave() {
    onSave({ title, description, category, faculty, academicLevel, courseType })
    onClose()
  }

  return (
    <AnimatePresence>
      {course && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0"
            style={{ background: 'var(--overlay-bg)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
          />

          <motion.div
            className="relative w-full max-w-lg max-h-[85vh] overflow-y-auto scrollbar-thin rounded-2xl"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            <div
              className="flex items-center justify-between px-6 py-5 border-b"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              <h3
                className="text-base font-bold"
                style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
              >
                Edit Course
              </h3>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ color: 'var(--muted-foreground)' }}
                aria-label="Close"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-4">
              <Field label="Course Title">
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                  autoFocus
                />
              </Field>
              <Field label="Description">
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm resize-none"
                />
              </Field>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Category">
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Academic Level">
                  <select
                    value={academicLevel}
                    onChange={(e) => setAcademicLevel(e.target.value)}
                    className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                  >
                    {academicLevels.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Faculty">
                <select
                  value={faculty}
                  onChange={(e) => setFaculty(e.target.value)}
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                >
                  {[
                    'Faculty of Engineering',
                    'Faculty of Science',
                    'Faculty of Business',
                    'Faculty of Arts',
                  ].map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Course Type">
                <select
                  value={courseType}
                  onChange={(e) => setCourseType(e.target.value as CourseType)}
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                >
                  {(['university', 'public', 'premium'] as CourseType[]).map((t) => (
                    <option key={t} value={t}>
                      {courseTypeLabel[t]}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div
              className="flex items-center justify-end gap-2 px-6 py-4 border-t"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              <button
                onClick={onClose}
                className="text-sm font-medium px-4 py-2 rounded-lg"
                style={{ color: 'var(--muted-foreground)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="text-sm font-semibold px-5 py-2.5 rounded-full"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                Save Changes
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label
        className="text-xs font-semibold mb-1.5 block"
        style={{ color: 'var(--muted-foreground)' }}
      >
        {label}
      </label>
      {children}
    </div>
  )
}

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { CourseType } from '../../../../types/course'
import DropZone from '../../shared/DropZone'
import { courseTypeLabel } from './courseMeta'

interface CreateCourseModalProps {
  open: boolean
  onClose: () => void
  onCreate: (input: {
    title: string
    description: string
    category: string
    faculty: string
    department: string
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

const steps = ['Basic Information', 'Course Type', 'Upload Materials'] as const

/**
 * Full "Create New Course" flow — basic info, course type selection, and
 * upload surfaces for thumbnail/intro video/lectures/resources. Uploads
 * reuse the existing DropZone component so the interaction language matches
 * the rest of the app exactly (same drag/drop, same progress bars).
 */
export default function CreateCourseModal({ open, onClose, onCreate }: CreateCourseModalProps) {
  const [step, setStep] = useState(0)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState(categories[0])
  const [faculty, setFaculty] = useState('Faculty of Engineering')
  const [academicLevel, setAcademicLevel] = useState(academicLevels[0])
  const [courseType, setCourseType] = useState<CourseType>('university')

  function reset() {
    setStep(0)
    setTitle('')
    setDescription('')
    setCategory(categories[0])
    setFaculty('Faculty of Engineering')
    setAcademicLevel(academicLevels[0])
    setCourseType('university')
  }

  function handleClose() {
    reset()
    onClose()
  }

  function handleSubmit() {
    onCreate({
      title,
      description,
      category,
      faculty,
      department: `${category.slice(0, 4).toUpperCase()} · ${category}`,
      academicLevel,
      courseType,
    })
    handleClose()
  }

  const canContinue = step === 0 ? title.trim().length > 0 : true

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0"
            style={{ background: 'var(--overlay-bg)', backdropFilter: 'blur(4px)' }}
            onClick={handleClose}
          />

          <motion.div
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto scrollbar-thin rounded-2xl"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-6 py-5 border-b sticky top-0 z-10"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--surface-2)' }}
            >
              <div>
                <h3
                  className="text-base font-bold"
                  style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
                >
                  Create New Course
                </h3>
                <div className="flex items-center gap-1.5 mt-2">
                  {steps.map((s, i) => (
                    <div key={s} className="flex items-center gap-1.5">
                      <span
                        className="w-1.5 h-1.5 rounded-full transition-colors"
                        style={{ background: i <= step ? 'var(--primary)' : 'var(--tint-5)' }}
                      />
                      <span
                        className="text-xs hidden sm:inline"
                        style={{ color: i === step ? 'var(--primary)' : 'var(--muted-foreground)' }}
                      >
                        {s}
                      </span>
                      {i < steps.length - 1 && (
                        <span
                          className="w-4 h-px mx-0.5"
                          style={{ background: 'var(--border-subtle)' }}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <button
                onClick={handleClose}
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

            {/* Body */}
            <div className="p-6">
              <AnimatePresence mode="wait">
                {step === 0 && (
                  <motion.div
                    key="basic"
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -12 }}
                    transition={{ duration: 0.2 }}
                    className="space-y-4"
                  >
                    <Field label="Course Title">
                      <input
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Advanced Quantum Mechanics"
                        className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                        autoFocus
                      />
                    </Field>
                    <Field label="Description">
                      <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="What will students learn in this course?"
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
                  </motion.div>
                )}

                {step === 1 && (
                  <motion.div
                    key="type"
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -12 }}
                    transition={{ duration: 0.2 }}
                  >
                    <p
                      className="text-xs font-semibold mb-3"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      Course Type
                    </p>
                    <div className="grid grid-cols-1 gap-3">
                      {(['university', 'public', 'premium'] as CourseType[]).map((t) => (
                        <button
                          key={t}
                          onClick={() => setCourseType(t)}
                          className="text-left p-4 rounded-xl transition-all flex items-start gap-3"
                          style={{
                            background:
                              courseType === t ? 'rgba(45,212,191,0.08)' : 'var(--tint-1)',
                            border: `1.5px solid ${courseType === t ? 'var(--primary)' : 'var(--border-subtle)'}`,
                          }}
                        >
                          <span
                            className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                            style={{
                              border: `2px solid ${courseType === t ? 'var(--primary)' : 'var(--border)'}`,
                            }}
                          >
                            {courseType === t && (
                              <span
                                className="w-2.5 h-2.5 rounded-full"
                                style={{ background: 'var(--primary)' }}
                              />
                            )}
                          </span>
                          <div>
                            <p
                              className="text-sm font-semibold"
                              style={{ color: 'var(--foreground)' }}
                            >
                              {courseTypeLabel[t]}
                            </p>
                            <p
                              className="text-xs mt-0.5"
                              style={{ color: 'var(--muted-foreground)' }}
                            >
                              {t === 'university' &&
                                'Enrolled students only, tied to a faculty and department.'}
                              {t === 'public' && 'Open to any LearnX student, free to enroll.'}
                              {t === 'premium' &&
                                'Paid course with premium materials and priority AI support.'}
                            </p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}

                {step === 2 && (
                  <motion.div
                    key="upload"
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -12 }}
                    transition={{ duration: 0.2 }}
                    className="space-y-4"
                  >
                    <div>
                      <p
                        className="text-xs font-semibold mb-2"
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        Course Thumbnail & Intro Video
                      </p>
                      <DropZone
                        title="Drag & drop thumbnail or intro video"
                        subtitle="PNG, JPG, or MP4 — up to 200MB"
                        accept="image/*,.mp4,.mov"
                      />
                    </div>
                    <div>
                      <p
                        className="text-xs font-semibold mb-2"
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        Lecture Videos, PDFs, PPTs, DOCX, Assignments, Exams & Resources
                      </p>
                      <DropZone
                        title="Drag & drop course materials"
                        subtitle="Video, PDF, PPT, DOCX, assignment, or exam files"
                        accept=".pdf,.ppt,.pptx,.doc,.docx,.mp4,.mov"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Footer */}
            <div
              className="flex items-center justify-between px-6 py-4 border-t sticky bottom-0"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--surface-2)' }}
            >
              <button
                onClick={() => (step === 0 ? handleClose() : setStep((s) => s - 1))}
                className="text-sm font-medium px-4 py-2 rounded-lg"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {step === 0 ? 'Cancel' : '← Back'}
              </button>
              {step < steps.length - 1 ? (
                <button
                  onClick={() => canContinue && setStep((s) => s + 1)}
                  disabled={!canContinue}
                  className="text-sm font-semibold px-5 py-2.5 rounded-full transition-opacity"
                  style={{
                    background: 'var(--primary)',
                    color: 'var(--primary-foreground)',
                    opacity: canContinue ? 1 : 0.5,
                  }}
                >
                  Continue →
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  className="text-sm font-semibold px-5 py-2.5 rounded-full"
                  style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                >
                  ✓ Save as Draft
                </button>
              )}
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

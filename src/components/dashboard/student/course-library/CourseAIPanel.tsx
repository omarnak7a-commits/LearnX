import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Course } from '../../../../types/course'

interface CourseAIPanelProps {
  course: Course
  initialTool: AITool
  onClose: () => void
}

export type AITool = 'chat' | 'summary' | 'flashcards' | 'quiz' | 'mindmap' | 'important' | 'plan'

const TOOLS: Array<{ id: AITool; label: string; icon: string }> = [
  { id: 'chat', label: 'Ask AI', icon: '✨' },
  { id: 'summary', label: 'Summary', icon: '💡' },
  { id: 'flashcards', label: 'Flashcards', icon: '🗂️' },
  { id: 'quiz', label: 'Quiz', icon: '❓' },
  { id: 'mindmap', label: 'Mind Map', icon: '🧠' },
  { id: 'important', label: 'Important Questions', icon: '⭐' },
  { id: 'plan', label: 'Study Plan', icon: '📅' },
]

const suggestions = [
  'Explain this lecture',
  'Summarize this chapter',
  'Create exam questions',
  'Find important topics',
]

function allLessonTitles(course: Course): string[] {
  return course.modules.flatMap((m) => m.lessons.map((l) => l.title))
}

function generateAnswer(question: string, course: Course): string {
  const lower = question.toLowerCase()
  const titles = allLessonTitles(course)
  const first = titles[0] ?? course.title
  const topic = course.analytics.strugglingTopic

  if (lower.includes('summar')) {
    return `Here's a quick summary of ${course.title}: the course covers ${course.modules
      .map((m) => m.title)
      .join(
        ', '
      )}. Start with "${first}" and build up from there — most students find "${topic}" the trickiest part, so budget extra time for it.`
  }
  if (lower.includes('explain')) {
    return `Let's break down "${first}" from ${course.title}. This lesson builds on the fundamentals from Module 1, and connects directly to ${topic} later in the course. Want me to generate a step-by-step walkthrough?`
  }
  if (lower.includes('exam') || lower.includes('question')) {
    return `Based on ${course.doctorName}'s materials, here are likely exam angles for ${course.title}: definitions and worked examples from "${first}", plus at least one question testing ${topic} — that's the topic ${course.analytics.strugglingPct}% of students found hardest.`
  }
  if (lower.includes('important') || lower.includes('topic')) {
    return `The highest-weight topics in ${course.title} are: ${course.modules
      .slice(0, 2)
      .map((m) => m.title)
      .join(
        ', '
      )}. Pay special attention to ${topic} — it shows up in the quiz analytics as the biggest knowledge gap.`
  }
  return `Great question about "${question.slice(0, 60)}" — drawing from ${course.title}'s materials (${titles.length} lessons across ${course.modules.length} modules), here's what stands out: focus on ${topic} first, then work through the rest of ${course.modules[0]?.title ?? 'Module 1'} in order.`
}

function buildSummary(course: Course) {
  return course.modules.map((m) => ({
    title: m.title,
    points: m.lessons
      .slice(0, 3)
      .map((l) => `${l.title} — key concept covered in ${l.durationMinutes ?? 15} min`),
  }))
}

interface FlashcardData {
  id: string
  question: string
  answer: string
}

function buildFlashcards(course: Course): FlashcardData[] {
  return allLessonTitles(course)
    .slice(0, 6)
    .map((title, i) => ({
      id: `${course.id}-fc-${i}`,
      question: `What is the core idea behind "${title}"?`,
      answer: `"${title}" is a key concept from ${course.title}, taught by ${course.doctorName}. Review the lesson materials and course notes for the full explanation.`,
    }))
}

interface QuizQ {
  id: string
  prompt: string
  options: string[]
  correctIndex: number
}

function buildQuiz(course: Course): QuizQ[] {
  const titles = allLessonTitles(course)
  return titles.slice(0, 5).map((title, i) => ({
    id: `${course.id}-q-${i}`,
    prompt: `Which module does "${title}" belong to?`,
    options: course.modules.map((m) => m.title),
    correctIndex: course.modules.findIndex((m) => m.lessons.some((l) => l.title === title)),
  }))
}

interface ImportantQuestion {
  id: string
  question: string
  reason: string
}

function buildImportantQuestions(course: Course): ImportantQuestion[] {
  const a = course.analytics
  const titles = allLessonTitles(course)
  const questions: ImportantQuestion[] = [
    {
      id: `${course.id}-iq-1`,
      question: `Explain the key concept behind "${a.strugglingTopic}" in ${course.title}.`,
      reason: `${a.strugglingPct}% of students found this topic the hardest — high exam likelihood.`,
    },
    {
      id: `${course.id}-iq-2`,
      question: `Walk through "${a.mostViewedLessonTitle}" step by step.`,
      reason: 'Most-viewed lesson in this course — foundational material examiners often test.',
    },
  ]
  if (titles[titles.length - 1]) {
    questions.push({
      id: `${course.id}-iq-3`,
      question: `Compare and contrast the ideas covered in "${titles[titles.length - 1]}" with earlier lessons.`,
      reason: 'Later lessons often synthesize earlier material — a common exam question pattern.',
    })
  }
  return questions
}

interface StudyPlanDay {
  day: string
  focus: string
  lessons: string[]
}

function buildStudyPlan(course: Course): StudyPlanDay[] {
  const remaining = course.modules
    .flatMap((m) => m.lessons.map((l) => ({ module: m.title, lesson: l })))
    .filter((entry) => !entry.lesson.completed)

  if (remaining.length === 0) {
    return []
  }

  const dayNames = ['Today', 'Tomorrow', 'Day 3', 'Day 4', 'Day 5']
  const chunkSize = Math.max(1, Math.ceil(remaining.length / dayNames.length))
  const days: StudyPlanDay[] = []
  for (let i = 0; i < dayNames.length && i * chunkSize < remaining.length; i++) {
    const chunk = remaining.slice(i * chunkSize, (i + 1) * chunkSize)
    days.push({
      day: dayNames[i],
      focus: chunk[0]?.module ?? course.modules[0]?.title ?? course.title,
      lessons: chunk.map((c) => c.lesson.title),
    })
  }
  return days
}

/**
 * Every Doctor-uploaded course becomes an AI learning source. This panel
 * hosts AI Chat, Summary, Flashcards, Quiz, and Mind Map generation —
 * all grounded in the course's own modules/lessons/analytics so answers
 * reference real course materials rather than generic placeholder text.
 */
export default function CourseAIPanel({ course, initialTool, onClose }: CourseAIPanelProps) {
  const [tool, setTool] = useState<AITool>(initialTool)
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([
    {
      role: 'assistant',
      text: `Hi! I'm your AI tutor for ${course.title}. I've indexed all ${course.modules.length} modules — ask me anything about the material.`,
    },
  ])
  const [input, setInput] = useState('')

  const summary = useMemo(() => buildSummary(course), [course])
  const flashcards = useMemo(() => buildFlashcards(course), [course])
  const quiz = useMemo(() => buildQuiz(course), [course])
  const importantQuestions = useMemo(() => buildImportantQuestions(course), [course])
  const studyPlan = useMemo(() => buildStudyPlan(course), [course])

  const [cardIndex, setCardIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [quizIndex, setQuizIndex] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [score, setScore] = useState(0)

  function send(text: string) {
    if (!text.trim()) return
    setMessages((prev) => [
      ...prev,
      { role: 'user', text },
      { role: 'assistant', text: generateAnswer(text, course) },
    ])
    setInput('')
  }

  function submitQuizAnswer(idx: number) {
    if (selected !== null) return
    setSelected(idx)
    if (idx === quiz[quizIndex]?.correctIndex) setScore((s) => s + 1)
  }

  function nextQuiz() {
    setSelected(null)
    setQuizIndex((i) => Math.min(quiz.length - 1, i + 1))
  }

  return (
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
        className="relative w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-2xl flex flex-col"
        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 24, scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 320, damping: 30 }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
              AI Learning Tools
            </p>
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {course.title}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center"
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

        {/* Tool tabs */}
        <div className="flex items-center gap-1 px-4 pt-3 flex-wrap">
          {TOOLS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTool(t.id)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
              style={{
                background: tool === t.id ? 'var(--primary)' : 'var(--tint-2)',
                color: tool === t.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-5">
          <AnimatePresence mode="wait">
            {tool === 'chat' && (
              <motion.div
                key="chat"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col h-full"
              >
                <div className="space-y-3 flex-1">
                  {messages.map((m, i) => (
                    <div
                      key={i}
                      className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className="max-w-[85%] px-3 py-2 rounded-xl text-sm leading-relaxed"
                        style={{
                          background: m.role === 'user' ? 'rgba(45,212,191,0.15)' : 'var(--tint-3)',
                          color: 'var(--foreground)',
                          borderRadius:
                            m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                        }}
                      >
                        {m.text}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-1.5 mt-4 mb-3">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="text-xs px-2.5 py-1 rounded-full"
                      style={{
                        background: 'rgba(45,212,191,0.08)',
                        color: 'var(--primary)',
                        border: '1px solid rgba(45,212,191,0.2)',
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    send(input)
                  }}
                  className="flex items-center gap-2"
                >
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={`Ask about ${course.title}...`}
                    className="input-field flex-1 px-3.5 py-2.5 rounded-lg text-sm"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2.5 rounded-lg text-sm font-semibold flex-shrink-0"
                    style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                  >
                    Send
                  </button>
                </form>
              </motion.div>
            )}

            {tool === 'summary' && (
              <motion.div
                key="summary"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                {summary.map((s) => (
                  <div
                    key={s.title}
                    className="p-4 rounded-xl"
                    style={{ background: 'var(--tint-1)' }}
                  >
                    <p className="text-sm font-bold mb-2" style={{ color: 'var(--foreground)' }}>
                      {s.title}
                    </p>
                    <ul className="space-y-1.5">
                      {s.points.map((p, i) => (
                        <li
                          key={i}
                          className="text-xs flex items-start gap-2"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          <span style={{ color: 'var(--primary)' }}>▸</span> {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </motion.div>
            )}

            {tool === 'flashcards' && flashcards[cardIndex] && (
              <motion.div
                key="flashcards"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <p
                  className="text-xs mb-3 text-center"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Card {cardIndex + 1} of {flashcards.length}
                </p>
                <motion.button
                  onClick={() => setFlipped((f) => !f)}
                  className="w-full aspect-[3/2] rounded-2xl flex items-center justify-center p-6 text-center cursor-pointer"
                  style={{ background: 'var(--tint-2)', border: '1px solid var(--border-subtle)' }}
                  whileTap={{ scale: 0.98 }}
                >
                  <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                    {flipped ? flashcards[cardIndex].answer : flashcards[cardIndex].question}
                  </p>
                </motion.button>
                <p
                  className="text-xs text-center mt-2"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Tap card to {flipped ? 'see question' : 'reveal answer'}
                </p>
                <div className="flex items-center justify-between mt-4">
                  <button
                    onClick={() => {
                      setFlipped(false)
                      setCardIndex((i) => Math.max(0, i - 1))
                    }}
                    className="text-xs font-semibold px-4 py-2 rounded-lg"
                    style={{ background: 'var(--tint-2)', color: 'var(--foreground)' }}
                  >
                    ← Prev
                  </button>
                  <button
                    onClick={() => {
                      setFlipped(false)
                      setCardIndex((i) => Math.min(flashcards.length - 1, i + 1))
                    }}
                    className="text-xs font-semibold px-4 py-2 rounded-lg"
                    style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                  >
                    Next →
                  </button>
                </div>
              </motion.div>
            )}

            {tool === 'quiz' && (
              <motion.div
                key="quiz"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {quiz.length === 0 || quizIndex >= quiz.length ? (
                  <div className="text-center py-8">
                    <p className="text-lg font-bold" style={{ color: 'var(--primary)' }}>
                      {score} / {quiz.length}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                      Quiz complete!
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>
                      Question {quizIndex + 1} of {quiz.length}
                    </p>
                    <p
                      className="text-sm font-semibold mb-4"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {quiz[quizIndex].prompt}
                    </p>
                    <div className="space-y-2">
                      {quiz[quizIndex].options.map((opt, i) => {
                        const isCorrect = i === quiz[quizIndex].correctIndex
                        const isSelected = i === selected
                        return (
                          <button
                            key={i}
                            onClick={() => submitQuizAnswer(i)}
                            className="w-full text-left px-4 py-2.5 rounded-lg text-sm transition-colors"
                            style={{
                              background:
                                selected !== null && isCorrect
                                  ? 'var(--success-soft)'
                                  : isSelected
                                    ? 'var(--danger-soft)'
                                    : 'var(--tint-1)',
                              color: 'var(--foreground)',
                              border: `1px solid ${selected !== null && isCorrect ? 'var(--success)' : isSelected ? 'var(--danger)' : 'var(--border-subtle)'}`,
                            }}
                          >
                            {opt}
                          </button>
                        )
                      })}
                    </div>
                    {selected !== null && (
                      <button
                        onClick={nextQuiz}
                        className="mt-4 text-xs font-semibold px-4 py-2 rounded-lg"
                        style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                      >
                        {quizIndex === quiz.length - 1 ? 'See Results →' : 'Next Question →'}
                      </button>
                    )}
                  </div>
                )}
              </motion.div>
            )}

            {tool === 'mindmap' && (
              <motion.div
                key="mindmap"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-3"
              >
                <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
                  {course.title}
                </p>
                {course.modules.map((m, mi) => (
                  <div
                    key={m.id}
                    className="pl-4"
                    style={{ borderLeft: '2px solid var(--border-subtle)' }}
                  >
                    <p
                      className="text-sm font-semibold mb-1.5"
                      style={{ color: ['#2DD4BF', '#a855f7', '#f59e0b', '#38bdf8'][mi % 4] }}
                    >
                      {m.title}
                    </p>
                    <div className="space-y-1 pl-3">
                      {m.lessons.map((l) => (
                        <p
                          key={l.id}
                          className="text-xs"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          • {l.title}
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </motion.div>
            )}

            {tool === 'important' && (
              <motion.div
                key="important"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-3"
              >
                <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                  AI-flagged questions most likely to appear on your exam, based on this course's
                  analytics.
                </p>
                {importantQuestions.map((q, i) => (
                  <div
                    key={q.id}
                    className="p-4 rounded-xl"
                    style={{
                      background: 'rgba(255,126,54,0.06)',
                      border: '1px solid rgba(255,126,54,0.18)',
                    }}
                  >
                    <p
                      className="text-sm font-semibold mb-1.5"
                      style={{ color: 'var(--foreground)' }}
                    >
                      ⭐ Q{i + 1}. {q.question}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--accent)' }}>
                      {q.reason}
                    </p>
                  </div>
                ))}
              </motion.div>
            )}

            {tool === 'plan' && (
              <motion.div
                key="plan"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-3"
              >
                {studyPlan.length === 0 ? (
                  <p
                    className="text-sm text-center py-8"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    You've completed every lesson in {course.title} — no study plan needed. 🎉
                  </p>
                ) : (
                  <>
                    <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                      A personalized plan to finish {course.title}, built from your remaining
                      lessons.
                    </p>
                    {studyPlan.map((d) => (
                      <div
                        key={d.day}
                        className="p-4 rounded-xl"
                        style={{ background: 'var(--tint-1)' }}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
                            {d.day}
                          </p>
                          <span
                            className="text-xs px-2 py-0.5 rounded-full font-mono"
                            style={{ background: 'rgba(45,212,191,0.1)', color: 'var(--primary)' }}
                          >
                            {d.focus}
                          </span>
                        </div>
                        <ul className="space-y-1">
                          {d.lessons.map((l, i) => (
                            <li
                              key={i}
                              className="text-xs flex items-start gap-2"
                              style={{ color: 'var(--muted-foreground)' }}
                            >
                              <span style={{ color: 'var(--primary)' }}>▸</span> {l}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </motion.div>
  )
}

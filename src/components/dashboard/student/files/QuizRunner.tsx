import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { VaultQuestionType, VaultQuizQuestion } from '../../../../types/fileVault'

interface QuizRunnerProps {
  title: string
  questions: VaultQuizQuestion[]
  onComplete: (result: { scorePct: number; totalQuestions: number; correctCount: number }) => void
  onExit: () => void
  accentColor: string
}

const typeLabel: Record<VaultQuestionType, string> = {
  mcq: 'Multiple Choice',
  'true-false': 'True / False',
  'fill-blank': 'Fill in the Blank',
  'short-answer': 'Short Answer',
}

/**
 * Runs any list of VaultQuizQuestion — used for both "Practice Quiz
 * (Covered Topics Only)" and the "Take AI Exam" flow. Every question comes
 * from the backend's understanding-first pipeline (semantic study map ->
 * knowledge targets -> blueprint -> validated question), so this component is
 * purely presentational/scoring logic.
 */
export default function QuizRunner({
  title,
  questions,
  onComplete,
  onExit,
  accentColor,
}: QuizRunnerProps) {
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [textAnswer, setTextAnswer] = useState('')
  const [revealed, setRevealed] = useState(false)
  const [correctCount, setCorrectCount] = useState(0)
  const [finished, setFinished] = useState(false)

  const q = questions[index]

  if (questions.length === 0) {
    return (
      <div className="text-center py-10">
        <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
          Not enough content has been covered yet to generate questions.
        </p>
        <button
          onClick={onExit}
          className="mt-4 text-xs font-semibold"
          style={{ color: 'var(--primary)' }}
        >
          ← Back
        </button>
      </div>
    )
  }

  function submit(answer: string) {
    if (revealed) return
    setSelected(answer)
    setRevealed(true)
    const isCorrect = answer.trim().toLowerCase() === q.correctAnswer.trim().toLowerCase()
    if (isCorrect) setCorrectCount((c) => c + 1)
  }

  function next() {
    if (index === questions.length - 1) {
      const scorePct = Math.round((correctCount / questions.length) * 100)
      setFinished(true)
      onComplete({ scorePct, totalQuestions: questions.length, correctCount })
      return
    }
    setSelected(null)
    setTextAnswer('')
    setRevealed(false)
    setIndex((i) => i + 1)
  }

  if (finished) {
    const scorePct = Math.round((correctCount / questions.length) * 100)
    return (
      <motion.div
        className="text-center py-10"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <p
          className="text-4xl font-black mb-2"
          style={{ fontFamily: 'Orbitron, sans-serif', color: accentColor }}
        >
          {scorePct}%
        </p>
        <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
          {correctCount} of {questions.length} correct
        </p>
        <p className="text-xs mt-2" style={{ color: 'var(--muted-foreground)' }}>
          {scorePct >= 80
            ? 'Excellent work — you know this material well.'
            : scorePct >= 50
              ? 'Good effort — review the topics you missed.'
              : 'Consider re-reading this document before your exam.'}
        </p>
        <button
          onClick={onExit}
          className="mt-5 text-xs font-semibold px-4 py-2 rounded-lg"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Done
        </button>
      </motion.div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {title} · Question {index + 1} of {questions.length}
          </p>
          <p className="text-xs font-semibold mt-0.5" style={{ color: accentColor }}>
            {typeLabel[q.type]} · {q.difficulty[0].toUpperCase() + q.difficulty.slice(1)} · from
            page {q.sourcePages.join(', ')}
          </p>
        </div>
        <button
          onClick={onExit}
          className="text-xs font-semibold"
          style={{ color: 'var(--muted-foreground)' }}
        >
          Exit
        </button>
      </div>

      <div
        className="h-1 rounded-full overflow-hidden mb-5"
        style={{ background: 'var(--tint-3)' }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ background: accentColor }}
          animate={{ width: `${((index + 1) / questions.length) * 100}%` }}
        />
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={q.id}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
        >
          <p className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
            {q.prompt}
          </p>

          {(q.type === 'mcq' || q.type === 'true-false') && q.options && (
            <div className="space-y-2">
              {q.options.map((opt, i) => {
                const isCorrectOpt =
                  opt.trim().toLowerCase() === q.correctAnswer.trim().toLowerCase()
                const isSelected = opt === selected
                return (
                  <button
                    key={i}
                    onClick={() => submit(opt)}
                    className="w-full text-left px-4 py-2.5 rounded-lg text-sm transition-colors"
                    style={{
                      background:
                        revealed && isCorrectOpt
                          ? 'var(--success-soft)'
                          : isSelected
                            ? 'var(--danger-soft)'
                            : 'var(--tint-1)',
                      border: `1px solid ${revealed && isCorrectOpt ? 'var(--success)' : isSelected ? 'var(--danger)' : 'var(--border-subtle)'}`,
                      color: 'var(--foreground)',
                    }}
                  >
                    {opt}
                  </button>
                )
              })}
            </div>
          )}

          {(q.type === 'fill-blank' || q.type === 'short-answer') && (
            <div className="space-y-2">
              <input
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                disabled={revealed}
                placeholder="Type your answer..."
                className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                onKeyDown={(e) => e.key === 'Enter' && submit(textAnswer)}
              />
              {!revealed && (
                <button
                  onClick={() => submit(textAnswer)}
                  className="text-xs font-semibold px-4 py-2 rounded-lg"
                  style={{ background: accentColor, color: '#fff' }}
                >
                  Submit
                </button>
              )}
            </div>
          )}

          {revealed && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 p-3 rounded-lg text-xs leading-relaxed"
              style={{ background: 'var(--tint-1)', color: 'var(--muted-foreground)' }}
            >
              💡 {q.explanation}
            </motion.div>
          )}

          {revealed && (
            <button
              onClick={next}
              className="mt-4 text-xs font-semibold px-4 py-2 rounded-lg"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              {index === questions.length - 1 ? 'See Results →' : 'Next Question →'}
            </button>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

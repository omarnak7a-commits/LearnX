import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { QuizQuestion } from '../../../../types/video'
import Badge from '../../../ui/Badge'

interface QuizPanelProps {
  questions: QuizQuestion[]
}

export default function QuizPanel({ questions }: QuizPanelProps) {
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [score, setScore] = useState(0)
  const [finished, setFinished] = useState(false)
  const [textAnswer, setTextAnswer] = useState('')

  const q = questions[index]

  function submit(answer: string) {
    if (revealed) return
    setSelected(answer)
    setRevealed(true)
    if (answer.trim().toLowerCase() === q.correctAnswer.trim().toLowerCase()) {
      setScore((s) => s + 1)
    }
  }

  function next() {
    if (index === questions.length - 1) {
      setFinished(true)
      return
    }
    setIndex((i) => i + 1)
    setSelected(null)
    setRevealed(false)
    setTextAnswer('')
  }

  function restart() {
    setIndex(0)
    setSelected(null)
    setRevealed(false)
    setScore(0)
    setFinished(false)
    setTextAnswer('')
  }

  if (finished) {
    const pct = Math.round((score / questions.length) * 100)
    return (
      <div className="text-center py-8">
        <motion.div
          className="text-5xl mb-4"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 18 }}
        >
          {pct >= 80 ? '🏆' : pct >= 50 ? '👍' : '📚'}
        </motion.div>
        <p className="text-2xl font-black mb-1" style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--primary)' }}>
          {score} / {questions.length}
        </p>
        <p className="text-sm mb-6" style={{ color: 'var(--muted-foreground)' }}>
          {pct}% correct — {pct >= 80 ? 'excellent recall!' : pct >= 50 ? 'good, review the missed ones' : 'let\u2019s revisit the flashcards first'}
        </p>
        <button
          onClick={restart}
          className="px-5 py-2.5 rounded-full text-sm font-semibold"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Retake Quiz
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Badge tone="primary" size="xs" mono>
          {q.type.replace('-', ' ')}
        </Badge>
        <span className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>
          {index + 1} / {questions.length}
        </span>
      </div>

      <p className="text-base font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
        {q.prompt}
      </p>

      {q.type === 'mcq' && (
        <div className="space-y-2 mb-4">
          {q.options?.map((opt) => {
            const isCorrect = opt === q.correctAnswer
            const isSelected = opt === selected
            return (
              <button
                key={opt}
                onClick={() => submit(opt)}
                disabled={revealed}
                className="w-full text-left px-4 py-2.5 rounded-xl text-sm transition-colors"
                style={{
                  background: revealed
                    ? isCorrect
                      ? 'var(--success-soft)'
                      : isSelected
                        ? 'var(--danger-soft)'
                        : 'var(--tint-1)'
                    : 'var(--tint-1)',
                  border: `1px solid ${
                    revealed && isCorrect
                      ? 'var(--success)'
                      : revealed && isSelected
                        ? 'var(--danger)'
                        : 'var(--border-subtle)'
                  }`,
                  color: 'var(--foreground)',
                }}
              >
                {opt}
              </button>
            )
          })}
        </div>
      )}

      {q.type === 'true-false' && (
        <div className="grid grid-cols-2 gap-2 mb-4">
          {['True', 'False'].map((opt) => {
            const isCorrect = opt === q.correctAnswer
            const isSelected = opt === selected
            return (
              <button
                key={opt}
                onClick={() => submit(opt)}
                disabled={revealed}
                className="py-3 rounded-xl text-sm font-semibold transition-colors"
                style={{
                  background: revealed
                    ? isCorrect
                      ? 'var(--success-soft)'
                      : isSelected
                        ? 'var(--danger-soft)'
                        : 'var(--tint-1)'
                    : 'var(--tint-1)',
                  border: `1px solid ${
                    revealed && isCorrect ? 'var(--success)' : revealed && isSelected ? 'var(--danger)' : 'var(--border-subtle)'
                  }`,
                  color: 'var(--foreground)',
                }}
              >
                {opt}
              </button>
            )
          })}
        </div>
      )}

      {(q.type === 'short-answer' || q.type === 'fill-blank') && (
        <div className="mb-4">
          <input
            value={textAnswer}
            onChange={(e) => setTextAnswer(e.target.value)}
            disabled={revealed}
            placeholder="Type your answer..."
            className="input-field w-full px-4 py-2.5 rounded-xl text-sm mb-2"
          />
          {!revealed && (
            <button
              onClick={() => submit(textAnswer)}
              disabled={!textAnswer.trim()}
              className="px-4 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Submit
            </button>
          )}
        </div>
      )}

      <AnimatePresence>
        {revealed && (
          <motion.div
            className="p-3.5 rounded-xl mb-4"
            style={{ background: 'rgba(45,212,191,0.06)', border: '1px solid rgba(45,212,191,0.16)' }}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--primary)' }}>
              Correct answer: {q.correctAnswer}
            </p>
            <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              {q.explanation}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {revealed && (
        <button
          onClick={next}
          className="w-full py-2.5 rounded-xl text-sm font-semibold"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          {index === questions.length - 1 ? 'See results →' : 'Next question →'}
        </button>
      )}
    </div>
  )
}

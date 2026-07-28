import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Flashcard } from '../../../../types/video'
import Badge from '../../../ui/Badge'

interface FlashcardsPanelProps {
  flashcards: Flashcard[]
}

const difficultyTone: Record<Flashcard['difficulty'], 'success' | 'warning' | 'danger'> = {
  easy: 'success',
  medium: 'warning',
  hard: 'danger',
}

export default function FlashcardsPanel({ flashcards }: FlashcardsPanelProps) {
  const [cards, setCards] = useState(flashcards)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [filter, setFilter] = useState<'all' | 'favorites'>('all')

  const visible = filter === 'favorites' ? cards.filter((c) => c.favorite) : cards
  const card = visible[Math.min(index, visible.length - 1)]

  function next() {
    setFlipped(false)
    setIndex((i) => Math.min(visible.length - 1, i + 1))
  }
  function prev() {
    setFlipped(false)
    setIndex((i) => Math.max(0, i - 1))
  }
  function toggleFavorite() {
    if (!card) return
    setCards((prev) => prev.map((c) => (c.id === card.id ? { ...c, favorite: !c.favorite } : c)))
  }
  function rate(level: number) {
    if (!card) return
    setCards((prev) => prev.map((c) => (c.id === card.id ? { ...c, masteredLevel: level } : c)))
    next()
  }

  if (!card) {
    return (
      <p className="text-sm text-center py-10" style={{ color: 'var(--muted-foreground)' }}>
        No favorited flashcards yet.
      </p>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          {(['all', 'favorites'] as const).map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f)
                setIndex(0)
                setFlipped(false)
              }}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-colors"
              style={{
                background: filter === f ? 'var(--primary)' : 'var(--tint-2)',
                color: filter === f ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>
          {index + 1} / {visible.length}
        </span>
      </div>

      {/* Flip card */}
      <div className="relative h-56 mb-4" style={{ perspective: 1000 }}>
        <motion.div
          className="absolute inset-0 cursor-pointer"
          style={{ transformStyle: 'preserve-3d' }}
          animate={{ rotateY: flipped ? 180 : 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          onClick={() => setFlipped((f) => !f)}
        >
          {/* Front */}
          <div
            className="absolute inset-0 rounded-2xl p-6 flex flex-col"
            style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)', backfaceVisibility: 'hidden' }}
          >
            <div className="flex items-center justify-between mb-4">
              <Badge tone={difficultyTone[card.difficulty]} size="xs">
                {card.difficulty}
              </Badge>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  toggleFavorite()
                }}
                className="text-lg"
              >
                {card.favorite ? '⭐' : '☆'}
              </button>
            </div>
            <div className="flex-1 flex items-center justify-center text-center">
              <p className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>
                {card.question}
              </p>
            </div>
            <p className="text-xs text-center" style={{ color: 'var(--muted-foreground)' }}>
              Tap to reveal answer
            </p>
          </div>

          {/* Back */}
          <div
            className="absolute inset-0 rounded-2xl p-6 flex flex-col items-center justify-center text-center"
            style={{
              background: 'rgba(45,212,191,0.08)',
              border: '1px solid rgba(45,212,191,0.24)',
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)',
            }}
          >
            <p className="text-base font-medium leading-relaxed" style={{ color: 'var(--foreground)' }}>
              {card.answer}
            </p>
          </div>
        </motion.div>
      </div>

      {/* Spaced repetition rating */}
      <AnimatePresence>
        {flipped && (
          <motion.div
            className="flex items-center gap-2 mb-4"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <span className="text-xs mr-1" style={{ color: 'var(--muted-foreground)' }}>
              How well did you know it?
            </span>
            {['Again', 'Hard', 'Good', 'Easy'].map((label, i) => (
              <button
                key={label}
                onClick={() => rate(i + 2)}
                className="flex-1 text-xs font-semibold py-2 rounded-lg"
                style={{
                  background: ['var(--danger-soft)', 'var(--warning-soft)', 'rgba(45,212,191,0.12)', 'var(--success-soft)'][i],
                  color: ['var(--danger)', 'var(--warning)', 'var(--primary)', 'var(--success)'][i],
                }}
              >
                {label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center gap-2">
        <button
          onClick={prev}
          disabled={index === 0}
          className="flex-1 py-2 rounded-lg text-xs font-semibold input-field disabled:opacity-40"
        >
          ← Previous
        </button>
        <button
          onClick={next}
          disabled={index === visible.length - 1}
          className="flex-1 py-2 rounded-lg text-xs font-semibold"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Next →
        </button>
      </div>
    </div>
  )
}

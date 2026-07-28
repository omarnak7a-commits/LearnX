import { motion } from 'framer-motion'
import type { Chapter } from '../../../../types/video'
import { formatTimestamp } from '../../../../data/videoIntelligenceMock'
import Badge from '../../../ui/Badge'

interface ChaptersPanelProps {
  chapters: Chapter[]
  activeChapterId: string | undefined
  onJump: (startSec: number) => void
}

const difficultyTone: Record<Chapter['difficulty'], 'success' | 'warning' | 'danger'> = {
  easy: 'success',
  medium: 'warning',
  hard: 'danger',
}

export default function ChaptersPanel({ chapters, activeChapterId, onJump }: ChaptersPanelProps) {
  return (
    <div className="space-y-2.5">
      {chapters.map((c, i) => {
        const isActive = c.id === activeChapterId
        return (
          <motion.button
            key={c.id}
            onClick={() => onJump(c.startSec)}
            className="w-full text-left rounded-xl p-3.5 transition-colors"
            style={{
              background: isActive ? 'rgba(45,212,191,0.1)' : 'var(--tint-1)',
              border: `1px solid ${isActive ? 'rgba(45,212,191,0.3)' : 'var(--border-subtle)'}`,
            }}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
          >
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className="w-5 h-5 rounded-md flex items-center justify-center text-xs font-bold flex-shrink-0"
                  style={{
                    background: isActive ? 'var(--primary)' : 'var(--tint-4)',
                    color: isActive ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                  }}
                >
                  {c.index}
                </span>
                <p className="text-sm font-semibold truncate" style={{ color: 'var(--foreground)' }}>
                  {c.title}
                </p>
              </div>
              <span className="text-xs font-mono flex-shrink-0" style={{ color: 'var(--muted-foreground)' }}>
                {formatTimestamp(c.startSec)}
              </span>
            </div>

            <div className="flex items-center gap-1.5 flex-wrap mb-2">
              <Badge tone={difficultyTone[c.difficulty]} size="xs">
                {c.difficulty}
              </Badge>
              <Badge tone="neutral" size="xs">
                {Math.round((c.endSec - c.startSec) / 60)} min
              </Badge>
              <Badge tone="primary" size="xs">
                {c.examImportance}% exam weight
              </Badge>
            </div>

            {c.keyConcepts.length > 0 && (
              <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
                {c.keyConcepts.map((k) => k.term).join(' · ')}
              </p>
            )}

            <div className="flex items-center gap-1.5 mt-2">
              <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${c.confidence * 100}%`, background: 'var(--primary)' }}
                />
              </div>
              <span className="text-xs flex-shrink-0" style={{ color: 'var(--muted-foreground)' }}>
                {Math.round(c.confidence * 100)}% confidence
              </span>
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}

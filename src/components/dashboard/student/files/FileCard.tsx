import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import { readingPercent, isFullyRead, aiReadinessScore } from '../../../../types/fileVault'
import { useFileVault } from '../../../../context/FileVaultContext'
import ProgressRing from '../../../ui/ProgressRing'
import Badge from '../../../ui/Badge'
import { statusMeta, formatRelativeTime, formatBytes, pagesRemaining } from './fileVaultFormat'

interface FileCardProps {
  file: VaultFile
  delay?: number
  onOpen: (tab?: WorkspaceTab) => void
}

export type WorkspaceTab =
  | 'viewer'
  | 'chat'
  | 'summary'
  | 'topics'
  | 'notes'
  | 'flashcards'
  | 'mindmap'
  | 'quiz'
  | 'exam'
  | 'stats'

/**
 * The signature "PDF card" of the Smart AI File Vault. On hover the card
 * lifts, enlarges slightly, and an AI Preview Panel slides up from the
 * bottom — all inside the card, no popups — surfacing real, per-file AI
 * analysis (topics, difficulty, reading progress, recommendation) plus
 * the full action set (Continue Reading / Generate Quiz / AI Summary /
 * Flashcards / Open Workspace) and the Smart Exam Button.
 */
export default function FileCard({ file, delay = 0, onOpen }: FileCardProps) {
  const { toggleFavorite, togglePinned } = useFileVault()
  const [hovered, setHovered] = useState(false)
  const pct = readingPercent(file)
  const fullyRead = isFullyRead(file)
  const readiness = aiReadinessScore(file)
  const status = statusMeta[file.status]
  const remaining = pagesRemaining(file)

  const recommendation = fullyRead
    ? "You've finished this document — take the AI Exam to test full retention."
    : pct === 0
      ? 'Not started yet. Estimated ' + file.estimatedReadingMinutes + ' min to read.'
      : `${remaining} page${remaining === 1 ? '' : 's'} left — you're ${pct}% through.`

  return (
    <motion.div
      layout
      className="relative rounded-2xl overflow-hidden"
      initial={{ opacity: 0, y: 16 }}
      animate={{
        opacity: 1,
        y: hovered ? -12 : 0,
        scale: hovered ? 1.02 : 1,
      }}
      transition={{ delay, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      whileTap={{ scale: 0.99 }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        boxShadow: hovered ? '0 24px 60px rgba(0,0,0,0.22)' : '0 1px 2px rgba(0,0,0,0.04)',
      }}
    >
      {/* Thumbnail */}
      <div
        className="relative aspect-[4/3] cursor-pointer overflow-hidden"
        onClick={() => onOpen('viewer')}
      >
        {file.thumbnailDataUrl ? (
          <motion.img
            src={file.thumbnailDataUrl}
            alt={file.title}
            className="w-full h-full object-cover object-top"
            animate={{
              scale: hovered ? 1.06 : 1,
              filter: hovered ? 'brightness(1.05)' : 'brightness(1)',
            }}
            transition={{ duration: 0.4 }}
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center text-4xl"
            style={{ background: `linear-gradient(135deg, ${file.color}26, ${file.color}0d)` }}
          >
            📄
          </div>
        )}

        {/* Top-left status badge */}
        <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
          <Badge tone={status.tone} size="xs">
            {status.label}
          </Badge>
        </div>

        {/* Top-right favorite/pin */}
        <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5">
          <button
            onClick={(e) => {
              e.stopPropagation()
              togglePinned(file.id)
            }}
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs"
            style={{ background: 'rgba(0,0,0,0.45)', color: file.pinned ? '#2DD4BF' : '#fff' }}
            aria-label={file.pinned ? 'Unpin' : 'Pin'}
          >
            📌
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              toggleFavorite(file.id)
            }}
            className="w-7 h-7 rounded-full flex items-center justify-center text-sm"
            style={{ background: 'rgba(0,0,0,0.45)', color: file.favorite ? '#FF7E36' : '#fff' }}
            aria-label={file.favorite ? 'Remove favorite' : 'Add favorite'}
          >
            {file.favorite ? '★' : '☆'}
          </button>
        </div>

        {/* Bottom progress bar */}
        {pct > 0 && (
          <div
            className="absolute bottom-0 left-0 right-0 px-2.5 py-2 flex items-center gap-2"
            style={{ background: 'rgba(0,0,0,0.5)' }}
          >
            <div
              className="flex-1 h-1.5 rounded-full overflow-hidden"
              style={{ background: 'rgba(255,255,255,0.25)' }}
            >
              <div
                className="h-full rounded-full"
                style={{ width: `${pct}%`, background: file.color }}
              />
            </div>
            <span className="text-xs font-semibold" style={{ color: '#fff' }}>
              {pct}%
            </span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4">
        <p
          className="text-sm font-semibold leading-snug truncate cursor-pointer"
          style={{ color: 'var(--foreground)' }}
          onClick={() => onOpen('viewer')}
        >
          {file.title}
        </p>
        <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--muted-foreground)' }}>
          {file.course} · {file.doctorName}
        </p>

        <div className="flex items-center gap-3 mt-3">
          <ProgressRing
            pct={pct}
            color={file.color}
            size={40}
            strokeWidth={4}
            valueLabel={`${pct}%`}
          />
          <div className="min-w-0 flex-1">
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {file.pageCount} pages · {file.estimatedReadingMinutes} min read
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
              Uploaded {formatRelativeTime(file.uploadedAt)} · {formatBytes(file.sizeBytes)}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between mt-3">
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Last viewed {formatRelativeTime(file.lastViewedAt)}
          </span>
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{
              background: `${readinessColor(readiness)}18`,
              color: readinessColor(readiness),
            }}
          >
            AI Ready {readiness}%
          </span>
        </div>
      </div>

      {/* AI Preview Panel — slides up from inside the card on hover */}
      <AnimatePresence>
        {hovered && (
          <motion.div
            className="absolute inset-x-0 bottom-0 rounded-t-2xl p-4 space-y-3 overflow-y-auto scrollbar-thin"
            style={{
              background: 'var(--surface-2)',
              borderTop: `1px solid ${file.color}33`,
              maxHeight: '78%',
              boxShadow: '0 -12px 32px rgba(0,0,0,0.18)',
            }}
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            {file.analysis ? (
              <>
                <div>
                  <p className="text-xs font-bold mb-1.5" style={{ color: 'var(--foreground)' }}>
                    📌 Important Topics
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {file.analysis.keyConcepts.slice(0, 4).map((t) => (
                      <span
                        key={t}
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: `${file.color}18`, color: file.color }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span style={{ color: 'var(--muted-foreground)' }}>
                    Difficulty:{' '}
                    <strong style={{ color: 'var(--foreground)' }}>
                      {file.analysis.difficulty[0].toUpperCase() +
                        file.analysis.difficulty.slice(1)}
                    </strong>
                  </span>
                  <span style={{ color: 'var(--muted-foreground)' }}>
                    {remaining > 0 ? `${remaining} pages left` : 'Fully read'}
                  </span>
                </div>

                <p
                  className="text-xs p-2.5 rounded-lg leading-relaxed"
                  style={{ background: `${file.color}0d`, color: 'var(--foreground)' }}
                >
                  💡 {recommendation}
                </p>

                <div className="flex flex-wrap gap-1.5 pt-1">
                  <MiniButton primary onClick={() => onOpen('viewer')}>
                    {pct === 0 ? 'Start Reading' : 'Continue Reading'}
                  </MiniButton>
                  <MiniButton onClick={() => onOpen('summary')}>AI Summary</MiniButton>
                  <MiniButton onClick={() => onOpen('flashcards')}>Flashcards</MiniButton>
                  {fullyRead ? (
                    <MiniButton accent onClick={() => onOpen('exam')}>
                      🎓 Take AI Exam
                    </MiniButton>
                  ) : pct > 0 ? (
                    <MiniButton onClick={() => onOpen('quiz')}>
                      Practice Quiz (Read Pages)
                    </MiniButton>
                  ) : (
                    <MiniButton onClick={() => onOpen('viewer')}>Finish Reading First</MiniButton>
                  )}
                  <MiniButton onClick={() => onOpen('viewer')}>Open Workspace</MiniButton>
                </div>
              </>
            ) : (
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                AI is still analyzing this document...
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function readinessColor(score: number): string {
  if (score >= 75) return 'var(--success)'
  if (score >= 40) return '#f59e0b'
  return 'var(--danger)'
}

function MiniButton({
  children,
  onClick,
  primary = false,
  accent = false,
}: {
  children: React.ReactNode
  onClick: () => void
  primary?: boolean
  accent?: boolean
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      className="text-xs font-semibold px-2.5 py-1.5 rounded-lg transition-all"
      style={
        primary
          ? { background: 'var(--primary)', color: 'var(--primary-foreground)' }
          : accent
            ? { background: 'var(--accent)', color: 'var(--accent-foreground)' }
            : { background: 'var(--tint-2)', color: 'var(--foreground)' }
      }
    >
      {children}
    </button>
  )
}

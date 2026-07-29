import { motion } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import { buildTodaysStudyPlan } from '../../../../lib/fileVault/studyHub'

interface StudyTimelineProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
}

/**
 * Visual learning timeline — the spec's literal replacement for the old
 * standalone planner UI ("Today → Continue Biology → Take Practice Quiz
 * → Review Flashcards → Finish Physics PDF → AI Revision"). Built from
 * the exact same buildTodaysStudyPlan() output as the card grid above,
 * just rendered as a connected vertical flow instead of a grid — same
 * data, different visualization, so there's no separate plan to keep in
 * sync.
 */
export default function StudyTimeline({ files, onOpenFile }: StudyTimelineProps) {
  const cards = buildTodaysStudyPlan(files)
  if (cards.length === 0) return null

  return (
    <motion.div
      className="glass-card p-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h3 className="text-sm font-bold mb-5" style={{ color: 'var(--foreground)' }}>
        🗺️ Study Timeline
      </h3>
      <div className="relative pl-6">
        <div
          className="absolute left-[9px] top-2 bottom-2 w-px"
          style={{ background: 'var(--border-subtle)' }}
        />

        <TimelineNode label="Today" isAnchor />

        {cards.map((card, i) => (
          <TimelineNode
            key={card.id}
            label={`${card.actionLabel}: ${card.fileTitle}`}
            icon={card.icon}
            delay={0.08 * (i + 1)}
            onClick={() => onOpenFile(card.fileId, card.tab)}
          />
        ))}

        <TimelineNode label="AI Revision" icon="🔄" delay={0.08 * (cards.length + 1)} isLast />
      </div>
    </motion.div>
  )
}

function TimelineNode({
  label,
  icon,
  delay = 0,
  isAnchor = false,
  isLast = false,
  onClick,
}: {
  label: string
  icon?: string
  delay?: number
  isAnchor?: boolean
  isLast?: boolean
  onClick?: () => void
}) {
  const Wrapper = onClick ? motion.button : motion.div
  return (
    <Wrapper
      onClick={onClick}
      className={`relative flex items-center gap-3 py-2.5 text-left w-full ${!isLast ? 'mb-1' : ''}`}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay }}
    >
      <span
        className="absolute -left-6 w-4.5 h-4.5 rounded-full flex items-center justify-center flex-shrink-0"
        style={{
          background: isAnchor ? 'var(--primary)' : 'var(--surface-2)',
          border: `2px solid ${isAnchor ? 'var(--primary)' : 'var(--border)'}`,
        }}
      />
      {icon && <span className="text-sm flex-shrink-0">{icon}</span>}
      <span
        className="text-sm truncate"
        style={{
          color: isAnchor ? 'var(--primary)' : 'var(--foreground)',
          fontWeight: isAnchor ? 700 : 500,
        }}
      >
        {label}
      </span>
    </Wrapper>
  )
}

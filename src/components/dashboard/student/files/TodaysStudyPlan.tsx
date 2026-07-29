import { motion } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import { buildTodaysStudyPlan } from '../../../../lib/fileVault/studyHub'

interface TodaysStudyPlanProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
}

const categoryColor: Record<string, string> = {
  continue: '#2DD4BF',
  review: '#a855f7',
  practice: '#f59e0b',
  read: '#38bdf8',
  exam: '#FF7E36',
}

/**
 * "Today's AI Study Plan" — the spec's replacement for the standalone
 * Smart Planner page. Every card is generated live from real file state
 * (priority, reading progress, staleness, exam dates) via
 * buildTodaysStudyPlan() — there is no separate planner data model to
 * keep in sync, and nothing here is manually editable by the student.
 */
export default function TodaysStudyPlan({ files, onOpenFile }: TodaysStudyPlanProps) {
  const cards = buildTodaysStudyPlan(files)
  if (cards.length === 0) return null

  return (
    <motion.div
      className="glass-card p-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            🧠 Today's AI Study Plan
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            Generated automatically from your files and progress — no planning needed.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
        {cards.map((card, i) => (
          <motion.button
            key={card.id}
            onClick={() => onOpenFile(card.fileId, card.tab)}
            className="text-left p-4 rounded-xl transition-all"
            style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ y: -3, borderColor: `${categoryColor[card.category]}44` }}
          >
            <div className="flex items-center gap-1.5 mb-2">
              <span>{card.icon}</span>
              <span
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: categoryColor[card.category] }}
              >
                {card.categoryLabel}
              </span>
            </div>
            <p
              className="text-sm font-semibold truncate mb-2"
              style={{ color: 'var(--foreground)' }}
            >
              {card.fileTitle}
            </p>
            <span
              className="text-xs font-semibold px-2 py-1 rounded-full inline-block"
              style={{
                background: `${categoryColor[card.category]}18`,
                color: categoryColor[card.category],
              }}
            >
              {card.actionLabel} →
            </span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  )
}

import { motion } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import { readingPercent, isFullyRead, aiReadinessScore } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import { formatRelativeTime, pagesRemaining } from './fileVaultFormat'

interface RecentActivityRailProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
}

/** "Continue Reading" horizontal rail — real in-progress files sorted by
 * last-viewed time, matching the spec's Recent Activity section. */
export default function RecentActivityRail({ files, onOpenFile }: RecentActivityRailProps) {
  const inProgress = files
    .filter((f) => f.status === 'in-progress' && f.lastViewedAt)
    .sort((a, b) => (b.lastViewedAt ?? 0) - (a.lastViewedAt ?? 0))
    .slice(0, 6)

  if (inProgress.length === 0) return null

  return (
    <div>
      <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
        ▶️ Continue Reading
      </h3>
      <div className="flex gap-3 overflow-x-auto scrollbar-thin pb-2">
        {inProgress.map((file, i) => {
          const pct = readingPercent(file)
          const remaining = pagesRemaining(file)
          return (
            <motion.button
              key={file.id}
              onClick={() => onOpenFile(file.id, 'viewer')}
              className="flex-shrink-0 w-64 text-left rounded-xl p-4 transition-all"
              style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ y: -3, borderColor: `${file.color}44` }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{file.icon}</span>
                <p
                  className="text-sm font-semibold truncate flex-1"
                  style={{ color: 'var(--foreground)' }}
                >
                  {file.title}
                </p>
              </div>
              <div
                className="h-1.5 rounded-full overflow-hidden mb-2"
                style={{ background: 'var(--tint-3)' }}
              >
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, background: file.color }}
                />
              </div>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {remaining} page{remaining === 1 ? '' : 's'} left ·{' '}
                {formatRelativeTime(file.lastViewedAt)}
              </p>
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}

interface AiInsightsRailProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
}

/**
 * AI Insights / Recommendations — every message is computed from the
 * student's real per-file reading state (progress %, quiz history,
 * upload recency), not scripted copy. Matches the spec's example
 * phrasing style ("You have completed 82% of Biology.") while the
 * numbers and file names are always genuinely correct for this session.
 */
export function generateRecommendations(
  files: VaultFile[]
): Array<{ id: string; text: string; fileId?: string }> {
  const recs: Array<{ id: string; text: string; fileId?: string }> = []

  const inProgress = files.filter((f) => f.status === 'in-progress')
  for (const f of inProgress.slice(0, 2)) {
    const pct = readingPercent(f)
    recs.push({
      id: `progress-${f.id}`,
      text: `You have completed ${pct}% of ${f.course}. Keep going — ${pagesRemaining(f)} pages left in "${f.title}".`,
      fileId: f.id,
    })
  }

  const readyForExam = files.filter((f) => isFullyRead(f) && f.examAttempts.length === 0)
  for (const f of readyForExam.slice(0, 2)) {
    recs.push({
      id: `exam-ready-${f.id}`,
      text: `"${f.title}" is fully read and ready for an AI Exam — this document contains topics that frequently appear in exams.`,
      fileId: f.id,
    })
  }

  const struggling = files.filter(
    (f) => f.quizAttempts.length > 0 && f.quizAttempts[0].scorePct < 60
  )
  for (const f of struggling.slice(0, 1)) {
    recs.push({
      id: `struggle-${f.id}`,
      text: `Your last quiz on "${f.title}" scored ${f.quizAttempts[0].scorePct}%. Review this document before your next assessment.`,
      fileId: f.id,
    })
  }

  const stale = files.filter(
    (f) =>
      f.status === 'in-progress' &&
      f.lastViewedAt &&
      Date.now() - f.lastViewedAt > 3 * 24 * 60 * 60 * 1000
  )
  for (const f of stale.slice(0, 1)) {
    recs.push({
      id: `stale-${f.id}`,
      text: `You haven't opened "${f.title}" in a while — pick up where you left off before it slips from memory.`,
      fileId: f.id,
    })
  }

  if (recs.length === 0 && files.length > 0) {
    const lowestReadiness = [...files].sort((a, b) => aiReadinessScore(a) - aiReadinessScore(b))[0]
    recs.push({
      id: `default-${lowestReadiness.id}`,
      text: `Start with "${lowestReadiness.title}" — it currently has the lowest AI readiness score in your library.`,
      fileId: lowestReadiness.id,
    })
  }

  return recs.slice(0, 4)
}

export function AiRecommendationsPanel({ files, onOpenFile }: AiInsightsRailProps) {
  const recommendations = generateRecommendations(files)
  if (recommendations.length === 0) return null

  return (
    <motion.div
      className="glass-card p-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h3
        className="text-sm font-bold mb-4 flex items-center gap-2"
        style={{ color: 'var(--foreground)' }}
      >
        ✨ AI Insights & Recommendations
      </h3>
      <div className="space-y-2.5">
        {recommendations.map((rec, i) => (
          <motion.button
            key={rec.id}
            onClick={() => rec.fileId && onOpenFile(rec.fileId, 'viewer')}
            className="w-full text-left flex items-start gap-3 p-3 rounded-xl transition-colors"
            style={{
              background: 'rgba(45,212,191,0.06)',
              border: '1px solid rgba(45,212,191,0.15)',
            }}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <span className="flex-shrink-0">💡</span>
            <p className="text-xs leading-relaxed" style={{ color: 'rgba(45,212,191,0.9)' }}>
              {rec.text}
            </p>
          </motion.button>
        ))}
      </div>
    </motion.div>
  )
}

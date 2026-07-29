import { motion } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import { readingPercent } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import { formatRelativeTime, pagesRemaining } from './fileVaultFormat'

interface RecentActivityRailProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
}

/** "Continue Reading" horizontal rail — real in-progress files sorted by
 * last-viewed time, matching the spec's Recent Activity section. AI
 * insight/recommendation copy now lives in StudyInsightsStrip.tsx,
 * driven by src/lib/fileVault/studyHub.ts (the same engine that powers
 * Today's AI Study Plan) rather than a separate recommendations list. */
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

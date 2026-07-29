import { motion } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import { buildStudyInsights } from '../../../../lib/fileVault/studyHub'

interface StudyInsightsStripProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
}

/** Top-of-page AI Insights strip — sentence-form observations computed
 * live from real per-file progress/quiz/exam-date state, matching the
 * spec's exact example phrasing style ("You are ready for the Biology
 * exam.", "Chapter 4 has your lowest quiz score."). */
export default function StudyInsightsStrip({ files, onOpenFile }: StudyInsightsStripProps) {
  const insights = buildStudyInsights(files)
  if (insights.length === 0) return null

  return (
    <motion.div
      className="flex gap-3 overflow-x-auto scrollbar-thin pb-1"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {insights.map((insight, i) => (
        <motion.button
          key={insight.id}
          onClick={() => insight.fileId && onOpenFile(insight.fileId, 'viewer')}
          className="flex-shrink-0 max-w-xs text-left flex items-start gap-2 px-3.5 py-2.5 rounded-xl"
          style={{ background: 'rgba(45,212,191,0.06)', border: '1px solid rgba(45,212,191,0.15)' }}
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
        >
          <span className="flex-shrink-0">✨</span>
          <p className="text-xs leading-relaxed" style={{ color: 'rgba(45,212,191,0.9)' }}>
            {insight.text}
          </p>
        </motion.button>
      ))}
    </motion.div>
  )
}

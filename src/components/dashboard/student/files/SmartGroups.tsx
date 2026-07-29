import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import FileCard from './FileCard'
import {
  buildSmartGroups,
  smartGroupMeta,
  type SmartGroupKey,
} from '../../../../lib/fileVault/studyHub'

interface SmartGroupsProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
  allCollections: string[]
}

const GROUP_ORDER: SmartGroupKey[] = [
  'upcomingExams',
  'needsRevision',
  'thisWeek',
  'nextWeek',
  'recentlyViewed',
  'favorites',
  'completed',
]

/**
 * "Weekly Organization" from the spec — groups files into smart,
 * overlapping lenses (a file can appear in multiple groups) computed
 * live from real state via buildSmartGroups(). Students instantly see
 * what to study next without any manual categorization.
 */
export default function SmartGroups({ files, onOpenFile, allCollections }: SmartGroupsProps) {
  const groups = buildSmartGroups(files)
  const [expandedGroup, setExpandedGroup] = useState<SmartGroupKey | null>(null)

  const nonEmptyGroups = GROUP_ORDER.filter((key) => groups[key].length > 0)
  if (nonEmptyGroups.length === 0) return null

  return (
    <div>
      <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
        🗂️ Smart Organization
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3 mb-4">
        {nonEmptyGroups.map((key) => {
          const meta = smartGroupMeta[key]
          const isActive = expandedGroup === key
          return (
            <button
              key={key}
              onClick={() => setExpandedGroup(isActive ? null : key)}
              className="flex items-center gap-2.5 p-3.5 rounded-xl text-left transition-all"
              style={{
                background: isActive ? 'rgba(45,212,191,0.1)' : 'var(--tint-1)',
                border: `1px solid ${isActive ? 'var(--primary)' : 'var(--border-subtle)'}`,
              }}
            >
              <span className="text-lg flex-shrink-0">{meta.icon}</span>
              <div className="min-w-0">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {meta.label}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {groups[key].length} file{groups[key].length === 1 ? '' : 's'}
                </p>
              </div>
            </button>
          )
        })}
      </div>

      <AnimatePresence>
        {expandedGroup && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{ overflow: 'hidden' }}
          >
            <div className="glass-card p-5 mb-4">
              <p
                className="text-xs font-semibold mb-4"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {smartGroupMeta[expandedGroup].icon} {smartGroupMeta[expandedGroup].label}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {groups[expandedGroup].map((file, i) => (
                  <FileCard
                    key={file.id}
                    file={file}
                    delay={i * 0.04}
                    onOpen={(tab) => onOpenFile(file.id, tab)}
                    allCollections={allCollections}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

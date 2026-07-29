import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { VaultFile } from '../../../../types/fileVault'
import type { WorkspaceTab } from './FileCard'
import FileCard from './FileCard'

interface WeekTimelineProps {
  files: VaultFile[]
  onOpenFile: (id: string, tab?: WorkspaceTab) => void
  allCollections: string[]
}

interface WeekGroup {
  weekKey: string
  weekNumber: number
  weekLabel: string
  files: VaultFile[]
}

/** Groups files by their real upload week and numbers weeks sequentially
 * (earliest = Week 1) — exactly the "Week 1 / Week 2 / Week 3" example
 * from the spec, computed from real upload timestamps, not hardcoded. */
function groupByWeek(files: VaultFile[]): WeekGroup[] {
  const uniqueWeekKeys = [...new Set(files.map((f) => f.weekKey))].sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime()
  )
  const weekNumberByKey = new Map(uniqueWeekKeys.map((key, i) => [key, i + 1]))

  const groups = new Map<string, WeekGroup>()
  for (const file of files) {
    if (!groups.has(file.weekKey)) {
      groups.set(file.weekKey, {
        weekKey: file.weekKey,
        weekNumber: weekNumberByKey.get(file.weekKey) ?? 1,
        weekLabel: file.weekLabel,
        files: [],
      })
    }
    groups.get(file.weekKey)!.files.push(file)
  }

  return [...groups.values()].sort((a, b) => b.weekNumber - a.weekNumber)
}

type SortMode = 'recent' | 'title' | 'progress'

/** Automatically groups uploaded files by week with collapse/expand,
 * sort, and per-week file grids — the spec's "Week Organization" section. */
export default function WeekTimeline({ files, onOpenFile, allCollections }: WeekTimelineProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [sortMode, setSortMode] = useState<SortMode>('recent')

  const groups = useMemo(() => groupByWeek(files), [files])

  function sortFiles(list: VaultFile[]): VaultFile[] {
    const copy = [...list]
    switch (sortMode) {
      case 'title':
        return copy.sort((a, b) => a.title.localeCompare(b.title))
      case 'progress':
        return copy.sort((a, b) => b.progressPct - a.progressPct)
      case 'recent':
      default:
        return copy.sort((a, b) => b.uploadedAt - a.uploadedAt)
    }
  }

  if (groups.length === 0) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          📅 Week Timeline
        </h3>
        <div
          className="flex items-center gap-1 p-1 rounded-lg"
          style={{ background: 'var(--muted)' }}
        >
          {(
            [
              { id: 'recent', label: 'Recent' },
              { id: 'title', label: 'A–Z' },
              { id: 'progress', label: 'Progress' },
            ] as const
          ).map((opt) => (
            <button
              key={opt.id}
              onClick={() => setSortMode(opt.id)}
              className="px-2.5 py-1 rounded-md text-xs font-semibold transition-colors"
              style={{
                background: sortMode === opt.id ? 'var(--primary)' : 'transparent',
                color:
                  sortMode === opt.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {groups.map((group) => {
        const isCollapsed = collapsed[group.weekKey]
        return (
          <div key={group.weekKey} className="glass-card overflow-hidden">
            <button
              onClick={() =>
                setCollapsed((prev) => ({ ...prev, [group.weekKey]: !prev[group.weekKey] }))
              }
              className="w-full flex items-center gap-3 px-5 py-3.5 text-left"
            >
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{ background: 'rgba(45,212,191,0.12)', color: 'var(--primary)' }}
              >
                W{group.weekNumber}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                  Week {group.weekNumber}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {group.weekLabel} · {group.files.length} file{group.files.length === 1 ? '' : 's'}
                </p>
              </div>
              <motion.span
                animate={{ rotate: isCollapsed ? 0 : 90 }}
                style={{ color: 'var(--muted-foreground)' }}
              >
                ›
              </motion.span>
            </button>

            <AnimatePresence initial={false}>
              {!isCollapsed && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{ overflow: 'hidden' }}
                >
                  <div className="px-5 pb-5 pt-1">
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 pb-4">
                      {sortFiles(group.files).map((file, i) => (
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
      })}
    </div>
  )
}

import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useFileVault } from '../../../context/FileVaultContext'
import type { VaultFile } from '../../../types/fileVault'
import { aiReadinessScore } from '../../../types/fileVault'
import FileUploadZone from './files/FileUploadZone'
import FileSearchAndFilters, {
  defaultFilters,
  type FileVaultFilters,
} from './files/FileSearchAndFilters'
import WeekTimeline from './files/WeekTimeline'
import FileCard, { type WorkspaceTab } from './files/FileCard'
import FileWorkspace from './files/FileWorkspace'
import RecentActivityRail, { AiRecommendationsPanel } from './files/RecentActivityAndInsights'
import StatCard from '../shared/StatCard'
import EmptyState from '../shared/EmptyState'

/** Matches a file against a free-text query across filename, course,
 * doctor, and — crucially — its real AI-extracted key concepts and
 * definition terms, so searching "Binary Trees" finds any PDF whose
 * actual content discusses binary trees, per the spec's semantic search
 * requirement. */
function matchesFileSearch(file: VaultFile, query: string): boolean {
  if (!query.trim()) return true
  const q = query.toLowerCase()
  const haystacks = [
    file.title,
    file.course,
    file.doctorName,
    file.weekLabel,
    ...(file.analysis?.keyConcepts ?? []),
    ...(file.analysis?.definitions.map((d) => d.term) ?? []),
    ...(file.tags ?? []),
  ]
  return haystacks.some((h) => h.toLowerCase().includes(q))
}

/**
 * Smart AI File Vault — the student's intelligent academic library.
 * Layout follows the spec exactly: Search → Filters → Week Timeline →
 * Files Grid → AI Insights, backed entirely by real pdf.js extraction,
 * a deterministic extractive-AI analysis engine, and IndexedDB
 * persistence (see src/lib/fileVault/* and src/context/FileVaultContext).
 */
export default function MyFilesPage() {
  const { files, loading } = useFileVault()
  const [filters, setFilters] = useState<FileVaultFilters>(defaultFilters)
  const [openFileId, setOpenFileId] = useState<string | null>(null)
  const [openTab, setOpenTab] = useState<WorkspaceTab>('viewer')

  const courses = useMemo(() => [...new Set(files.map((f) => f.course))].sort(), [files])

  const filteredFiles = useMemo(() => {
    let list = files.filter((f) => matchesFileSearch(f, filters.query))
    if (filters.course) list = list.filter((f) => f.course === filters.course)
    if (filters.status !== 'all') list = list.filter((f) => f.status === filters.status)
    if (filters.onlyFavorites) list = list.filter((f) => f.favorite)
    if (filters.onlyPinned) list = list.filter((f) => f.pinned)

    switch (filters.sortBy) {
      case 'recent-viewed':
        return [...list].sort((a, b) => (b.lastViewedAt ?? 0) - (a.lastViewedAt ?? 0))
      case 'title':
        return [...list].sort((a, b) => a.title.localeCompare(b.title))
      case 'recent-upload':
      default:
        return [...list].sort((a, b) => b.uploadedAt - a.uploadedAt)
    }
  }, [files, filters])

  const openFile = files.find((f) => f.id === openFileId)

  function handleOpenFile(id: string, tab: WorkspaceTab = 'viewer') {
    setOpenFileId(id)
    setOpenTab(tab)
  }

  if (openFile) {
    return <FileWorkspace file={openFile} initialTab={openTab} onBack={() => setOpenFileId(null)} />
  }

  const completedCount = files.filter((f) => f.status === 'completed').length
  const totalStudyMinutes = Math.round(files.reduce((sum, f) => sum + f.studyTimeSeconds, 0) / 60)
  const avgReadiness =
    files.length > 0
      ? Math.round(files.reduce((sum, f) => sum + aiReadinessScore(f), 0) / files.length)
      : 0
  const pinnedFiles = files.filter((f) => f.pinned)

  const isFiltering =
    filters.query.trim() !== '' ||
    filters.course !== null ||
    filters.status !== 'all' ||
    filters.onlyFavorites ||
    filters.onlyPinned

  return (
    <div className="space-y-6">
      {/* Stats overview */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="📚"
          label="Total Documents"
          value={files.length}
          color="#2DD4BF"
          delay={0}
        />
        <StatCard icon="✅" label="Completed" value={completedCount} color="#22c55e" delay={0.05} />
        <StatCard
          icon="⏱️"
          label="Study Time"
          value={totalStudyMinutes}
          suffix="m"
          color="#f59e0b"
          delay={0.1}
        />
        <StatCard
          icon="🧠"
          label="Avg. AI Readiness"
          value={avgReadiness}
          suffix="%"
          color="#a855f7"
          delay={0.15}
        />
      </div>

      <FileUploadZone />

      {loading ? (
        <div
          className="glass-card p-10 text-center text-sm"
          style={{ color: 'var(--muted-foreground)' }}
        >
          Loading your file library...
        </div>
      ) : files.length === 0 ? (
        <div className="glass-card">
          <EmptyState
            icon="📚"
            title="Your library is empty"
            body="Upload your first PDF to build your AI-powered academic workspace."
          />
        </div>
      ) : (
        <>
          <FileSearchAndFilters filters={filters} onChange={setFilters} courses={courses} />

          {!isFiltering && <RecentActivityRail files={files} onOpenFile={handleOpenFile} />}

          {pinnedFiles.length > 0 && !isFiltering && (
            <div>
              <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
                📌 Pinned
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {pinnedFiles.map((file, i) => (
                  <FileCard
                    key={file.id}
                    file={file}
                    delay={i * 0.04}
                    onOpen={(tab) => handleOpenFile(file.id, tab)}
                  />
                ))}
              </div>
            </div>
          )}

          {isFiltering ? (
            filteredFiles.length === 0 ? (
              <div className="glass-card">
                <EmptyState
                  icon="🔍"
                  title="No files match your search"
                  body="Try a different keyword or clear your filters."
                />
              </div>
            ) : (
              <div>
                <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
                  {filteredFiles.length} result{filteredFiles.length === 1 ? '' : 's'}
                </h3>
                <motion.div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4" layout>
                  {filteredFiles.map((file, i) => (
                    <FileCard
                      key={file.id}
                      file={file}
                      delay={i * 0.04}
                      onOpen={(tab) => handleOpenFile(file.id, tab)}
                    />
                  ))}
                </motion.div>
              </div>
            )
          ) : (
            <WeekTimeline files={filteredFiles} onOpenFile={handleOpenFile} />
          )}

          <AiRecommendationsPanel files={files} onOpenFile={handleOpenFile} />
        </>
      )}
    </div>
  )
}

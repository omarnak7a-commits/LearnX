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
import RecentActivityRail from './files/RecentActivityAndInsights'
import TodaysStudyPlan from './files/TodaysStudyPlan'
import StudyInsightsStrip from './files/StudyInsightsStrip'
import StudyTimeline from './files/StudyTimeline'
import SmartGroups from './files/SmartGroups'
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
    ...(file.collections ?? []),
  ]
  return haystacks.some((h) => h.toLowerCase().includes(q))
}

/**
 * My Files — the student's complete AI Study Hub. Every uploaded PDF
 * automatically becomes part of the study plan; there is no separate
 * "Smart Planner" page. Layout: AI Insights → Today's AI Study Plan →
 * Search → Filters → Smart Organization (This Week/Next Week/Completed/
 * Needs Revision/Recently Viewed/Favorites/Upcoming Exams) → Study
 * Timeline → Week Timeline → Files Grid — all computed live from real
 * pdf.js extraction, a deterministic extractive-AI analysis engine, and
 * IndexedDB persistence (see src/lib/fileVault/* and
 * src/context/FileVaultContext). Planning logic itself lives in
 * src/lib/fileVault/studyHub.ts and is derived entirely from file state
 * — nothing is manually built by the student.
 */
export default function MyFilesPage() {
  const { files, loading } = useFileVault()
  const [filters, setFilters] = useState<FileVaultFilters>(defaultFilters)
  const [openFileId, setOpenFileId] = useState<string | null>(null)
  const [openTab, setOpenTab] = useState<WorkspaceTab>('viewer')

  const courses = useMemo(() => [...new Set(files.map((f) => f.course))].sort(), [files])
  const allCollections = useMemo(
    () => [...new Set(files.flatMap((f) => f.collections))].sort(),
    [files]
  )

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
      {/* AI Insights strip */}
      {!loading && files.length > 0 && (
        <StudyInsightsStrip files={files} onOpenFile={handleOpenFile} />
      )}

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

      {/* Today's AI Study Plan — replaces the standalone Smart Planner page */}
      {!loading && files.length > 0 && (
        <TodaysStudyPlan files={files} onOpenFile={handleOpenFile} />
      )}

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

          {!isFiltering && (
            <SmartGroups
              files={files}
              onOpenFile={handleOpenFile}
              allCollections={allCollections}
            />
          )}

          {!isFiltering && <StudyTimeline files={files} onOpenFile={handleOpenFile} />}

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
                    allCollections={allCollections}
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
                      allCollections={allCollections}
                    />
                  ))}
                </motion.div>
              </div>
            )
          ) : (
            <WeekTimeline
              files={filteredFiles}
              onOpenFile={handleOpenFile}
              allCollections={allCollections}
            />
          )}
        </>
      )}
    </div>
  )
}

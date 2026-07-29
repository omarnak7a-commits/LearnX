import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export interface FileVaultFilters {
  query: string
  course: string | null
  status: 'all' | 'not-started' | 'in-progress' | 'viewed' | 'completed'
  onlyFavorites: boolean
  onlyPinned: boolean
  sortBy: 'recent-upload' | 'recent-viewed' | 'title'
}

export const defaultFilters: FileVaultFilters = {
  query: '',
  course: null,
  status: 'all',
  onlyFavorites: false,
  onlyPinned: false,
  sortBy: 'recent-upload',
}

interface FileSearchAndFiltersProps {
  filters: FileVaultFilters
  onChange: (filters: FileVaultFilters) => void
  courses: string[]
}

const statusOptions: Array<{ id: FileVaultFilters['status']; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'not-started', label: 'Not Started' },
  { id: 'in-progress', label: 'In Progress' },
  { id: 'viewed', label: 'Viewed' },
  { id: 'completed', label: 'Completed' },
]

/**
 * Search + filter bar for the file library. Search is genuinely semantic
 * within the scope of what we can compute client-side: it matches not
 * just filenames but each document's real AI-extracted key concepts and
 * definitions, so searching "Binary Trees" finds any PDF whose actual
 * content discusses binary trees — see `matchesFileSearch` in
 * `MyFilesPage.tsx` for the matching logic that consumes this query.
 */
export default function FileSearchAndFilters({
  filters,
  onChange,
  courses,
}: FileSearchAndFiltersProps) {
  const [filtersOpen, setFiltersOpen] = useState(false)

  function update<K extends keyof FileVaultFilters>(key: K, value: FileVaultFilters[K]) {
    onChange({ ...filters, [key]: value })
  }

  const activeFilterCount =
    (filters.course ? 1 : 0) +
    (filters.status !== 'all' ? 1 : 0) +
    (filters.onlyFavorites ? 1 : 0) +
    (filters.onlyPinned ? 1 : 0)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: 'var(--muted-foreground)' }}
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            value={filters.query}
            onChange={(e) => update('query', e.target.value)}
            placeholder="Search by course, doctor, topic, or keyword — e.g. 'Binary Trees'"
            className="input-field w-full pl-10 pr-3.5 py-2.5 rounded-xl text-sm"
          />
        </div>

        <button
          onClick={() => setFiltersOpen((v) => !v)}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
          style={{
            background: filtersOpen ? 'var(--primary)' : 'var(--tint-2)',
            color: filtersOpen ? 'var(--primary-foreground)' : 'var(--foreground)',
          }}
        >
          ⚙️ Filters
          {activeFilterCount > 0 && (
            <span
              className="text-xs px-1.5 rounded-full font-mono"
              style={{
                background: filtersOpen ? 'rgba(0,0,0,0.2)' : 'var(--primary)',
                color: filtersOpen ? '#fff' : 'var(--primary-foreground)',
              }}
            >
              {activeFilterCount}
            </span>
          )}
        </button>

        <select
          value={filters.sortBy}
          onChange={(e) => update('sortBy', e.target.value as FileVaultFilters['sortBy'])}
          className="input-field px-3 py-2.5 rounded-xl text-sm"
        >
          <option value="recent-upload">Recently Uploaded</option>
          <option value="recent-viewed">Recently Viewed</option>
          <option value="title">A–Z</option>
        </select>
      </div>

      <AnimatePresence initial={false}>
        {filtersOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div className="glass-card p-4 flex flex-wrap items-center gap-4">
              <div>
                <p
                  className="text-xs font-semibold mb-1.5"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Course
                </p>
                <select
                  value={filters.course ?? ''}
                  onChange={(e) => update('course', e.target.value || null)}
                  className="input-field px-3 py-1.5 rounded-lg text-xs"
                >
                  <option value="">All courses</option>
                  {courses.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <p
                  className="text-xs font-semibold mb-1.5"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Status
                </p>
                <div className="flex flex-wrap gap-1">
                  {statusOptions.map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => update('status', opt.id)}
                      className="text-xs px-2.5 py-1 rounded-lg font-medium transition-colors"
                      style={{
                        background: filters.status === opt.id ? 'var(--primary)' : 'var(--tint-2)',
                        color:
                          filters.status === opt.id
                            ? 'var(--primary-foreground)'
                            : 'var(--muted-foreground)',
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <ToggleChip
                  active={filters.onlyFavorites}
                  onClick={() => update('onlyFavorites', !filters.onlyFavorites)}
                >
                  ★ Favorites
                </ToggleChip>
                <ToggleChip
                  active={filters.onlyPinned}
                  onClick={() => update('onlyPinned', !filters.onlyPinned)}
                >
                  📌 Pinned
                </ToggleChip>
              </div>

              {activeFilterCount > 0 && (
                <button
                  onClick={() => onChange(defaultFilters)}
                  className="text-xs font-semibold ml-auto"
                  style={{ color: 'var(--danger)' }}
                >
                  Clear all
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className="text-xs px-2.5 py-1.5 rounded-lg font-medium transition-colors"
      style={{
        background: active ? 'rgba(255,126,54,0.15)' : 'var(--tint-2)',
        color: active ? 'var(--accent)' : 'var(--muted-foreground)',
      }}
    >
      {children}
    </button>
  )
}

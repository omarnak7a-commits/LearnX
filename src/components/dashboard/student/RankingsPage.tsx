import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useProfileStats } from '../../../hooks/useProfileStats'
import { getSeededCohort } from '../../../data/leaderboardSeed'
import { applyRankingFilters, rankEntries, type RankedEntry } from '../../../lib/profile/ranking'
import { computeLevelProgress } from '../../../lib/profile/xp'
import { getBadgeDefinition } from '../../../data/badges'
import {
  getUniversity,
  getFaculty,
  getDepartment,
  UNIVERSITIES,
  FACULTIES,
  DEPARTMENTS,
  ACADEMIC_YEARS,
} from '../../../data/academicCatalog'
import { initialCourses } from '../../../data/coursesMock'
import SearchableSelect from '../../ui/SearchableSelect'
import Badge from '../../ui/Badge'
import type { RankingScope, RankingTimeframe } from '../../../types/profile'

const SCOPE_TABS: Array<{ id: RankingScope; label: string; icon: string }> = [
  { id: 'university', label: 'University', icon: '🏛️' },
  { id: 'faculty', label: 'Faculty', icon: '⚙️' },
  { id: 'department', label: 'Department', icon: '🧭' },
  { id: 'academicYear', label: 'Academic Year', icon: '📅' },
  { id: 'course', label: 'Course', icon: '📚' },
  { id: 'friends', label: 'Friends', icon: '🤝' },
]

const TIMEFRAME_TABS: Array<{ id: RankingTimeframe; label: string }> = [
  { id: 'weekly', label: 'Weekly' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'all-time', label: 'All Time' },
]

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }

function RankBadge({ rank }: { rank: number }) {
  const medal = MEDALS[rank]
  if (medal) {
    return <span className="text-xl">{medal}</span>
  }
  return (
    <span
      className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
      style={{ background: 'var(--tint-2)', color: 'var(--muted-foreground)' }}
    >
      {rank}
    </span>
  )
}

function StudentCard({ entry, index }: { entry: RankedEntry; index: number }) {
  const university = getUniversity(entry.universityId)
  const faculty = getFaculty(entry.facultyId)
  const department = getDepartment(entry.departmentId)
  const level = computeLevelProgress(entry.xp)

  return (
    <motion.div
      className="rounded-xl p-4 flex items-center gap-4 flex-wrap sm:flex-nowrap"
      style={{
        background: entry.isCurrentUser ? 'rgba(45,212,191,0.08)' : 'var(--tint-1)',
        border: `1px solid ${entry.isCurrentUser ? 'rgba(45,212,191,0.3)' : 'var(--border-subtle)'}`,
      }}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.5), duration: 0.35 }}
    >
      <RankBadge rank={entry.rank} />

      <div
        className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 overflow-hidden"
        style={{
          background: entry.avatarDataUrl
            ? undefined
            : 'linear-gradient(135deg, var(--primary), var(--secondary))',
          color: 'var(--primary-foreground)',
        }}
      >
        {entry.avatarDataUrl ? (
          <img
            src={entry.avatarDataUrl}
            alt={entry.fullName}
            className="w-full h-full object-cover"
          />
        ) : (
          entry.fullName.charAt(0).toUpperCase()
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p
          className="text-sm font-bold truncate flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          {entry.fullName}
          {entry.isCurrentUser && (
            <Badge tone="primary" size="xs">
              You
            </Badge>
          )}
        </p>
        <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
          {faculty?.name ?? university?.name ?? '—'}
          {department ? ` · ${department.name}` : ''}
        </p>
        {entry.badges.length > 0 && (
          <div className="flex gap-1 mt-1.5">
            {entry.badges.slice(0, 3).map((b) => (
              <span key={b} title={getBadgeDefinition(b).label} className="text-xs">
                {getBadgeDefinition(b).icon}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 sm:gap-5 flex-shrink-0 text-right">
        <div>
          <p
            className="text-sm font-black"
            style={{ color: 'var(--accent)', fontFamily: 'Orbitron, sans-serif' }}
          >
            L{level.level}
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Level
          </p>
        </div>
        <div>
          <p
            className="text-sm font-black"
            style={{ color: 'var(--primary)', fontFamily: 'Orbitron, sans-serif' }}
          >
            {entry.xp.toLocaleString()}
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            XP
          </p>
        </div>
        <div className="hidden sm:block">
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            {entry.studyHours}h
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Study
          </p>
        </div>
        <div className="hidden md:block">
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            {entry.coursesCompleted}
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Courses
          </p>
        </div>
        <div className="hidden md:block">
          <p
            className="text-sm font-bold flex items-center gap-1"
            style={{ color: 'var(--foreground)' }}
          >
            🔥 {entry.streakDays}d
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Streak
          </p>
        </div>
      </div>
    </motion.div>
  )
}

/**
 * Complete leaderboard per the spec's "STUDENT RANKING SYSTEM" /
 * "LEADERBOARD" / "FILTERS" sections — ranks the current user (real,
 * live stats from `useProfileStats()`) against the seeded peer cohort
 * (`getSeededCohort()`), with every scope/timeframe/filter the spec
 * calls for wired to `applyRankingFilters`/`rankEntries`
 * (`src/lib/profile/ranking.ts`) rather than being decorative tabs that
 * don't actually change the results.
 */
export default function RankingsPage() {
  const stats = useProfileStats()
  const [scope, setScope] = useState<RankingScope>('university')
  const [timeframe, setTimeframe] = useState<RankingTimeframe>('all-time')
  const [universityId, setUniversityId] = useState<string | null>(null)
  const [facultyId, setFacultyId] = useState<string | null>(null)
  const [departmentId, setDepartmentId] = useState<string | null>(null)
  const [academicYearId, setAcademicYearId] = useState<string | null>(null)
  const [courseId, setCourseId] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const cohort = useMemo(() => getSeededCohort(), [])
  const currentUser = stats.currentUserEntry

  const ranked = useMemo(() => {
    const pool = [currentUser, ...cohort]
    const filtered = applyRankingFilters(pool, currentUser, {
      scope,
      timeframe,
      universityId,
      facultyId,
      departmentId,
      academicYearId,
      courseId,
      search,
    })
    return rankEntries(filtered, timeframe)
  }, [
    currentUser,
    cohort,
    scope,
    timeframe,
    universityId,
    facultyId,
    departmentId,
    academicYearId,
    courseId,
    search,
  ])

  const myRank = ranked.find((e) => e.isCurrentUser)

  const facultyOptionsForFilter = useMemo(
    () => (universityId ? FACULTIES.filter((f) => f.universityId === universityId) : FACULTIES),
    [universityId]
  )
  const departmentOptionsForFilter = useMemo(
    () => (facultyId ? DEPARTMENTS.filter((d) => d.facultyId === facultyId) : DEPARTMENTS),
    [facultyId]
  )

  return (
    <div className="space-y-5">
      {/* Your rank hero */}
      {myRank && (
        <motion.div
          className="glass-card p-6"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                Your position in this leaderboard
              </p>
              <p
                className="text-3xl font-black"
                style={{ color: 'var(--primary)', fontFamily: 'Orbitron, sans-serif' }}
              >
                #{myRank.rank}{' '}
                <span className="text-sm font-normal" style={{ color: 'var(--muted-foreground)' }}>
                  of {ranked.length}
                </span>
              </p>
            </div>
            <div className="flex gap-5 text-right">
              <div>
                <p className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>
                  {stats.xp.toLocaleString()}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  Total XP
                </p>
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>
                  L{stats.level.level}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  Level
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Scope + timeframe */}
      <motion.div
        className="glass-card p-4 sm:p-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <div className="flex flex-wrap gap-2 mb-4">
          {SCOPE_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setScope(tab.id)}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
              style={{
                background: scope === tab.id ? 'var(--primary)' : 'var(--tint-1)',
                color: scope === tab.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--muted)' }}>
            {TIMEFRAME_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setTimeframe(tab.id)}
                className="relative px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors"
                style={{
                  color:
                    timeframe === tab.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                }}
              >
                {timeframe === tab.id && (
                  <motion.span
                    layoutId="ranking-timeframe-pill"
                    className="absolute inset-0 rounded-md -z-10"
                    style={{ background: 'var(--primary)' }}
                    transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                  />
                )}
                {tab.label}
              </button>
            ))}
          </div>

          <div className="input-field flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs w-full sm:w-64">
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              style={{ color: 'var(--muted-foreground)' }}
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search student…"
              className="flex-1 bg-transparent outline-none"
              style={{ color: 'var(--foreground)' }}
            />
          </div>
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div
        className="glass-card p-4 sm:p-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <p className="text-xs font-semibold mb-3" style={{ color: 'var(--muted-foreground)' }}>
          Narrow further
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <SearchableSelect
            label="University"
            placeholder="Any university"
            options={UNIVERSITIES.map((u) => ({ id: u.id, label: u.shortName }))}
            value={universityId}
            onChange={(id) => {
              setUniversityId(id)
              setFacultyId(null)
              setDepartmentId(null)
            }}
          />
          <SearchableSelect
            label="Faculty"
            placeholder="Any faculty"
            options={facultyOptionsForFilter.map((f) => ({
              id: f.id,
              label: f.name,
              icon: f.icon,
            }))}
            value={facultyId}
            onChange={(id) => {
              setFacultyId(id)
              setDepartmentId(null)
            }}
          />
          <SearchableSelect
            label="Department"
            placeholder="Any department"
            options={departmentOptionsForFilter.map((d) => ({ id: d.id, label: d.name }))}
            value={departmentId}
            onChange={setDepartmentId}
          />
          <SearchableSelect
            label="Academic Year"
            placeholder="Any year"
            options={ACADEMIC_YEARS.map((y) => ({ id: y.id, label: y.label }))}
            value={academicYearId}
            onChange={setAcademicYearId}
          />
          <SearchableSelect
            label="Course"
            placeholder="Any course"
            options={initialCourses.map((c) => ({ id: c.id, label: c.title }))}
            value={courseId}
            onChange={setCourseId}
          />
        </div>
      </motion.div>

      {/* Leaderboard */}
      <motion.div
        className="glass-card p-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            🏆 Leaderboard
          </h3>
          <Badge tone="neutral" size="xs" mono>
            {ranked.length} students
          </Badge>
        </div>

        <div className="space-y-2.5 max-h-[720px] overflow-y-auto scrollbar-thin pr-1">
          <AnimatePresence mode="popLayout">
            {ranked.map((entry, i) => (
              <StudentCard key={entry.id} entry={entry} index={i} />
            ))}
          </AnimatePresence>
          {ranked.length === 0 && (
            <p className="text-xs text-center py-8" style={{ color: 'var(--muted-foreground)' }}>
              No students match these filters.
            </p>
          )}
        </div>
      </motion.div>
    </div>
  )
}

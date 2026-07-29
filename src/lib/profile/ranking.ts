import type { LeaderboardEntry, RankingScope, RankingTimeframe } from '../../types/profile'

/** Which numeric field a timeframe ranks by. */
export function xpFieldForTimeframe(timeframe: RankingTimeframe): 'xp' | 'weeklyXp' | 'monthlyXp' {
  if (timeframe === 'weekly') return 'weeklyXp'
  if (timeframe === 'monthly') return 'monthlyXp'
  return 'xp'
}

export interface RankingFilters {
  scope: RankingScope
  timeframe: RankingTimeframe
  universityId?: string | null
  facultyId?: string | null
  departmentId?: string | null
  academicYearId?: string | null
  courseId?: string | null
  search?: string
}

/** Narrows the full pool (current user + seeded cohort) down to whichever
 *  peer group the selected scope implies, before ranking. `scope` and the
 *  explicit filter fields are independent — scope decides which single
 *  dimension is *used for peer-grouping* (e.g. "Faculty" ranks everyone
 *  in the current user's faculty), while the explicit filters narrow the
 *  visible table further (e.g. also only Course X, also search "ahmed"). */
export function applyRankingFilters(
  pool: LeaderboardEntry[],
  currentUser: LeaderboardEntry,
  filters: RankingFilters
): LeaderboardEntry[] {
  let result = pool

  switch (filters.scope) {
    case 'university':
      result = result.filter((e) => e.universityId === currentUser.universityId)
      break
    case 'faculty':
      result = result.filter((e) => e.facultyId === currentUser.facultyId)
      break
    case 'department':
      result = result.filter((e) => e.departmentId === currentUser.departmentId)
      break
    case 'academicYear':
      result = result.filter((e) => e.academicYearId === currentUser.academicYearId)
      break
    case 'course':
      if (filters.courseId) {
        result = result.filter((e) => e.courseIds.includes(filters.courseId!))
      }
      break
    case 'friends':
      result = result.filter((e) => e.isFriend || e.isCurrentUser)
      break
  }

  if (filters.universityId) {
    result = result.filter((e) => e.universityId === filters.universityId)
  }
  if (filters.facultyId) {
    result = result.filter((e) => e.facultyId === filters.facultyId)
  }
  if (filters.departmentId) {
    result = result.filter((e) => e.departmentId === filters.departmentId)
  }
  if (filters.academicYearId) {
    result = result.filter((e) => e.academicYearId === filters.academicYearId)
  }
  if (filters.scope !== 'course' && filters.courseId) {
    result = result.filter((e) => e.courseIds.includes(filters.courseId!))
  }
  if (filters.search && filters.search.trim().length > 0) {
    const q = filters.search.trim().toLowerCase()
    result = result.filter((e) => e.fullName.toLowerCase().includes(q))
  }

  // Always guarantee the current user appears even if a narrow filter
  // combination would otherwise exclude them (e.g. searching a name that
  // isn't theirs) — matches "know their current rank among classmates"
  // requirement; the rank number is still computed against the *filtered*
  // pool including them.
  if (!result.some((e) => e.isCurrentUser)) {
    result = [...result, currentUser]
  }

  return result
}

export interface RankedEntry extends LeaderboardEntry {
  rank: number
  sortValue: number
}

/** Sorts by the timeframe's XP field (descending) and assigns 1-based
 *  ranks, with stable tie-breaking by total XP then name so ranks never
 *  flicker between renders. */
export function rankEntries(
  entries: LeaderboardEntry[],
  timeframe: RankingTimeframe
): RankedEntry[] {
  const field = xpFieldForTimeframe(timeframe)
  const sorted = [...entries].sort((a, b) => {
    if (b[field] !== a[field]) return b[field] - a[field]
    if (b.xp !== a.xp) return b.xp - a.xp
    return a.fullName.localeCompare(b.fullName)
  })
  return sorted.map((entry, i) => ({ ...entry, rank: i + 1, sortValue: entry[field] }))
}

/** Convenience: current user's rank + pool size for a given scope, used
 *  by the compact Dashboard Integration widget ("Rank #8"). */
export function findCurrentUserRank(
  pool: LeaderboardEntry[],
  currentUser: LeaderboardEntry,
  filters: RankingFilters
): { rank: number; total: number } {
  const filtered = applyRankingFilters(pool, currentUser, filters)
  const ranked = rankEntries(filtered, filters.timeframe)
  const mine = ranked.find((e) => e.isCurrentUser)
  return { rank: mine?.rank ?? ranked.length, total: ranked.length }
}

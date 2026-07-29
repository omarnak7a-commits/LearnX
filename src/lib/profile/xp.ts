/**
 * Pure XP/level math for the Duolingo-style progression system. No React,
 * no side effects — deterministic functions so both the Profile page,
 * dashboard widgets, TopBar XP badge, and leaderboard can all compute the
 * exact same level/progress numbers from a single `xp` integer instead of
 * storing level redundantly and letting it drift out of sync.
 *
 * Level curve: level N requires cumulative XP of `250 * N * (N + 1) / 2`
 * (triangular growth) — i.e. level 1→2 costs 500 XP, level 2→3 costs
 * 750 XP, etc., so early levels come quickly and later levels take
 * meaningfully longer, matching typical gamified-learning curves.
 */

const BASE_XP_PER_LEVEL = 250

/** Total cumulative XP required to *reach* the given level (level 1 = 0). */
export function xpRequiredForLevel(level: number): number {
  if (level <= 1) return 0
  const n = level - 1
  return BASE_XP_PER_LEVEL * ((n * (n + 1)) / 2 + n)
}

export interface LevelProgress {
  level: number
  currentLevelXp: number
  xpIntoLevel: number
  xpForNextLevel: number
  xpToNextLevel: number
  progressPct: number
}

/** Resolve a raw XP total into level + progress-to-next-level, single
 *  source of truth used everywhere a "Level N · X% to Level N+1" readout
 *  is shown. */
export function computeLevelProgress(xp: number): LevelProgress {
  const safeXp = Math.max(0, Math.floor(xp))
  let level = 1
  while (xpRequiredForLevel(level + 1) <= safeXp) {
    level += 1
  }
  const currentLevelXp = xpRequiredForLevel(level)
  const nextLevelXp = xpRequiredForLevel(level + 1)
  const xpForNextLevel = nextLevelXp - currentLevelXp
  const xpIntoLevel = safeXp - currentLevelXp
  const xpToNextLevel = Math.max(0, nextLevelXp - safeXp)
  const progressPct =
    xpForNextLevel > 0 ? Math.min(100, Math.round((xpIntoLevel / xpForNextLevel) * 100)) : 100

  return {
    level,
    currentLevelXp,
    xpIntoLevel,
    xpForNextLevel,
    xpToNextLevel,
    progressPct,
  }
}

/** Whether studying "today" (ISO date) continues an existing streak,
 *  starts a new one, or is a no-op repeat of today. */
export function nextStreak(
  lastStudyDateIso: string | null,
  todayIso: string,
  currentStreak: number
): number {
  if (!lastStudyDateIso) return 1
  if (lastStudyDateIso === todayIso) return currentStreak || 1

  const last = new Date(lastStudyDateIso + 'T00:00:00Z').getTime()
  const today = new Date(todayIso + 'T00:00:00Z').getTime()
  const dayMs = 24 * 60 * 60 * 1000
  const diffDays = Math.round((today - last) / dayMs)

  if (diffDays === 1) return (currentStreak || 0) + 1
  if (diffDays <= 0) return currentStreak || 1
  return 1 // streak broken — more than a day gap
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

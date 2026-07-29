import type { ChallengeDefinition } from '../../types/gamification'
import { hashString, seededRandom } from '../profile/random'

/**
 * Catalog of every possible Daily/Weekly Challenge from the spec's
 * FEATURE 5/6 sections. A deterministic seeded subset "rotates in" per
 * period (day for daily, ISO week for weekly) — same rotation
 * methodology as the seeded leaderboard cohort (`leaderboardSeed.ts`):
 * a fixed seed derived from the period key means the same challenges
 * show up for the same day/week across reloads, but change when the
 * calendar day/week actually changes, without needing a server.
 */

const DAILY_POOL: ChallengeDefinition[] = [
  {
    id: 'daily-study-30',
    cadence: 'daily',
    metric: 'study-minutes',
    label: 'Study 30 minutes',
    icon: '⏱️',
    target: 30,
    xpReward: 40,
  },
  {
    id: 'daily-quiz',
    cadence: 'daily',
    metric: 'quiz-complete',
    label: 'Complete a quiz',
    icon: '❓',
    target: 1,
    xpReward: 100,
  },
  {
    id: 'daily-lesson',
    cadence: 'daily',
    metric: 'lesson-complete',
    label: 'Finish a lesson',
    icon: '🎬',
    target: 1,
    xpReward: 50,
  },
  {
    id: 'daily-flashcards',
    cadence: 'daily',
    metric: 'flashcards-generated',
    label: 'Generate flashcards',
    icon: '🗂️',
    target: 1,
    xpReward: 25,
  },
  {
    id: 'daily-read-pdf',
    cadence: 'daily',
    metric: 'pdf-read',
    label: 'Read a PDF page',
    icon: '📖',
    target: 5,
    xpReward: 30,
  },
  {
    id: 'daily-watch-lecture',
    cadence: 'daily',
    metric: 'lecture-watched',
    label: 'Watch a lecture',
    icon: '🎥',
    target: 1,
    xpReward: 50,
  },
  {
    id: 'daily-upload-notes',
    cadence: 'daily',
    metric: 'notes-uploaded',
    label: 'Upload notes',
    icon: '📝',
    target: 1,
    xpReward: 20,
  },
  {
    id: 'daily-assignment',
    cadence: 'daily',
    metric: 'assignment-complete',
    label: 'Complete an assignment',
    icon: '📋',
    target: 1,
    xpReward: 80,
  },
]

const WEEKLY_POOL: ChallengeDefinition[] = [
  {
    id: 'weekly-study-5h',
    cadence: 'weekly',
    metric: 'study-minutes',
    label: 'Study 5 hours',
    icon: '⏱️',
    target: 300,
    xpReward: 400,
    bonusBadgeId: 'weekly-champion',
  },
  {
    id: 'weekly-finish-course',
    cadence: 'weekly',
    metric: 'course-complete',
    label: 'Finish a course',
    icon: '🎓',
    target: 1,
    xpReward: 600,
    bonusCouponPercent: 15,
  },
  {
    id: 'weekly-streak-7',
    cadence: 'weekly',
    metric: 'streak-days',
    label: 'Maintain a 7-day streak',
    icon: '🔥',
    target: 7,
    xpReward: 300,
    bonusBadgeId: '30-day-streak',
  },
  {
    id: 'weekly-high-score',
    cadence: 'weekly',
    metric: 'quiz-high-score',
    label: 'Score above 90% on a quiz',
    icon: '🌟',
    target: 1,
    xpReward: 250,
    bonusCouponPercent: 10,
  },
  {
    id: 'weekly-earn-1000xp',
    cadence: 'weekly',
    metric: 'xp-earned',
    label: 'Earn 1,000 XP',
    icon: '⚡',
    target: 1000,
    xpReward: 200,
  },
]

const DAILY_ROTATION_SIZE = 4
const WEEKLY_ROTATION_SIZE = 3

/** ISO date string, e.g. "2026-07-29" — the daily rotation key. */
export function dailyPeriodKey(date = new Date()): string {
  return date.toISOString().slice(0, 10)
}

/** Monday-anchored ISO date string for the week containing `date` — the
 *  weekly rotation key (matches `weekKeyFor` in fileVault/weeks.ts). */
export function weeklyPeriodKey(date = new Date()): string {
  const d = new Date(date)
  const day = d.getDay()
  const diff = (day + 6) % 7
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - diff)
  return d.toISOString().slice(0, 10)
}

function pickRotation(
  pool: ChallengeDefinition[],
  periodKey: string,
  count: number
): ChallengeDefinition[] {
  const rng = seededRandom(hashString(periodKey))
  const shuffled = [...pool]
  // Fisher-Yates using the seeded RNG so the same period always yields
  // the same order/selection.
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled.slice(0, Math.min(count, shuffled.length))
}

export function getTodaysDailyChallenges(): ChallengeDefinition[] {
  return pickRotation(DAILY_POOL, dailyPeriodKey(), DAILY_ROTATION_SIZE)
}

export function getThisWeeksChallenges(): ChallengeDefinition[] {
  return pickRotation(WEEKLY_POOL, weeklyPeriodKey(), WEEKLY_ROTATION_SIZE)
}

export function getChallengeDefinition(id: string): ChallengeDefinition | undefined {
  return [...DAILY_POOL, ...WEEKLY_POOL].find((c) => c.id === id)
}

import type { BadgeId } from '../../types/profile'

export interface BadgeEngineInput {
  streakDays: number
  quizScores: number[] // scorePct of every practice quiz attempt across all files
  examScores: number[] // scorePct of every exam attempt across all files
  coursesCompleted: number
  usedQuiz: boolean
  usedExam: boolean
  usedNotes: boolean
  usedBookmarks: boolean
  allTimeRank: number | null
  allTimePoolSize: number
  weeklyRank: number | null
  monthlyRank: number | null
  isEngineeringFaculty: boolean
  engineeringFacultyRank: number | null
}

/**
 * Every badge is *earned automatically* from real, already-tracked
 * activity — reading progress, real quiz/exam scores (from the
 * deterministic AI Study Hub engine), real notes/bookmarks the student
 * actually created, real course completions, and real leaderboard
 * standing (computed in `ranking.ts` against the same seeded cohort the
 * Rankings page renders). There is no manual "grant badge" button
 * anywhere — this keeps the badge system honest instead of being
 * placeholder UI.
 */
export function computeEarnedBadges(input: BadgeEngineInput): BadgeId[] {
  const earned = new Set<BadgeId>()

  if (input.streakDays >= 30) earned.add('30-day-streak')
  if (input.quizScores.some((s) => s >= 100) || input.examScores.some((s) => s >= 100)) {
    earned.add('perfect-quiz')
  }
  if (input.coursesCompleted >= 10) earned.add('course-master')
  if (input.usedQuiz && input.usedExam && input.usedNotes && input.usedBookmarks) {
    earned.add('ai-explorer')
  }
  if (input.coursesCompleted >= 1 && input.examScores.some((s) => s >= 85)) {
    earned.add('fast-learner')
  }
  if (input.allTimeRank !== null && input.allTimeRank <= 10 && input.allTimePoolSize >= 10) {
    earned.add('top-10-student')
  }
  if (input.isEngineeringFaculty && input.engineeringFacultyRank === 1) {
    earned.add('top-engineering-student')
  }
  if (input.weeklyRank === 1) earned.add('weekly-champion')
  if (input.monthlyRank === 1) earned.add('monthly-champion')

  return Array.from(earned)
}

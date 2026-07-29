import { useMemo } from 'react'
import { useProfile } from '../context/ProfileContext'
import { useCourseCatalog } from '../context/CourseCatalogContext'
import { useFileVault } from '../context/FileVaultContext'
import { useXp } from '../context/XpContext'
import { isFullyRead } from '../types/fileVault'
import type { LevelProgress } from '../lib/profile/xp'
import { computeEarnedBadges } from '../lib/profile/badgeEngine'
import { applyRankingFilters, rankEntries } from '../lib/profile/ranking'
import { getSeededCohort } from '../data/leaderboardSeed'
import { getFaculty } from '../data/academicCatalog'
import type { BadgeId, LeaderboardEntry } from '../types/profile'

export interface ProfileStats {
  xp: number
  level: LevelProgress
  studyHours: number
  coursesEnrolled: number
  coursesCompleted: number
  filesUploaded: number
  filesFullyRead: number
  quizzesTaken: number
  averageQuizScore: number | null
  badges: BadgeId[]
  currentUserEntry: LeaderboardEntry
  allTimeRank: number
  allTimePoolSize: number
  weeklyRank: number
  monthlyRank: number
}

/**
 * Single source of truth turning real, already-tracked student activity
 * (course enrollment/progress from `useCourseCatalog()`, File Vault
 * reading + quiz/exam history from `useFileVault()`, the persisted
 * streak from `useProfile()`, and — since the Global XP System shipped —
 * the real XP ledger from `useXp()`) into every derived progression
 * number the spec asks for: XP, Level, Study Hours, Courses Completed,
 * Badges, and Current Rank.
 *
 * XP/Level themselves are read straight from `useXp()` (the spec's
 * "Create ONE centralized XP system... XP should be stored globally")
 * rather than computed independently here, so the Profile page, Sidebar,
 * TopBar, Rankings leaderboard, Dashboard widget, Gamification page, and
 * Reward Store all show the exact same number — there is exactly one XP
 * total in this app. Everything else here (study hours, quiz average,
 * badges, rank) is still derived live from real activity, never stored
 * redundantly.
 */
export function useProfileStats(): ProfileStats {
  const { profile } = useProfile()
  const { courses } = useCourseCatalog()
  const { files } = useFileVault()
  const { totalXp, weeklyXp, monthlyXp, level } = useXp()

  return useMemo(() => {
    const enrolledCourses = courses.filter((c) => c.enrolled)
    const coursesCompleted = enrolledCourses.filter((c) => c.progressPct >= 100).length

    const quizAttempts = files.flatMap((f) => f.quizAttempts)
    const examAttempts = files.flatMap((f) => f.examAttempts)
    const allAttempts = [...quizAttempts, ...examAttempts]
    const averageQuizScore =
      allAttempts.length > 0
        ? Math.round(allAttempts.reduce((sum, a) => sum + a.scorePct, 0) / allAttempts.length)
        : null

    const filesFullyRead = files.filter(isFullyRead).length
    const studyTimeSeconds = files.reduce((sum, f) => sum + f.studyTimeSeconds, 0)
    const studyHours = Math.round((studyTimeSeconds / 3600) * 10) / 10

    const university = profile?.universityId ?? 'cairo-u'
    const faculty = profile?.facultyId ?? null
    const department = profile?.departmentId ?? null
    const academicYear = profile?.academicYearId ?? null

    const currentUserEntry: LeaderboardEntry = {
      id: 'me',
      isCurrentUser: true,
      fullName: profile?.fullName || 'You',
      avatarDataUrl: profile?.avatarDataUrl ?? null,
      universityId: university,
      facultyId: faculty ?? '',
      departmentId: department ?? '',
      academicYearId: academicYear ?? '',
      courseIds: enrolledCourses.map((c) => c.id),
      xp: totalXp,
      weeklyXp,
      monthlyXp,
      studyHours,
      coursesCompleted,
      streakDays: profile?.streakDays ?? 0,
      badges: [],
      isFriend: false,
    }

    const cohort = getSeededCohort()
    const pool = [currentUserEntry, ...cohort]

    const allTimeFiltered = applyRankingFilters(pool, currentUserEntry, {
      scope: 'university',
      timeframe: 'all-time',
    })
    const allTimeRanked = rankEntries(allTimeFiltered, 'all-time')
    const allTimeRank = allTimeRanked.find((e) => e.isCurrentUser)?.rank ?? allTimeRanked.length
    const allTimePoolSize = allTimeRanked.length

    const weeklyRanked = rankEntries(
      applyRankingFilters(pool, currentUserEntry, { scope: 'university', timeframe: 'weekly' }),
      'weekly'
    )
    const weeklyRank = weeklyRanked.find((e) => e.isCurrentUser)?.rank ?? weeklyRanked.length

    const monthlyRanked = rankEntries(
      applyRankingFilters(pool, currentUserEntry, { scope: 'university', timeframe: 'monthly' }),
      'monthly'
    )
    const monthlyRank = monthlyRanked.find((e) => e.isCurrentUser)?.rank ?? monthlyRanked.length

    const facultyRanked = rankEntries(
      applyRankingFilters(pool, currentUserEntry, { scope: 'faculty', timeframe: 'all-time' }),
      'all-time'
    )
    const facultyRank = facultyRanked.find((e) => e.isCurrentUser)?.rank ?? null
    const facultyRecord = getFaculty(faculty)
    const isEngineeringFaculty = facultyRecord?.name === 'Faculty of Engineering'

    const badges = computeEarnedBadges({
      streakDays: profile?.streakDays ?? 0,
      quizScores: quizAttempts.map((a) => a.scorePct),
      examScores: examAttempts.map((a) => a.scorePct),
      coursesCompleted,
      usedQuiz: quizAttempts.length > 0,
      usedExam: examAttempts.length > 0,
      usedNotes: files.some((f) => f.notes.length > 0),
      usedBookmarks: files.some((f) => f.bookmarks.length > 0),
      allTimeRank,
      allTimePoolSize,
      weeklyRank,
      monthlyRank,
      isEngineeringFaculty,
      engineeringFacultyRank: isEngineeringFaculty ? facultyRank : null,
    })

    return {
      xp: totalXp,
      level,
      studyHours,
      coursesEnrolled: enrolledCourses.length,
      coursesCompleted,
      filesUploaded: files.length,
      filesFullyRead,
      quizzesTaken: allAttempts.length,
      averageQuizScore,
      badges,
      currentUserEntry: { ...currentUserEntry, badges },
      allTimeRank,
      allTimePoolSize,
      weeklyRank,
      monthlyRank,
    }
  }, [profile, courses, files, totalXp, weeklyXp, monthlyXp, level])
}

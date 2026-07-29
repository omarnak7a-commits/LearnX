import { useMemo } from 'react'
import { useProfile } from '../context/ProfileContext'
import { useCourseCatalog } from '../context/CourseCatalogContext'
import { useFileVault } from '../context/FileVaultContext'
import { isFullyRead } from '../types/fileVault'
import { computeLevelProgress, type LevelProgress } from '../lib/profile/xp'
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
 * reading + quiz/exam history from `useFileVault()`, and the persisted
 * streak from `useProfile()`) into every derived progression number the
 * spec asks for: XP, Level, Study Hours, Courses Completed, Badges, and
 * Current Rank.
 *
 * XP is deliberately *computed* here rather than stored as a mutable
 * counter on the profile — see `types/profile.ts`'s header comment for
 * why: it can never drift out of sync with the real activity it
 * represents, there's no risk of double-crediting the same quiz attempt
 * twice, and every screen that shows XP (TopBar badge, Profile page,
 * Dashboard widget, Leaderboard) is guaranteed to agree with each other
 * because they all call this one hook.
 */
export function useProfileStats(): ProfileStats {
  const { profile } = useProfile()
  const { courses } = useCourseCatalog()
  const { files } = useFileVault()

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

    // XP model: course progress + completion bonus + quiz/exam performance
    // + real study time + streak — every term traces back to a concrete,
    // already-persisted activity signal, never an arbitrary constant per
    // page view.
    const courseXp = enrolledCourses.reduce(
      (sum, c) => sum + c.progressPct * 8 + (c.progressPct >= 100 ? 300 : 0),
      0
    )
    const quizXp = quizAttempts.reduce((sum, a) => sum + Math.round(a.scorePct * 1.2), 0)
    const examXp = examAttempts.reduce((sum, a) => sum + Math.round(a.scorePct * 2.5), 0)
    const studyTimeXp = Math.round(studyTimeSeconds / 20) // ~3 XP/min studied
    const readingXp = filesFullyRead * 150
    const streakXp = (profile?.streakDays ?? 0) * 20

    const xp = Math.max(0, courseXp + quizXp + examXp + studyTimeXp + readingXp + streakXp)
    const level = computeLevelProgress(xp)

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
      xp,
      weeklyXp: Math.round(xp * 0.12),
      monthlyXp: Math.round(xp * 0.4),
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
      xp,
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
  }, [profile, courses, files])
}

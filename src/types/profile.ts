/**
 * Shared types for the Student Profile, University Info, and Academic
 * Ranking system.
 *
 * Same posture as `src/types/course.ts` / `src/types/fileVault.ts`: this
 * is a frontend-only build (no live backend exists — see
 * `backend/README.md`), so the "user profile" lives in client state via
 * `useProfile()` (`src/context/ProfileContext.tsx`) and persists to
 * `localStorage` so it survives reloads for the current browser. The
 * shape is deliberately backend-shaped — `universityId` / `facultyId` /
 * `departmentId` are real foreign keys into
 * `src/data/academicCatalog.ts` (never duplicated strings), badges are a
 * list of stable `BadgeId`s resolved against `src/data/badges.ts`, and
 * every derived stat (XP, level, rank, badges) is computed by pure
 * functions in `src/lib/profile/*` from real activity rather than being
 * stored redundantly — so wiring a real API later means replacing the
 * persistence layer only, not the data model or any UI.
 */

export type BadgeId =
  | 'top-10-student'
  | 'top-engineering-student'
  | 'perfect-quiz'
  | '30-day-streak'
  | 'ai-explorer'
  | 'fast-learner'
  | 'course-master'
  | 'weekly-champion'
  | 'monthly-champion'

export interface StudentProfile {
  /** Stable id for this local profile — always `'me'` in this frontend-only
   *  build (single-user browser session), kept as a real field so a
   *  future backend integration only needs to replace how it's populated. */
  id: string

  /* ── Personal ── */
  fullName: string
  email: string
  avatarDataUrl: string | null
  dateOfBirth: string | null // ISO date string, optional
  country: string | null
  preferredLanguage: string // LanguageOption id
  bio: string

  /* ── Academic — real foreign keys into academicCatalog.ts ── */
  universityId: string | null
  facultyId: string | null
  departmentId: string | null
  academicYearId: string | null
  semesterId: string | null
  studentIdNumber: string | null // optional university-issued ID
  studyGoals: string[]

  /* ── System rules ── */
  /** University & Faculty are locked after onboarding unless an admin/
   *  transfer workflow unlocks them — matches the spec's "University and
   *  Faculty should only be editable if allowed by system rules." */
  academicIdentityLocked: boolean

  /* ── Progression (Duolingo-style) ──
   * `xp`, `level`, `rank`, and `badges` are deliberately NOT stored here.
   * They are always *computed* from real, live activity (course
   * enrollment/progress/completion, File Vault reading progress and
   * quiz/exam scores, and the seeded leaderboard pool) by
   * `useProfileStats()` (`src/hooks/useProfileStats.ts`) every render —
   * see that file's header comment for why a derived value is safer than
   * a persisted counter in a frontend-only build (it can never drift out
   * of sync with the activity it represents, and there is no risk of
   * double-awarding XP for the same action). `streakDays` is the one
   * progression field that genuinely can't be derived from other stored
   * data (it's a record of *daily app engagement*), so it is persisted
   * and updated at most once per calendar day. */
  streakDays: number
  /** Highest `streakDays` value ever reached — updated whenever the
   *  current streak surpasses it, never decremented. */
  longestStreakDays: number
  lastStudyDate: string | null // ISO date, drives streak continuation

  /* ── Lifecycle ── */
  onboardingComplete: boolean
  createdAt: number
  updatedAt: number
}

export interface OnboardingInput {
  fullName: string
  avatarDataUrl: string | null
  dateOfBirth: string | null
  country: string | null
  preferredLanguage: string
  universityId: string
  facultyId: string
  departmentId: string
  academicYearId: string
  semesterId: string
  studentIdNumber: string | null
  studyGoals: string[]
}

export interface ProfileEditableFields {
  avatarDataUrl: string | null
  fullName: string
  preferredLanguage: string
  studyGoals: string[]
  bio: string
}

/** A single leaderboard row — either the current user or a seeded peer.
 *  Shaped identically for both so ranking/filtering logic never branches
 *  on "is this me". */
export interface LeaderboardEntry {
  id: string
  isCurrentUser: boolean
  fullName: string
  avatarDataUrl: string | null
  universityId: string
  facultyId: string
  departmentId: string
  academicYearId: string
  courseIds: string[]
  xp: number
  weeklyXp: number
  monthlyXp: number
  studyHours: number
  coursesCompleted: number
  streakDays: number
  badges: BadgeId[]
  isFriend: boolean
}

export type RankingScope =
  'university' | 'faculty' | 'department' | 'academicYear' | 'course' | 'friends'
export type RankingTimeframe = 'weekly' | 'monthly' | 'all-time'

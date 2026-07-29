/**
 * Shared types for the LearnX Course ecosystem — the data model that
 * connects Doctor-authored courses to Student enrollment & learning.
 *
 * This is a frontend-only build (see `backend/` for the reference auth
 * architecture), so the "catalog" lives in client state via
 * `useCourseCatalog` and is seeded from `src/data/coursesMock.ts`. The
 * shape is deliberately backend-shaped (status workflow, module/lesson
 * tree, per-course analytics) so it maps cleanly onto a real API later.
 */

export type CourseStatus = 'draft' | 'pending-review' | 'published' | 'archived'

export type CourseType = 'university' | 'public' | 'premium'

export type LessonType = 'video' | 'pdf' | 'notes' | 'quiz' | 'assignment'

export interface LessonResource {
  id: string
  name: string
  kind: 'pdf' | 'docx' | 'ppt' | 'link' | 'dataset'
  sizeLabel: string
}

export interface Lesson {
  id: string
  title: string
  type: LessonType
  durationMinutes?: number
  /** Whether the single demo student ("Alex Chen") has completed this lesson. */
  completed: boolean
  resources: LessonResource[]
}

export interface Module {
  id: string
  title: string
  lessons: Lesson[]
}

export interface CourseAnalytics {
  totalStudents: number
  activeStudents: number
  completionRate: number
  avgWatchTimeMinutes: number
  mostViewedLessonTitle: string
  dropOffLessonTitle: string
  quizAvgScore: number
  strugglingTopic: string
  strugglingPct: number
  aiInsights: string[]
}

export interface Course {
  id: string
  title: string
  description: string
  category: string
  faculty: string
  department: string
  academicLevel: string
  courseType: CourseType
  status: CourseStatus
  color: string
  icon: string
  doctorName: string
  doctorInitials: string
  rating: number
  studentsCount: number
  completionRate: number
  lastUpdated: string
  createdAt: string
  modules: Module[]
  analytics: CourseAnalytics
  /** Student-facing enrollment/progress state (single demo persona: Alex Chen). */
  enrolled: boolean
  saved: boolean
  progressPct: number
  lastLessonTitle: string | null
  lastViewedAt: string | null
  completedAt: string | null
  /**
   * Monetization — only meaningful for `courseType === 'premium'`.
   * `priceUsd` is the real-money price a doctor sets when publishing a
   * premium course; `allowXpRedemption`/`xpPrice` let a doctor opt the
   * course into the Reward Store's "pay with XP instead of money"
   * exchange (spec: "Teachers can choose whether a paid course supports
   * XP redemption"). Both null for non-premium courses.
   */
  priceUsd: number | null
  allowXpRedemption: boolean
  xpPrice: number | null
  /** Real purchase record for a student who redeemed this course via the
   * Reward Store (XP or XP+money) rather than the ordinary Enroll flow. */
  purchasedViaReward: boolean
}

export function totalLessons(course: Course): number {
  return course.modules.reduce((sum, m) => sum + m.lessons.length, 0)
}

export function completedLessons(course: Course): number {
  return course.modules.reduce((sum, m) => sum + m.lessons.filter((l) => l.completed).length, 0)
}

export function remainingLessons(course: Course): number {
  return totalLessons(course) - completedLessons(course)
}

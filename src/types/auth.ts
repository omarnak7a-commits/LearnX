export type UserRole = 'student' | 'doctor'

/** Normalized authenticated user shared by AuthContext and onboarding. */
export interface AuthUser {
  id: string
  email: string
  fullName: string
  role: UserRole
  provider: string
  avatarUrl: string | null
  emailVerified: boolean
  onboardingComplete: boolean
  universityId: string | null
  facultyId: string | null
  departmentId: string | null
  academicYear: string | null
  semester?: string | null
  preferredLanguage: string
  studyGoals: string[]
  weakSubjects: string[]
  strongSubjects: string[]
  academicPosition?: string | null
  specialization?: string | null
  coursesTaught: string[]
  officeHours?: string | null
  xp: number
  level: number
  streakDays: number
  createdAt: string
  lastLogin: string | null
}

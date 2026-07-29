import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { OnboardingInput, ProfileEditableFields, StudentProfile } from '../types/profile'
import { loadProfile, saveProfile } from '../lib/profile/storage'
import { nextStreak, todayIso } from '../lib/profile/xp'

interface ProfileContextValue {
  /** `null` until onboarding completes — the app treats this as "no
   *  academic identity yet" and routes to the onboarding flow, mirroring
   *  the spec's "collect during Sign Up or immediately after first
   *  login" requirement. */
  profile: StudentProfile | null
  loading: boolean
  completeOnboarding: (input: OnboardingInput, email: string) => void
  updateProfile: (fields: Partial<ProfileEditableFields>) => void
  /** Unlocks University/Faculty/Department/Year/Semester for editing —
   *  gated behind an explicit confirmation step in the Profile page UI
   *  (not a bare toggle) so it genuinely represents "allowed by system
   *  rules" rather than being always-editable. */
  requestAcademicChange: () => void
  updateAcademicIdentity: (
    fields: Pick<
      StudentProfile,
      'universityId' | 'facultyId' | 'departmentId' | 'academicYearId' | 'semesterId'
    >
  ) => void
  /** Records that the student engaged with the platform today — the one
   *  genuinely time-based signal (daily app usage) that can't be derived
   *  from other stored data, so it's the only progression field actually
   *  persisted (see `types/profile.ts` header comment). Called once per
   *  Dashboard mount. */
  recordDailyActivity: () => void
  resetProfile: () => void
}

const ProfileContext = createContext<ProfileContextValue | null>(null)

function buildProfile(input: OnboardingInput, email: string): StudentProfile {
  const now = Date.now()
  return {
    id: 'me',
    fullName: input.fullName.trim(),
    email,
    avatarDataUrl: input.avatarDataUrl,
    dateOfBirth: input.dateOfBirth,
    country: input.country,
    preferredLanguage: input.preferredLanguage,
    bio: '',
    universityId: input.universityId,
    facultyId: input.facultyId,
    departmentId: input.departmentId,
    academicYearId: input.academicYearId,
    semesterId: input.semesterId,
    studentIdNumber: input.studentIdNumber,
    studyGoals: input.studyGoals,
    academicIdentityLocked: true,
    streakDays: 0,
    lastStudyDate: null,
    onboardingComplete: true,
    createdAt: now,
    updatedAt: now,
  }
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setProfile(loadProfile())
    setLoading(false)
  }, [])

  const persist = useCallback((next: StudentProfile) => {
    setProfile(next)
    saveProfile(next)
  }, [])

  const completeOnboarding = useCallback(
    (input: OnboardingInput, email: string) => {
      persist(buildProfile(input, email))
    },
    [persist]
  )

  const updateProfile = useCallback((fields: Partial<ProfileEditableFields>) => {
    setProfile((prev) => {
      if (!prev) return prev
      const next: StudentProfile = { ...prev, ...fields, updatedAt: Date.now() }
      saveProfile(next)
      return next
    })
  }, [])

  const requestAcademicChange = useCallback(() => {
    setProfile((prev) => {
      if (!prev) return prev
      const next: StudentProfile = { ...prev, academicIdentityLocked: false, updatedAt: Date.now() }
      saveProfile(next)
      return next
    })
  }, [])

  const updateAcademicIdentity = useCallback(
    (
      fields: Pick<
        StudentProfile,
        'universityId' | 'facultyId' | 'departmentId' | 'academicYearId' | 'semesterId'
      >
    ) => {
      setProfile((prev) => {
        if (!prev) return prev
        const next: StudentProfile = {
          ...prev,
          ...fields,
          academicIdentityLocked: true,
          updatedAt: Date.now(),
        }
        saveProfile(next)
        return next
      })
    },
    []
  )

  const recordDailyActivity = useCallback(() => {
    setProfile((prev) => {
      if (!prev) return prev
      const today = todayIso()
      if (prev.lastStudyDate === today) return prev
      const streakDays = nextStreak(prev.lastStudyDate, today, prev.streakDays)
      const next: StudentProfile = {
        ...prev,
        streakDays,
        lastStudyDate: today,
        updatedAt: Date.now(),
      }
      saveProfile(next)
      return next
    })
  }, [])

  const resetProfile = useCallback(() => {
    setProfile(null)
  }, [])

  const value = useMemo<ProfileContextValue>(
    () => ({
      profile,
      loading,
      completeOnboarding,
      updateProfile,
      requestAcademicChange,
      updateAcademicIdentity,
      recordDailyActivity,
      resetProfile,
    }),
    [
      profile,
      loading,
      completeOnboarding,
      updateProfile,
      requestAcademicChange,
      updateAcademicIdentity,
      recordDailyActivity,
      resetProfile,
    ]
  )

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
}

export function useProfile() {
  const ctx = useContext(ProfileContext)
  if (!ctx) throw new Error('useProfile must be used within a ProfileProvider')
  return ctx
}

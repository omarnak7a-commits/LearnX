import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Logo from '../ui/Logo'
import SearchableSelect from '../ui/SearchableSelect'
import {
  UNIVERSITIES,
  getFacultiesForUniversity,
  getDepartmentsForFaculty,
} from '../../data/academicCatalog'
import { useAuth } from '../../context/AuthContext'
import { useProfile } from '../../context/ProfileContext'
import type { AuthUser, UserRole } from '../../types/auth'
import { authHeaders } from '../../lib/apiClient'

interface OnboardingFlowProps {
  email?: string
  onComplete: (user: AuthUser) => void
}

const STEPS = [
  { step: 1, label: 'Role', title: 'What are you?' },
  { step: 2, label: 'University', title: 'Which university do you attend?' },
  { step: 3, label: 'Year', title: 'What year / position are you in?' },
  { step: 4, label: 'Faculty', title: 'Which faculty/college are you in?' },
  { step: 5, label: 'Department', title: 'Which department are you in?' },
]

const STUDENT_YEARS = [
  { id: 'year-1', label: '1st Year', icon: '🎓' },
  { id: 'year-2', label: '2nd Year', icon: '🎓' },
  { id: 'year-3', label: '3rd Year', icon: '🎓' },
  { id: 'year-4', label: '4th Year', icon: '🎓' },
  { id: 'year-5', label: '5th Year', icon: '🎓' },
  { id: 'year-6', label: '6th Year', icon: '🎓' },
  { id: 'graduate', label: 'Graduate', icon: '🎓' },
  { id: 'other', label: 'Other', icon: '🎓' },
]

const DOCTOR_RANKS = [
  { id: 'ta', label: 'Teaching Assistant', icon: '👨‍🏫' },
  { id: 'lecturer', label: 'Lecturer', icon: '👨‍🏫' },
  { id: 'asst-prof', label: 'Assistant Professor', icon: '👨‍🏫' },
  { id: 'assoc-prof', label: 'Associate Professor', icon: '👨‍🏫' },
  { id: 'prof', label: 'Professor', icon: '👨‍🏫' },
  { id: 'dept-head', label: 'Department Head', icon: '👨‍🏫' },
  { id: 'other-doc', label: 'Other', icon: '👨‍🏫' },
]

export default function OnboardingFlow({ email, onComplete }: OnboardingFlowProps) {
  const { user, setUserFromAuthResponse } = useAuth()
  const { updateAcademicIdentity } = useProfile()

  const [currentStep, setCurrentStep] = useState<number>(1)
  const [role, setRole] = useState<UserRole | null>(user?.role ?? 'student')

  const [universityId, setUniversityId] = useState<string | null>(user?.universityId ?? null)
  const [academicYearId, setAcademicYearId] = useState<string | null>(user?.academicYear ?? null)
  const [facultyId, setFacultyId] = useState<string | null>(user?.facultyId ?? null)
  const [departmentId, setDepartmentId] = useState<string | null>(user?.departmentId ?? null)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const universityOptions = useMemo(
    () =>
      UNIVERSITIES.map((u) => ({
        id: u.id,
        label: u.name,
        sublabel: `${u.city}, ${u.country}`,
        icon: '🏛️',
      })),
    []
  )

  const yearOptions = useMemo(() => {
    return role === 'doctor' ? DOCTOR_RANKS : STUDENT_YEARS
  }, [role])

  const facultyOptions = useMemo(() => {
    if (!universityId) return []
    return getFacultiesForUniversity(universityId).map((f) => ({
      id: f.id,
      label: f.name,
      icon: f.icon || '📚',
    }))
  }, [universityId])

  const departmentOptions = useMemo(() => {
    if (!facultyId) return []
    return getDepartmentsForFaculty(facultyId).map((d) => ({
      id: d.id,
      label: d.name,
      icon: '📂',
    }))
  }, [facultyId])

  const canProceed = useMemo(() => {
    if (currentStep === 1) return Boolean(role)
    if (currentStep === 2) return Boolean(universityId)
    if (currentStep === 3) return Boolean(academicYearId)
    if (currentStep === 4) return Boolean(facultyId)
    if (currentStep === 5) {
      if (departmentOptions.length > 0) return Boolean(departmentId)
      return true
    }
    return false
  }, [currentStep, role, universityId, academicYearId, facultyId, departmentId, departmentOptions])

  function handleNext() {
    setError(null)
    if (!canProceed) {
      if (currentStep === 1) setError('Please select your role (Student or Doctor).')
      else if (currentStep === 2) setError('Please select your university.')
      else if (currentStep === 3) setError('Please select your academic year or position.')
      else if (currentStep === 4) setError('Please select your faculty / college.')
      else if (currentStep === 5 && departmentOptions.length > 0)
        setError('Please select your department.')
      return
    }
    if (currentStep < 5) {
      setCurrentStep((s) => s + 1)
    } else {
      void handleSubmitFinal()
    }
  }

  function handleBack() {
    setError(null)
    if (currentStep > 1) {
      setCurrentStep((s) => s - 1)
    }
  }

  async function handleSubmitFinal() {
    if (!canProceed || submitting) return
    setSubmitting(true)
    setError(null)

    const chosenRole = role ?? 'student'
    const finalPayload = {
      role: chosenRole,
      university_id: universityId,
      faculty_id: facultyId,
      department_id: departmentId || null,
      academic_year: academicYearId,
      onboarding_complete: true,
    }

    try {
      const endpoint =
        chosenRole === 'doctor' ? '/api/v1/auth/onboarding/doctor' : '/api/v1/auth/onboarding/student'

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        credentials: 'include',
        body: JSON.stringify({
          university_id: universityId,
          faculty_id: facultyId,
          department_id: departmentId,
          academic_year: academicYearId,
          academic_position: academicYearId,
          specialization: 'General',
        }),
      })

      let updatedUserData: any = null
      if (res.ok) updatedUserData = await res.json()

      try {
        await fetch('/api/v1/auth/me', {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders(),
          },
          credentials: 'include',
          body: JSON.stringify(finalPayload),
        })
      } catch {}

      const activeUser: AuthUser = {
        id: updatedUserData?.id || user?.id || String(Date.now()),
        email: updatedUserData?.email || user?.email || email || '',
        fullName: updatedUserData?.fullName || updatedUserData?.full_name || user?.fullName || 'User',
        role: chosenRole,
        provider: user?.provider || 'email',
        avatarUrl: user?.avatarUrl ?? null,
        emailVerified: true,
        onboardingComplete: true,
        universityId,
        facultyId,
        departmentId,
        academicYear: academicYearId,
        preferredLanguage: 'ar',
        studyGoals: [],
        weakSubjects: [],
        strongSubjects: [],
        coursesTaught: [],
        xp: user?.xp ?? 0,
        level: user?.level ?? 1,
        streakDays: user?.streakDays ?? 0,
        createdAt: user?.createdAt ?? new Date().toISOString(),
        lastLogin: new Date().toISOString(),
      }

      setUserFromAuthResponse(activeUser)
      updateAcademicIdentity({
        universityId,
        facultyId,
        departmentId,
        academicYearId,
        semesterId: null,
      })

      localStorage.setItem('learnx_user', JSON.stringify(activeUser))
      onComplete(activeUser)

      const targetUrl = chosenRole === 'doctor' ? '/doctor/dashboard' : '/student/dashboard'
      window.location.href = targetUrl
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save onboarding. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="relative min-h-screen flex items-center justify-center px-4 py-12 overflow-hidden"
      style={{ background: 'var(--section-dark, #0A0D14)' }}
    >
      <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none" />
      <motion.div
        className="glass-card w-full max-w-xl p-6 sm:p-8 relative z-10 rounded-2xl border border-white/10 bg-slate-900/80 shadow-2xl backdrop-blur-xl"
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex flex-col items-center mb-6">
          <Logo variant="symbol" size="lg" className="mb-3" />
          <h1
            className="text-xl sm:text-2xl font-bold text-white text-center"
            style={{ fontFamily: 'Orbitron, sans-serif' }}
          >
            {STEPS[currentStep - 1].title}
          </h1>
          <p className="text-xs text-slate-400 mt-1 text-center">
            Step {currentStep} of 5 · Academic Profile Setup
          </p>
        </div>

        {/* 5-Step Progress Indicator */}
        <div className="mb-6">
          <div className="flex items-center justify-between gap-1 mb-2">
            {STEPS.map((s) => {
              const isPast = s.step < currentStep
              const isCurrent = s.step === currentStep
              return (
                <div key={s.step} className="flex-1 flex flex-col items-center gap-1 text-center">
                  <span
                    className={`text-[10px] font-bold uppercase transition-colors ${
                      isCurrent ? 'text-teal-400' : isPast ? 'text-slate-300' : 'text-slate-600'
                    }`}
                  >
                    0{s.step} {s.label}
                  </span>
                  <div
                    className={`h-1.5 w-full rounded-full transition-all duration-300 ${
                      isPast ? 'bg-teal-400' : isCurrent ? 'bg-teal-400 shadow-sm shadow-teal-400/50' : 'bg-slate-800'
                    }`}
                  />
                </div>
              )
            })}
          </div>
        </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-4 px-3.5 py-2.5 rounded-xl text-xs bg-red-500/10 text-red-400 border border-red-500/20 text-center"
          >
            {error}
          </motion.div>
        )}

        <div className="min-h-[220px] flex flex-col justify-center">
          <AnimatePresence mode="wait">
            {/* STEP 1: ROLE */}
            {currentStep === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-3"
              >
                <p className="text-xs text-slate-400 text-center mb-4">
                  Select your primary account type. This configures your dashboard and permissions.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <button
                    type="button"
                    onClick={() => setRole('student')}
                    className={`p-5 rounded-2xl border text-left transition-all relative overflow-hidden ${
                      role === 'student'
                        ? 'border-teal-400 bg-teal-500/10 shadow-lg shadow-teal-500/15 ring-2 ring-teal-400/20'
                        : 'border-white/10 bg-slate-800/40 hover:border-white/20'
                    }`}
                  >
                    <div className="text-3xl mb-2">🎓</div>
                    <div className="font-bold text-white text-base">Student</div>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Learn smarter, access courses, track your GPA, and compete on the leaderboard.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setRole('doctor')}
                    className={`p-5 rounded-2xl border text-left transition-all relative overflow-hidden ${
                      role === 'doctor'
                        ? 'border-teal-400 bg-teal-500/10 shadow-lg shadow-teal-500/15 ring-2 ring-teal-400/20'
                        : 'border-white/10 bg-slate-800/40 hover:border-white/20'
                    }`}
                  >
                    <div className="text-3xl mb-2">👨‍🏫</div>
                    <div className="font-bold text-white text-base">Doctor / Instructor</div>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Build courses, upload lectures & PDFs, manage students, and analyze performance.
                    </p>
                  </button>
                </div>
              </motion.div>
            )}

            {/* STEP 2: UNIVERSITY */}
            {currentStep === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <p className="text-xs text-slate-400 text-center mb-2">
                  Search and select your university from our accredited directory.
                </p>
                <SearchableSelect
                  label="University"
                  required
                  placeholder="e.g. Cairo University, MIT, Imperial College..."
                  options={universityOptions}
                  value={universityId}
                  onChange={(id) => {
                    setUniversityId(id)
                    setFacultyId(null)
                    setDepartmentId(null)
                  }}
                />
              </motion.div>
            )}

            {/* STEP 3: ACADEMIC YEAR / POSITION */}
            {currentStep === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <p className="text-xs text-slate-400 text-center mb-2">
                  {role === 'doctor'
                    ? 'Select your current academic teaching rank.'
                    : 'Select your current academic study level.'}
                </p>
                <SearchableSelect
                  label={role === 'doctor' ? 'Academic Position' : 'Academic Year'}
                  required
                  placeholder={role === 'doctor' ? 'e.g. Assistant Professor, Lecturer...' : 'e.g. 1st Year, 2nd Year...'}
                  options={yearOptions}
                  value={academicYearId}
                  onChange={setAcademicYearId}
                />
              </motion.div>
            )}

            {/* STEP 4: FACULTY / COLLEGE */}
            {currentStep === 4 && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <p className="text-xs text-slate-400 text-center mb-2">
                  Faculties available for your selected university.
                </p>
                <SearchableSelect
                  label="Faculty / College"
                  required
                  placeholder="e.g. Faculty of Engineering, Faculty of Medicine..."
                  options={facultyOptions}
                  value={facultyId}
                  onChange={(id) => {
                    setFacultyId(id)
                    setDepartmentId(null)
                  }}
                />
              </motion.div>
            )}

            {/* STEP 5: DEPARTMENT */}
            {currentStep === 5 && (
              <motion.div
                key="step5"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <p className="text-xs text-slate-400 text-center mb-2">
                  {departmentOptions.length > 0
                    ? 'Select your department or major specialization.'
                    : 'Your selected faculty does not require a separate department.'}
                </p>
                {departmentOptions.length > 0 ? (
                  <SearchableSelect
                    label="Department"
                    required
                    placeholder="e.g. Computer Science, Mechanical Engineering..."
                    options={departmentOptions}
                    value={departmentId}
                    onChange={setDepartmentId}
                  />
                ) : (
                  <div className="p-4 rounded-xl border border-teal-500/20 bg-teal-500/5 text-center">
                    <p className="text-sm font-semibold text-teal-400 mb-1">✓ General Department</p>
                    <p className="text-xs text-slate-400">
                      All required academic identity data has been gathered.
                    </p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex items-center gap-3 mt-8">
          {currentStep > 1 && (
            <button
              type="button"
              onClick={handleBack}
              disabled={submitting}
              className="px-5 py-3 rounded-xl text-sm font-semibold text-slate-300 bg-slate-800/80 hover:bg-slate-800 border border-white/10 transition-all"
            >
              Back
            </button>
          )}

          <motion.button
            type="button"
            onClick={handleNext}
            disabled={!canProceed || submitting}
            className="flex-1 py-3 rounded-xl text-sm font-bold bg-teal-400 text-slate-950 disabled:opacity-40 hover:bg-teal-300 transition-all flex items-center justify-center gap-2"
            whileHover={!canProceed || submitting ? undefined : { scale: 1.01 }}
            whileTap={!canProceed || submitting ? undefined : { scale: 0.99 }}
          >
            {submitting ? 'Saving Profile…' : currentStep === 5 ? 'Complete & Enter LearnX 🚀' : 'Continue →'}
          </motion.button>
        </div>
      </motion.div>
    </div>
  )
}

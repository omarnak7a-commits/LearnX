import { useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Logo from '../ui/Logo'
import SearchableSelect from '../ui/SearchableSelect'
import {
  UNIVERSITIES,
  COUNTRIES,
  LANGUAGES,
  STUDY_GOAL_OPTIONS,
  ACADEMIC_YEARS,
  SEMESTERS,
  getFacultiesForUniversity,
  getDepartmentsForFaculty,
} from '../../data/academicCatalog'
import { useProfile } from '../../context/ProfileContext'
import type { OnboardingInput } from '../../types/profile'

interface OnboardingFlowProps {
  email: string
  onComplete: () => void
}

type Step = 'personal' | 'academic' | 'goals'

const STEPS: Step[] = ['personal', 'academic', 'goals']

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

/**
 * Extended Sign-Up / Onboarding flow — collects every field in the
 * spec's "SIGN UP" section (Personal + Academic) immediately after first
 * login, with searchable University → Faculty → Department cascading
 * dropdowns exactly as the spec's example describes. Blocks entry to the
 * dashboard until complete (`App.tsx` only renders `DashboardPage` once
 * `profile.onboardingComplete` is true) so no student ever reaches a
 * dashboard with an incomplete academic identity.
 */
export default function OnboardingFlow({ email, onComplete }: OnboardingFlowProps) {
  const { completeOnboarding } = useProfile()
  const [step, setStep] = useState<Step>('personal')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [fullName, setFullName] = useState('')
  const [avatarDataUrl, setAvatarDataUrl] = useState<string | null>(null)
  const [dateOfBirth, setDateOfBirth] = useState('')
  const [country, setCountry] = useState<string | null>(null)
  const [preferredLanguage, setPreferredLanguage] = useState('en')

  const [universityId, setUniversityId] = useState<string | null>(null)
  const [facultyId, setFacultyId] = useState<string | null>(null)
  const [departmentId, setDepartmentId] = useState<string | null>(null)
  const [academicYearId, setAcademicYearId] = useState<string | null>(null)
  const [semesterId, setSemesterId] = useState<string | null>(null)
  const [studentIdNumber, setStudentIdNumber] = useState('')
  const [studyGoals, setStudyGoals] = useState<string[]>([])

  const [avatarError, setAvatarError] = useState<string | null>(null)

  const universityOptions = useMemo(
    () => UNIVERSITIES.map((u) => ({ id: u.id, label: u.name, sublabel: u.country })),
    []
  )
  const facultyOptions = useMemo(
    () =>
      getFacultiesForUniversity(universityId).map((f) => ({
        id: f.id,
        label: f.name,
        icon: f.icon,
      })),
    [universityId]
  )
  const departmentOptions = useMemo(
    () => getDepartmentsForFaculty(facultyId).map((d) => ({ id: d.id, label: d.name })),
    [facultyId]
  )
  const yearOptions = useMemo(() => ACADEMIC_YEARS.map((y) => ({ id: y.id, label: y.label })), [])
  const semesterOptions = useMemo(() => SEMESTERS.map((s) => ({ id: s.id, label: s.label })), [])
  const countryOptions = useMemo(() => COUNTRIES.map((c) => ({ id: c, label: c })), [])
  const languageOptions = useMemo(() => LANGUAGES.map((l) => ({ id: l.id, label: l.label })), [])

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setAvatarError('Please choose an image file.')
      return
    }
    if (file.size > 4 * 1024 * 1024) {
      setAvatarError('Image must be under 4MB.')
      return
    }
    setAvatarError(null)
    const dataUrl = await readFileAsDataUrl(file)
    setAvatarDataUrl(dataUrl)
  }

  function toggleGoal(goal: string) {
    setStudyGoals((prev) =>
      prev.includes(goal) ? prev.filter((g) => g !== goal) : [...prev, goal]
    )
  }

  const personalValid = fullName.trim().length >= 2
  const academicValid = Boolean(
    universityId && facultyId && departmentId && academicYearId && semesterId
  )
  const canFinish = personalValid && academicValid

  function goNext() {
    const idx = STEPS.indexOf(step)
    if (idx < STEPS.length - 1) setStep(STEPS[idx + 1])
  }
  function goBack() {
    const idx = STEPS.indexOf(step)
    if (idx > 0) setStep(STEPS[idx - 1])
  }

  function handleFinish() {
    if (!canFinish) return
    const input: OnboardingInput = {
      fullName: fullName.trim(),
      avatarDataUrl,
      dateOfBirth: dateOfBirth || null,
      country,
      preferredLanguage,
      universityId: universityId!,
      facultyId: facultyId!,
      departmentId: departmentId!,
      academicYearId: academicYearId!,
      semesterId: semesterId!,
      studentIdNumber: studentIdNumber.trim() || null,
      studyGoals,
    }
    completeOnboarding(input, email)
    onComplete()
  }

  const stepIndex = STEPS.indexOf(step)

  return (
    <div
      className="relative min-h-screen flex items-center justify-center px-6 py-12 overflow-hidden"
      style={{ background: 'var(--section-dark)' }}
    >
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <div
        className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none"
        style={{
          background:
            'radial-gradient(circle at 70% 30%, rgba(45,212,191,0.08) 0%, transparent 65%)',
        }}
      />

      <motion.div
        className="glass-card w-full max-w-xl p-8 relative z-10"
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="flex flex-col items-center mb-6">
          <Logo variant="symbol" size="lg" className="mb-4" />
          <h1
            className="text-xl font-bold"
            style={{
              fontFamily: 'Orbitron, sans-serif',
              color: 'var(--foreground)',
              letterSpacing: '-0.01em',
            }}
          >
            Set up your academic identity
          </h1>
          <p className="text-xs mt-1.5 text-center" style={{ color: 'var(--muted-foreground)' }}>
            One quick step so LearnX can personalize your dashboard, rankings, and study plan.
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-7">
          {STEPS.map((s, i) => (
            <div key={s} className="flex-1 flex items-center gap-2">
              <div
                className="w-full h-1 rounded-full overflow-hidden"
                style={{ background: 'var(--tint-2)' }}
              >
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: 'linear-gradient(90deg, #2DD4BF, var(--secondary))' }}
                  initial={false}
                  animate={{ width: i <= stepIndex ? '100%' : '0%' }}
                  transition={{ duration: 0.4 }}
                />
              </div>
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {step === 'personal' && (
            <motion.div
              key="personal"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-16 h-16 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden"
                  style={{
                    background: avatarDataUrl
                      ? undefined
                      : 'linear-gradient(135deg, var(--primary), var(--secondary))',
                    color: 'var(--primary-foreground)',
                  }}
                  aria-label="Upload profile picture"
                >
                  {avatarDataUrl ? (
                    <img src={avatarDataUrl} alt="Profile" className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-xl font-bold">
                      {fullName.trim().charAt(0).toUpperCase() || '+'}
                    </span>
                  )}
                </button>
                <div>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="text-xs font-semibold px-3 py-1.5 rounded-full"
                    style={{ background: 'rgba(45,212,191,0.1)', color: 'var(--primary)' }}
                  >
                    Upload photo (optional)
                  </button>
                  {avatarError && (
                    <p className="text-xs mt-1" style={{ color: 'var(--danger)' }}>
                      {avatarError}
                    </p>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleAvatarChange}
                />
              </div>

              <div>
                <label
                  className="text-xs font-medium mb-1.5 flex items-center gap-1"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Full Name <span style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Ahmed Hassan"
                  className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    className="text-xs font-medium mb-1.5 block"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    Date of Birth (optional)
                  </label>
                  <input
                    type="date"
                    value={dateOfBirth}
                    onChange={(e) => setDateOfBirth(e.target.value)}
                    className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
                  />
                </div>
                <SearchableSelect
                  label="Country"
                  placeholder="Select country"
                  options={countryOptions}
                  value={country}
                  onChange={setCountry}
                />
              </div>

              <SearchableSelect
                label="Preferred Language"
                options={languageOptions}
                value={preferredLanguage}
                onChange={setPreferredLanguage}
              />
            </motion.div>
          )}

          {step === 'academic' && (
            <motion.div
              key="academic"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              <SearchableSelect
                label="University"
                required
                placeholder="e.g. Cairo University"
                options={universityOptions}
                value={universityId}
                onChange={(id) => {
                  setUniversityId(id)
                  setFacultyId(null)
                  setDepartmentId(null)
                }}
              />
              <SearchableSelect
                label="Faculty / College"
                required
                placeholder={
                  universityId ? 'e.g. Faculty of Engineering' : 'Choose a university first'
                }
                options={facultyOptions}
                value={facultyId}
                disabled={!universityId}
                onChange={(id) => {
                  setFacultyId(id)
                  setDepartmentId(null)
                }}
              />
              <SearchableSelect
                label="Department"
                required
                placeholder={facultyId ? 'e.g. Computer Engineering' : 'Choose a faculty first'}
                options={departmentOptions}
                value={departmentId}
                disabled={!facultyId}
                onChange={setDepartmentId}
              />
              <div className="grid grid-cols-2 gap-4">
                <SearchableSelect
                  label="Academic Year"
                  required
                  placeholder="e.g. Second Year"
                  options={yearOptions}
                  value={academicYearId}
                  onChange={setAcademicYearId}
                />
                <SearchableSelect
                  label="Semester"
                  required
                  placeholder="e.g. Semester 1"
                  options={semesterOptions}
                  value={semesterId}
                  onChange={setSemesterId}
                />
              </div>
              <div>
                <label
                  className="text-xs font-medium mb-1.5 block"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Student ID (optional)
                </label>
                <input
                  value={studentIdNumber}
                  onChange={(e) => setStudentIdNumber(e.target.value)}
                  placeholder="e.g. 20231234"
                  className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
                />
              </div>
            </motion.div>
          )}

          {step === 'goals' && (
            <motion.div
              key="goals"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              <div>
                <p className="text-sm font-semibold mb-1" style={{ color: 'var(--foreground)' }}>
                  What are your study goals?
                </p>
                <p className="text-xs mb-3" style={{ color: 'var(--muted-foreground)' }}>
                  Pick as many as apply — this tunes your AI study plan and dashboard insights.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {STUDY_GOAL_OPTIONS.map((goal) => {
                    const active = studyGoals.includes(goal)
                    return (
                      <button
                        key={goal}
                        type="button"
                        onClick={() => toggleGoal(goal)}
                        className="text-xs font-medium px-3 py-2.5 rounded-xl text-left transition-colors"
                        style={{
                          background: active ? 'rgba(45,212,191,0.12)' : 'var(--tint-1)',
                          border: `1px solid ${active ? 'rgba(45,212,191,0.4)' : 'var(--border-subtle)'}`,
                          color: active ? 'var(--primary)' : 'var(--foreground)',
                        }}
                      >
                        {active ? '✓ ' : ''}
                        {goal}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div
                className="p-4 rounded-xl"
                style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
              >
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--foreground)' }}>
                  Your academic identity
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {fullName || 'Your name'} · {email}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-3 mt-7">
          {stepIndex > 0 && (
            <button
              type="button"
              onClick={goBack}
              className="px-4 py-2.5 rounded-xl text-sm font-semibold input-field"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Back
            </button>
          )}
          {step !== 'goals' ? (
            <motion.button
              type="button"
              onClick={goNext}
              disabled={step === 'personal' ? !personalValid : !academicValid}
              className="flex-1 py-3 rounded-xl text-sm font-bold"
              style={{
                background: 'var(--primary)',
                color: 'var(--primary-foreground)',
                opacity: (step === 'personal' ? !personalValid : !academicValid) ? 0.5 : 1,
              }}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
            >
              Continue
            </motion.button>
          ) : (
            <motion.button
              type="button"
              onClick={handleFinish}
              disabled={!canFinish}
              className="flex-1 py-3 rounded-xl text-sm font-bold"
              style={{
                background: 'var(--primary)',
                color: 'var(--primary-foreground)',
                opacity: !canFinish ? 0.5 : 1,
              }}
              whileHover={{ scale: 1.01, boxShadow: '0 0 32px rgba(45,212,191,0.4)' }}
              whileTap={{ scale: 0.98 }}
            >
              Enter LearnX
            </motion.button>
          )}
        </div>
      </motion.div>
    </div>
  )
}

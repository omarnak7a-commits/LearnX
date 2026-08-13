import { useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../../../context/AuthContext'
import { useProfile } from '../../../context/ProfileContext'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import { useProfileStats } from '../../../hooks/useProfileStats'
import ProgressRing from '../../ui/ProgressRing'
import Badge from '../../ui/Badge'
import SearchableSelect from '../../ui/SearchableSelect'
import { getBadgeDefinition } from '../../../data/badges'
import {
  getUniversity,
  getFaculty,
  getDepartment,
  getAcademicYear,
  getSemester,
  UNIVERSITIES,
  ACADEMIC_YEARS,
  SEMESTERS,
  STUDY_GOAL_OPTIONS,
  LANGUAGES,
  getFacultiesForUniversity,
  getDepartmentsForFaculty,
} from '../../../data/academicCatalog'

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export default function ProfilePage() {
  const { user } = useAuth()
  const { profile, updateProfile, requestAcademicChange, updateAcademicIdentity } = useProfile()
  const { courses } = useCourseCatalog()
  const stats = useProfileStats()

  const realFullName = user?.fullName || profile?.fullName || 'Scholar'
  const realEmail = user?.email || profile?.email || ''
  const realRole = user?.role || 'student'
  const realUniversityId = user?.universityId || profile?.universityId || null
  const realFacultyId = user?.facultyId || profile?.facultyId || null
  const realDepartmentId = user?.departmentId || profile?.departmentId || null
  const realYearId = user?.academicYear || profile?.academicYearId || null

  const [editing, setEditing] = useState(false)
  const [showUnlockModal, setShowUnlockModal] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [draftName, setDraftName] = useState(realFullName)
  const [draftLanguage, setDraftLanguage] = useState(profile?.preferredLanguage ?? 'ar')
  const [draftBio, setDraftBio] = useState(profile?.bio ?? '')
  const [draftGoals, setDraftGoals] = useState<string[]>(profile?.studyGoals ?? [])
  const [draftAvatar, setDraftAvatar] = useState<string | null>(profile?.avatarDataUrl ?? user?.avatarUrl ?? null)

  const [draftUniversityId, setDraftUniversityId] = useState(realUniversityId)
  const [draftFacultyId, setDraftFacultyId] = useState(realFacultyId)
  const [draftDepartmentId, setDraftDepartmentId] = useState(realDepartmentId)
  const [draftYearId, setDraftYearId] = useState(realYearId)
  const [draftSemesterId, setDraftSemesterId] = useState(profile?.semesterId ?? null)

  const university = getUniversity(realUniversityId)
  const faculty = getFaculty(realFacultyId)
  const department = getDepartment(realDepartmentId)
  const academicYear = getAcademicYear(realYearId)
  const semester = getSemester(profile?.semesterId)

  const enrolledCourses = useMemo(() => courses.filter((c) => c.enrolled), [courses])
  const favoriteSubjects = useMemo(() => {
    const counts = new Map<string, number>()
    for (const c of enrolledCourses) counts.set(c.category, (counts.get(c.category) ?? 0) + 1)
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([category]) => category)
  }, [enrolledCourses])

  const recentAchievements = stats.badges.slice(0, 4).map(getBadgeDefinition)

  function startEditing() {
    setDraftName(realFullName)
    setDraftLanguage(profile?.preferredLanguage ?? 'ar')
    setDraftBio(profile?.bio ?? '')
    setDraftGoals(profile?.studyGoals ?? [])
    setDraftAvatar(profile?.avatarDataUrl ?? user?.avatarUrl ?? null)
    setEditing(true)
  }

  function saveEdits() {
    updateProfile({
      fullName: draftName.trim() || realFullName,
      preferredLanguage: draftLanguage,
      bio: draftBio,
      studyGoals: draftGoals,
      avatarDataUrl: draftAvatar,
    })
    setEditing(false)
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    const dataUrl = await readFileAsDataUrl(file)
    setDraftAvatar(dataUrl)
  }

  function toggleGoal(goal: string) {
    setDraftGoals((prev) =>
      prev.includes(goal) ? prev.filter((g) => g !== goal) : [...prev, goal]
    )
  }

  function saveAcademicIdentity() {
    if (!draftUniversityId || !draftFacultyId || !draftYearId) return
    updateAcademicIdentity({
      universityId: draftUniversityId,
      facultyId: draftFacultyId,
      departmentId: draftDepartmentId,
      academicYearId: draftYearId,
      semesterId: draftSemesterId,
    })
  }

  // These bindings support the existing academic-profile editor flow. The
  // current compact profile surface does not render that modal yet, but keep
  // the implementation intact and type-checked rather than removing it.
  void [
    AnimatePresence,
    SearchableSelect,
    UNIVERSITIES,
    ACADEMIC_YEARS,
    SEMESTERS,
    STUDY_GOAL_OPTIONS,
    LANGUAGES,
    getFacultiesForUniversity,
    getDepartmentsForFaculty,
    requestAcademicChange,
    showUnlockModal,
    setShowUnlockModal,
    setDraftUniversityId,
    setDraftFacultyId,
    setDraftDepartmentId,
    setDraftYearId,
    setDraftSemesterId,
    semester,
    favoriteSubjects,
    recentAchievements,
    toggleGoal,
    saveAcademicIdentity,
  ]

  return (
    <div className="space-y-5">
      {/* Header card */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center gap-5">
          <div className="relative flex-shrink-0">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold overflow-hidden"
              style={{
                background: (editing ? draftAvatar : profile?.avatarDataUrl)
                  ? undefined
                  : 'linear-gradient(135deg, var(--primary), var(--secondary))',
                color: 'var(--primary-foreground)',
              }}
            >
              {(editing ? draftAvatar : profile?.avatarDataUrl) ? (
                <img
                  src={(editing ? draftAvatar : profile?.avatarDataUrl)!}
                  alt={realFullName}
                  className="w-full h-full object-cover"
                />
              ) : (
                realFullName.charAt(0).toUpperCase() || 'S'
              )}
            </div>
            {editing && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center text-xs"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                aria-label="Change profile picture"
              >
                ✎
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatarChange}
            />
          </div>

          <div className="flex-1 min-w-0">
            {editing ? (
              <input
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                className="input-field px-3 py-1.5 rounded-lg text-lg font-bold w-full max-w-xs"
                style={{ fontFamily: 'Orbitron, sans-serif' }}
              />
            ) : (
              <h2
                className="text-xl font-bold"
                style={{
                  fontFamily: 'Orbitron, sans-serif',
                  color: 'var(--foreground)',
                  letterSpacing: '-0.01em',
                }}
              >
                {realFullName}
              </h2>
            )}
            <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
              {realEmail}
            </p>
            <div className="flex flex-wrap items-center gap-2 mt-2.5">
              <span
                className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full"
                style={{
                  background: 'rgba(0,229,192,0.1)',
                  color: '#00E5C0',
                  border: '1px solid rgba(0,229,192,0.24)',
                }}
              >
                {realRole === 'doctor' ? '👨‍🏫 Doctor' : '🎓 Student'}
              </span>
              {university && (
                <Badge tone="primary" size="xs">
                  🏛️ {university.shortName || university.name}
                </Badge>
              )}
              {faculty && (
                <Badge tone="neutral" size="xs">
                  {faculty.icon || '📚'} {faculty.name}
                </Badge>
              )}
              {department && (
                <Badge tone="neutral" size="xs">
                  {department.name}
                </Badge>
              )}
              {academicYear && (
                <Badge tone="accent" size="xs">
                  {academicYear.label}
                </Badge>
              )}
            </div>
          </div>

          <div className="flex flex-col items-center gap-1 flex-shrink-0">
            <ProgressRing
              pct={stats.level.progressPct}
              valueLabel={`L${stats.level.level}`}
              size={72}
              color="var(--accent)"
            />
            <span className="text-xs font-mono font-bold" style={{ color: 'var(--accent)' }}>
              {stats.xp.toLocaleString()} XP
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between mt-6 pt-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            🔥 Current Streak: <strong className="text-white">{profile?.streakDays ?? 0} days</strong>
          </p>
          {editing ? (
            <div className="flex gap-2">
              <button
                onClick={() => setEditing(false)}
                className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={saveEdits}
                className="px-4 py-1.5 rounded-xl text-xs font-bold bg-teal-400 text-slate-950"
              >
                Save
              </button>
            </div>
          ) : (
            <button
              onClick={startEditing}
              className="px-4 py-1.5 rounded-xl text-xs font-bold bg-teal-500/10 text-teal-400 border border-teal-500/30 hover:bg-teal-500/20"
            >
              Edit Profile
            </button>
          )}
        </div>
      </motion.div>
    </div>
  )
}

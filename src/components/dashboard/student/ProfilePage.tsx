import { useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
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

function StatTile({
  icon,
  label,
  value,
  color = 'var(--primary)',
}: {
  icon: string
  label: string
  value: string
  color?: string
}) {
  return (
    <div
      className="rounded-xl p-3.5 flex items-center gap-3"
      style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
    >
      <span
        className="w-9 h-9 rounded-lg flex items-center justify-center text-base flex-shrink-0"
        style={{ background: `${color}18` }}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p
          className="text-sm font-bold truncate"
          style={{ color: 'var(--foreground)', fontFamily: 'Orbitron, sans-serif' }}
        >
          {value}
        </p>
        <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
          {label}
        </p>
      </div>
    </div>
  )
}

/** Confirms the "system rule" gate before unlocking University/Faculty/
 *  Department for editing — per the spec's "University and Faculty
 *  should only be editable if allowed by system rules," this is a real
 *  decision point (transfer/correction request), not a bare toggle. */
function AcademicChangeModal({
  onConfirm,
  onCancel,
}: {
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'var(--overlay-bg)', backdropFilter: 'blur(8px)' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onCancel}
    >
      <motion.div
        className="surface-popover w-full max-w-sm rounded-2xl p-6"
        initial={{ opacity: 0, y: -12, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -12, scale: 0.96 }}
        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm font-bold mb-2" style={{ color: 'var(--foreground)' }}>
          Request an academic identity change?
        </p>
        <p className="text-xs mb-5" style={{ color: 'var(--muted-foreground)' }}>
          Your University, Faculty, and Department are locked after onboarding to keep your
          leaderboard standing and course recommendations accurate. Confirming will unlock these
          fields for editing below.
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-xl text-xs font-semibold input-field"
            style={{ color: 'var(--muted-foreground)' }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-xl text-xs font-bold"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            Unlock fields
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

/** Complete Student Profile page — every field, stat, and edit control
 *  called for by the spec's "PROFILE PAGE" and "STUDENT CARD" sections,
 *  all sourced from real state (`useProfile`, `useCourseCatalog`,
 *  `useFileVault` via `useProfileStats`) — no placeholder numbers. */
export default function ProfilePage() {
  const { profile, updateProfile, requestAcademicChange, updateAcademicIdentity } = useProfile()
  const { courses } = useCourseCatalog()
  const stats = useProfileStats()

  const [editing, setEditing] = useState(false)
  const [showUnlockModal, setShowUnlockModal] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [draftName, setDraftName] = useState(profile?.fullName ?? '')
  const [draftLanguage, setDraftLanguage] = useState(profile?.preferredLanguage ?? 'en')
  const [draftBio, setDraftBio] = useState(profile?.bio ?? '')
  const [draftGoals, setDraftGoals] = useState<string[]>(profile?.studyGoals ?? [])
  const [draftAvatar, setDraftAvatar] = useState<string | null>(profile?.avatarDataUrl ?? null)

  const [draftUniversityId, setDraftUniversityId] = useState(profile?.universityId ?? null)
  const [draftFacultyId, setDraftFacultyId] = useState(profile?.facultyId ?? null)
  const [draftDepartmentId, setDraftDepartmentId] = useState(profile?.departmentId ?? null)
  const [draftYearId, setDraftYearId] = useState(profile?.academicYearId ?? null)
  const [draftSemesterId, setDraftSemesterId] = useState(profile?.semesterId ?? null)

  const university = getUniversity(profile?.universityId)
  const faculty = getFaculty(profile?.facultyId)
  const department = getDepartment(profile?.departmentId)
  const academicYear = getAcademicYear(profile?.academicYearId)
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

  if (!profile) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
          Loading your profile…
        </p>
      </div>
    )
  }

  function startEditing() {
    setDraftName(profile!.fullName)
    setDraftLanguage(profile!.preferredLanguage)
    setDraftBio(profile!.bio)
    setDraftGoals(profile!.studyGoals)
    setDraftAvatar(profile!.avatarDataUrl)
    setEditing(true)
  }

  function saveEdits() {
    updateProfile({
      fullName: draftName.trim() || profile!.fullName,
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
    if (
      !draftUniversityId ||
      !draftFacultyId ||
      !draftDepartmentId ||
      !draftYearId ||
      !draftSemesterId
    ) {
      return
    }
    updateAcademicIdentity({
      universityId: draftUniversityId,
      facultyId: draftFacultyId,
      departmentId: draftDepartmentId,
      academicYearId: draftYearId,
      semesterId: draftSemesterId,
    })
  }

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
                background: (editing ? draftAvatar : profile.avatarDataUrl)
                  ? undefined
                  : 'linear-gradient(135deg, var(--primary), var(--secondary))',
                color: 'var(--primary-foreground)',
              }}
            >
              {(editing ? draftAvatar : profile.avatarDataUrl) ? (
                <img
                  src={(editing ? draftAvatar : profile.avatarDataUrl)!}
                  alt={profile.fullName}
                  className="w-full h-full object-cover"
                />
              ) : (
                profile.fullName.charAt(0).toUpperCase() || 'S'
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
                {profile.fullName}
              </h2>
            )}
            <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
              {profile.email}
            </p>
            <div className="flex flex-wrap items-center gap-2 mt-2.5">
              {university && (
                <Badge tone="primary" size="xs">
                  🏛️ {university.shortName}
                </Badge>
              )}
              {faculty && (
                <Badge tone="neutral" size="xs">
                  {faculty.icon} {faculty.name}
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
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {stats.level.progressPct}% to L{stats.level.level + 1}
            </p>
          </div>

          {!editing ? (
            <button
              onClick={startEditing}
              className="flex-shrink-0 px-4 py-2 rounded-xl text-xs font-semibold input-field"
              style={{ color: 'var(--primary)' }}
            >
              Edit Profile
            </button>
          ) : (
            <div className="flex gap-2 flex-shrink-0">
              <button
                onClick={() => setEditing(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold input-field"
                style={{ color: 'var(--muted-foreground)' }}
              >
                Cancel
              </button>
              <button
                onClick={saveEdits}
                className="px-4 py-2 rounded-xl text-xs font-bold"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                Save
              </button>
            </div>
          )}
        </div>
      </motion.div>

      {/* Learning statistics */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          📊 Learning Statistics
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <StatTile
            icon="🔥"
            label="Learning Streak"
            value={`${profile.streakDays}d`}
            color="#FF7E36"
          />
          <StatTile icon="⚡" label="Total XP" value={stats.xp.toLocaleString()} color="#2DD4BF" />
          <StatTile
            icon="🏆"
            label="Current Rank"
            value={`#${stats.allTimeRank}`}
            color="#a855f7"
          />
          <StatTile
            icon="📚"
            label="Courses Enrolled"
            value={String(stats.coursesEnrolled)}
            color="#38bdf8"
          />
          <StatTile
            icon="🎓"
            label="Completed Courses"
            value={String(stats.coursesCompleted)}
            color="#22c55e"
          />
          <StatTile icon="⏱️" label="Study Hours" value={`${stats.studyHours}h`} color="#f59e0b" />
          <StatTile
            icon="🧠"
            label="Avg Quiz Score"
            value={stats.averageQuizScore !== null ? `${stats.averageQuizScore}%` : '—'}
            color="#2DD4BF"
          />
          <StatTile
            icon="🗂️"
            label="Files Uploaded"
            value={String(stats.filesUploaded)}
            color="#a855f7"
          />
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Badges */}
        <motion.div
          className="glass-card p-6 h-full"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
            🏅 Badges ({stats.badges.length})
          </h3>
          {stats.badges.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              Keep studying to earn your first badge.
            </p>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {stats.badges.map((badgeId, i) => {
                const def = getBadgeDefinition(badgeId)
                return (
                  <motion.div
                    key={badgeId}
                    className="flex flex-col items-center gap-2 p-3.5 rounded-xl text-center"
                    style={{
                      background: 'rgba(255,126,54,0.08)',
                      border: '1px solid rgba(255,126,54,0.2)',
                    }}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.05 * i, type: 'spring', stiffness: 260, damping: 20 }}
                    title={def.description}
                  >
                    <span className="text-2xl">{def.icon}</span>
                    <span
                      className="text-xs font-medium leading-tight"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {def.label}
                    </span>
                  </motion.div>
                )
              })}
            </div>
          )}
        </motion.div>

        {/* Recent achievements */}
        <motion.div
          className="glass-card p-6 h-full"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
            ✨ Recent Achievements
          </h3>
          {recentAchievements.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              No achievements unlocked yet — your progress is tracked automatically.
            </p>
          ) : (
            <div className="space-y-2.5">
              {recentAchievements.map((def, i) => (
                <motion.div
                  key={def.id}
                  className="flex items-center gap-3 p-3 rounded-xl"
                  style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.08 * i }}
                >
                  <span
                    className="w-9 h-9 rounded-lg flex items-center justify-center text-base flex-shrink-0"
                    style={{ background: 'rgba(45,212,191,0.12)' }}
                  >
                    {def.icon}
                  </span>
                  <div className="min-w-0">
                    <p
                      className="text-xs font-semibold truncate"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {def.label}
                    </p>
                    <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                      {def.description}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Current courses */}
        <motion.div
          className="glass-card p-6 h-full"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
            📖 Current Courses
          </h3>
          {enrolledCourses.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              Not enrolled in any course yet.
            </p>
          ) : (
            <div className="space-y-2.5">
              {enrolledCourses.slice(0, 5).map((c) => (
                <div key={c.id} className="flex items-center gap-3">
                  <span
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                    style={{ background: `${c.color}18` }}
                  >
                    {c.icon}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-xs font-semibold truncate"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {c.title}
                    </p>
                    <div
                      className="h-1 rounded-full mt-1 overflow-hidden"
                      style={{ background: 'var(--tint-2)' }}
                    >
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${c.progressPct}%`, background: c.color }}
                      />
                    </div>
                  </div>
                  <span
                    className="text-xs flex-shrink-0"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {c.progressPct}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Favorite subjects + study goals + bio */}
        <motion.div
          className="glass-card p-6 h-full"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--foreground)' }}>
            ❤️ Favorite Subjects
          </h3>
          <div className="flex flex-wrap gap-2 mb-5">
            {favoriteSubjects.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                Enroll in courses to see your favorite subjects.
              </p>
            ) : (
              favoriteSubjects.map((s) => (
                <Badge key={s} tone="info" size="xs">
                  {s}
                </Badge>
              ))
            )}
          </div>

          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--foreground)' }}>
            🎯 Study Goals
          </h3>
          {editing ? (
            <div className="grid grid-cols-2 gap-2 mb-5">
              {STUDY_GOAL_OPTIONS.map((goal) => {
                const active = draftGoals.includes(goal)
                return (
                  <button
                    key={goal}
                    onClick={() => toggleGoal(goal)}
                    className="text-xs font-medium px-3 py-2 rounded-lg text-left transition-colors"
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
          ) : (
            <div className="flex flex-wrap gap-2 mb-5">
              {profile.studyGoals.length === 0 ? (
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  No study goals set yet.
                </p>
              ) : (
                profile.studyGoals.map((g) => (
                  <Badge key={g} tone="success" size="xs">
                    {g}
                  </Badge>
                ))
              )}
            </div>
          )}

          <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            📝 Bio
          </h3>
          {editing ? (
            <textarea
              value={draftBio}
              onChange={(e) => setDraftBio(e.target.value)}
              placeholder="Tell classmates a bit about yourself…"
              rows={3}
              className="input-field w-full px-3 py-2.5 rounded-xl text-xs resize-none"
            />
          ) : (
            <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              {profile.bio || 'No bio yet.'}
            </p>
          )}

          {editing && (
            <div className="mt-4">
              <SearchableSelect
                label="Preferred Language"
                options={LANGUAGES.map((l) => ({ id: l.id, label: l.label }))}
                value={draftLanguage}
                onChange={setDraftLanguage}
              />
            </div>
          )}
        </motion.div>
      </div>

      {/* Academic identity — locked unless a change is requested */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            🎓 Academic Information
          </h3>
          {profile.academicIdentityLocked ? (
            <button
              onClick={() => setShowUnlockModal(true)}
              className="text-xs font-semibold px-3 py-1.5 rounded-full"
              style={{ background: 'var(--tint-2)', color: 'var(--muted-foreground)' }}
            >
              🔒 Locked — request change
            </button>
          ) : (
            <Badge tone="warning" size="xs">
              Unlocked for editing
            </Badge>
          )}
        </div>

        {profile.academicIdentityLocked ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatTile icon="🏛️" label="University" value={university?.shortName ?? '—'} />
            <StatTile icon={faculty?.icon ?? '⚙️'} label="Faculty" value={faculty?.name ?? '—'} />
            <StatTile icon="🧭" label="Department" value={department?.name ?? '—'} />
            <StatTile icon="📅" label="Academic Year" value={academicYear?.label ?? '—'} />
            <StatTile icon="🗓️" label="Semester" value={semester?.label ?? '—'} />
            <StatTile icon="🆔" label="Student ID" value={profile.studentIdNumber ?? 'Not set'} />
          </div>
        ) : (
          <div className="space-y-4">
            <SearchableSelect
              label="University"
              required
              options={UNIVERSITIES.map((u) => ({ id: u.id, label: u.name, sublabel: u.country }))}
              value={draftUniversityId}
              onChange={(id) => {
                setDraftUniversityId(id)
                setDraftFacultyId(null)
                setDraftDepartmentId(null)
              }}
            />
            <SearchableSelect
              label="Faculty / College"
              required
              options={getFacultiesForUniversity(draftUniversityId).map((f) => ({
                id: f.id,
                label: f.name,
                icon: f.icon,
              }))}
              value={draftFacultyId}
              disabled={!draftUniversityId}
              onChange={(id) => {
                setDraftFacultyId(id)
                setDraftDepartmentId(null)
              }}
            />
            <SearchableSelect
              label="Department"
              required
              options={getDepartmentsForFaculty(draftFacultyId).map((d) => ({
                id: d.id,
                label: d.name,
              }))}
              value={draftDepartmentId}
              disabled={!draftFacultyId}
              onChange={setDraftDepartmentId}
            />
            <div className="grid grid-cols-2 gap-4">
              <SearchableSelect
                label="Academic Year"
                required
                options={ACADEMIC_YEARS.map((y) => ({ id: y.id, label: y.label }))}
                value={draftYearId}
                onChange={setDraftYearId}
              />
              <SearchableSelect
                label="Semester"
                required
                options={SEMESTERS.map((s) => ({ id: s.id, label: s.label }))}
                value={draftSemesterId}
                onChange={setDraftSemesterId}
              />
            </div>
            <button
              onClick={saveAcademicIdentity}
              disabled={
                !draftUniversityId ||
                !draftFacultyId ||
                !draftDepartmentId ||
                !draftYearId ||
                !draftSemesterId
              }
              className="px-4 py-2.5 rounded-xl text-xs font-bold"
              style={{
                background: 'var(--primary)',
                color: 'var(--primary-foreground)',
                opacity:
                  !draftUniversityId ||
                  !draftFacultyId ||
                  !draftDepartmentId ||
                  !draftYearId ||
                  !draftSemesterId
                    ? 0.5
                    : 1,
              }}
            >
              Save & re-lock academic identity
            </button>
          </div>
        )}
      </motion.div>

      <AnimatePresence>
        {showUnlockModal && (
          <AcademicChangeModal
            onCancel={() => setShowUnlockModal(false)}
            onConfirm={() => {
              requestAcademicChange()
              setDraftUniversityId(profile.universityId)
              setDraftFacultyId(profile.facultyId)
              setDraftDepartmentId(profile.departmentId)
              setDraftYearId(profile.academicYearId)
              setDraftSemesterId(profile.semesterId)
              setShowUnlockModal(false)
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

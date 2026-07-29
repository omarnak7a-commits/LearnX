import { motion } from 'framer-motion'
import { useProfile } from '../../../context/ProfileContext'
import { useProfileStats } from '../../../hooks/useProfileStats'
import { getUniversity, getFaculty, getDepartment } from '../../../data/academicCatalog'

/**
 * "DASHBOARD INTEGRATION" widget from the spec — University / Faculty /
 * Department / Current Rank / XP / Next Level Progress, all sourced from
 * the real profile + `useProfileStats()` (same numbers shown on the
 * Profile page and Rankings leaderboard, never independently hardcoded).
 */
export default function AcademicIdentityWidget() {
  const { profile } = useProfile()
  const stats = useProfileStats()

  if (!profile) return null

  const university = getUniversity(profile.universityId)
  const faculty = getFaculty(profile.facultyId)
  const department = getDepartment(profile.departmentId)

  return (
    <motion.div
      className="glass-card p-5 h-full flex flex-col"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          🎓 Academic Identity
        </h3>
        <span
          className="text-xs font-bold px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(168,85,247,0.12)', color: '#a855f7' }}
        >
          Rank #{stats.allTimeRank}
        </span>
      </div>

      <div className="space-y-1.5 mb-4">
        <p className="text-sm font-semibold truncate" style={{ color: 'var(--foreground)' }}>
          {faculty?.name ?? 'Faculty not set'}
        </p>
        <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
          {department?.name ?? 'Department not set'}
        </p>
        <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)', opacity: 0.75 }}>
          {university?.name ?? 'University not set'}
        </p>
      </div>

      <div className="mt-auto">
        <div className="flex items-center justify-between mb-1.5">
          <span
            className="text-xs font-black"
            style={{ color: 'var(--accent)', fontFamily: 'Orbitron, sans-serif' }}
          >
            Level {stats.level.level}
          </span>
          <span className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>
            {stats.xp.toLocaleString()} XP
          </span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-2)' }}>
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg, var(--accent), #ffad7a)' }}
            initial={{ width: 0 }}
            animate={{ width: `${stats.level.progressPct}%` }}
            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
        <p className="text-xs mt-1.5" style={{ color: 'var(--muted-foreground)' }}>
          {stats.level.progressPct}% to Level {stats.level.level + 1}
        </p>
      </div>
    </motion.div>
  )
}

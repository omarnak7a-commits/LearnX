import { motion } from 'framer-motion'

interface Achievement {
  icon: string
  label: string
  unlocked: boolean
}

const achievements: Achievement[] = [
  { icon: '🏅', label: 'Early Bird', unlocked: true },
  { icon: '🔥', label: '21-Day Streak', unlocked: true },
  { icon: '🧠', label: 'Quiz Master', unlocked: true },
  { icon: '📚', label: 'Bookworm', unlocked: true },
  { icon: '⚡', label: 'Speed Learner', unlocked: false },
  { icon: '👑', label: 'Top 1%', unlocked: false },
]

const certificates = [
  { name: 'Foundations of Calculus', date: 'Issued May 2026', icon: '📜' },
  { name: 'Intro to Cell Biology', date: 'Issued Feb 2026', icon: '📜' },
]

/** Certificates + Achievements grid. */
export default function CertificatesAchievements() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <motion.div
        className="glass-card p-6 h-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          🏆 Achievements
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {achievements.map((a, i) => (
            <motion.div
              key={a.label}
              className="flex flex-col items-center gap-2 p-3.5 rounded-xl text-center"
              style={{
                background: a.unlocked ? 'rgba(255,126,54,0.08)' : 'var(--tint-1)',
                border: `1px solid ${a.unlocked ? 'rgba(255,126,54,0.2)' : 'var(--border-subtle)'}`,
                opacity: a.unlocked ? 1 : 0.45,
              }}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: a.unlocked ? 1 : 0.45, scale: 1 }}
              transition={{
                delay: 0.05 * i,
                type: 'spring',
                stiffness: 260,
                damping: 20,
              }}
              whileHover={a.unlocked ? { scale: 1.05 } : undefined}
            >
              <span className="text-2xl">{a.icon}</span>
              <span
                className="text-xs font-medium leading-tight"
                style={{ color: 'var(--foreground)' }}
              >
                {a.label}
              </span>
            </motion.div>
          ))}
        </div>
      </motion.div>

      <motion.div
        className="glass-card p-6 h-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.05 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          📜 Certificates
        </h3>
        <div className="space-y-2.5">
          {certificates.map((c, i) => (
            <motion.div
              key={c.name}
              className="flex items-center gap-3 p-3.5 rounded-xl"
              style={{
                background: 'var(--tint-1)',
                border: '1px solid var(--border-subtle)',
              }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.08 * i }}
            >
              <span
                className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
                style={{ background: 'rgba(45,212,191,0.12)' }}
              >
                {c.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {c.name}
                </p>
                <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                  {c.date}
                </p>
              </div>
              <button
                className="text-xs font-semibold flex-shrink-0"
                style={{ color: 'var(--primary)' }}
              >
                Download
              </button>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

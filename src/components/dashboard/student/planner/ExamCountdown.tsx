import { motion } from 'framer-motion'
import type { UpcomingExam } from '../../../../types/planner'

interface ExamCountdownProps {
  exams: UpcomingExam[]
}

export default function ExamCountdown({ exams }: ExamCountdownProps) {
  return (
    <div className="space-y-3">
      {exams.map((exam, i) => (
        <motion.div
          key={exam.id}
          className="p-4 rounded-xl"
          style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
        >
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                {exam.title}
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                {exam.subject} · {exam.date}
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              <p
                className="text-2xl font-black leading-none"
                style={{
                  fontFamily: 'Orbitron, sans-serif',
                  color: exam.daysAway <= 5 ? 'var(--danger)' : 'var(--accent)',
                }}
              >
                {exam.daysAway}
              </p>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                days left
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              Readiness
            </p>
            <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
              {exam.readiness}%
            </p>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
            <motion.div
              className="h-full rounded-full"
              style={{
                background:
                  exam.readiness >= 70
                    ? 'var(--success)'
                    : exam.readiness >= 45
                      ? 'var(--warning)'
                      : 'var(--danger)',
              }}
              initial={{ width: 0 }}
              animate={{ width: `${exam.readiness}%` }}
              transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        </motion.div>
      ))}
    </div>
  )
}

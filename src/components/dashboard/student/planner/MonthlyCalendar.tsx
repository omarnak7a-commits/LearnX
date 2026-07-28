import { motion } from 'framer-motion'
import type { StudyTask } from '../../../../types/planner'

interface MonthlyCalendarProps {
  tasks: StudyTask[]
}

/** Simplified monthly overview: density heat per upcoming day, built from the 7-day rolling task window. */
export default function MonthlyCalendar({ tasks }: MonthlyCalendarProps) {
  const daysInView = 28
  const density = Array.from({ length: daysInView }, (_, i) => {
    const dayTasks = tasks.filter((t) => t.day === i % 7 && t.type !== 'break')
    return dayTasks.length
  })
  const max = Math.max(1, ...density)

  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5">
        {Array.from({ length: daysInView }, (_, i) => {
          const intensity = density[i] / max
          return (
            <motion.div
              key={i}
              className="aspect-square rounded-md flex items-center justify-center text-xs font-mono"
              style={{
                background:
                  intensity === 0
                    ? 'var(--tint-2)'
                    : `color-mix(in srgb, var(--primary) ${Math.round(20 + intensity * 70)}%, transparent)`,
                color: intensity > 0.5 ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.01 }}
            >
              {i + 1}
            </motion.div>
          )
        })}
      </div>
      <div className="flex items-center gap-2 mt-4 text-xs" style={{ color: 'var(--muted-foreground)' }}>
        <span>Lighter</span>
        <div className="flex gap-1">
          {[0.15, 0.4, 0.65, 0.9].map((v) => (
            <div
              key={v}
              style={{
                width: 12,
                height: 12,
                borderRadius: 3,
                background: `color-mix(in srgb, var(--primary) ${Math.round(v * 100)}%, transparent)`,
              }}
            />
          ))}
        </div>
        <span>Busier</span>
      </div>
    </div>
  )
}

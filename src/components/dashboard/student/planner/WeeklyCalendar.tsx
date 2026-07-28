import { useState } from 'react'
import { motion } from 'framer-motion'
import type { StudyTask } from '../../../../types/planner'

interface WeeklyCalendarProps {
  tasks: StudyTask[]
  onSelectDay: (day: number) => void
  selectedDay: number
}

const DAY_LABELS = ['Today', 'Tomorrow', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export default function WeeklyCalendar({ tasks, onSelectDay, selectedDay }: WeeklyCalendarProps) {
  const [hoveredTask, setHoveredTask] = useState<string | null>(null)

  return (
    <div className="grid grid-cols-7 gap-2">
      {DAY_LABELS.map((label, day) => {
        const dayTasks = tasks.filter((t) => t.day === day && t.type !== 'break')
        const isSelected = day === selectedDay
        const doneCount = dayTasks.filter((t) => t.done).length

        return (
          <motion.button
            key={day}
            onClick={() => onSelectDay(day)}
            className="rounded-xl p-2.5 text-left transition-colors flex flex-col"
            style={{
              background: isSelected ? 'rgba(45,212,191,0.1)' : 'var(--tint-1)',
              border: `1px solid ${isSelected ? 'rgba(45,212,191,0.3)' : 'var(--border-subtle)'}`,
              minHeight: 120,
            }}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: day * 0.04 }}
          >
            <p
              className="text-xs font-semibold mb-2"
              style={{ color: isSelected ? 'var(--primary)' : 'var(--foreground)' }}
            >
              {label}
            </p>
            <div className="space-y-1 flex-1">
              {dayTasks.slice(0, 3).map((t) => (
                <div
                  key={t.id}
                  onMouseEnter={() => setHoveredTask(t.id)}
                  onMouseLeave={() => setHoveredTask(null)}
                  className="text-xs px-1.5 py-1 rounded truncate relative"
                  style={{
                    background: `${t.color}18`,
                    color: t.color,
                    textDecoration: t.done ? 'line-through' : 'none',
                    opacity: t.done ? 0.6 : 1,
                  }}
                >
                  {t.title}
                  {hoveredTask === t.id && (
                    <div className="surface-tooltip absolute z-20 left-0 top-full mt-1 px-2 py-1.5 rounded-lg text-xs w-40 whitespace-normal shadow-lg">
                      {t.title} · {t.durationMinutes}min
                    </div>
                  )}
                </div>
              ))}
              {dayTasks.length > 3 && (
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  +{dayTasks.length - 3} more
                </p>
              )}
            </div>
            {dayTasks.length > 0 && (
              <p className="text-xs mt-2" style={{ color: 'var(--muted-foreground)' }}>
                {doneCount}/{dayTasks.length} done
              </p>
            )}
          </motion.button>
        )
      })}
    </div>
  )
}

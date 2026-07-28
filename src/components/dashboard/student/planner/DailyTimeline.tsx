import { motion } from 'framer-motion'
import type { StudyTask } from '../../../../types/planner'
import Badge from '../../../ui/Badge'

interface DailyTimelineProps {
  tasks: StudyTask[]
  onToggle: (id: string) => void
}

const typeIcon: Record<StudyTask['type'], string> = {
  lecture: '🎬',
  revision: '🔁',
  practice: '✍️',
  quiz: '❓',
  flashcards: '🗂️',
  assignment: '📝',
  break: '☕',
  'exam-prep': '🧾',
}

const priorityTone: Record<StudyTask['priority'], 'neutral' | 'primary' | 'warning' | 'danger'> = {
  low: 'neutral',
  medium: 'primary',
  high: 'warning',
  critical: 'danger',
}

function formatMinute(m: number): string {
  const h = Math.floor(m / 60)
  const min = m % 60
  const period = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${String(min).padStart(2, '0')} ${period}`
}

export default function DailyTimeline({ tasks, onToggle }: DailyTimelineProps) {
  const sorted = [...tasks].sort((a, b) => a.startMinute - b.startMinute)

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-center py-10" style={{ color: 'var(--muted-foreground)' }}>
        No tasks scheduled for this day.
      </p>
    )
  }

  return (
    <div className="relative pl-2">
      {sorted.map((task, i) => {
        const isLast = i === sorted.length - 1
        return (
          <motion.div
            key={task.id}
            className="relative flex gap-3 pb-4 last:pb-0"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
          >
            {!isLast && (
              <span
                className="absolute left-[9px] top-6 bottom-0 w-px"
                style={{ background: 'var(--border-subtle)' }}
              />
            )}
            <button
              onClick={() => onToggle(task.id)}
              className="relative flex-shrink-0 w-5 h-5 mt-1 rounded-full flex items-center justify-center transition-all"
              style={{
                background: task.done ? 'var(--primary)' : 'var(--tint-3)',
                border: `1.5px solid ${task.done ? 'var(--primary)' : 'var(--border)'}`,
              }}
            >
              {task.done && (
                <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5l2.5 2.5 4-4" stroke="var(--primary-foreground)" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              )}
            </button>

            <div
              className="flex-1 min-w-0 p-3.5 rounded-xl"
              style={{
                background: task.type === 'break' ? 'var(--tint-1)' : `${task.color}0f`,
                border: `1px solid ${task.type === 'break' ? 'var(--border-subtle)' : `${task.color}30`}`,
                opacity: task.done ? 0.65 : 1,
              }}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm flex-shrink-0">{typeIcon[task.type]}</span>
                  <p
                    className="text-sm font-semibold truncate"
                    style={{
                      color: 'var(--foreground)',
                      textDecoration: task.done ? 'line-through' : 'none',
                    }}
                  >
                    {task.title}
                  </p>
                </div>
                <span className="text-xs font-mono flex-shrink-0" style={{ color: 'var(--muted-foreground)' }}>
                  {formatMinute(task.startMinute)}
                </span>
              </div>

              {task.subject && (
                <p className="text-xs mb-1.5" style={{ color: 'var(--muted-foreground)' }}>
                  {task.subject} · {task.durationMinutes} min
                </p>
              )}

              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p className="text-xs leading-relaxed flex items-center gap-1" style={{ color: 'var(--muted-foreground)' }}>
                  <span style={{ color: task.color }}>✨</span> {task.aiReason}
                </p>
                {task.priority !== 'low' && (
                  <Badge tone={priorityTone[task.priority]} size="xs">
                    {task.priority}
                  </Badge>
                )}
              </div>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}

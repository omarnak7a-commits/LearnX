import { motion } from 'framer-motion'
import MiniCalendar from '../shared/MiniCalendar'
import Badge from '../../ui/Badge'

const events = [
  { day: 27, label: 'Physics Lab Report due', color: '#2DD4BF' },
  { day: 27, label: 'AI Tutor session 6pm', color: '#a855f7' },
  { day: 30, label: 'Problem Set 6 due', color: '#f59e0b' },
  { day: 8, label: 'Midterm Exam — Mechanics', color: '#FF7E36' },
]

const notifications = [
  { icon: '📋', text: 'Quiz results ready: Biology Chapter 8', time: '2m ago' },
  { icon: '🏆', text: 'Streak milestone: 21 days', time: '1h ago' },
  { icon: '🤖', text: 'AI generated 12 new flashcards', time: '3h ago' },
]

/** Calendar (with events) + Notifications feed panel. */
export default function CalendarNotifications() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <motion.div
        className="glass-card p-6 h-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h3
          className="text-sm font-bold mb-4 flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          📅 Calendar
        </h3>
        <MiniCalendar month="July" year={2026} today={27} events={events} />
      </motion.div>

      <motion.div
        className="glass-card p-6 h-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.05 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3
            className="text-sm font-bold flex items-center gap-1.5"
            style={{ color: 'var(--foreground)' }}
          >
            🔔 Notifications
          </h3>
          <Badge tone="accent" size="xs">
            {notifications.length} new
          </Badge>
        </div>
        <div className="space-y-2">
          {notifications.map((n, i) => (
            <motion.div
              key={n.text}
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.06 * i }}
            >
              <span className="text-base flex-shrink-0">{n.icon}</span>
              <div className="min-w-0 flex-1">
                <p className="text-xs leading-relaxed" style={{ color: 'var(--foreground)' }}>
                  {n.text}
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  {n.time}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

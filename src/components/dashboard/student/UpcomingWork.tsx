import { motion, AnimatePresence } from 'framer-motion'
import Badge from '../../ui/Badge'
import { useCalendar } from '../../../context/CalendarContext'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import { EVENT_TYPE_META } from '../../../types/calendar'
import {
  daysRemaining,
  formatDaysRemaining,
  formatEventDate,
  formatEventTime,
  sortByNearest,
} from '../../../lib/calendar/eventFormat'

/**
 * Upcoming Events widget per the spec's "FEATURE 1" — reads from the
 * exact same `useCalendar()` context the Calendar page uses, so
 * creating/editing/deleting/completing an event there is reflected here
 * immediately via ordinary React re-render (no refresh, no separate
 * mock data to keep in sync — this *is* the "Calendar Integration").
 * Shows Event Title, Course, Date, Time, Days Remaining, and an Event
 * Type badge for every supported event type, auto-sorted by nearest
 * upcoming, and automatically excludes anything already past due
 * (matching "if an event expires, remove it automatically from Upcoming
 * Events").
 */
export default function UpcomingWork() {
  const { events } = useCalendar()
  const { getCourse } = useCourseCatalog()

  const upcoming = sortByNearest(events.filter((e) => !e.completed && daysRemaining(e) >= 0)).slice(
    0,
    6
  )

  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between mb-4">
        <p
          className="text-xs font-bold flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          <span>📅</span>
          Upcoming Events
        </p>
        <Badge tone="primary" size="xs">
          {upcoming.length}
        </Badge>
      </div>

      <div className="space-y-2">
        <AnimatePresence initial={false}>
          {upcoming.map((e, i) => {
            const course = e.courseId ? getCourse(e.courseId) : undefined
            const days = daysRemaining(e)
            const meta = EVENT_TYPE_META[e.type]
            return (
              <motion.div
                key={e.id}
                className="flex items-center gap-3 p-3 rounded-xl"
                style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={{ delay: 0.06 * i }}
              >
                <span
                  className="w-1.5 h-8 rounded-full flex-shrink-0"
                  style={{ background: e.color }}
                />
                <div className="min-w-0 flex-1">
                  <p
                    className="text-xs font-semibold truncate"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {e.title}
                  </p>
                  <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                    {course ? `${course.title} · ` : ''}
                    {formatEventDate(e)} · {formatEventTime(e)}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <span
                    className="text-xs px-1.5 py-0.5 rounded font-semibold"
                    style={{
                      background: `${meta.defaultColor}18`,
                      color: meta.defaultColor,
                      fontSize: 9,
                    }}
                  >
                    {meta.icon} {meta.label}
                  </span>
                  <Badge tone={days <= 1 ? 'accent' : 'neutral'} size="xs">
                    {formatDaysRemaining(days)}
                  </Badge>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
        {upcoming.length === 0 && (
          <p className="text-xs text-center py-6" style={{ color: 'var(--muted-foreground)' }}>
            No upcoming events — add one from the Calendar page.
          </p>
        )}
      </div>
    </motion.div>
  )
}

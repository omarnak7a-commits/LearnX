import { useState } from 'react'
import { motion } from 'framer-motion'
import MiniCalendar from './MiniCalendar'
import FullCalendarGrid from './FullCalendarGrid'
import CreateEventModal from './CreateEventModal'
import Badge from '../../ui/Badge'
import type { Role } from '../Sidebar'
import { useFileVault } from '../../../context/FileVaultContext'
import { useCalendar } from '../../../context/CalendarContext'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import { daysUntil } from '../../../lib/fileVault/studyHub'
import type { CalendarEvent } from '../../../types/calendar'
import { EVENT_TYPE_META } from '../../../types/calendar'
import {
  daysRemaining,
  formatDaysRemaining,
  formatEventDate,
  formatEventTime,
  sortByNearest,
} from '../../../lib/calendar/eventFormat'

interface CalendarPageProps {
  role: Role
}

const doctorEvents = [
  { day: 27, label: 'Office hours 2–4pm', color: '#2DD4BF' },
  { day: 29, label: 'CS201 Pop Quiz', color: '#f59e0b' },
  { day: 30, label: 'Department meeting', color: '#a855f7' },
  { day: 8, label: 'CS201 Midterm proctoring', color: '#FF7E36' },
]

const doctorUpcoming = [
  { title: 'Office hours', time: 'Today, 2:00pm', color: '#2DD4BF' },
  { title: 'CS201 Pop Quiz', time: 'Jul 29, 9:00am', color: '#f59e0b' },
  { title: 'Department meeting', time: 'Jul 30, 3:00pm', color: '#a855f7' },
]

/** Formats a real file-derived exam date relative to "today" without
 * pretending to know the current calendar month's exact day numbers used
 * by the (static, out-of-scope) doctor demo calendar. */
function formatExamTime(daysAway: number): string {
  if (daysAway <= 0) return 'Today'
  if (daysAway === 1) return 'Tomorrow'
  return `In ${daysAway} days`
}

/**
 * Full Calendar Integration per the spec's "FEATURE 1" — real month
 * grid, create/edit/delete any event type, and a live Upcoming list that
 * shares the exact same `useCalendar()` state as the Dashboard's
 * Upcoming Events widget, so creating/editing/deleting here updates that
 * widget instantly with no refresh (React re-render is the sync
 * mechanism, per the same context both components subscribe to).
 *
 * Doctor role keeps its pre-existing static demo calendar unchanged —
 * this feature is scoped to the Student Dashboard per the spec.
 */
export default function CalendarPage({ role }: CalendarPageProps) {
  const { files } = useFileVault()

  if (role === 'doctor') {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        <motion.div
          className="glass-card p-6"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <MiniCalendar month="July" year={2026} today={27} events={doctorEvents} />
        </motion.div>
        <motion.div
          className="glass-card p-6"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
              Upcoming
            </h3>
            <Badge tone="primary" size="xs">
              {doctorUpcoming.length}
            </Badge>
          </div>
          <div className="space-y-2.5">
            {doctorUpcoming.map((e, i) => (
              <motion.div
                key={e.title}
                className="flex items-center gap-3 p-3 rounded-xl"
                style={{ background: 'var(--tint-1)' }}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.08 * i }}
              >
                <span
                  className="w-1.5 h-8 rounded-full flex-shrink-0"
                  style={{ background: e.color }}
                />
                <div className="min-w-0">
                  <p
                    className="text-xs font-semibold truncate"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {e.title}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    {e.time}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    )
  }

  return <StudentCalendar files={files} />
}

function StudentCalendar({ files }: { files: ReturnType<typeof useFileVault>['files'] }) {
  const { events, createEvent, updateEvent, deleteEvent } = useCalendar()
  const { getCourse } = useCourseCatalog()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null)
  const [defaultDate, setDefaultDate] = useState<string | null>(null)

  const fileExamEvents = files
    .filter((f) => f.examDate !== null)
    .map((f) => {
      const daysAway = daysUntil(f.examDate) ?? 0
      return { title: `${f.course} Exam`, time: formatExamTime(daysAway), color: f.color, daysAway }
    })
    .filter((e) => e.daysAway >= 0)

  const upcoming = sortByNearest(events.filter((e) => !e.completed && daysRemaining(e) >= 0)).slice(
    0,
    12
  )

  function openCreate(iso?: string) {
    setEditingEvent(null)
    setDefaultDate(iso ?? null)
    setModalOpen(true)
  }

  function openEdit(event: CalendarEvent) {
    setEditingEvent(event)
    setModalOpen(true)
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5">
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Click any day to add an event, or click an existing event to edit it.
          </p>
          <button
            onClick={() => openCreate()}
            className="text-xs font-semibold px-4 py-2 rounded-full flex-shrink-0"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            + New Event
          </button>
        </div>
        <FullCalendarGrid events={events} onSelectDate={openCreate} onSelectEvent={openEdit} />
      </motion.div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Upcoming
          </h3>
          <Badge tone="primary" size="xs">
            {upcoming.length + fileExamEvents.length}
          </Badge>
        </div>
        <div className="space-y-2.5 max-h-[560px] overflow-y-auto scrollbar-thin pr-1">
          {fileExamEvents.map((e, i) => (
            <motion.div
              key={`file-exam-${e.title}-${i}`}
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.05 * i }}
            >
              <span
                className="w-1.5 h-8 rounded-full flex-shrink-0"
                style={{ background: e.color }}
              />
              <div className="min-w-0">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {e.title}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {e.time} · from My Files
                </p>
              </div>
            </motion.div>
          ))}
          {upcoming.map((e, i) => {
            const course = e.courseId ? getCourse(e.courseId) : undefined
            const days = daysRemaining(e)
            return (
              <motion.button
                key={e.id}
                onClick={() => openEdit(e)}
                className="w-full text-left flex items-center gap-3 p-3 rounded-xl transition-colors"
                style={{ background: 'var(--tint-1)' }}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * (i + fileExamEvents.length) }}
                onMouseEnter={(ev) => (ev.currentTarget.style.background = 'var(--surface-hover)')}
                onMouseLeave={(ev) => (ev.currentTarget.style.background = 'var(--tint-1)')}
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
                    {EVENT_TYPE_META[e.type].icon} {e.title}
                  </p>
                  <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                    {course ? `${course.title} · ` : ''}
                    {formatEventDate(e)} · {formatEventTime(e)}
                  </p>
                </div>
                <Badge tone={days <= 1 ? 'accent' : 'neutral'} size="xs">
                  {formatDaysRemaining(days)}
                </Badge>
              </motion.button>
            )
          })}
          {upcoming.length === 0 && fileExamEvents.length === 0 && (
            <p className="text-xs text-center py-6" style={{ color: 'var(--muted-foreground)' }}>
              No upcoming events — click "+ New Event" to add one.
            </p>
          )}
        </div>
      </motion.div>

      <CreateEventModal
        open={modalOpen}
        editingEvent={editingEvent}
        defaultDate={defaultDate}
        onClose={() => setModalOpen(false)}
        onCreate={createEvent}
        onUpdate={updateEvent}
        onDelete={deleteEvent}
      />
    </div>
  )
}

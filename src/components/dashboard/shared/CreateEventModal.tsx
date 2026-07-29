import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { CalendarEvent, CalendarEventInput, CalendarEventType } from '../../../types/calendar'
import { EVENT_TYPE_META, REMINDER_OPTIONS } from '../../../types/calendar'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'

const EVENT_TYPES = Object.keys(EVENT_TYPE_META) as CalendarEventType[]

interface CreateEventModalProps {
  open: boolean
  editingEvent: CalendarEvent | null
  defaultDate?: string | null
  onClose: () => void
  onCreate: (input: CalendarEventInput) => void
  onUpdate: (id: string, input: CalendarEventInput) => void
  onDelete: (id: string) => void
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

/**
 * Real create/edit/delete surface for Calendar Events — every field from
 * the spec's "Each event should include" list (Title, Description, Date,
 * Time, Color, Event Type, Optional Course, Reminder), backed by
 * `useCalendar()` so saving here immediately reflects in both the
 * Calendar and the Dashboard's Upcoming Events widget.
 */
export default function CreateEventModal({
  open,
  editingEvent,
  defaultDate,
  onClose,
  onCreate,
  onUpdate,
  onDelete,
}: CreateEventModalProps) {
  const { courses } = useCourseCatalog()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [date, setDate] = useState(todayIso())
  const [time, setTime] = useState('')
  const [type, setType] = useState<CalendarEventType>('assignment')
  const [courseId, setCourseId] = useState<string>('')
  const [reminderMinutesBefore, setReminderMinutesBefore] = useState<number | null>(null)

  useEffect(() => {
    if (editingEvent) {
      setTitle(editingEvent.title)
      setDescription(editingEvent.description)
      setDate(editingEvent.date)
      setTime(editingEvent.time ?? '')
      setType(editingEvent.type)
      setCourseId(editingEvent.courseId ?? '')
      setReminderMinutesBefore(editingEvent.reminderMinutesBefore)
    } else {
      setTitle('')
      setDescription('')
      setDate(defaultDate ?? todayIso())
      setTime('')
      setType('assignment')
      setCourseId('')
      setReminderMinutesBefore(null)
    }
  }, [editingEvent, defaultDate, open])

  function handleSave() {
    if (!title.trim()) return
    const input: CalendarEventInput = {
      title: title.trim(),
      description: description.trim(),
      date,
      time: time || null,
      color: EVENT_TYPE_META[type].defaultColor,
      type,
      courseId: courseId || null,
      reminderMinutesBefore,
    }
    if (editingEvent) {
      onUpdate(editingEvent.id, input)
    } else {
      onCreate(input)
    }
    onClose()
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0"
            style={{ background: 'var(--overlay-bg)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
          />
          <motion.div
            className="relative w-full max-w-lg max-h-[85vh] overflow-y-auto scrollbar-thin rounded-2xl"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            <div
              className="flex items-center justify-between px-6 py-5 border-b"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              <h3
                className="text-base font-bold"
                style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
              >
                {editingEvent ? 'Edit Event' : 'New Event'}
              </h3>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ color: 'var(--muted-foreground)' }}
                aria-label="Close"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label
                  className="text-xs font-semibold mb-1.5 block"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Title
                </label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Midterm Exam"
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                  autoFocus
                />
              </div>

              <div>
                <label
                  className="text-xs font-semibold mb-1.5 block"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  placeholder="Optional details…"
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    className="text-xs font-semibold mb-1.5 block"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    Date
                  </label>
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label
                    className="text-xs font-semibold mb-1.5 block"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    Time (optional)
                  </label>
                  <input
                    type="time"
                    value={time}
                    onChange={(e) => setTime(e.target.value)}
                    className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div>
                <label
                  className="text-xs font-semibold mb-1.5 block"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Event Type
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {EVENT_TYPES.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setType(t)}
                      className="text-xs font-medium px-2.5 py-2 rounded-lg flex items-center gap-1.5 justify-center transition-colors"
                      style={{
                        background:
                          type === t ? `${EVENT_TYPE_META[t].defaultColor}22` : 'var(--tint-1)',
                        border: `1.5px solid ${type === t ? EVENT_TYPE_META[t].defaultColor : 'var(--border-subtle)'}`,
                        color: type === t ? EVENT_TYPE_META[t].defaultColor : 'var(--foreground)',
                      }}
                    >
                      <span>{EVENT_TYPE_META[t].icon}</span>
                      {EVENT_TYPE_META[t].label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label
                  className="text-xs font-semibold mb-1.5 block"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Course (optional)
                </label>
                <select
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value)}
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                >
                  <option value="">No course</option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  className="text-xs font-semibold mb-1.5 block"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Reminder
                </label>
                <select
                  value={reminderMinutesBefore === null ? '' : String(reminderMinutesBefore)}
                  onChange={(e) =>
                    setReminderMinutesBefore(e.target.value === '' ? null : Number(e.target.value))
                  }
                  className="input-field w-full px-3.5 py-2.5 rounded-lg text-sm"
                >
                  {REMINDER_OPTIONS.map((opt) => (
                    <option key={opt.label} value={opt.id === null ? '' : opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div
              className="flex items-center justify-between px-6 py-4 border-t"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              {editingEvent ? (
                <button
                  onClick={() => {
                    onDelete(editingEvent.id)
                    onClose()
                  }}
                  className="text-sm font-medium px-4 py-2 rounded-lg"
                  style={{ color: 'var(--danger)' }}
                >
                  Delete Event
                </button>
              ) : (
                <span />
              )}
              <div className="flex items-center gap-2">
                <button
                  onClick={onClose}
                  className="text-sm font-medium px-4 py-2 rounded-lg"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!title.trim()}
                  className="text-sm font-semibold px-5 py-2.5 rounded-full"
                  style={{
                    background: 'var(--primary)',
                    color: 'var(--primary-foreground)',
                    opacity: title.trim() ? 1 : 0.5,
                  }}
                >
                  {editingEvent ? 'Save Changes' : 'Create Event'}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

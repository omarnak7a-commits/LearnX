/**
 * Shared types for the Calendar Integration feature — a single source of
 * truth for scheduled events, consumed by both the Calendar page and the
 * Student Dashboard's "Upcoming Events" widget so the two are always in
 * sync (spec: "creating, editing, or deleting an event in the Calendar
 * must update Upcoming Events automatically without requiring a page
 * refresh").
 *
 * Same posture as the rest of this frontend-only build: persisted via
 * `src/lib/calendar/storage.ts` (localStorage) behind
 * `src/context/CalendarContext.tsx`, shaped so a real backend can be
 * swapped in later without touching any UI code.
 */

export type CalendarEventType =
  | 'exam'
  | 'assignment'
  | 'quiz'
  | 'study-session'
  | 'personal'
  | 'course-deadline'
  | 'meeting'
  | 'custom'

export interface CalendarEvent {
  id: string
  title: string
  description: string
  /** ISO date string, e.g. "2026-08-03". */
  date: string
  /** 24h "HH:mm", optional (all-day events omit this). */
  time: string | null
  color: string
  type: CalendarEventType
  /** Real course id from the shared course catalog, or null. */
  courseId: string | null
  /** Minutes before the event to remind the student, or null for none. */
  reminderMinutesBefore: number | null
  completed: boolean
  completedAt: number | null
  createdAt: number
  updatedAt: number
}

export interface CalendarEventInput {
  title: string
  description: string
  date: string
  time: string | null
  color: string
  type: CalendarEventType
  courseId: string | null
  reminderMinutesBefore: number | null
}

export const EVENT_TYPE_META: Record<
  CalendarEventType,
  { label: string; icon: string; defaultColor: string }
> = {
  exam: { label: 'Exam', icon: '🧾', defaultColor: '#FF7E36' },
  assignment: { label: 'Assignment', icon: '📝', defaultColor: '#2DD4BF' },
  quiz: { label: 'Quiz', icon: '❓', defaultColor: '#a855f7' },
  'study-session': { label: 'Study Session', icon: '⏱️', defaultColor: '#38bdf8' },
  personal: { label: 'Personal Reminder', icon: '🔔', defaultColor: '#f59e0b' },
  'course-deadline': { label: 'Course Deadline', icon: '📚', defaultColor: '#22c55e' },
  meeting: { label: 'Meeting', icon: '🤝', defaultColor: '#eab308' },
  custom: { label: 'Custom Event', icon: '✨', defaultColor: '#94a3b8' },
}

export const REMINDER_OPTIONS: Array<{ id: number | null; label: string }> = [
  { id: null, label: 'No reminder' },
  { id: 15, label: '15 minutes before' },
  { id: 60, label: '1 hour before' },
  { id: 1440, label: '1 day before' },
  { id: 2880, label: '2 days before' },
]

import type { CalendarEvent, CalendarEventType } from '../../types/calendar'
import { EVENT_TYPE_META } from '../../types/calendar'

interface SeedDef {
  title: string
  description: string
  type: CalendarEventType
  daysFromNow: number
  time: string | null
  courseId: string | null
  reminderMinutesBefore: number | null
}

/** Realistic starter schedule, same "seed once on first run only" posture
 *  as `src/lib/fileVault/seedLibrary.ts` — every date is computed relative
 *  to *today* (never a hardcoded calendar date) so the demo always looks
 *  current regardless of when the app is opened. */
const SEED_DEFS: SeedDef[] = [
  {
    title: 'Physics Lab Report due',
    description: 'Submit the kinematics lab write-up via the course portal.',
    type: 'assignment',
    daysFromNow: 1,
    time: '23:59',
    courseId: 'phys150',
    reminderMinutesBefore: 1440,
  },
  {
    title: 'AI Tutor session',
    description: 'Weekly check-in on weak topics flagged by the AI Study Hub.',
    type: 'study-session',
    daysFromNow: 0,
    time: '18:00',
    courseId: null,
    reminderMinutesBefore: 60,
  },
  {
    title: 'Problem Set 6 due',
    description: 'Discrete math problem set covering graph theory.',
    type: 'course-deadline',
    daysFromNow: 3,
    time: '23:59',
    courseId: 'math210',
    reminderMinutesBefore: 1440,
  },
  {
    title: 'Midterm Exam — Classical Mechanics',
    description: 'Covers chapters 1-9: kinematics through rotational dynamics.',
    type: 'exam',
    daysFromNow: 12,
    time: '10:00',
    courseId: 'phys150',
    reminderMinutesBefore: 2880,
  },
  {
    title: 'Database Systems Quiz',
    description: 'Short quiz on normalization and indexing.',
    type: 'quiz',
    daysFromNow: 5,
    time: '09:00',
    courseId: 'cs310',
    reminderMinutesBefore: 60,
  },
]

const SEED_MARKER_KEY = 'learnx-calendar-seeded-v1'

function toIsoDate(daysFromNow: number): string {
  const d = new Date()
  d.setDate(d.getDate() + daysFromNow)
  return d.toISOString().slice(0, 10)
}

function buildSeedEvent(def: SeedDef, index: number): CalendarEvent {
  const now = Date.now()
  return {
    id: `seed-event-${index}`,
    title: def.title,
    description: def.description,
    date: toIsoDate(def.daysFromNow),
    time: def.time,
    color: EVENT_TYPE_META[def.type].defaultColor,
    type: def.type,
    courseId: def.courseId,
    reminderMinutesBefore: def.reminderMinutesBefore,
    completed: false,
    completedAt: null,
    createdAt: now,
    updatedAt: now,
  }
}

/** Only seeds if the calendar is genuinely empty and hasn't been seeded
 *  this session — never overwrites real user-created events. */
export function getSeedEventsIfNeeded(existing: CalendarEvent[]): CalendarEvent[] {
  if (existing.length > 0) return []
  let alreadySeeded = false
  try {
    alreadySeeded = sessionStorage.getItem(SEED_MARKER_KEY) === '1'
  } catch {
    alreadySeeded = false
  }
  if (alreadySeeded) return []
  try {
    sessionStorage.setItem(SEED_MARKER_KEY, '1')
  } catch {
    // ignore
  }
  return SEED_DEFS.map(buildSeedEvent)
}

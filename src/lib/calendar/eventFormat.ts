import type { CalendarEvent } from '../../types/calendar'

/** Combines an event's date + optional time into a real timestamp
 *  (midnight local time if no time is set). */
export function eventTimestamp(event: CalendarEvent): number {
  const [y, m, d] = event.date.split('-').map(Number)
  if (event.time) {
    const [h, min] = event.time.split(':').map(Number)
    return new Date(y, m - 1, d, h, min).getTime()
  }
  return new Date(y, m - 1, d, 23, 59, 59).getTime()
}

/** Whole days remaining until the event (negative once it's passed). */
export function daysRemaining(event: CalendarEvent): number {
  const now = Date.now()
  const ts = eventTimestamp(event)
  return Math.ceil((ts - now) / (24 * 60 * 60 * 1000))
}

export function isUpcoming(event: CalendarEvent): boolean {
  if (event.completed) return false
  return eventTimestamp(event) >= Date.now() - 60 * 1000
}

/** Sorts by nearest upcoming first — matches the spec's "sort
 *  automatically by nearest upcoming event" requirement. */
export function sortByNearest(events: CalendarEvent[]): CalendarEvent[] {
  return [...events].sort((a, b) => eventTimestamp(a) - eventTimestamp(b))
}

export function formatDaysRemaining(days: number): string {
  if (days < 0) return 'Past due'
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  return `In ${days} days`
}

export function formatEventTime(event: CalendarEvent): string {
  if (!event.time) return 'All day'
  const [h, m] = event.time.split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 === 0 ? 12 : h % 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

export function formatEventDate(event: CalendarEvent): string {
  const [y, m, d] = event.date.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

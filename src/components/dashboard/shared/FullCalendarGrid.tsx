import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import type { CalendarEvent } from '../../../types/calendar'
import { EVENT_TYPE_META } from '../../../types/calendar'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

function isoDate(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

interface FullCalendarGridProps {
  events: CalendarEvent[]
  onSelectDate: (iso: string) => void
  onSelectEvent: (event: CalendarEvent) => void
}

/**
 * Real month-grid calendar (genuine current date, genuine prev/next
 * month navigation) for the student Calendar page — distinct from
 * `MiniCalendar` (which stays hardcoded to a fixed demo month for the
 * Dashboard's small preview widget and the Doctor Calendar, both out of
 * this feature's scope) because the spec's Feature 1 requires actually
 * creating/editing/deleting events on arbitrary real dates, not just
 * displaying a static month.
 */
export default function FullCalendarGrid({
  events,
  onSelectDate,
  onSelectEvent,
}: FullCalendarGridProps) {
  const today = new Date()
  const [viewYear, setViewYear] = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    for (const e of events) {
      const list = map.get(e.date) ?? []
      list.push(e)
      map.set(e.date, list)
    }
    return map
  }, [events])

  const firstOfMonth = new Date(viewYear, viewMonth, 1)
  const firstWeekday = firstOfMonth.getDay()
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()

  const cells: Array<{ day: number; iso: string } | null> = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => ({
      day: i + 1,
      iso: isoDate(viewYear, viewMonth, i + 1),
    })),
  ]

  const todayIso = isoDate(today.getFullYear(), today.getMonth(), today.getDate())

  function goToMonth(delta: number) {
    let m = viewMonth + delta
    let y = viewYear
    if (m < 0) {
      m = 11
      y -= 1
    } else if (m > 11) {
      m = 0
      y += 1
    }
    setViewMonth(m)
    setViewYear(y)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          {MONTH_NAMES[viewMonth]} {viewYear}
        </p>
        <div className="flex gap-1">
          <button
            onClick={() => goToMonth(-1)}
            className="w-7 h-7 rounded-md flex items-center justify-center text-xs transition-colors"
            style={{ color: 'var(--muted-foreground)' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            aria-label="Previous month"
          >
            ‹
          </button>
          <button
            onClick={() => {
              setViewMonth(today.getMonth())
              setViewYear(today.getFullYear())
            }}
            className="px-2 h-7 rounded-md flex items-center justify-center text-xs font-semibold transition-colors"
            style={{ color: 'var(--primary)' }}
          >
            Today
          </button>
          <button
            onClick={() => goToMonth(1)}
            className="w-7 h-7 rounded-md flex items-center justify-center text-xs transition-colors"
            style={{ color: 'var(--muted-foreground)' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            aria-label="Next month"
          >
            ›
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center mb-1">
        {WEEKDAYS.map((d) => (
          <span
            key={d}
            className="text-xs font-medium"
            style={{ color: 'var(--muted-foreground)', opacity: 0.7 }}
          >
            {d[0]}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell, i) => {
          if (!cell) return <div key={i} />
          const dayEvents = eventsByDate.get(cell.iso) ?? []
          const isToday = cell.iso === todayIso
          return (
            <div
              key={cell.iso}
              role="button"
              tabIndex={0}
              onClick={() => onSelectDate(cell.iso)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelectDate(cell.iso)
                }
              }}
              className="relative aspect-square flex flex-col items-center justify-start pt-1.5 gap-0.5 rounded-lg text-xs transition-colors cursor-pointer"
              style={{
                background: isToday ? 'rgba(45,212,191,0.1)' : 'transparent',
                border: isToday ? '1px solid rgba(45,212,191,0.3)' : '1px solid transparent',
                color: isToday ? 'var(--primary)' : 'var(--foreground)',
                fontWeight: isToday ? 700 : 500,
                minHeight: 56,
              }}
              onMouseEnter={(e) => {
                if (!isToday) e.currentTarget.style.background = 'var(--surface-hover)'
              }}
              onMouseLeave={(e) => {
                if (!isToday) e.currentTarget.style.background = 'transparent'
              }}
            >
              {cell.day}
              <div className="flex flex-col gap-0.5 w-full px-0.5">
                {dayEvents.slice(0, 2).map((ev) => (
                  <motion.button
                    key={ev.id}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectEvent(ev)
                    }}
                    className="w-full text-left px-1 py-0.5 rounded truncate"
                    style={{
                      background: `${ev.color}22`,
                      color: ev.color,
                      fontSize: 8.5,
                      opacity: ev.completed ? 0.5 : 1,
                      textDecoration: ev.completed ? 'line-through' : 'none',
                    }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: ev.completed ? 0.5 : 1 }}
                    title={ev.title}
                  >
                    {EVENT_TYPE_META[ev.type].icon} {ev.title}
                  </motion.button>
                ))}
                {dayEvents.length > 2 && (
                  <span
                    className="text-xs"
                    style={{ color: 'var(--muted-foreground)', fontSize: 8 }}
                  >
                    +{dayEvents.length - 2} more
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

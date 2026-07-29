import { useState } from 'react'
import { motion } from 'framer-motion'

interface CalendarEvent {
  day: number
  label: string
  color: string
}

interface MiniCalendarProps {
  month?: string
  year?: number
  events?: CalendarEvent[]
  today?: number
}

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

/** Compact month calendar with event dots, reused in both dashboards. */
export default function MiniCalendar({
  month = 'July',
  year = 2026,
  events = [],
  today = 27,
}: MiniCalendarProps) {
  const [selected, setSelected] = useState(today)
  // July 2026 starts on a Wednesday
  const firstWeekday = 3
  const daysInMonth = 31

  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  const eventsByDay = events.reduce<Record<number, CalendarEvent[]>>((acc, e) => {
    acc[e.day] = [...(acc[e.day] ?? []), e]
    return acc
  }, {})

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          {month} {year}
        </p>
        <div className="flex gap-1">
          {['‹', '›'].map((a) => (
            <button
              key={a}
              className="w-6 h-6 rounded-md flex items-center justify-center text-xs transition-colors"
              style={{ color: 'var(--muted-foreground)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-7 gap-y-2 text-center">
        {WEEKDAYS.map((d, i) => (
          <span
            key={i}
            className="text-xs font-medium"
            style={{ color: 'var(--muted-foreground)', opacity: 0.7 }}
          >
            {d}
          </span>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={i} />
          const isToday = day === today
          const isSelected = day === selected
          const dayEvents = eventsByDay[day]
          return (
            <button
              key={i}
              onClick={() => setSelected(day)}
              className="relative aspect-square flex flex-col items-center justify-center rounded-lg text-xs mx-auto transition-all"
              style={{
                width: 28,
                height: 28,
                background: isSelected
                  ? 'var(--primary)'
                  : isToday
                    ? 'rgba(45,212,191,0.12)'
                    : 'transparent',
                color: isSelected
                  ? 'var(--primary-foreground)'
                  : isToday
                    ? 'var(--primary)'
                    : 'var(--foreground)',
                fontWeight: isToday || isSelected ? 700 : 500,
              }}
            >
              {day}
              {dayEvents && (
                <span className="absolute -bottom-1.5 flex gap-0.5">
                  {dayEvents.slice(0, 3).map((e, ei) => (
                    <motion.span
                      key={ei}
                      className="w-1 h-1 rounded-full"
                      style={{
                        background: isSelected ? 'var(--primary-foreground)' : e.color,
                      }}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.3 + ei * 0.05 }}
                    />
                  ))}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {eventsByDay[selected] && (
        <div
          className="mt-5 space-y-2 pt-4 border-t"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          {eventsByDay[selected].map((e, i) => (
            <div key={i} className="flex items-center gap-2.5 text-xs">
              <span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ background: e.color }}
              />
              <span style={{ color: 'var(--foreground)' }}>{e.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

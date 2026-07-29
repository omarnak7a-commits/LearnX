import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { CalendarEvent, CalendarEventInput } from '../types/calendar'
import { loadEvents, saveEvents } from '../lib/calendar/storage'
import { getSeedEventsIfNeeded } from '../lib/calendar/seedEvents'

interface CalendarContextValue {
  events: CalendarEvent[]
  loading: boolean
  createEvent: (input: CalendarEventInput) => CalendarEvent
  updateEvent: (id: string, input: Partial<CalendarEventInput>) => void
  deleteEvent: (id: string) => void
  toggleCompleted: (id: string) => void
  getEvent: (id: string) => CalendarEvent | undefined
}

const CalendarContext = createContext<CalendarContextValue | null>(null)

let eventCounter = 0

/**
 * Single source of truth for Calendar Events — both the Calendar page
 * and the Student Dashboard's Upcoming Events widget read from this same
 * context, so any create/edit/delete/complete is reflected everywhere
 * instantly via normal React re-render (no page refresh, no separate
 * data copies to keep in sync — this *is* the sync mechanism the spec's
 * FEATURE 1 asks for).
 */
export function CalendarProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const existing = loadEvents()
    const seeded = getSeedEventsIfNeeded(existing)
    const initial = seeded.length > 0 ? seeded : existing
    setEvents(initial)
    if (seeded.length > 0) saveEvents(initial)
    setLoading(false)
  }, [])

  const createEvent = useCallback((input: CalendarEventInput): CalendarEvent => {
    eventCounter += 1
    const now = Date.now()
    const event: CalendarEvent = {
      id: `event-${now}-${eventCounter}`,
      ...input,
      completed: false,
      completedAt: null,
      createdAt: now,
      updatedAt: now,
    }
    setEvents((prev) => {
      const next = [...prev, event]
      saveEvents(next)
      return next
    })
    return event
  }, [])

  const updateEvent = useCallback((id: string, input: Partial<CalendarEventInput>) => {
    setEvents((prev) => {
      const next = prev.map((e) => (e.id === id ? { ...e, ...input, updatedAt: Date.now() } : e))
      saveEvents(next)
      return next
    })
  }, [])

  const deleteEvent = useCallback((id: string) => {
    setEvents((prev) => {
      const next = prev.filter((e) => e.id !== id)
      saveEvents(next)
      return next
    })
  }, [])

  const toggleCompleted = useCallback((id: string) => {
    setEvents((prev) => {
      const next = prev.map((e) =>
        e.id === id
          ? {
              ...e,
              completed: !e.completed,
              completedAt: !e.completed ? Date.now() : null,
              updatedAt: Date.now(),
            }
          : e
      )
      saveEvents(next)
      return next
    })
  }, [])

  const getEvent = useCallback((id: string) => events.find((e) => e.id === id), [events])

  const value = useMemo<CalendarContextValue>(
    () => ({ events, loading, createEvent, updateEvent, deleteEvent, toggleCompleted, getEvent }),
    [events, loading, createEvent, updateEvent, deleteEvent, toggleCompleted, getEvent]
  )

  return <CalendarContext.Provider value={value}>{children}</CalendarContext.Provider>
}

export function useCalendar() {
  const ctx = useContext(CalendarContext)
  if (!ctx) throw new Error('useCalendar must be used within a CalendarProvider')
  return ctx
}

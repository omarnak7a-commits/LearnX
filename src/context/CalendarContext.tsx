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
import { calendarApi, apiEventToFrontend } from '../lib/calendar/apiClient'

interface CalendarContextValue {
  events: CalendarEvent[]
  loading: boolean
  apiError: string | null
  createEvent: (input: CalendarEventInput) => Promise<CalendarEvent>
  updateEvent: (id: string, input: Partial<CalendarEventInput>) => Promise<void>
  deleteEvent: (id: string) => Promise<void>
  toggleCompleted: (id: string) => Promise<void>
  getEvent: (id: string) => CalendarEvent | undefined
}

const CalendarContext = createContext<CalendarContextValue | null>(null)

/**
 * Single source of truth for Calendar Events — backed by the real
 * `/api/v1/calendar` API (no localStorage seeding). Both the Calendar
 * page and the Student Dashboard's Upcoming Events widget read from this
 * context, so any create/edit/delete/complete is reflected everywhere
 * instantly.
 */
export function CalendarProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await calendarApi.list()
        if (cancelled) return
        setEvents(list.map(apiEventToFrontend))
        setApiError(null)
      } catch (err) {
        if (cancelled) return
        setApiError(err instanceof Error ? err.message : 'Failed to load calendar')
        setEvents([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const createEvent = useCallback(async (input: CalendarEventInput): Promise<CalendarEvent> => {
    const api = await calendarApi.create(input)
    const event = apiEventToFrontend(api)
    setEvents((prev) => [...prev, event])
    return event
  }, [])

  const updateEvent = useCallback(async (id: string, input: Partial<CalendarEventInput>) => {
    const api = await calendarApi.update(id, input)
    const updated = apiEventToFrontend(api)
    setEvents((prev) => prev.map((e) => (e.id === id ? updated : e)))
  }, [])

  const deleteEvent = useCallback(async (id: string) => {
    await calendarApi.remove(id)
    setEvents((prev) => prev.filter((e) => e.id !== id))
  }, [])

  const toggleCompleted = useCallback(
    async (id: string) => {
      const current = events.find((e) => e.id === id)
      if (!current) return
      try {
        const api = await calendarApi.update(id, { completed: !current.completed })
        const updated = apiEventToFrontend(api)
        setEvents((prev) => prev.map((e) => (e.id === id ? updated : e)))
      } catch {
        // leave state unchanged on failure
      }
    },
    [events],
  )

  const getEvent = useCallback((id: string) => events.find((e) => e.id === id), [events])

  const value = useMemo<CalendarContextValue>(
    () => ({
      events,
      loading,
      apiError,
      createEvent,
      updateEvent,
      deleteEvent,
      toggleCompleted,
      getEvent,
    }),
    [events, loading, apiError, createEvent, updateEvent, deleteEvent, toggleCompleted, getEvent],
  )

  return <CalendarContext.Provider value={value}>{children}</CalendarContext.Provider>
}

export function useCalendar() {
  const ctx = useContext(CalendarContext)
  if (!ctx) throw new Error('useCalendar must be used within a CalendarProvider')
  return ctx
}

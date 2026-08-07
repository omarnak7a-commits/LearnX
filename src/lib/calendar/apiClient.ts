/**
 * Calendar API client — real CRUD for calendar events.
 */

import { apiFetch } from '../apiClient'
import type { CalendarEvent, CalendarEventInput } from '../../types/calendar'

export interface ApiCalendarEvent {
  id: string
  title: string
  description: string
  date: string
  time: string | null
  color: string
  type: CalendarEvent['type']
  courseId: string | null
  reminderMinutesBefore: number | null
  completed: boolean
  completedAt: number | null
  createdAt: number
  updatedAt: number
}

export function apiEventToFrontend(e: ApiCalendarEvent): CalendarEvent {
  return {
    id: e.id,
    title: e.title,
    description: e.description,
    date: e.date,
    time: e.time,
    color: e.color,
    type: e.type,
    courseId: e.courseId,
    reminderMinutesBefore: e.reminderMinutesBefore,
    completed: e.completed,
    completedAt: e.completedAt,
    createdAt: e.createdAt,
    updatedAt: e.updatedAt,
  }
}

export const calendarApi = {
  list: () => apiFetch<ApiCalendarEvent[]>('/api/v1/calendar'),

  create: (input: CalendarEventInput) =>
    apiFetch<ApiCalendarEvent>('/api/v1/calendar', { method: 'POST', body: input }),

  update: (id: string, input: Partial<CalendarEventInput> & { completed?: boolean }) =>
    apiFetch<ApiCalendarEvent>(`/api/v1/calendar/${id}`, { method: 'PATCH', body: input }),

  remove: (id: string) => apiFetch<void>(`/api/v1/calendar/${id}`, { method: 'DELETE' }),
}

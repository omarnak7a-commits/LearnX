import type { CalendarEvent } from '../../types/calendar'

/**
 * localStorage persistence for Calendar Events — same posture as
 * `src/lib/profile/storage.ts` / `src/lib/fileVault/storage.ts` (small
 * load/save interface, swappable for a real backend later without
 * touching any UI).
 */

const STORAGE_KEY = 'learnx-calendar-events-v1'

export function loadEvents(): CalendarEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveEvents(events: CalendarEvent[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events))
  } catch {
    // Storage unavailable — events just won't persist this session.
  }
}

/**
 * NotificationsContext — real notification feed from the backend
 * (`/api/v1/notifications`). Consumed by the dashboard UI to show the
 * student's announcements, reminders and unread count.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  notificationsApi,
  type ApiNotification,
} from '../lib/notifications/apiClient'

export interface Notification {
  id: string
  kind: string
  title: string
  body: string
  icon: string
  link: string | null
  read: boolean
  createdAt: number
}

interface NotificationsContextValue {
  notifications: Notification[]
  unreadCount: number
  loading: boolean
  apiError: string | null
  reload: () => Promise<void>
  markRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null)

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      const [list, unread] = await Promise.all([
        notificationsApi.list(),
        notificationsApi.unreadCount(),
      ])
      setNotifications(list)
      setUnreadCount(unread.count)
      setApiError(null)
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Failed to load notifications')
      setNotifications([])
      setUnreadCount(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const markRead = useCallback(
    async (id: string) => {
      try {
        await notificationsApi.markRead(id)
      } catch {
        // optimistic state still applied below
      }
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n)),
      )
      setUnreadCount((c) => Math.max(0, c - 1))
    },
    [],
  )

  const markAllRead = useCallback(async () => {
    try {
      await notificationsApi.markAllRead()
    } catch {
      // optimistic state still applied below
    }
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    setUnreadCount(0)
  }, [])

  const value = useMemo<NotificationsContextValue>(
    () => ({ notifications, unreadCount, loading, apiError, reload, markRead, markAllRead }),
    [notifications, unreadCount, loading, apiError, reload, markRead, markAllRead],
  )

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}

export function useNotifications(): NotificationsContextValue {
  const ctx = useContext(NotificationsContext)
  if (!ctx) throw new Error('useNotifications must be used within a NotificationsProvider')
  return ctx
}

export type { ApiNotification }

/**
 * Notifications API client — real notification feed.
 */

import { apiFetch } from '../apiClient'

export interface ApiNotification {
  id: string
  kind: string
  title: string
  body: string
  icon: string
  link: string | null
  read: boolean
  createdAt: number
}

export const notificationsApi = {
  list: () => apiFetch<ApiNotification[]>('/api/v1/notifications'),

  unreadCount: () => apiFetch<{ count: number }>('/api/v1/notifications/unread-count'),

  markRead: (id: string) =>
    apiFetch<{ ok: boolean }>(`/api/v1/notifications/${id}/read`, { method: 'POST' }),

  markAllRead: () => apiFetch<{ ok: boolean }>('/api/v1/notifications/read-all', { method: 'POST' }),
}

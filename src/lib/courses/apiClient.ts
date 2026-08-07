/**
 * Courses API client — the real Course & Roster engine client.
 * Maps backend `CourseOut` (snake_case) onto the frontend `Course` type.
 */

import { apiFetch } from '../apiClient'
import type {
  Course,
  CourseAnalytics,
  CourseStatus,
  CourseType,
  Lesson,
  LessonType,
  Module,
} from '../../types/course'

export interface ApiLesson {
  id: string
  title: string
  type: LessonType
  durationMinutes?: number | null
  completed: boolean
  resources: Array<{ name: string; kind: string; sizeLabel: string }>
}

export interface ApiModule {
  id: string
  title: string
  lessons: ApiLesson[]
}

export interface ApiCourse {
  id: string
  title: string
  description: string
  category: string
  faculty: string
  department: string
  academicLevel: string
  courseType: CourseType
  status: CourseStatus
  color: string
  icon: string
  priceUsd: number | null
  allowXpRedemption: boolean
  xpPrice: number | null
  doctorName: string
  doctorInitials: string
  rating: number
  studentsCount: number
  completionRate: number
  createdAt: string
  lastUpdated: string
  modules: ApiModule[]
  enrolled: boolean
  saved: boolean
  progressPct: number
  completedLessonIds: string[]
  purchasedViaReward: boolean
}

function emptyAnalytics(): CourseAnalytics {
  return {
    totalStudents: 0,
    activeStudents: 0,
    completionRate: 0,
    avgWatchTimeMinutes: 0,
    mostViewedLessonTitle: '—',
    dropOffLessonTitle: '—',
    quizAvgScore: 0,
    strugglingTopic: '—',
    strugglingPct: 0,
    aiInsights: [],
  }
}

function fmtDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

export function apiCourseToFrontend(api: ApiCourse): Course {
  const modules: Module[] = api.modules.map((m) => ({
    id: m.id,
    title: m.title,
    lessons: m.lessons.map((l): Lesson => ({
      id: l.id,
      title: l.title,
      type: l.type,
      durationMinutes: l.durationMinutes ?? undefined,
      completed: l.completed,
      resources: l.resources.map((r) => ({
        id: `${l.id}-${r.name}`,
        name: r.name,
        kind: r.kind as Lesson['resources'][number]['kind'],
        sizeLabel: r.sizeLabel,
      })),
    })),
  }))

  const total = modules.reduce((s, m) => s + m.lessons.length, 0)
  const done = modules.reduce((s, m) => s + m.lessons.filter((l) => l.completed).length, 0)
  const completedSet = new Set(api.completedLessonIds ?? [])
  const firstIncomplete = modules
    .flatMap((m) => m.lessons)
    .find((l) => !completedSet.has(l.id))

  return {
    id: api.id,
    title: api.title,
    description: api.description,
    category: api.category,
    faculty: api.faculty,
    department: api.department,
    academicLevel: api.academicLevel,
    courseType: api.courseType,
    status: api.status,
    color: api.color,
    icon: api.icon,
    doctorName: api.doctorName,
    doctorInitials: api.doctorInitials,
    rating: api.rating,
    studentsCount: api.studentsCount,
    completionRate: api.completionRate,
    lastUpdated: api.lastUpdated ? fmtDate(api.lastUpdated) : '',
    createdAt: api.createdAt ? fmtDate(api.createdAt) : '',
    modules,
    analytics: {
      ...emptyAnalytics(),
      totalStudents: api.studentsCount,
      completionRate: api.completionRate,
    },
    enrolled: api.enrolled,
    saved: api.saved,
    progressPct: api.progressPct,
    lastLessonTitle: firstIncomplete?.title ?? null,
    lastViewedAt: null,
    completedAt: null,
    priceUsd: api.priceUsd,
    allowXpRedemption: api.allowXpRedemption,
    xpPrice: api.xpPrice,
    purchasedViaReward: api.purchasedViaReward,
    // progressPct already computed; done/total kept consistent
    ...(total > 0 ? { progressPct: Math.round((done / total) * 100) } : {}),
  }
}

export const coursesApi = {
  list: (scope: 'catalog' | 'mine' = 'catalog') =>
    apiFetch<ApiCourse[]>(`/api/v1/courses?scope=${scope}`),

  get: (id: string) => apiFetch<ApiCourse>(`/api/v1/courses/${id}`),

  create: (input: Record<string, unknown>) =>
    apiFetch<ApiCourse>('/api/v1/courses', { method: 'POST', body: input }),

  update: (id: string, input: Record<string, unknown>) =>
    apiFetch<ApiCourse>(`/api/v1/courses/${id}`, { method: 'PATCH', body: input }),

  remove: (id: string) => apiFetch<void>(`/api/v1/courses/${id}`, { method: 'DELETE' }),

  addModule: (courseId: string, title: string) =>
    apiFetch<ApiModule>(`/api/v1/courses/${courseId}/modules`, {
      method: 'POST',
      body: { title },
    }),

  addLesson: (
    courseId: string,
    moduleId: string,
    title: string,
    type: LessonType,
    resources: ApiLesson['resources'] = [],
  ) =>
    apiFetch<{ id: string }>(`/api/v1/courses/${courseId}/modules/${moduleId}/lessons`, {
      method: 'POST',
      body: { title, type, resources },
    }),

  renameModule: (moduleId: string, title: string) =>
    apiFetch(`/api/v1/courses/modules/${moduleId}`, { method: 'PATCH', body: { title } }),

  renameLesson: (lessonId: string, title: string) =>
    apiFetch(`/api/v1/courses/lessons/${lessonId}`, { method: 'PATCH', body: { title } }),

  deleteModule: (moduleId: string) =>
    apiFetch(`/api/v1/courses/modules/${moduleId}`, { method: 'DELETE' }),

  deleteLesson: (lessonId: string) =>
    apiFetch(`/api/v1/courses/lessons/${lessonId}`, { method: 'DELETE' }),

  reorderModules: (courseId: string, moduleIds: string[]) =>
    apiFetch(`/api/v1/courses/${courseId}/reorder-modules`, {
      method: 'POST',
      body: { moduleIds },
    }),

  reorderLessons: (moduleId: string, lessonIds: string[]) =>
    apiFetch(`/api/v1/courses/modules/${moduleId}/reorder-lessons`, {
      method: 'POST',
      body: { lessonIds },
    }),

  enroll: (id: string, purchasedViaReward = false) =>
    apiFetch(`/api/v1/courses/${id}/enroll`, {
      method: 'POST',
      body: { purchasedViaReward },
    }),

  toggleSaved: (id: string) =>
    apiFetch<{ saved: boolean }>(`/api/v1/courses/${id}/save`, { method: 'POST' }),

  completeLesson: (courseId: string, lessonId: string, completed = true) =>
    apiFetch<{ lessonId: string; completed: boolean; progressPct: number }>(
      `/api/v1/courses/${courseId}/lessons/${lessonId}/complete`,
      { method: 'POST', body: { completed } },
    ),

  roster: () => apiFetch<Array<Record<string, unknown>>>('/api/v1/courses/roster/students'),
}

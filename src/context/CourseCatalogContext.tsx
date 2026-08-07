import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Course, CourseStatus, CourseType, Lesson, LessonType, Module } from '../types/course'
import { coursesApi, apiCourseToFrontend, type ApiCourse } from '../lib/courses/apiClient'

interface NewCourseInput {
  title: string
  description: string
  category: string
  faculty: string
  department: string
  academicLevel: string
  courseType: CourseType
  priceUsd: number | null
  allowXpRedemption: boolean
  xpPrice: number | null
}

interface CourseCatalogValue {
  courses: Course[]
  /** Network/API error surfaced for the UI. */
  apiError: string | null
  loading: boolean
  reload: () => Promise<void>
  getCourse: (id: string) => Course | undefined
  createCourse: (input: NewCourseInput) => Promise<Course>
  updateCourseInfo: (id: string, input: Partial<NewCourseInput>) => Promise<void>
  setStatus: (id: string, status: CourseStatus) => Promise<void>
  publishCourse: (id: string) => Promise<void>
  archiveCourse: (id: string) => Promise<void>
  submitForReview: (id: string) => Promise<void>
  revertToDraft: (id: string) => Promise<void>
  addModule: (courseId: string, title: string) => Promise<void>
  addLesson: (courseId: string, moduleId: string, title: string, type: LessonType) => Promise<void>
  updateModuleTitle: (courseId: string, moduleId: string, title: string) => Promise<void>
  updateLessonTitle: (courseId: string, moduleId: string, lessonId: string, title: string) => Promise<void>
  deleteLesson: (courseId: string, moduleId: string, lessonId: string) => Promise<void>
  deleteModule: (courseId: string, moduleId: string) => Promise<void>
  reorderModules: (courseId: string, modules: Module[]) => Promise<void>
  reorderLessons: (courseId: string, moduleId: string, lessons: Lesson[]) => Promise<void>
  toggleEnroll: (id: string) => Promise<void>
  toggleSaved: (id: string) => Promise<void>
  markLessonComplete: (courseId: string, lessonId: string) => Promise<void>
  /** Marks a premium course as purchased via the Reward Store (XP or
   *  XP+money redemption) — distinct from `toggleEnroll`. */
  markPurchasedViaReward: (id: string) => Promise<void>
}

const CourseCatalogContext = createContext<CourseCatalogValue | null>(null)

/**
 * Course Catalog — backed by the real `/api/v1/courses` engine (no mock
 * seeding). Loads the published catalog (students) or the doctor's own
 * courses (`scope=mine`); every mutation is a real API call, applied
 * optimistically and rolled back on failure.
 */
export function CourseCatalogProvider({ children }: { children: ReactNode }) {
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setApiError(null)
    try {
      // Students see the published catalog; doctors additionally see their
      // own courses (drafts included). A 403 on `mine` just means student.
      const [catalog, mine] = await Promise.all([
        coursesApi.list('catalog').catch(() => []),
        coursesApi.list('mine').catch(() => []),
      ])
      const merged = new Map<string, ApiCourse>()
      for (const c of [...mine, ...catalog]) merged.set(c.id, c)
      setCourses([...merged.values()].map(apiCourseToFrontend))
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Failed to load courses')
      setCourses([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const apply = useCallback((updater: (prev: Course[]) => Course[]) => {
    setCourses(updater)
  }, [])

  const upsert = useCallback((api: ApiCourse) => {
    const course = apiCourseToFrontend(api)
    apply((prev) => {
      const exists = prev.some((c) => c.id === course.id)
      return exists ? prev.map((c) => (c.id === course.id ? course : c)) : [course, ...prev]
    })
    return course
  }, [apply])

  const getCourse = useCallback((id: string) => courses.find((c) => c.id === id), [courses])

  const createCourse = useCallback(
    async (input: NewCourseInput): Promise<Course> => {
      const api = await coursesApi.create({ ...input })
      return upsert(api)
    },
    [upsert],
  )

  const updateCourseInfo = useCallback(
    async (id: string, input: Partial<NewCourseInput>) => {
      const api = await coursesApi.update(id, input)
      upsert(api)
    },
    [upsert],
  )

  const setStatus = useCallback(
    async (id: string, status: CourseStatus) => {
      const api = await coursesApi.update(id, { status })
      upsert(api)
    },
    [upsert],
  )

  const publishCourse = useCallback((id: string) => setStatus(id, 'published'), [setStatus])
  const archiveCourse = useCallback((id: string) => setStatus(id, 'archived'), [setStatus])
  const submitForReview = useCallback((id: string) => setStatus(id, 'pending-review'), [setStatus])
  const revertToDraft = useCallback((id: string) => setStatus(id, 'draft'), [setStatus])

  const addModule = useCallback(
    async (courseId: string, title: string) => {
      const module = await coursesApi.addModule(courseId, title)
      apply((prev) =>
        prev.map((c) => (c.id !== courseId ? c : { ...c, modules: [...c.modules, { id: module.id, title: module.title, lessons: [] }] })),
      )
    },
    [apply],
  )

  const addLesson = useCallback(
    async (courseId: string, moduleId: string, title: string, type: LessonType) => {
      await coursesApi.addLesson(courseId, moduleId, title, type)
      await reload()
    },
    [reload],
  )

  const updateModuleTitle = useCallback(
    async (courseId: string, moduleId: string, title: string) => {
      await coursesApi.renameModule(moduleId, title)
      apply((prev) =>
        prev.map((c) =>
          c.id !== courseId
            ? c
            : { ...c, modules: c.modules.map((m) => (m.id === moduleId ? { ...m, title } : m)) },
        ),
      )
    },
    [apply],
  )

  const updateLessonTitle = useCallback(
    async (courseId: string, moduleId: string, lessonId: string, title: string) => {
      await coursesApi.renameLesson(lessonId, title)
      apply((prev) =>
        prev.map((c) =>
          c.id !== courseId
            ? c
            : {
                ...c,
                modules: c.modules.map((m) =>
                  m.id !== moduleId
                    ? m
                    : { ...m, lessons: m.lessons.map((l) => (l.id === lessonId ? { ...l, title } : l)) },
                ),
              },
        ),
      )
    },
    [apply],
  )

  const deleteLesson = useCallback(
    async (courseId: string, moduleId: string, lessonId: string) => {
      await coursesApi.deleteLesson(lessonId)
      apply((prev) =>
        prev.map((c) =>
          c.id !== courseId
            ? c
            : { ...c, modules: c.modules.map((m) => (m.id !== moduleId ? m : { ...m, lessons: m.lessons.filter((l) => l.id !== lessonId) })) },
        ),
      )
    },
    [apply],
  )

  const deleteModule = useCallback(
    async (courseId: string, moduleId: string) => {
      await coursesApi.deleteModule(moduleId)
      apply((prev) =>
        prev.map((c) =>
          c.id !== courseId ? c : { ...c, modules: c.modules.filter((m) => m.id !== moduleId) },
        ),
      )
    },
    [apply],
  )

  const reorderModules = useCallback(
    async (courseId: string, modules: Module[]) => {
      await coursesApi.reorderModules(courseId, modules.map((m) => m.id))
      apply((prev) => prev.map((c) => (c.id === courseId ? { ...c, modules } : c)))
    },
    [apply],
  )

  const reorderLessons = useCallback(
    async (courseId: string, moduleId: string, lessons: Lesson[]) => {
      await coursesApi.reorderLessons(moduleId, lessons.map((l) => l.id))
      apply((prev) =>
        prev.map((c) =>
          c.id !== courseId
            ? c
            : { ...c, modules: c.modules.map((m) => (m.id === moduleId ? { ...m, lessons } : m)) },
        ),
      )
    },
    [apply],
  )

  const toggleEnroll = useCallback(
    async (id: string) => {
      const target = courses.find((c) => c.id === id)
      if (!target) return
      try {
        const resp = await coursesApi.enroll(id)
        apply((prev) =>
          prev.map((c) =>
            c.id === id
              ? { ...c, enrolled: resp.enrolled, progressPct: resp.progressPct ?? 0 }
              : c,
          ),
        )
      } catch {
        // leave state unchanged on failure
      }
    },
    [courses, apply],
  )

  const toggleSaved = useCallback(
    async (id: string) => {
      try {
        const resp = await coursesApi.toggleSaved(id)
        apply((prev) => prev.map((c) => (c.id === id ? { ...c, saved: resp.saved } : c)))
      } catch {
        // leave state unchanged on failure
      }
    },
    [apply],
  )

  const markLessonComplete = useCallback(
    async (courseId: string, lessonId: string) => {
      try {
        const resp = await coursesApi.completeLesson(courseId, lessonId, true)
        apply((prev) =>
          prev.map((c) => {
            if (c.id !== courseId) return c
            const modules = c.modules.map((m) => ({
              ...m,
              lessons: m.lessons.map((l) =>
                l.id === lessonId ? { ...l, completed: resp.completed } : l,
              ),
            }))
            const lesson = modules.flatMap((m) => m.lessons).find((l) => l.id === lessonId)
            return {
              ...c,
              modules,
              progressPct: resp.progressPct,
              lastLessonTitle: lesson?.title ?? c.lastLessonTitle,
              lastViewedAt: 'Just now',
            }
          }),
        )
      } catch {
        // leave state unchanged on failure
      }
    },
    [apply],
  )

  const markPurchasedViaReward = useCallback(
    async (id: string) => {
      try {
        await coursesApi.enroll(id, true)
        apply((prev) =>
          prev.map((c) =>
            c.id === id
              ? { ...c, enrolled: true, purchasedViaReward: true, studentsCount: c.studentsCount + 1 }
              : c,
          ),
        )
      } catch {
        // leave state unchanged on failure
      }
    },
    [apply],
  )

  const value = useMemo<CourseCatalogValue>(
    () => ({
      courses,
      apiError,
      loading,
      reload,
      getCourse,
      createCourse,
      updateCourseInfo,
      setStatus,
      publishCourse,
      archiveCourse,
      submitForReview,
      revertToDraft,
      addModule,
      addLesson,
      updateModuleTitle,
      updateLessonTitle,
      deleteLesson,
      deleteModule,
      reorderModules,
      reorderLessons,
      toggleEnroll,
      toggleSaved,
      markLessonComplete,
      markPurchasedViaReward,
    }),
    [
      courses,
      apiError,
      loading,
      reload,
      getCourse,
      createCourse,
      updateCourseInfo,
      setStatus,
      publishCourse,
      archiveCourse,
      submitForReview,
      revertToDraft,
      addModule,
      addLesson,
      updateModuleTitle,
      updateLessonTitle,
      deleteLesson,
      deleteModule,
      reorderModules,
      reorderLessons,
      toggleEnroll,
      toggleSaved,
      markLessonComplete,
      markPurchasedViaReward,
    ],
  )

  return <CourseCatalogContext.Provider value={value}>{children}</CourseCatalogContext.Provider>
}

export function useCourseCatalog() {
  const ctx = useContext(CourseCatalogContext)
  if (!ctx) throw new Error('useCourseCatalog must be used within a CourseCatalogProvider')
  return ctx
}

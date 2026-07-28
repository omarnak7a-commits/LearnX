import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Course, CourseStatus, CourseType, Lesson, LessonType, Module } from '../types/course'
import { initialCourses } from '../data/coursesMock'

interface NewCourseInput {
  title: string
  description: string
  category: string
  faculty: string
  department: string
  academicLevel: string
  courseType: CourseType
}

interface CourseCatalogValue {
  courses: Course[]
  getCourse: (id: string) => Course | undefined
  createCourse: (input: NewCourseInput) => Course
  updateCourseInfo: (id: string, input: Partial<NewCourseInput>) => void
  setStatus: (id: string, status: CourseStatus) => void
  publishCourse: (id: string) => void
  archiveCourse: (id: string) => void
  submitForReview: (id: string) => void
  revertToDraft: (id: string) => void
  addModule: (courseId: string, title: string) => void
  addLesson: (courseId: string, moduleId: string, title: string, type: LessonType) => void
  updateModuleTitle: (courseId: string, moduleId: string, title: string) => void
  updateLessonTitle: (courseId: string, moduleId: string, lessonId: string, title: string) => void
  deleteLesson: (courseId: string, moduleId: string, lessonId: string) => void
  deleteModule: (courseId: string, moduleId: string) => void
  reorderModules: (courseId: string, modules: Module[]) => void
  reorderLessons: (courseId: string, moduleId: string, lessons: Lesson[]) => void
  toggleEnroll: (id: string) => void
  toggleSaved: (id: string) => void
  markLessonComplete: (courseId: string, lessonId: string) => void
}

const CourseCatalogContext = createContext<CourseCatalogValue | null>(null)

const ICONS_BY_CATEGORY: Record<string, string> = {
  'Computer Science': '💻',
  Mathematics: '📐',
  Physics: '⚛️',
  Chemistry: '🧪',
  Biology: '🧬',
  Business: '📈',
  Design: '🎨',
}

const COLORS = ['#2DD4BF', '#a855f7', '#f59e0b', '#38bdf8', '#22c55e', '#FF7E36']

let courseCounter = 0

export function CourseCatalogProvider({ children }: { children: ReactNode }) {
  const [courses, setCourses] = useState<Course[]>(initialCourses)

  const getCourse = useCallback((id: string) => courses.find((c) => c.id === id), [courses])

  const createCourse = useCallback((input: NewCourseInput): Course => {
    courseCounter += 1
    const newCourse: Course = {
      id: `draft-${Date.now()}-${courseCounter}`,
      title: input.title || 'Untitled Course',
      description: input.description,
      category: input.category,
      faculty: input.faculty,
      department: input.department,
      academicLevel: input.academicLevel,
      courseType: input.courseType,
      status: 'draft',
      color: COLORS[courseCounter % COLORS.length],
      icon: ICONS_BY_CATEGORY[input.category] ?? '📘',
      doctorName: 'Dr. Sarah Novak',
      doctorInitials: 'SN',
      rating: 0,
      studentsCount: 0,
      completionRate: 0,
      lastUpdated: 'Just now',
      createdAt: 'Jul 2026',
      enrolled: false,
      saved: false,
      progressPct: 0,
      lastLessonTitle: null,
      lastViewedAt: null,
      completedAt: null,
      modules: [],
      analytics: {
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
      },
    }
    setCourses((prev) => [newCourse, ...prev])
    return newCourse
  }, [])

  const updateCourseInfo = useCallback((id: string, input: Partial<NewCourseInput>) => {
    setCourses((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...input, lastUpdated: 'Just now' } : c))
    )
  }, [])

  const setStatus = useCallback((id: string, status: CourseStatus) => {
    setCourses((prev) =>
      prev.map((c) => (c.id === id ? { ...c, status, lastUpdated: 'Just now' } : c))
    )
  }, [])

  const publishCourse = useCallback((id: string) => setStatus(id, 'published'), [setStatus])
  const archiveCourse = useCallback((id: string) => setStatus(id, 'archived'), [setStatus])
  const submitForReview = useCallback((id: string) => setStatus(id, 'pending-review'), [setStatus])
  const revertToDraft = useCallback((id: string) => setStatus(id, 'draft'), [setStatus])

  const addModule = useCallback((courseId: string, title: string) => {
    setCourses((prev) =>
      prev.map((c) => {
        if (c.id !== courseId) return c
        const newModule: Module = {
          id: `${courseId}-mod-${Date.now()}`,
          title: title || `Module ${c.modules.length + 1}`,
          lessons: [],
        }
        return { ...c, modules: [...c.modules, newModule], lastUpdated: 'Just now' }
      })
    )
  }, [])

  const addLesson = useCallback(
    (courseId: string, moduleId: string, title: string, type: LessonType) => {
      setCourses((prev) =>
        prev.map((c) => {
          if (c.id !== courseId) return c
          return {
            ...c,
            lastUpdated: 'Just now',
            modules: c.modules.map((m) => {
              if (m.id !== moduleId) return m
              const newLesson: Lesson = {
                id: `${moduleId}-lsn-${Date.now()}`,
                title: title || `Lesson ${m.lessons.length + 1}`,
                type,
                durationMinutes: type === 'video' ? 15 : undefined,
                completed: false,
                resources: [],
              }
              return { ...m, lessons: [...m.lessons, newLesson] }
            }),
          }
        })
      )
    },
    []
  )

  const deleteLesson = useCallback((courseId: string, moduleId: string, lessonId: string) => {
    setCourses((prev) =>
      prev.map((c) => {
        if (c.id !== courseId) return c
        return {
          ...c,
          lastUpdated: 'Just now',
          modules: c.modules.map((m) =>
            m.id !== moduleId ? m : { ...m, lessons: m.lessons.filter((l) => l.id !== lessonId) }
          ),
        }
      })
    )
  }, [])

  const updateModuleTitle = useCallback((courseId: string, moduleId: string, title: string) => {
    setCourses((prev) =>
      prev.map((c) => {
        if (c.id !== courseId) return c
        return {
          ...c,
          lastUpdated: 'Just now',
          modules: c.modules.map((m) => (m.id === moduleId ? { ...m, title } : m)),
        }
      })
    )
  }, [])

  const updateLessonTitle = useCallback(
    (courseId: string, moduleId: string, lessonId: string, title: string) => {
      setCourses((prev) =>
        prev.map((c) => {
          if (c.id !== courseId) return c
          return {
            ...c,
            lastUpdated: 'Just now',
            modules: c.modules.map((m) =>
              m.id !== moduleId
                ? m
                : {
                    ...m,
                    lessons: m.lessons.map((l) => (l.id === lessonId ? { ...l, title } : l)),
                  }
            ),
          }
        })
      )
    },
    []
  )

  const deleteModule = useCallback((courseId: string, moduleId: string) => {
    setCourses((prev) =>
      prev.map((c) =>
        c.id !== courseId
          ? c
          : { ...c, lastUpdated: 'Just now', modules: c.modules.filter((m) => m.id !== moduleId) }
      )
    )
  }, [])

  const reorderModules = useCallback((courseId: string, modules: Module[]) => {
    setCourses((prev) => prev.map((c) => (c.id === courseId ? { ...c, modules } : c)))
  }, [])

  const reorderLessons = useCallback((courseId: string, moduleId: string, lessons: Lesson[]) => {
    setCourses((prev) =>
      prev.map((c) =>
        c.id !== courseId
          ? c
          : { ...c, modules: c.modules.map((m) => (m.id === moduleId ? { ...m, lessons } : m)) }
      )
    )
  }, [])

  const toggleEnroll = useCallback((id: string) => {
    setCourses((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              enrolled: !c.enrolled,
              lastViewedAt: !c.enrolled ? 'Just now' : c.lastViewedAt,
              lastLessonTitle: !c.enrolled
                ? (c.modules[0]?.lessons[0]?.title ?? null)
                : c.lastLessonTitle,
            }
          : c
      )
    )
  }, [])

  const toggleSaved = useCallback((id: string) => {
    setCourses((prev) => prev.map((c) => (c.id === id ? { ...c, saved: !c.saved } : c)))
  }, [])

  const markLessonComplete = useCallback((courseId: string, lessonId: string) => {
    setCourses((prev) =>
      prev.map((c) => {
        if (c.id !== courseId) return c
        const modules = c.modules.map((m) => ({
          ...m,
          lessons: m.lessons.map((l) => (l.id === lessonId ? { ...l, completed: true } : l)),
        }))
        const total = modules.reduce((sum, m) => sum + m.lessons.length, 0)
        const done = modules.reduce(
          (sum, m) => sum + m.lessons.filter((l) => l.completed).length,
          0
        )
        const progressPct = total > 0 ? Math.round((done / total) * 100) : 0
        const lesson = modules.flatMap((m) => m.lessons).find((l) => l.id === lessonId)
        return {
          ...c,
          modules,
          progressPct,
          lastLessonTitle: lesson?.title ?? c.lastLessonTitle,
          lastViewedAt: 'Just now',
          completedAt: progressPct === 100 ? 'Jul 2026' : c.completedAt,
        }
      })
    )
  }, [])

  const value = useMemo<CourseCatalogValue>(
    () => ({
      courses,
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
    }),
    [
      courses,
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
    ]
  )

  return <CourseCatalogContext.Provider value={value}>{children}</CourseCatalogContext.Provider>
}

export function useCourseCatalog() {
  const ctx = useContext(CourseCatalogContext)
  if (!ctx) throw new Error('useCourseCatalog must be used within a CourseCatalogProvider')
  return ctx
}

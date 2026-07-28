/** Shared types for the AI Study Plan Generator (Part 3). */

export type StudyTaskType =
  | 'lecture'
  | 'revision'
  | 'practice'
  | 'quiz'
  | 'flashcards'
  | 'assignment'
  | 'break'
  | 'exam-prep'

export type StudyTaskPriority = 'low' | 'medium' | 'high' | 'critical'

export interface StudyTask {
  id: string
  title: string
  subject: string
  type: StudyTaskType
  priority: StudyTaskPriority
  startMinute: number // minutes from midnight
  durationMinutes: number
  day: number // 0 = today, 1 = tomorrow, ... within the visible window
  done: boolean
  aiReason: string
  color: string
}

export interface WeakTopic {
  subject: string
  topic: string
  masteryPct: number
  trend: 'up' | 'down' | 'flat'
}

export interface UpcomingExam {
  id: string
  subject: string
  title: string
  date: string
  daysAway: number
  readiness: number
}

export interface StudyRecommendation {
  id: string
  icon: string
  title: string
  body: string
  actionLabel: string
  kind: 'next' | 'revise' | 'break' | 'lecture' | 'quiz' | 'flashcards' | 'weak-topic'
}

export interface PlannerInputsSummary {
  upcomingExams: number
  weakSubjects: string[]
  strongSubjects: string[]
  availableHoursPerDay: number
  focusScore: number
  quizAccuracy: number
  learningSpeed: 'slower' | 'average' | 'faster'
  currentStreak: number
}

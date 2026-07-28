import type {
  PlannerInputsSummary,
  StudyRecommendation,
  StudyTask,
  UpcomingExam,
  WeakTopic,
} from '../types/planner'

/**
 * Simulated output of the AI Study Plan Generator. In production this is
 * produced by a planning service that ingests exam dates, quiz results,
 * lecture completion, focus scores, and available hours (see
 * `backend/README.md` § Study Planner) and re-runs whenever any of those
 * signals change. Here the same "regenerate on change" behavior is
 * simulated client-side in `useStudyPlan.ts`.
 */

export const plannerInputs: PlannerInputsSummary = {
  upcomingExams: 2,
  weakSubjects: ['Organic Chemistry', 'Physics — Rotational Dynamics'],
  strongSubjects: ['Calculus', 'Cell Biology'],
  availableHoursPerDay: 3.5,
  focusScore: 94,
  quizAccuracy: 87,
  learningSpeed: 'faster',
  currentStreak: 21,
}

export const weakTopics: WeakTopic[] = [
  { subject: 'Chemistry', topic: 'SN1 vs SN2 mechanisms', masteryPct: 42, trend: 'down' },
  { subject: 'Physics', topic: 'Moment of inertia (compound bodies)', masteryPct: 58, trend: 'up' },
  { subject: 'Mathematics', topic: 'Variational calculus edge cases', masteryPct: 63, trend: 'flat' },
]

export const upcomingExams: UpcomingExam[] = [
  { id: 'ex1', subject: 'Physics 201', title: 'Midterm Exam', date: 'Aug 8', daysAway: 12, readiness: 71 },
  { id: 'ex2', subject: 'Organic Chemistry II', title: 'Chapter 14 Quiz', date: 'Jul 31', daysAway: 4, readiness: 48 },
]

const colors: Record<StudyTask['type'], string> = {
  lecture: '#2DD4BF',
  revision: '#a855f7',
  practice: '#f59e0b',
  quiz: '#22c55e',
  flashcards: '#38bdf8',
  assignment: '#FF7E36',
  break: '#64748b',
  'exam-prep': '#ef4444',
}

function task(partial: Omit<StudyTask, 'color'>): StudyTask {
  return { ...partial, color: colors[partial.type] }
}

/** 7-day rolling window of AI-generated study tasks, day 0 = today. */
export const initialTasks: StudyTask[] = [
  // Today
  task({ id: 'd0-1', title: 'Watch: Rotational Dynamics (AI-optimized)', subject: 'Physics', type: 'lecture', priority: 'high', startMinute: 9 * 60, durationMinutes: 42, day: 0, done: true, aiReason: 'Queued next in your course sequence — optimized cut saves 12 min.' }),
  task({ id: 'd0-2', title: 'Flashcards: Torque & Moment of Inertia', subject: 'Physics', type: 'flashcards', priority: 'medium', startMinute: 10 * 60, durationMinutes: 15, day: 0, done: true, aiReason: 'Reinforces the lecture you just watched while retention is highest.' }),
  task({ id: 'd0-3', title: 'Break', subject: '', type: 'break', priority: 'low', startMinute: 10 * 60 + 15, durationMinutes: 15, day: 0, done: true, aiReason: 'Short recovery break after a focused block.' }),
  task({ id: 'd0-4', title: 'Practice: SN1 vs SN2 mechanisms', subject: 'Chemistry', type: 'practice', priority: 'critical', startMinute: 16 * 60, durationMinutes: 40, day: 0, done: false, aiReason: 'Weakest topic (42% mastery) with a quiz in 4 days — highest priority today.' }),
  task({ id: 'd0-5', title: 'Revise: Variational Calculus', subject: 'Mathematics', type: 'revision', priority: 'medium', startMinute: 17 * 60, durationMinutes: 25, day: 0, done: false, aiReason: 'Spaced-repetition review due today based on the forgetting curve.' }),
  task({ id: 'd0-6', title: 'Quiz: Chapter 8 Checkpoint', subject: 'Biology', type: 'quiz', priority: 'low', startMinute: 19 * 60, durationMinutes: 20, day: 0, done: false, aiReason: 'Keeps your strong subject warm without taking time from weak topics.' }),

  // Tomorrow
  task({ id: 'd1-1', title: 'Watch: SN1/SN2 Deep Dive (AI-optimized)', subject: 'Chemistry', type: 'lecture', priority: 'critical', startMinute: 9 * 60, durationMinutes: 35, day: 1, done: false, aiReason: 'Directly targets your weakest topic ahead of Thursday\u2019s quiz.' }),
  task({ id: 'd1-2', title: 'Practice Set: Reaction Mechanisms', subject: 'Chemistry', type: 'practice', priority: 'critical', startMinute: 9 * 60 + 45, durationMinutes: 45, day: 1, done: false, aiReason: 'Reinforces the lecture immediately — best retention window.' }),
  task({ id: 'd1-3', title: 'Assignment: Lab Report Draft', subject: 'Physics', type: 'assignment', priority: 'high', startMinute: 17 * 60, durationMinutes: 50, day: 1, done: false, aiReason: 'Due in 2 days — scheduled with buffer for revisions.' }),

  // Day 2
  task({ id: 'd2-1', title: 'Revision Sheet: Rotational Dynamics', subject: 'Physics', type: 'revision', priority: 'medium', startMinute: 9 * 60, durationMinutes: 30, day: 2, done: false, aiReason: 'Second-pass revision before the midterm countdown intensifies.' }),
  task({ id: 'd2-2', title: 'Mock Quiz: SN1/SN2', subject: 'Chemistry', type: 'quiz', priority: 'critical', startMinute: 10 * 60, durationMinutes: 25, day: 2, done: false, aiReason: 'Dress-rehearsal for Thursday\u2019s real quiz.' }),

  // Day 3
  task({ id: 'd3-1', title: 'Exam Countdown Review — Chemistry', subject: 'Chemistry', type: 'exam-prep', priority: 'critical', startMinute: 9 * 60, durationMinutes: 60, day: 3, done: false, aiReason: 'Final consolidated review the day before the quiz.' }),

  // Day 4 (quiz day)
  task({ id: 'd4-1', title: 'Light review — Chapter 14 formulas', subject: 'Chemistry', type: 'revision', priority: 'high', startMinute: 8 * 60, durationMinutes: 20, day: 4, done: false, aiReason: 'Quiz day — light touch review only, no new material.' }),

  // Day 5
  task({ id: 'd5-1', title: 'Watch: Parallel Axis Theorem Examples', subject: 'Physics', type: 'lecture', priority: 'high', startMinute: 9 * 60, durationMinutes: 38, day: 5, done: false, aiReason: 'Midterm-relevant chapter — moving into exam-prep mode.' }),
  task({ id: 'd5-2', title: 'Flashcards: Full Physics Deck', subject: 'Physics', type: 'flashcards', priority: 'high', startMinute: 10 * 60, durationMinutes: 20, day: 5, done: false, aiReason: 'Spaced repetition due date for the full deck.' }),

  // Day 6
  task({ id: 'd6-1', title: 'Practice Exam — Full Length', subject: 'Physics', type: 'exam-prep', priority: 'critical', startMinute: 9 * 60, durationMinutes: 90, day: 6, done: false, aiReason: '6 days to midterm — first full-length timed practice exam.' }),
]

export const recommendations: StudyRecommendation[] = [
  { id: 'r1', icon: '🎯', title: 'Study this next', body: 'SN1 vs SN2 mechanisms — your weakest topic, quiz in 4 days.', actionLabel: 'Start now', kind: 'weak-topic' },
  { id: 'r2', icon: '🔁', title: 'Due for revision', body: 'Variational Calculus — spaced repetition flags this today.', actionLabel: 'Revise', kind: 'revise' },
  { id: 'r3', icon: '🎬', title: 'Recommended lecture', body: 'SN1/SN2 Deep Dive — AI-optimized, 35 min instead of 47.', actionLabel: 'Watch', kind: 'lecture' },
  { id: 'r4', icon: '❓', title: 'Recommended quiz', body: 'Chapter 8 Checkpoint — keeps Biology warm with minimal time.', actionLabel: 'Take quiz', kind: 'quiz' },
  { id: 'r5', icon: '🗂️', title: 'Flashcards due', body: 'Torque & Moment of Inertia deck — 12 cards due today.', actionLabel: 'Review', kind: 'flashcards' },
  { id: 'r6', icon: '☕', title: 'Take a break', body: 'You\u2019ve completed 2 focused blocks — a 15 min break improves retention.', actionLabel: 'Start break', kind: 'break' },
]

export const studyTips = [
  'Interleave Chemistry practice with Physics revision — switching subjects every 40–50 min improves long-term retention.',
  'Your focus score peaks 9–11am. Schedule your hardest topic (SN1/SN2) in that window when possible.',
  'You retain flashcards best when reviewed within 2 hours of first watching the related lecture.',
]

import { useCallback, useState } from 'react'
import type { StudyTask } from '../types/planner'
import { initialTasks } from '../data/plannerMock'

export type PlanTrigger =
  | 'quiz-completed'
  | 'lecture-uploaded'
  | 'exam-added'
  | 'assignment-submitted'
  | 'performance-improved'
  | 'performance-declined'

const triggerMessages: Record<PlanTrigger, string> = {
  'quiz-completed': 'Quiz result received — adjusting revision priorities.',
  'lecture-uploaded': 'New lecture detected — inserting it into your schedule.',
  'exam-added': 'New exam date added — rebuilding your countdown plan.',
  'assignment-submitted': 'Assignment submitted — freeing up that time block.',
  'performance-improved': 'Performance trending up — reducing revision load slightly.',
  'performance-declined': 'Performance dipped — adding extra practice sessions.',
}

/**
 * Client-side simulation of the AI Study Planner's "no manual intervention
 * required" adaptive regeneration. Call `regenerate(trigger)` whenever a
 * signal changes (quiz completed, new exam, etc.) and the plan
 * re-prioritizes — mirroring what a real backend planning service would do
 * server-side on the same events.
 */
export function useStudyPlan() {
  const [tasks, setTasks] = useState<StudyTask[]>(initialTasks)
  const [regenerating, setRegenerating] = useState(false)
  const [lastTrigger, setLastTrigger] = useState<PlanTrigger | null>(null)
  const [history, setHistory] = useState<Array<{ trigger: PlanTrigger; message: string; at: string }>>([])

  const toggleTask = useCallback((id: string) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)))
  }, [])

  const regenerate = useCallback((trigger: PlanTrigger) => {
    setRegenerating(true)
    setLastTrigger(trigger)
    setHistory((prev) => [
      { trigger, message: triggerMessages[trigger], at: 'just now' },
      ...prev,
    ].slice(0, 5))

    setTimeout(() => {
      setTasks((prev) => {
        // Lightweight, deterministic re-prioritization so the UI visibly
        // reacts without needing a real planning engine.
        const shuffledPriority = prev.map((t) => {
          if (trigger === 'performance-declined' && t.type === 'practice') {
            return { ...t, priority: 'critical' as const }
          }
          if (trigger === 'performance-improved' && t.priority === 'critical' && t.type === 'revision') {
            return { ...t, priority: 'medium' as const }
          }
          return t
        })
        return shuffledPriority
      })
      setRegenerating(false)
    }, 1400)
  }, [])

  const todayTasks = tasks.filter((t) => t.day === 0)
  const doneCount = todayTasks.filter((t) => t.done).length
  const completionPct = todayTasks.length > 0 ? Math.round((doneCount / todayTasks.length) * 100) : 0
  const remainingMinutes = todayTasks.filter((t) => !t.done).reduce((sum, t) => sum + t.durationMinutes, 0)

  return {
    tasks,
    toggleTask,
    regenerate,
    regenerating,
    lastTrigger,
    history,
    todayTasks,
    completionPct,
    remainingMinutes,
    doneCount,
  }
}

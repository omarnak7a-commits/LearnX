import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { ChallengeDefinition, ChallengeMetric } from '../types/gamification'
import {
  getTodaysDailyChallenges,
  getThisWeeksChallenges,
  dailyPeriodKey,
  weeklyPeriodKey,
} from '../lib/xp/challenges'
import {
  loadMetricRows,
  saveMetricRows,
  loadClaims,
  saveClaims,
  type MetricProgressRow,
} from '../lib/xp/challengeStorage'
import { useXp } from './XpContext'
import { useProfile } from './ProfileContext'

export interface ChallengeWithProgress extends ChallengeDefinition {
  periodKey: string
  current: number
  completed: boolean
}

interface ChallengesContextValue {
  loading: boolean
  dailyChallenges: ChallengeWithProgress[]
  weeklyChallenges: ChallengeWithProgress[]
  allDailyCompleted: boolean
  /** Reports real progress toward a metric (e.g. a quiz was just
   *  completed, 12 minutes were just studied). Safe to call from any
   *  real action call-site — accumulates independently per rotation
   *  period so it can never be "spent twice". */
  recordProgress: (metric: ChallengeMetric, amount?: number) => void
}

const ChallengesContext = createContext<ChallengesContextValue | null>(null)

function metricTotal(
  rows: MetricProgressRow[],
  periodKey: string,
  metric: ChallengeMetric
): number {
  return rows
    .filter((r) => r.periodKey === periodKey && r.metric === metric)
    .reduce((sum, r) => sum + r.amount, 0)
}

export function ChallengesProvider({ children }: { children: ReactNode }) {
  const [rows, setRows] = useState<MetricProgressRow[]>([])
  const [claims, setClaims] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const { award } = useXp()
  const { profile } = useProfile()
  const { weeklyXp } = useXp()

  useEffect(() => {
    setRows(loadMetricRows())
    setClaims(loadClaims())
    setLoading(false)
  }, [])

  const recordProgress = useCallback((metric: ChallengeMetric, amount = 1) => {
    const dayKey = dailyPeriodKey()
    const weekKey = weeklyPeriodKey()
    setRows((prev) => {
      const next = [
        ...prev,
        { periodKey: dayKey, metric, amount },
        { periodKey: weekKey, metric, amount },
      ]
      saveMetricRows(next)
      return next
    })
  }, [])

  const dailyDefs = useMemo(() => getTodaysDailyChallenges(), [])
  const weeklyDefs = useMemo(() => getThisWeeksChallenges(), [])
  const dayKey = dailyPeriodKey()
  const weekKey = weeklyPeriodKey()

  const dailyChallenges = useMemo<ChallengeWithProgress[]>(
    () =>
      dailyDefs.map((def) => {
        const current = Math.min(def.target, metricTotal(rows, dayKey, def.metric))
        return { ...def, periodKey: dayKey, current, completed: current >= def.target }
      }),
    [dailyDefs, rows, dayKey]
  )

  const weeklyChallenges = useMemo<ChallengeWithProgress[]>(
    () =>
      weeklyDefs.map((def) => {
        let current: number
        if (def.metric === 'streak-days') {
          current = Math.min(def.target, profile?.streakDays ?? 0)
        } else if (def.metric === 'xp-earned') {
          current = Math.min(def.target, weeklyXp)
        } else {
          current = Math.min(def.target, metricTotal(rows, weekKey, def.metric))
        }
        return { ...def, periodKey: weekKey, current, completed: current >= def.target }
      }),
    [weeklyDefs, rows, weekKey, profile?.streakDays, weeklyXp]
  )

  const allDailyCompleted = dailyChallenges.length > 0 && dailyChallenges.every((c) => c.completed)

  // Award XP automatically the moment a challenge is newly completed —
  // `award()`'s dedupeKey makes this idempotent, so re-running on every
  // progress change is safe and never double-credits.
  useEffect(() => {
    for (const c of dailyChallenges) {
      if (c.completed) {
        award('daily-challenge', {
          amount: c.xpReward,
          detail: c.label,
          dedupeKey: `${c.periodKey}:${c.id}`,
        })
      }
    }
    if (allDailyCompleted) {
      award('daily-challenge-bonus', { dedupeKey: `bonus:${dayKey}` })
    }
  }, [dailyChallenges, allDailyCompleted, award, dayKey])

  useEffect(() => {
    for (const c of weeklyChallenges) {
      if (c.completed) {
        award('weekly-challenge', {
          amount: c.xpReward,
          detail: c.label,
          dedupeKey: `${c.periodKey}:${c.id}`,
        })
      }
    }
  }, [weeklyChallenges, award])

  const value = useMemo<ChallengesContextValue>(
    () => ({ loading, dailyChallenges, weeklyChallenges, allDailyCompleted, recordProgress }),
    [loading, dailyChallenges, weeklyChallenges, allDailyCompleted, recordProgress]
  )

  // Marking claims persisted for potential future UI (e.g. showing a
  // "claimed" state distinctly from "completed") — kept minimal since
  // the spec only asks that completing challenges grants XP, which
  // already happens automatically above.
  useEffect(() => {
    saveClaims(claims)
  }, [claims])

  return <ChallengesContext.Provider value={value}>{children}</ChallengesContext.Provider>
}

export function useChallenges() {
  const ctx = useContext(ChallengesContext)
  if (!ctx) throw new Error('useChallenges must be used within a ChallengesProvider')
  return ctx
}

import type { ChallengeMetric, ChallengeProgress } from '../../types/gamification'

/**
 * localStorage persistence for challenge progress — a flat array of
 * `{ periodKey, metric, amount }` accumulation rows (one row per metric
 * per rotation period), plus a set of "reward claimed" markers. Kept
 * deliberately simple (just running totals per metric per period)
 * because `src/lib/xp/challengeEngine.ts` re-derives each challenge's
 * specific progress from these shared per-metric totals — several
 * challenges can share the same underlying metric (e.g. both a daily and
 * weekly challenge can track "quiz-complete") without double-counting
 * anything, since each just reads the same running total for its period.
 */

export interface MetricProgressRow {
  periodKey: string
  metric: ChallengeMetric
  amount: number
}

const METRICS_KEY = 'learnx-challenge-metrics-v1'
const CLAIMS_KEY = 'learnx-challenge-claims-v1'

export function loadMetricRows(): MetricProgressRow[] {
  try {
    const raw = localStorage.getItem(METRICS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveMetricRows(rows: MetricProgressRow[]): void {
  try {
    localStorage.setItem(METRICS_KEY, JSON.stringify(rows))
  } catch {
    // ignore
  }
}

/** `${periodKey}::${challengeDefinitionId}` -> claimed reward flag. */
export function loadClaims(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(CLAIMS_KEY)
    if (!raw) return {}
    return JSON.parse(raw) ?? {}
  } catch {
    return {}
  }
}

export function saveClaims(claims: Record<string, boolean>): void {
  try {
    localStorage.setItem(CLAIMS_KEY, JSON.stringify(claims))
  } catch {
    // ignore
  }
}

export type { ChallengeProgress }

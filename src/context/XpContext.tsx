import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { XpSourceId, XpTransaction } from '../types/gamification'
import { XP_SOURCES } from '../types/gamification'
import { loadLedger, saveLedger } from '../lib/xp/storage'
import { computeLevelProgress, type LevelProgress } from '../lib/profile/xp'

interface AwardOptions {
  /** Overrides the source's default fixed amount — used for weekly-
   *  challenge bonuses etc. where the amount isn't the catalog default. */
  amount?: number
  detail?: string | null
  /** When set, this exact (source, dedupeKey) pair can only ever be
   *  awarded once — guards against e.g. double-crediting the same lesson
   *  completion if a component re-renders/re-fires the same handler. */
  dedupeKey?: string
}

interface XpContextValue {
  ledger: XpTransaction[]
  loading: boolean
  totalXp: number
  todayXp: number
  weeklyXp: number
  monthlyXp: number
  level: LevelProgress
  /** Awards XP for a real, tracked action. Returns `false` (no-op) if a
   *  `dedupeKey` was supplied and already used for this source — callers
   *  can use this to avoid double-toasting a "reward" UI too. */
  award: (source: XpSourceId, options?: AwardOptions) => boolean
  /** Spends XP (e.g. Reward Store redemption) — records a negative
   *  ledger entry. Returns `false` if `totalXp` is insufficient. */
  spend: (amount: number, label: string, detail?: string | null) => boolean
  hasAwarded: (source: XpSourceId, dedupeKey: string) => boolean
  /**
   * Feeds real elapsed study minutes (from PDF reading sessions in
   * FileWorkspace, or the manual Study Timer widget) into a persisted
   * running accumulator; every time the accumulator crosses a 30-minute
   * threshold it awards the "Study 30 Minutes" XP exactly once for that
   * block (via a monotonically increasing block-index dedupe key), so
   * the spec's "+40 XP per 30 minutes studied" rule is satisfied from
   * *any* real study-time source without ever double-counting the same
   * minutes twice.
   */
  recordStudyMinutes: (minutes: number) => void
}

const XpContext = createContext<XpContextValue | null>(null)

const DAY_MS = 24 * 60 * 60 * 1000
const WEEK_MS = 7 * DAY_MS
const STUDY_MINUTES_KEY = 'learnx-xp-study-minutes-accumulator-v1'

let txCounter = 0

function loadStudyMinutesTotal(): number {
  try {
    const raw = localStorage.getItem(STUDY_MINUTES_KEY)
    return raw ? Number(raw) || 0 : 0
  } catch {
    return 0
  }
}

function saveStudyMinutesTotal(total: number): void {
  try {
    localStorage.setItem(STUDY_MINUTES_KEY, String(total))
  } catch {
    // ignore
  }
}

export function XpProvider({ children }: { children: ReactNode }) {
  const [ledger, setLedger] = useState<XpTransaction[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLedger(loadLedger())
    setLoading(false)
  }, [])

  const hasAwarded = useCallback(
    (source: XpSourceId, dedupeKey: string) =>
      ledger.some((tx) => tx.source === source && tx.dedupeKey === dedupeKey),
    [ledger]
  )

  const award = useCallback((source: XpSourceId, options: AwardOptions = {}): boolean => {
    const def = XP_SOURCES[source]
    const dedupeKey = options.dedupeKey ?? null

    let awarded = true
    setLedger((prev) => {
      if (dedupeKey && prev.some((tx) => tx.source === source && tx.dedupeKey === dedupeKey)) {
        awarded = false
        return prev
      }
      txCounter += 1
      const tx: XpTransaction = {
        id: `xp-${Date.now()}-${txCounter}`,
        source,
        amount: options.amount ?? def.amount,
        label: def.label,
        detail: options.detail ?? null,
        dedupeKey,
        timestamp: Date.now(),
      }
      const next = [...prev, tx]
      saveLedger(next)
      return next
    })
    return awarded
  }, [])

  const spend = useCallback(
    (amount: number, label: string, detail: string | null = null): boolean => {
      let success = false
      setLedger((prev) => {
        const currentTotal = prev.reduce((sum, tx) => sum + tx.amount, 0)
        if (currentTotal < amount) {
          success = false
          return prev
        }
        success = true
        txCounter += 1
        const tx: XpTransaction = {
          id: `xp-${Date.now()}-${txCounter}`,
          source: 'reward-redeemed',
          amount: -amount,
          label,
          detail,
          dedupeKey: null,
          timestamp: Date.now(),
        }
        const next = [...prev, tx]
        saveLedger(next)
        return next
      })
      return success
    },
    []
  )

  const totalXp = useMemo(
    () =>
      Math.max(
        0,
        ledger.reduce((sum, tx) => sum + tx.amount, 0)
      ),
    [ledger]
  )

  const recordStudyMinutes = useCallback((minutes: number) => {
    if (minutes <= 0) return
    const before = loadStudyMinutesTotal()
    const after = before + minutes
    saveStudyMinutesTotal(after)
    const blocksBefore = Math.floor(before / 30)
    const blocksAfter = Math.floor(after / 30)
    if (blocksAfter > blocksBefore) {
      setLedger((prev) => {
        let next = prev
        for (let block = blocksBefore + 1; block <= blocksAfter; block++) {
          const dedupeKey = `study-block-${block}`
          if (next.some((tx) => tx.source === 'study-30-min' && tx.dedupeKey === dedupeKey))
            continue
          txCounter += 1
          const tx: XpTransaction = {
            id: `xp-${Date.now()}-${txCounter}`,
            source: 'study-30-min',
            amount: XP_SOURCES['study-30-min'].amount,
            label: XP_SOURCES['study-30-min'].label,
            detail: null,
            dedupeKey,
            timestamp: Date.now(),
          }
          next = [...next, tx]
        }
        if (next !== prev) saveLedger(next)
        return next
      })
    }
  }, [])

  const todayXp = useMemo(() => {
    const cutoff = Date.now() - DAY_MS
    return ledger
      .filter((tx) => tx.timestamp >= cutoff && tx.amount > 0)
      .reduce((sum, tx) => sum + tx.amount, 0)
  }, [ledger])

  const weeklyXp = useMemo(() => {
    const cutoff = Date.now() - WEEK_MS
    return ledger
      .filter((tx) => tx.timestamp >= cutoff && tx.amount > 0)
      .reduce((sum, tx) => sum + tx.amount, 0)
  }, [ledger])

  const monthlyXp = useMemo(() => {
    const cutoff = Date.now() - 30 * DAY_MS
    return ledger
      .filter((tx) => tx.timestamp >= cutoff && tx.amount > 0)
      .reduce((sum, tx) => sum + tx.amount, 0)
  }, [ledger])

  const level = useMemo(() => computeLevelProgress(totalXp), [totalXp])

  const value = useMemo<XpContextValue>(
    () => ({
      ledger,
      loading,
      totalXp,
      todayXp,
      weeklyXp,
      monthlyXp,
      level,
      award,
      spend,
      hasAwarded,
      recordStudyMinutes,
    }),
    [
      ledger,
      loading,
      totalXp,
      todayXp,
      weeklyXp,
      monthlyXp,
      level,
      award,
      spend,
      hasAwarded,
      recordStudyMinutes,
    ]
  )

  return <XpContext.Provider value={value}>{children}</XpContext.Provider>
}

export function useXp() {
  const ctx = useContext(XpContext)
  if (!ctx) throw new Error('useXp must be used within an XpProvider')
  return ctx
}

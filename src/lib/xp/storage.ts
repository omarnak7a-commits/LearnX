import type { XpTransaction } from '../../types/gamification'

/**
 * localStorage persistence for the global XP ledger — same posture as
 * every other persistence module in this build. Stored as a flat array
 * of transactions (the ledger itself); `useXp()` derives totals/level/
 * weekly/monthly numbers from this array so the numbers can never drift
 * out of sync with the log they're computed from.
 */

const STORAGE_KEY = 'learnx-xp-ledger-v1'

export function loadLedger(): XpTransaction[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveLedger(ledger: XpTransaction[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ledger))
  } catch {
    // ignore
  }
}

/**
 * Reading tracker: decides which pages a student has genuinely *read*.
 *
 * This is deliberately a small, pure, framework-free module so the rule
 * "what counts as read" lives in exactly one place and can be tested without
 * React, pdf.js, IndexedDB or a browser.
 *
 * The distinction it enforces:
 *
 *   viewed — the page became the active page (or was preloaded next to it)
 *   read   — the page rendered, was actually on screen, and the student
 *            stayed on it for at least READ_PAGE_THRESHOLD_MS
 *
 * Why this matters: previously a page was marked read the instant its canvas
 * finished painting, so flipping 1 -> 2 -> 3 -> 4 -> 5 -> 20 marked six pages
 * read in about a second, and reading progress (and every feature derived from
 * it, including practice-quiz page selection) was wrong.
 *
 * Rendering is a separate concern and lives in the viewer; this module only
 * receives "page N became visible at time T" / "page N stopped being visible"
 * signals and answers "which pages are read".
 */

/**
 * How long a page must remain the visible page before it counts as read.
 *
 * Chosen as a deliberately modest dwell time: long enough that flipping
 * through pages does not mark them read, short enough that genuinely
 * skimming a light page still counts.
 */
export const READ_PAGE_THRESHOLD_MS = 3000

/** A page becoming visible, or ceasing to be visible. */
export interface PageVisibilityEvent {
  page: number
  /** Monotonic-ish timestamp in ms (Date.now() or performance.now()). */
  at: number
}

export interface ReadingTrackerOptions {
  thresholdMs?: number
  /** Pages already known to be read (restored from persistence). */
  initialPagesRead?: Iterable<number>
}

/**
 * Tracks dwell time per page and reports pages that cross the read threshold.
 *
 * Usage is intentionally imperative and side-effect free: the caller drives it
 * with `enter`/`leave`/`tick` and reads `pagesRead`. It never touches storage.
 */
export class ReadingTracker {
  private readonly thresholdMs: number
  private readonly read: Set<number>
  /** The page currently on screen, and when it became visible. */
  private active: { page: number; since: number } | null = null
  /** Dwell accumulated for the active page across pause/resume cycles. */
  private accumulated = 0
  /** Pages that crossed the threshold since the last `drainNewlyRead()`. */
  private pending: number[] = []
  /** True while the document is hidden (tab in background, viewer closed). */
  private paused = false

  constructor(options: ReadingTrackerOptions = {}) {
    this.thresholdMs = options.thresholdMs ?? READ_PAGE_THRESHOLD_MS
    this.read = new Set(options.initialPagesRead ?? [])
  }

  /** Every page considered read, ascending. */
  get pagesRead(): number[] {
    return [...this.read].sort((a, b) => a - b)
  }

  hasRead(page: number): boolean {
    return this.read.has(page)
  }

  /** The page currently being dwelled on, if any. */
  get activePage(): number | null {
    return this.active?.page ?? null
  }

  /**
   * The page became the visible page.
   *
   * Calling this with the page that is already active is a no-op, so repeated
   * renders of the same page (zoom changes, re-mounts, React strict-mode
   * double effects) do not reset or double-count dwell time.
   */
  enter(page: number, at: number): void {
    if (this.active?.page === page) return
    if (this.active) this.leave(at)
    this.active = { page, since: at }
    this.accumulated = 0
  }

  /**
   * The active page stopped being visible (navigation away, viewer closed).
   * Banks the dwell time accrued so far and promotes the page if it qualifies.
   */
  leave(at: number): void {
    if (!this.active) return
    this.settle(at)
    this.active = null
    this.accumulated = 0
  }

  /**
   * Stop accruing dwell time without giving up the active page.
   * Used when the tab is hidden or the viewer is not the visible tab.
   */
  pause(at: number): void {
    if (this.paused || !this.active) {
      this.paused = true
      return
    }
    this.accumulated += Math.max(0, at - this.active.since)
    this.paused = true
  }

  /** Resume accruing dwell time for the still-active page. */
  resume(at: number): void {
    if (!this.paused) return
    this.paused = false
    if (this.active) this.active.since = at
  }

  /**
   * Advance the clock, promoting the active page if it has now been visible
   * long enough. Safe to call as often as you like.
   */
  tick(at: number): void {
    this.settle(at, { keepActive: true })
  }

  /** Total dwell accrued on the active page as of `at`, in ms. */
  dwell(at: number): number {
    if (!this.active) return 0
    const live = this.paused ? 0 : Math.max(0, at - this.active.since)
    return this.accumulated + live
  }

  /**
   * Pages that became read since the last drain. The caller persists these;
   * draining keeps persistence writes proportional to real reading rather
   * than to render or scroll events.
   */
  drainNewlyRead(): number[] {
    const drained = this.pending
    this.pending = []
    return drained
  }

  /** Mark a page read regardless of dwell (e.g. restoring persisted state). */
  forceRead(page: number): void {
    if (!this.read.has(page)) this.read.add(page)
  }

  private settle(at: number, opts: { keepActive?: boolean } = {}): void {
    if (!this.active) return
    const total = this.dwell(at)
    if (total >= this.thresholdMs && !this.read.has(this.active.page)) {
      this.read.add(this.active.page)
      this.pending.push(this.active.page)
    }
    if (opts.keepActive && !this.paused) {
      // Fold elapsed time into the accumulator so repeated ticks do not
      // double count the same interval.
      this.accumulated = total
      this.active.since = at
    }
  }
}

/**
 * Reading progress as a percentage of distinct pages actually read.
 *
 * Deliberately set-based: a student who reads pages 1, 2, 7 and 15 of a
 * 20-page document has read 4 pages (20%), not "up to page 15" (75%).
 */
export function readingProgressPercent(
  pagesRead: Iterable<number>,
  pageCount: number
): number {
  if (!pageCount || pageCount <= 0) return 0
  const distinct = new Set<number>()
  for (const page of pagesRead) {
    if (Number.isFinite(page) && page >= 1 && page <= pageCount) {
      distinct.add(Math.trunc(page))
    }
  }
  return Math.round((distinct.size / pageCount) * 100)
}

/**
 * Merge newly read pages into an existing list, keeping it sorted, unique and
 * free of out-of-range values. Returns the *original array reference* when
 * nothing changed, so React state updates can be skipped cheaply.
 */
export function mergePagesRead(
  existing: number[],
  incoming: Iterable<number>,
  pageCount?: number
): number[] {
  const set = new Set(existing)
  let changed = false
  for (const raw of incoming) {
    if (!Number.isFinite(raw)) continue
    const page = Math.trunc(raw)
    if (page < 1) continue
    if (pageCount && page > pageCount) continue
    if (!set.has(page)) {
      set.add(page)
      changed = true
    }
  }
  if (!changed) return existing
  return [...set].sort((a, b) => a - b)
}

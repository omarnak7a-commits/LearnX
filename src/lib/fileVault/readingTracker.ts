/**
 * Reading tracker: records which pages a student has actually visited.
 *
 * This is deliberately a small, pure, framework-free module so the rule
 * "what counts as read" lives in exactly one place and can be tested without
 * React, pdf.js, IndexedDB or a browser.
 *
 * The rule:
 *
 *   read     — the page became the viewer's ACTIVE page through navigation,
 *              i.e. the student is looking at it now. Marked immediately.
 *   not read — the page was only decoded ahead of time for the preload
 *              window, or rendered in the background. Never marked.
 *
 * There is no dwell time and no timer: `visit()` is called by the viewer at
 * the moment a page becomes active, and the page is read from that instant.
 * Preloaded neighbours never reach this module, which is what keeps a jump
 * from page 3 to page 20 from marking pages 4-19.
 *
 * Rendering remains a separate concern owned by the viewer; this module only
 * receives "page N is now the active page" and answers "which pages are read".
 */

export interface ReadingTrackerOptions {
  /** Pages already known to be read (restored from persistence). */
  initialPagesRead?: Iterable<number>
  /** Upper bound used to reject nonsense page numbers. */
  pageCount?: number
}

/**
 * Records visited pages and reports the ones that are newly read.
 *
 * Usage is intentionally imperative and side-effect free: the caller drives it
 * with `visit()` and reads `pagesRead` / `drainNewlyRead()`. It never touches
 * storage, so persistence policy stays with the caller.
 */
export class ReadingTracker {
  private readonly read: Set<number>
  private readonly pageCount?: number
  /** Pages newly marked read since the last `drainNewlyRead()`. */
  private pending: number[] = []
  /** The page currently being viewed. */
  private active: number | null = null

  constructor(options: ReadingTrackerOptions = {}) {
    this.pageCount = options.pageCount
    this.read = new Set()
    for (const page of options.initialPagesRead ?? []) {
      const normalized = this.normalize(page)
      if (normalized !== null) this.read.add(normalized)
    }
  }

  /** Every page considered read, ascending. */
  get pagesRead(): number[] {
    return [...this.read].sort((a, b) => a - b)
  }

  hasRead(page: number): boolean {
    const normalized = this.normalize(page)
    return normalized !== null && this.read.has(normalized)
  }

  /** The page currently being viewed, if any. */
  get activePage(): number | null {
    return this.active
  }

  /**
   * The page became the viewer's active page: mark it read immediately.
   *
   * Idempotent. Re-visiting the active page (zoom change, re-mount, React
   * strict-mode double effect, revisiting later) never double counts, so
   * progress cannot be inflated by repeat visits.
   *
   * Returns true only when this call newly marked the page as read, which
   * lets the caller skip redundant persistence writes.
   */
  visit(page: number): boolean {
    const normalized = this.normalize(page)
    if (normalized === null) return false
    this.active = normalized
    if (this.read.has(normalized)) return false
    this.read.add(normalized)
    this.pending.push(normalized)
    return true
  }

  /**
   * Pages that became read since the last drain. The caller persists these,
   * so storage writes stay proportional to genuinely new pages rather than to
   * navigation, render or scroll events.
   */
  drainNewlyRead(): number[] {
    const drained = this.pending
    this.pending = []
    return drained
  }

  /** Mark a page read without treating it as the active page. */
  forceRead(page: number): void {
    const normalized = this.normalize(page)
    if (normalized === null || this.read.has(normalized)) return
    this.read.add(normalized)
    this.pending.push(normalized)
  }

  private normalize(page: number): number | null {
    if (!Number.isFinite(page)) return null
    const value = Math.trunc(page)
    if (value < 1) return null
    if (this.pageCount && value > this.pageCount) return null
    return value
  }
}

/**
 * The exact step the viewer performs when a page becomes active: clamp the
 * requested page into the document, mark it read immediately, and return the
 * pages that must be persisted (empty when nothing is new).
 *
 * Lives here rather than inline in the component so the "what counts as read"
 * rule stays in one testable place and cannot drift from the tracker.
 */
export function visitActivePage(
  tracker: ReadingTracker,
  page: number,
  pageCount: number
): number[] {
  if (!Number.isFinite(page) || !pageCount || pageCount <= 0) return []
  const target = Math.min(Math.max(1, Math.trunc(page)), pageCount)
  if (!tracker.visit(target)) return []
  return tracker.drainNewlyRead()
}

/**
 * Reading progress as a percentage of distinct pages actually read.
 *
 * Deliberately set-based: a student who visits pages 1, 2, 7 and 15 of a
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

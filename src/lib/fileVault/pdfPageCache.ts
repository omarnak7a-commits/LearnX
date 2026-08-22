/**
 * Page-level caching and render coordination for the PDF viewer.
 *
 * Two separate concerns, both framework-free so they can be unit tested:
 *
 *  1. `LruCache` — bounded in-memory cache. The viewer keeps a small window of
 *     decoded pages (previous / current / next) so stepping back and forth is
 *     instant, without letting a 400-page document pin every page in memory.
 *
 *  2. `RenderCoordinator` — guarantees that only the newest render may commit.
 *     pdf.js renders are asynchronous, so without this a slow render of page 2
 *     can finish *after* a fast render of page 10 and repaint the canvas with
 *     the wrong page. It also exposes the pdf.js `RenderTask.cancel()` hook so
 *     obsolete work is actually aborted rather than merely ignored.
 */

/** Minimal shape of a pdf.js RenderTask that we depend on. */
export interface CancellableTask {
  cancel: () => void
}

/** Bounded least-recently-used cache. */
export class LruCache<K, V> {
  private readonly max: number
  private readonly map = new Map<K, V>()
  private readonly onEvict?: (key: K, value: V) => void

  constructor(max: number, onEvict?: (key: K, value: V) => void) {
    this.max = Math.max(1, max)
    this.onEvict = onEvict
  }

  get size(): number {
    return this.map.size
  }

  keys(): K[] {
    return [...this.map.keys()]
  }

  has(key: K): boolean {
    return this.map.has(key)
  }

  get(key: K): V | undefined {
    if (!this.map.has(key)) return undefined
    // Refresh recency: delete + reinsert moves the key to the newest slot.
    const value = this.map.get(key) as V
    this.map.delete(key)
    this.map.set(key, value)
    return value
  }

  set(key: K, value: V): void {
    if (this.map.has(key)) this.map.delete(key)
    this.map.set(key, value)
    while (this.map.size > this.max) {
      const oldest = this.map.keys().next()
      if (oldest.done) break
      const evicted = this.map.get(oldest.value) as V
      this.map.delete(oldest.value)
      this.onEvict?.(oldest.value, evicted)
    }
  }

  delete(key: K): void {
    if (!this.map.has(key)) return
    const value = this.map.get(key) as V
    this.map.delete(key)
    this.onEvict?.(key, value)
  }

  clear(): void {
    for (const [key, value] of this.map) this.onEvict?.(key, value)
    this.map.clear()
  }
}

/**
 * Serialises renders so a stale one can never overwrite a newer page.
 *
 * Each `begin()` mints a monotonically increasing token and cancels whatever
 * was in flight. `isCurrent(token)` tells a completing render whether it is
 * still the newest request; only the newest may touch the canvas.
 */
export class RenderCoordinator {
  private token = 0
  private inFlight: CancellableTask | null = null

  /** Start a new render generation, cancelling any previous in-flight task. */
  begin(): number {
    this.cancelInFlight()
    this.token += 1
    return this.token
  }

  /** Register the cancellable pdf.js task for the current generation. */
  attach(token: number, task: CancellableTask): void {
    if (token !== this.token) {
      // Already superseded while the task was being created — abort now.
      task.cancel()
      return
    }
    this.inFlight = task
  }

  /** True when `token` is still the newest render generation. */
  isCurrent(token: number): boolean {
    return token === this.token
  }

  /** Mark the generation finished so we do not cancel a completed task. */
  settle(token: number): void {
    if (token === this.token) this.inFlight = null
  }

  cancelInFlight(): void {
    if (!this.inFlight) return
    const task = this.inFlight
    this.inFlight = null
    try {
      task.cancel()
    } catch {
      // pdf.js throws RenderingCancelledException from the render promise,
      // not from cancel(); any error here is not actionable.
    }
  }

  /** Invalidate everything (component unmount, document swap). */
  dispose(): void {
    this.cancelInFlight()
    this.token += 1
  }
}

/**
 * The window of pages worth keeping warm around the current page.
 * Returns in priority order: current first, then next, then previous.
 */
export function pageWindow(current: number, pageCount: number, radius = 1): number[] {
  if (pageCount <= 0) return []
  const clamp = (n: number) => Math.min(Math.max(1, n), pageCount)
  const seen = new Set<number>()
  const out: number[] = []
  const push = (n: number) => {
    const page = clamp(n)
    if (!seen.has(page)) {
      seen.add(page)
      out.push(page)
    }
  }
  push(current)
  for (let offset = 1; offset <= radius; offset++) {
    if (current + offset <= pageCount) push(current + offset)
    if (current - offset >= 1) push(current - offset)
  }
  return out
}

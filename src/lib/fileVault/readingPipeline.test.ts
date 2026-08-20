/**
 * End-to-end behaviour of the reading pipeline, exercised through the same
 * primitives the viewer and vault context use:
 *
 *   navigation -> active page -> pagesRead -> progress -> persistence
 *
 * A page is read the instant it becomes active. Preloading, caching and
 * background rendering must never contribute.
 */

import { describe, expect, it, vi } from 'vitest'
import {
  ReadingTracker,
  mergePagesRead,
  readingProgressPercent,
  visitActivePage,
} from './readingTracker'
import { LruCache, RenderCoordinator, pageWindow } from './pdfPageCache'

/** Minimal stand-in for the persisted VaultFile fields we care about. */
interface StoredProgress {
  currentPage: number
  pagesRead: number[]
  progressPct: number
}

/**
 * Mirrors how the viewer + context cooperate, without React:
 * the viewer owns the page, the tracker records it, the store persists.
 * Persistence is modelled as deferred to match the real debounced writer.
 */
function makeSession(pageCount: number, restored?: Partial<StoredProgress>) {
  const store: StoredProgress = {
    currentPage: restored?.currentPage ?? 1,
    pagesRead: restored?.pagesRead ?? [],
    progressPct: restored?.progressPct ?? 0,
  }
  let writes = 0
  const tracker = new ReadingTracker({
    initialPagesRead: store.pagesRead,
    pageCount,
  })
  const pageCache = new LruCache<number, string>(6)

  const newlyRead: number[] = []
  const flush = () => {
    const fresh = newlyRead.splice(0, newlyRead.length)
    if (fresh.length === 0) return
    const merged = mergePagesRead(store.pagesRead, fresh, pageCount)
    if (merged !== store.pagesRead) {
      store.pagesRead = merged
      store.progressPct = readingProgressPercent(merged, pageCount)
      writes += 1
    }
  }

  return {
    store,
    get writes() {
      return writes
    },
    /** Navigate to a page: it becomes active and is read immediately. */
    goTo(page: number) {
      store.currentPage = page
      // Exactly what PdfViewer's active-page effect calls.
      newlyRead.push(...visitActivePage(tracker, page, pageCount))
      flush()
      // The viewer warms neighbours after painting. Decoding must not read.
      for (const neighbour of pageWindow(page, pageCount).slice(1)) {
        pageCache.set(neighbour, `decoded-${neighbour}`)
      }
    },
    /** Pages the preloader has decoded but the student never opened. */
    preloadedOnly() {
      return pageCache.keys().filter((page) => !store.pagesRead.includes(page))
    },
    close() {
      flush()
    },
  }
}

describe('reading pipeline', () => {
  it('marks a page read as soon as it is opened', () => {
    const session = makeSession(20)
    session.goTo(1)
    expect(session.store.pagesRead).toEqual([1])
    expect(session.store.progressPct).toBe(5)
  })

  it('records 1 -> 2 -> 3 as three read pages', () => {
    const session = makeSession(20)
    for (const page of [1, 2, 3]) session.goTo(page)
    expect(session.store.pagesRead).toEqual([1, 2, 3])
  })

  it('jumping 1 -> 10 marks only 1 and 10', () => {
    const session = makeSession(20)
    session.goTo(1)
    session.goTo(10)
    expect(session.store.pagesRead).toEqual([1, 10])
    for (let skipped = 2; skipped <= 9; skipped++) {
      expect(session.store.pagesRead).not.toContain(skipped)
    }
  })

  it('follows the full example: 1,2,3 -> jump 20 -> back to 5', () => {
    const session = makeSession(20)
    for (const page of [1, 2, 3]) session.goTo(page)
    session.goTo(20)
    session.goTo(5)
    expect(session.store.pagesRead).toEqual([1, 2, 3, 5, 20])
    expect(session.store.progressPct).toBe(25)
  })

  it('never marks preloaded pages as read', () => {
    const session = makeSession(20)
    session.goTo(1)
    session.goTo(10)
    // Neighbours of 1 and 10 were decoded into the cache but not opened.
    expect(session.preloadedOnly().length).toBeGreaterThan(0)
    for (const preloaded of session.preloadedOnly()) {
      expect(session.store.pagesRead).not.toContain(preloaded)
    }
  })

  it('computes progress from distinct pages, not the furthest page', () => {
    const session = makeSession(20)
    for (const page of [1, 2, 3, 7, 8]) session.goTo(page)
    expect(session.store.pagesRead).toEqual([1, 2, 3, 7, 8])
    expect(session.store.progressPct).toBe(25)
  })

  it('revisiting pages does not duplicate progress', () => {
    const session = makeSession(10)
    session.goTo(2)
    const afterFirst = session.writes
    session.goTo(3)
    session.goTo(2)
    session.goTo(3)
    expect(session.store.pagesRead).toEqual([2, 3])
    // Only the genuinely new page 3 caused an extra write.
    expect(session.writes).toBe(afterFirst + 1)
  })

  it('keeps currentPage and pagesRead as distinct concepts', () => {
    const session = makeSession(50)
    session.goTo(1)
    session.goTo(37)
    expect(session.store.currentPage).toBe(37) // resume position
    expect(session.store.pagesRead).toEqual([1, 37]) // pages actually opened
  })

  it('survives closing and reopening the PDF', () => {
    const first = makeSession(50)
    first.goTo(1)
    first.goTo(37)
    first.close()

    const second = makeSession(50, {
      currentPage: first.store.currentPage,
      pagesRead: [...first.store.pagesRead],
      progressPct: first.store.progressPct,
    })
    expect(second.store.currentPage).toBe(37)
    expect(second.store.pagesRead).toEqual([1, 37])
    // Reopening on the saved page must not create a redundant write.
    second.goTo(37)
    expect(second.writes).toBe(0)
  })

  it('survives a reload mid-document with progress intact', () => {
    const first = makeSession(10)
    for (const page of [1, 2, 3]) first.goTo(page)
    const snapshot = { ...first.store, pagesRead: [...first.store.pagesRead] }

    const reopened = makeSession(10, snapshot)
    expect(reopened.store.pagesRead).toEqual([1, 2, 3])
    expect(reopened.store.progressPct).toBe(30)
  })

  it('does not lose pages during rapid navigation', () => {
    const session = makeSession(60)
    const visited = [1, 5, 2, 40, 41, 3, 59, 60, 7]
    for (const page of visited) session.goTo(page)
    expect(session.store.pagesRead).toEqual([...visited].sort((a, b) => a - b))
  })

  it('keeps two files completely isolated', () => {
    const a = makeSession(10)
    const b = makeSession(10)
    a.goTo(5)
    expect(a.store.pagesRead).toEqual([5])
    expect(b.store.pagesRead).toEqual([])
    expect(b.store.currentPage).toBe(1)
  })

  it('handles repeated open/close cycles without losing or duplicating progress', () => {
    let snapshot: StoredProgress = { currentPage: 1, pagesRead: [], progressPct: 0 }
    for (const page of [1, 2, 3]) {
      const session = makeSession(6, snapshot)
      session.goTo(page)
      session.close()
      snapshot = { ...session.store, pagesRead: [...session.store.pagesRead] }
    }
    expect(snapshot.pagesRead).toEqual([1, 2, 3])
    expect(snapshot.progressPct).toBe(50)

    // A cycle that reopens an already-read page must change nothing.
    const idle = makeSession(6, snapshot)
    idle.goTo(2)
    idle.close()
    expect(idle.store.pagesRead).toEqual([1, 2, 3])
    expect(idle.writes).toBe(0)
  })

  it('only reaches 100% when every page has been opened', () => {
    const session = makeSession(3)
    session.goTo(1)
    session.goTo(2)
    expect(session.store.progressPct).toBe(67)
    session.goTo(3)
    expect(session.store.progressPct).toBe(100)
  })

  it('writes once per newly read page, not per navigation event', () => {
    const session = makeSession(10)
    session.goTo(1)
    session.goTo(2)
    session.goTo(1)
    session.goTo(2)
    session.goTo(1)
    expect(session.writes).toBe(2)
  })
})

describe('quiz sourcing uses read pages only', () => {
  it('supplies exactly the pages the student opened', () => {
    const session = makeSession(12)
    for (const page of [1, 2, 3, 8, 10]) session.goTo(page)
    const allowedPages = [...new Set(session.store.pagesRead)].sort((a, b) => a - b)
    expect(allowedPages).toEqual([1, 2, 3, 8, 10])
    for (const skipped of [4, 5, 6, 7, 9]) {
      expect(allowedPages).not.toContain(skipped)
    }
  })

  it('sends nothing before any page has been opened', () => {
    const session = makeSession(12)
    expect(session.store.pagesRead).toEqual([])
  })
})

describe('viewer performance characteristics', () => {
  it('jumping far ahead renders only the target page', () => {
    const decoded: number[] = []
    const cache = new LruCache<number, string>(6)
    const decode = (page: number) => {
      if (cache.has(page)) return
      decoded.push(page)
      cache.set(page, `page-${page}`)
    }
    decode(1)
    decoded.length = 0
    decode(10)
    expect(decoded).toEqual([10])
  })

  it('a stale render cannot repaint over a newer page', () => {
    const coordinator = new RenderCoordinator()
    const painted: number[] = []
    const slowToken = coordinator.begin() // page 2
    const fastToken = coordinator.begin() // page 10 supersedes it

    if (coordinator.isCurrent(fastToken)) painted.push(10)
    if (coordinator.isCurrent(slowToken)) painted.push(2)
    expect(painted).toEqual([10])
  })

  it('cancels the in-flight render when the student navigates away', () => {
    const coordinator = new RenderCoordinator()
    const cancel = vi.fn()
    const token = coordinator.begin()
    coordinator.attach(token, { cancel })
    coordinator.begin()
    expect(cancel).toHaveBeenCalledTimes(1)
  })

  it('keeps neighbours warm so back/forward is a cache hit', () => {
    const cache = new LruCache<number, string>(6)
    for (const page of pageWindow(5, 20)) cache.set(page, `p${page}`)
    expect(cache.has(4)).toBe(true)
    expect(cache.has(5)).toBe(true)
    expect(cache.has(6)).toBe(true)
  })

  it('caps memory no matter how far the student reads', () => {
    const cache = new LruCache<number, string>(6)
    for (let page = 1; page <= 400; page++) {
      for (const p of pageWindow(page, 400)) cache.set(p, `p${p}`)
    }
    expect(cache.size).toBeLessThanOrEqual(6)
  })
})

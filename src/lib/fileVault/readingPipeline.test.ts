/**
 * End-to-end behaviour of the reading pipeline, exercised through the same
 * primitives the viewer and vault context use:
 *
 *   page render -> visibility -> dwell -> pagesRead -> progress -> persistence
 *
 * These are the regressions that made reading progress untrustworthy, so each
 * test names the real-world scenario it protects.
 */

import { describe, expect, it, vi } from 'vitest'
import {
  READ_PAGE_THRESHOLD_MS,
  ReadingTracker,
  mergePagesRead,
  readingProgressPercent,
} from './readingTracker'
import { LruCache, RenderCoordinator, pageWindow } from './pdfPageCache'

const T = READ_PAGE_THRESHOLD_MS

/** Minimal stand-in for the persisted VaultFile fields we care about. */
interface StoredProgress {
  currentPage: number
  pagesRead: number[]
  progressPct: number
}

/**
 * Mirrors how the viewer + context cooperate, without React:
 * the viewer owns the page, the tracker decides "read", the store persists.
 */
function makeSession(pageCount: number, restored?: Partial<StoredProgress>) {
  const store: StoredProgress = {
    currentPage: restored?.currentPage ?? 1,
    pagesRead: restored?.pagesRead ?? [],
    progressPct: restored?.progressPct ?? 0,
  }
  let writes = 0
  const tracker = new ReadingTracker({ initialPagesRead: store.pagesRead })
  let clock = 0

  const flush = () => {
    const fresh = tracker.drainNewlyRead()
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
    /** Navigate to a page (instant, as the viewer now behaves). */
    goTo(page: number) {
      store.currentPage = page
      tracker.enter(page, clock)
      flush()
    },
    /** Let time pass while the current page stays on screen. */
    dwell(ms: number) {
      clock += ms
      tracker.tick(clock)
      flush()
    },
    advance(ms: number) {
      clock += ms
    },
    hide() {
      tracker.pause(clock)
    },
    show() {
      tracker.resume(clock)
    },
    close() {
      tracker.leave(clock)
      flush()
    },
  }
}

describe('reading pipeline', () => {
  it('flipping through pages marks nothing as read', () => {
    const session = makeSession(20)
    for (const page of [1, 2, 3, 4, 5]) {
      session.goTo(page)
      session.dwell(200)
    }
    session.goTo(20)
    expect(session.store.pagesRead).toEqual([])
    expect(session.store.progressPct).toBe(0)
  })

  it('computes progress from distinct pages, not the furthest page', () => {
    const session = makeSession(20)
    for (const page of [1, 2, 3, 7, 8]) {
      session.goTo(page)
      session.dwell(T)
    }
    expect(session.store.pagesRead).toEqual([1, 2, 3, 7, 8])
    expect(session.store.progressPct).toBe(25)
  })

  it('keeps currentPage and pagesRead as distinct concepts', () => {
    // Student reads page 1, then jumps to 37 and stops there briefly.
    const session = makeSession(50)
    session.goTo(1)
    session.dwell(T)
    session.goTo(37)
    session.dwell(100)
    expect(session.store.currentPage).toBe(37) // resume position
    expect(session.store.pagesRead).toEqual([1]) // only page 1 was read
  })

  it('resumes at the saved page without re-reading it', () => {
    const first = makeSession(50)
    first.goTo(1)
    first.dwell(T)
    first.goTo(37)
    first.dwell(T)
    first.close()

    // Reopen with the persisted state.
    const second = makeSession(50, {
      currentPage: first.store.currentPage,
      pagesRead: first.store.pagesRead,
      progressPct: first.store.progressPct,
    })
    expect(second.store.currentPage).toBe(37)
    expect(second.store.pagesRead).toEqual([1, 37])
    // Reopening must not generate a redundant write for already-read pages.
    second.goTo(37)
    expect(second.writes).toBe(0)
  })

  it('survives a reload mid-document with progress intact', () => {
    const first = makeSession(10)
    for (const page of [1, 2, 3]) {
      first.goTo(page)
      first.dwell(T)
    }
    const snapshot = { ...first.store, pagesRead: [...first.store.pagesRead] }

    const reopened = makeSession(10, snapshot)
    expect(reopened.store.pagesRead).toEqual([1, 2, 3])
    expect(reopened.store.progressPct).toBe(30)
  })

  it('does not count time while the tab is hidden', () => {
    const session = makeSession(10)
    session.goTo(4)
    session.hide()
    session.advance(T * 5)
    session.dwell(0)
    expect(session.store.pagesRead).toEqual([])

    session.show()
    session.dwell(T)
    expect(session.store.pagesRead).toEqual([4])
  })

  it('revisiting a read page does not write again', () => {
    const session = makeSession(10)
    session.goTo(2)
    session.dwell(T)
    const writesAfterFirst = session.writes

    session.goTo(3)
    session.goTo(2)
    session.dwell(T)
    expect(session.store.pagesRead).toEqual([2])
    expect(session.writes).toBe(writesAfterFirst)
  })

  it('persists once per newly read page, not per navigation event', () => {
    const session = makeSession(10)
    // Lots of navigation, only two pages actually dwelled on.
    for (const page of [1, 2, 3, 4, 5, 6]) {
      session.goTo(page)
      session.dwell(50)
    }
    session.goTo(9)
    session.dwell(T)
    session.goTo(10)
    session.dwell(T)
    expect(session.store.pagesRead).toEqual([9, 10])
    expect(session.writes).toBe(2)
  })

  it('keeps two files completely isolated', () => {
    const a = makeSession(10)
    const b = makeSession(10)
    a.goTo(5)
    a.dwell(T)
    expect(a.store.pagesRead).toEqual([5])
    expect(b.store.pagesRead).toEqual([])
    expect(b.store.currentPage).toBe(1)
  })

  it('handles repeated open/close cycles without losing or duplicating progress', () => {
    let snapshot: StoredProgress = { currentPage: 1, pagesRead: [], progressPct: 0 }
    for (const page of [1, 2, 3]) {
      const session = makeSession(6, snapshot)
      session.goTo(page)
      session.dwell(T)
      session.close()
      snapshot = { ...session.store, pagesRead: [...session.store.pagesRead] }
    }
    expect(snapshot.pagesRead).toEqual([1, 2, 3])
    expect(snapshot.progressPct).toBe(50)

    // A fourth cycle that reads nothing must not change anything.
    const idle = makeSession(6, snapshot)
    idle.goTo(4)
    idle.close()
    expect(idle.store.pagesRead).toEqual([1, 2, 3])
  })

  it('only reaches 100% when every page has been read', () => {
    const session = makeSession(3)
    for (const page of [1, 2]) {
      session.goTo(page)
      session.dwell(T)
    }
    expect(session.store.progressPct).toBe(67)
    session.goTo(3)
    session.dwell(T)
    expect(session.store.progressPct).toBe(100)
  })
})

describe('quiz sourcing uses read pages only', () => {
  it('supplies exactly the pages the student read', () => {
    const session = makeSession(12)
    for (const page of [1, 2, 3, 8, 10]) {
      session.goTo(page)
      session.dwell(T)
    }
    // What generatePracticeQuiz sends as allowedPages.
    const allowedPages = [...new Set(session.store.pagesRead)].sort((a, b) => a - b)
    expect(allowedPages).toEqual([1, 2, 3, 8, 10])
    for (const skipped of [4, 5, 6, 7, 9]) {
      expect(allowedPages).not.toContain(skipped)
    }
  })

  it('sends nothing when no page has genuinely been read', () => {
    const session = makeSession(12)
    session.goTo(1)
    session.goTo(2)
    expect(session.store.pagesRead).toEqual([])
  })
})

describe('viewer performance characteristics', () => {
  it('jumping far ahead renders only the target page', () => {
    // Page 1 is warm; jumping to 10 must not decode 2..9.
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

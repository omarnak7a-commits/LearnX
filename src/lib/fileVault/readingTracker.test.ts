/**
 * Reading-tracker correctness.
 *
 * The rule under test: a page is read the moment it becomes the viewer's
 * ACTIVE page. There is no dwell time. Pages that are merely preloaded,
 * cached or rendered in the background never become active and so are never
 * read — which is what keeps a jump from page 3 to page 20 from marking the
 * seventeen pages in between.
 */

import { describe, expect, it } from 'vitest'
import {
  ReadingTracker,
  mergePagesRead,
  readingProgressPercent,
  visitActivePage,
} from './readingTracker'

describe('ReadingTracker', () => {
  it('marks the active page read immediately, with no waiting', () => {
    const tracker = new ReadingTracker()
    tracker.visit(1)
    expect(tracker.pagesRead).toEqual([1])
    expect(tracker.hasRead(1)).toBe(true)
  })

  it('records sequential navigation as it happens', () => {
    const tracker = new ReadingTracker()
    tracker.visit(1)
    tracker.visit(2)
    tracker.visit(3)
    expect(tracker.pagesRead).toEqual([1, 2, 3])
  })

  it('jumping 3 -> 20 records only 3 and 20, never the pages skipped', () => {
    const tracker = new ReadingTracker()
    tracker.visit(3)
    tracker.visit(20)
    expect(tracker.pagesRead).toEqual([3, 20])
    for (let skipped = 4; skipped <= 19; skipped++) {
      expect(tracker.hasRead(skipped)).toBe(false)
    }
  })

  it('records backward navigation too', () => {
    const tracker = new ReadingTracker()
    tracker.visit(20)
    tracker.visit(5)
    expect(tracker.pagesRead).toEqual([5, 20])
  })

  it('tracks non-sequential reading as distinct pages', () => {
    const tracker = new ReadingTracker()
    for (const page of [1, 2, 7, 15]) tracker.visit(page)
    expect(tracker.pagesRead).toEqual([1, 2, 7, 15])
  })

  it('never double counts a page visited twice', () => {
    const tracker = new ReadingTracker()
    tracker.visit(3)
    tracker.visit(4)
    tracker.visit(3)
    expect(tracker.pagesRead).toEqual([3, 4])
  })

  it('reports whether a visit was newly read, so writes can be skipped', () => {
    const tracker = new ReadingTracker()
    expect(tracker.visit(5)).toBe(true)
    expect(tracker.visit(5)).toBe(false)
  })

  it('re-visiting the active page is idempotent', () => {
    // Zoom changes and strict-mode double effects re-fire for the same page.
    const tracker = new ReadingTracker()
    tracker.visit(2)
    tracker.visit(2)
    tracker.visit(2)
    expect(tracker.pagesRead).toEqual([2])
    expect(tracker.drainNewlyRead()).toEqual([2])
  })

  it('exposes the active page', () => {
    const tracker = new ReadingTracker()
    tracker.visit(12)
    expect(tracker.activePage).toBe(12)
  })

  it('drains newly read pages exactly once', () => {
    const tracker = new ReadingTracker()
    tracker.visit(1)
    expect(tracker.drainNewlyRead()).toEqual([1])
    expect(tracker.drainNewlyRead()).toEqual([])
  })

  it('restores previously read pages without re-reporting them', () => {
    const tracker = new ReadingTracker({ initialPagesRead: [4, 9] })
    expect(tracker.pagesRead).toEqual([4, 9])
    expect(tracker.drainNewlyRead()).toEqual([])
    // Revisiting a restored page must not produce a redundant write.
    expect(tracker.visit(4)).toBe(false)
  })

  it('rejects page numbers outside the document', () => {
    const tracker = new ReadingTracker({ pageCount: 10 })
    expect(tracker.visit(0)).toBe(false)
    expect(tracker.visit(-3)).toBe(false)
    expect(tracker.visit(11)).toBe(false)
    expect(tracker.visit(Number.NaN)).toBe(false)
    expect(tracker.pagesRead).toEqual([])
  })

  it('accepts every page of the document', () => {
    const tracker = new ReadingTracker({ pageCount: 3 })
    for (const page of [1, 2, 3]) expect(tracker.visit(page)).toBe(true)
    expect(tracker.pagesRead).toEqual([1, 2, 3])
  })

  it('forceRead marks a page without making it active', () => {
    const tracker = new ReadingTracker()
    tracker.forceRead(8)
    expect(tracker.hasRead(8)).toBe(true)
    expect(tracker.activePage).toBeNull()
  })

  it('has no dwell-based API left', () => {
    // Guards against the 3-second threshold being reintroduced.
    const tracker = new ReadingTracker() as unknown as Record<string, unknown>
    for (const removed of ['enter', 'leave', 'tick', 'pause', 'resume', 'dwell']) {
      expect(tracker[removed]).toBeUndefined()
    }
  })
})

describe('visitActivePage (the step PdfViewer performs)', () => {
  it('returns the page to persist the first time it becomes active', () => {
    const tracker = new ReadingTracker()
    expect(visitActivePage(tracker, 1, 20)).toEqual([1])
  })

  it('returns nothing when the active page was already read', () => {
    const tracker = new ReadingTracker()
    visitActivePage(tracker, 4, 20)
    expect(visitActivePage(tracker, 4, 20)).toEqual([])
  })

  it('clamps a page beyond the document to the last page', () => {
    const tracker = new ReadingTracker()
    expect(visitActivePage(tracker, 99, 12)).toEqual([12])
  })

  it('clamps a page below 1 to the first page', () => {
    const tracker = new ReadingTracker()
    expect(visitActivePage(tracker, 0, 12)).toEqual([1])
  })

  it('does nothing before the document reports a page count', () => {
    const tracker = new ReadingTracker()
    expect(visitActivePage(tracker, 3, 0)).toEqual([])
    expect(tracker.pagesRead).toEqual([])
  })

  it('records every page of a rapid sequence, in order of first sight', () => {
    const tracker = new ReadingTracker()
    const persisted: number[] = []
    for (const page of [1, 9, 2, 9, 3]) {
      persisted.push(...visitActivePage(tracker, page, 20))
    }
    expect(persisted).toEqual([1, 9, 2, 3])
    expect(tracker.pagesRead).toEqual([1, 2, 3, 9])
  })
})

describe('readingProgressPercent', () => {
  it('counts distinct pages, not the furthest page reached', () => {
    // 20 pages, read {1,2,3,7,8} => 25%, never 40%.
    expect(readingProgressPercent([1, 2, 3, 7, 8], 20)).toBe(25)
  })

  it('is unaffected by duplicates and ordering', () => {
    expect(readingProgressPercent([8, 1, 1, 7, 2, 3, 8], 20)).toBe(25)
  })

  it('ignores pages outside the document', () => {
    expect(readingProgressPercent([1, 2, 999, 0, -3], 10)).toBe(20)
  })

  it('returns 0 for an unknown page count', () => {
    expect(readingProgressPercent([1, 2], 0)).toBe(0)
  })

  it('reaches 100 only when every page is read', () => {
    expect(readingProgressPercent([1, 2, 3], 4)).toBe(75)
    expect(readingProgressPercent([1, 2, 3, 4], 4)).toBe(100)
  })
})

describe('mergePagesRead', () => {
  it('adds new pages and keeps the list sorted and unique', () => {
    expect(mergePagesRead([3, 1], [2, 3])).toEqual([1, 2, 3])
  })

  it('returns the same reference when nothing changes', () => {
    const existing = [1, 2, 3]
    expect(mergePagesRead(existing, [2])).toBe(existing)
  })

  it('drops out-of-range pages', () => {
    expect(mergePagesRead([1], [0, -2, 5, 99], 10)).toEqual([1, 5])
  })
})

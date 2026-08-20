/**
 * Reading-tracker correctness.
 *
 * These encode the behaviour the product actually needs: a student who flips
 * through pages has NOT read them, a student who dwells has, and progress is
 * computed from the set of distinct pages rather than the highest page seen.
 */

import { describe, expect, it } from 'vitest'
import {
  READ_PAGE_THRESHOLD_MS,
  ReadingTracker,
  mergePagesRead,
  readingProgressPercent,
} from './readingTracker'

const T = READ_PAGE_THRESHOLD_MS

describe('ReadingTracker', () => {
  it('does not mark a page read before the dwell threshold', () => {
    const tracker = new ReadingTracker()
    tracker.enter(1, 0)
    tracker.tick(T - 1)
    expect(tracker.pagesRead).toEqual([])
    expect(tracker.hasRead(1)).toBe(false)
  })

  it('marks a page read once the threshold is reached', () => {
    const tracker = new ReadingTracker()
    tracker.enter(1, 0)
    tracker.tick(T)
    expect(tracker.pagesRead).toEqual([1])
  })

  it('does not mark pages read when the student flips through them', () => {
    // The exact regression: 1 -> 2 -> 3 -> 4 -> 5 -> 20 in ~1.2s total.
    const tracker = new ReadingTracker()
    let now = 0
    for (const page of [1, 2, 3, 4, 5]) {
      tracker.enter(page, now)
      now += 200
    }
    tracker.enter(20, now)
    expect(tracker.pagesRead).toEqual([])
  })

  it('marks only the page the student actually settled on', () => {
    const tracker = new ReadingTracker()
    let now = 0
    for (const page of [1, 2, 3]) {
      tracker.enter(page, now)
      now += 100
    }
    tracker.enter(20, now)
    tracker.tick(now + T)
    expect(tracker.pagesRead).toEqual([20])
  })

  it('tracks non-sequential reading as distinct pages', () => {
    const tracker = new ReadingTracker()
    let now = 0
    for (const page of [1, 2, 7, 15]) {
      tracker.enter(page, now)
      now += T
      tracker.tick(now)
    }
    expect(tracker.pagesRead).toEqual([1, 2, 7, 15])
  })

  it('never double counts a page visited twice', () => {
    const tracker = new ReadingTracker()
    tracker.enter(3, 0)
    tracker.tick(T)
    tracker.enter(4, T)
    tracker.enter(3, T + 100)
    tracker.tick(T + 100 + T)
    expect(tracker.pagesRead).toEqual([3])
  })

  it('re-entering the active page does not reset accumulated dwell', () => {
    // Zoom changes and strict-mode double effects re-fire enter() for the
    // same page; that must not prevent the page from ever being read.
    const tracker = new ReadingTracker()
    tracker.enter(2, 0)
    tracker.enter(2, T - 500)
    tracker.tick(T)
    expect(tracker.pagesRead).toEqual([2])
  })

  it('does not accrue dwell while paused (hidden tab)', () => {
    const tracker = new ReadingTracker()
    tracker.enter(1, 0)
    tracker.pause(1000)
    // A long time passes with the tab hidden.
    tracker.tick(1000 + T * 10)
    expect(tracker.pagesRead).toEqual([])

    tracker.resume(1000 + T * 10)
    tracker.tick(1000 + T * 10 + (T - 1000))
    expect(tracker.pagesRead).toEqual([1])
  })

  it('banks dwell time across a pause/resume cycle', () => {
    const tracker = new ReadingTracker()
    tracker.enter(5, 0)
    tracker.pause(T / 2) // half the threshold accrued
    tracker.resume(10_000) // long gap, not counted
    tracker.tick(10_000 + T / 2) // remaining half
    expect(tracker.pagesRead).toEqual([5])
  })

  it('promotes the page when navigating away after enough dwell', () => {
    const tracker = new ReadingTracker()
    tracker.enter(1, 0)
    tracker.enter(2, T) // leaving page 1 exactly at threshold
    expect(tracker.hasRead(1)).toBe(true)
    expect(tracker.hasRead(2)).toBe(false)
  })

  it('drains newly read pages exactly once', () => {
    const tracker = new ReadingTracker()
    tracker.enter(1, 0)
    tracker.tick(T)
    expect(tracker.drainNewlyRead()).toEqual([1])
    expect(tracker.drainNewlyRead()).toEqual([])
  })

  it('restores previously read pages without re-earning them', () => {
    const tracker = new ReadingTracker({ initialPagesRead: [4, 9] })
    expect(tracker.pagesRead).toEqual([4, 9])
    // Restored pages are not reported as newly read, so no redundant writes.
    expect(tracker.drainNewlyRead()).toEqual([])
  })

  it('reports the active page separately from read pages', () => {
    const tracker = new ReadingTracker()
    tracker.enter(12, 0)
    expect(tracker.activePage).toBe(12)
    expect(tracker.pagesRead).toEqual([])
  })

  it('honours a custom threshold', () => {
    const tracker = new ReadingTracker({ thresholdMs: 50 })
    tracker.enter(1, 0)
    tracker.tick(50)
    expect(tracker.pagesRead).toEqual([1])
  })
})

describe('readingProgressPercent', () => {
  it('counts distinct pages, not the furthest page reached', () => {
    // The spec example: 20 pages, read {1,2,3,7,8} => 25%, never 40%.
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

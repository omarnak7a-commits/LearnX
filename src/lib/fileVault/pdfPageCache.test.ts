/**
 * Page cache + render coordination.
 *
 * The race these guard against is real: pdf.js renders resolve out of order,
 * so a slow page-2 render finishing after a fast page-10 render used to
 * repaint the canvas with page 2 while the toolbar said 10.
 */

import { describe, expect, it, vi } from 'vitest'
import { LruCache, RenderCoordinator, pageWindow } from './pdfPageCache'

describe('LruCache', () => {
  it('returns cached values without recomputing', () => {
    const cache = new LruCache<number, string>(3)
    cache.set(1, 'one')
    expect(cache.get(1)).toBe('one')
    expect(cache.size).toBe(1)
  })

  it('evicts the least recently used entry past capacity', () => {
    const cache = new LruCache<number, string>(2)
    cache.set(1, 'a')
    cache.set(2, 'b')
    cache.set(3, 'c')
    expect(cache.has(1)).toBe(false)
    expect(cache.keys()).toEqual([2, 3])
  })

  it('treats a read as recent use', () => {
    const cache = new LruCache<number, string>(2)
    cache.set(1, 'a')
    cache.set(2, 'b')
    cache.get(1) // 1 is now newest, so 2 should be evicted next
    cache.set(3, 'c')
    expect(cache.has(1)).toBe(true)
    expect(cache.has(2)).toBe(false)
  })

  it('never grows beyond its bound', () => {
    const cache = new LruCache<number, number>(4)
    for (let i = 0; i < 500; i++) cache.set(i, i)
    expect(cache.size).toBe(4)
  })

  it('releases evicted resources so canvases can be reclaimed', () => {
    const freed: number[] = []
    const cache = new LruCache<number, string>(1, (key) => freed.push(key))
    cache.set(1, 'a')
    cache.set(2, 'b')
    expect(freed).toEqual([1])
  })

  it('releases everything on clear', () => {
    const freed: number[] = []
    const cache = new LruCache<number, string>(5, (key) => freed.push(key))
    cache.set(1, 'a')
    cache.set(2, 'b')
    cache.clear()
    expect(freed.sort()).toEqual([1, 2])
    expect(cache.size).toBe(0)
  })
})

describe('RenderCoordinator', () => {
  it('marks the newest generation current', () => {
    const coordinator = new RenderCoordinator()
    const first = coordinator.begin()
    expect(coordinator.isCurrent(first)).toBe(true)
  })

  it('invalidates a superseded generation', () => {
    const coordinator = new RenderCoordinator()
    const stale = coordinator.begin()
    const fresh = coordinator.begin()
    expect(coordinator.isCurrent(stale)).toBe(false)
    expect(coordinator.isCurrent(fresh)).toBe(true)
  })

  it('cancels the in-flight task when a new render starts', () => {
    const coordinator = new RenderCoordinator()
    const cancel = vi.fn()
    const token = coordinator.begin()
    coordinator.attach(token, { cancel })
    coordinator.begin()
    expect(cancel).toHaveBeenCalledTimes(1)
  })

  it('immediately cancels a task attached to an already-stale generation', () => {
    // Jumping 1 -> 10 while page 1's task object is still being constructed.
    const coordinator = new RenderCoordinator()
    const stale = coordinator.begin()
    coordinator.begin()
    const cancel = vi.fn()
    coordinator.attach(stale, { cancel })
    expect(cancel).toHaveBeenCalledTimes(1)
  })

  it('does not cancel a task that already settled', () => {
    const coordinator = new RenderCoordinator()
    const cancel = vi.fn()
    const token = coordinator.begin()
    coordinator.attach(token, { cancel })
    coordinator.settle(token)
    coordinator.begin()
    expect(cancel).not.toHaveBeenCalled()
  })

  it('stale renders cannot commit after a fast newer render', () => {
    // Simulates: start page 2 (slow), jump to page 10 (fast), page 2 resolves.
    const coordinator = new RenderCoordinator()
    const painted: number[] = []
    const slow = coordinator.begin()
    const fast = coordinator.begin()

    if (coordinator.isCurrent(fast)) painted.push(10)
    if (coordinator.isCurrent(slow)) painted.push(2)

    expect(painted).toEqual([10])
  })

  it('survives a cancel() that throws', () => {
    const coordinator = new RenderCoordinator()
    const token = coordinator.begin()
    coordinator.attach(token, {
      cancel: () => {
        throw new Error('already destroyed')
      },
    })
    expect(() => coordinator.begin()).not.toThrow()
  })

  it('dispose invalidates every outstanding generation', () => {
    const coordinator = new RenderCoordinator()
    const token = coordinator.begin()
    coordinator.dispose()
    expect(coordinator.isCurrent(token)).toBe(false)
  })
})

describe('pageWindow', () => {
  it('prioritises the current page, then next, then previous', () => {
    expect(pageWindow(5, 20)).toEqual([5, 6, 4])
  })

  it('clamps at the start of the document', () => {
    expect(pageWindow(1, 20)).toEqual([1, 2])
  })

  it('clamps at the end of the document', () => {
    expect(pageWindow(20, 20)).toEqual([20, 19])
  })

  it('handles a single-page document', () => {
    expect(pageWindow(1, 1)).toEqual([1])
  })

  it('returns nothing when the page count is unknown', () => {
    expect(pageWindow(1, 0)).toEqual([])
  })

  it('never returns duplicates', () => {
    const window = pageWindow(2, 3, 5)
    expect(new Set(window).size).toBe(window.length)
  })
})

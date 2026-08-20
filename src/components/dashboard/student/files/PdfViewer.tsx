import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { LruCache, RenderCoordinator, pageWindow } from '../../../../lib/fileVault/pdfPageCache'
import { ReadingTracker } from '../../../../lib/fileVault/readingTracker'

interface PdfViewerProps {
  doc: PDFDocumentProxy | null
  /** Page to open at. Only the *initial* value is honoured per document; the
   * viewer owns the page thereafter so navigation never waits on persistence. */
  initialPage: number
  onPageChange: (page: number) => void
  /** Fired when a page has genuinely been read (dwell threshold met). */
  onPageRead: (page: number) => void
  color: string
  onRequestReload?: () => void
  errorMessage?: string | null
  loadingMessage?: string | null
  /** Pauses reading accrual when the viewer tab is not on screen. */
  active?: boolean
}

type FitMode = 'width' | 'custom'

/** How many decoded pages to keep warm. Current + next + previous + slack. */
const PAGE_CACHE_SIZE = 6

/**
 * pdf.js reports a cancelled render by rejecting with RenderingCancelledException.
 * That is the normal result of navigating away mid-render, not a failure.
 */
function isCancellation(reason: unknown): boolean {
  if (!reason || typeof reason !== 'object') return false
  const name = (reason as { name?: unknown }).name
  return name === 'RenderingCancelledException' || name === 'AbortException'
}

/**
 * Real PDF page rendering via pdf.js canvas output — genuine pagination,
 * genuine zoom, and genuine "resume exactly where you stopped" behavior
 * (the workspace passes in the student's real last-read page).
 * Every page the student navigates to is reported back via `onPageRead`
 * so reading progress is driven entirely by real viewing activity.
 */
export default function PdfViewer({
  doc,
  initialPage,
  onPageChange,
  onPageRead,
  color,
  onRequestReload,
  errorMessage,
  loadingMessage,
  active = true,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(1.4)
  const [fitMode, setFitMode] = useState<FitMode>('width')
  const [rendering, setRendering] = useState(false)
  const [internalError, setInternalError] = useState<string | null>(null)

  const pageCount = doc?.numPages ?? 0
  const userError = errorMessage ?? null
  const error = userError ?? internalError

  // --- Page ownership -----------------------------------------------------
  // The viewer owns the displayed page. Previously the page number lived in
  // the vault context, so every click had to wait for a network PATCH and an
  // IndexedDB write before the UI could move. Persistence is now a
  // notification (onPageChange), never a precondition.
  const [page, setPage] = useState(() => Math.max(1, initialPage || 1))
  const pageRef = useRef(page)
  pageRef.current = page

  // Adopt the caller's resume position once per document, not on every
  // context update (which would fight the user's own navigation).
  const adoptedFor = useRef<PDFDocumentProxy | null>(null)
  useEffect(() => {
    if (!doc || adoptedFor.current === doc) return
    adoptedFor.current = doc
    const target = Math.min(Math.max(1, initialPage || 1), doc.numPages)
    setPage(target)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc])

  const goToPage = useCallback(
    (next: number) => {
      const limit = pageCount || Number.MAX_SAFE_INTEGER
      const target = Math.min(Math.max(1, Math.trunc(next) || 1), limit)
      if (target === pageRef.current) return
      pageRef.current = target
      setPage(target)
      onPageChange(target)
    },
    [pageCount, onPageChange]
  )

  // --- Render coordination ------------------------------------------------
  // One coordinator per mount: guarantees a stale render can never repaint
  // the canvas over a newer page, and cancels superseded pdf.js work.
  const coordinator = useMemo(() => new RenderCoordinator(), [])
  // Decoded pdf.js page objects, bounded so long documents cannot leak.
  const pageCache = useMemo(
    () => new LruCache<number, Awaited<ReturnType<PDFDocumentProxy['getPage']>>>(PAGE_CACHE_SIZE),
    []
  )

  useEffect(() => {
    // A new document invalidates every cached page and pending render.
    pageCache.clear()
    coordinator.cancelInFlight()
  }, [doc, pageCache, coordinator])

  useEffect(
    () => () => {
      coordinator.dispose()
      pageCache.clear()
    },
    [coordinator, pageCache]
  )

  const getPage = useCallback(
    async (target: number) => {
      const cached = pageCache.get(target)
      if (cached) return cached
      if (!doc) return null
      const loaded = await doc.getPage(target)
      pageCache.set(target, loaded)
      return loaded
    },
    [doc, pageCache]
  )

  // --- Reading tracking ---------------------------------------------------
  // Dwell-based, and deliberately decoupled from rendering: a page becomes
  // "read" only after it has been painted AND stayed on screen long enough.
  // Preloaded neighbours never reach this code path.
  const tracker = useMemo(() => new ReadingTracker(), [])
  const onPageReadRef = useRef(onPageRead)
  onPageReadRef.current = onPageRead

  const markVisible = useCallback(
    (visiblePage: number) => {
      tracker.enter(visiblePage, Date.now())
    },
    [tracker]
  )

  useEffect(() => {
    // A single interval per mount promotes the dwelling page and reports it
    // once. No timer is created per page, so navigation cannot leak timers.
    const id = window.setInterval(() => {
      tracker.tick(Date.now())
      for (const readPage of tracker.drainNewlyRead()) {
        onPageReadRef.current(readPage)
      }
    }, 500)
    return () => {
      window.clearInterval(id)
      tracker.leave(Date.now())
      for (const readPage of tracker.drainNewlyRead()) {
        onPageReadRef.current(readPage)
      }
    }
  }, [tracker])

  // Stop accruing reading time when the tab is hidden or the viewer is not
  // the visible workspace tab.
  useEffect(() => {
    const sync = () => {
      const visible = active && (typeof document === 'undefined' || !document.hidden)
      if (visible) tracker.resume(Date.now())
      else tracker.pause(Date.now())
    }
    sync()
    document.addEventListener('visibilitychange', sync)
    return () => document.removeEventListener('visibilitychange', sync)
  }, [active, tracker])

  // Render the visible page. Only the newest generation may touch the canvas,
  // so jumping 1 -> 10 paints page 10 and abandons page 1 rather than letting
  // a late-resolving render overwrite it.
  useEffect(() => {
    if (!doc) return
    const token = coordinator.begin()
    let disposed = false

    async function render() {
      if (!doc || !canvasRef.current || !containerRef.current) return
      setRendering(true)
      setInternalError(null)
      try {
        const targetPage = Math.min(Math.max(1, page), doc.numPages)
        const pdfPage = await getPage(targetPage)
        if (!pdfPage || disposed || !coordinator.isCurrent(token)) return

        const containerWidth = containerRef.current.clientWidth - 32
        const baseViewport = pdfPage.getViewport({ scale: 1 })
        const widthScale = containerWidth > 0 ? containerWidth / baseViewport.width : zoom
        const effectiveScale = fitMode === 'width' ? widthScale : zoom
        const viewport = pdfPage.getViewport({ scale: effectiveScale })
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        // Use devicePixelRatio for crisp text on hi-dpi displays.
        const dpr = Math.min(typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1, 2)
        canvas.width = Math.ceil(viewport.width * dpr)
        canvas.height = Math.ceil(viewport.height * dpr)
        canvas.style.width = `${Math.ceil(viewport.width)}px`
        canvas.style.height = `${Math.ceil(viewport.height)}px`
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

        const task = pdfPage.render({
          canvas,
          canvasContext: ctx,
          viewport,
          transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
        })
        coordinator.attach(token, task)
        await task.promise
        coordinator.settle(token)

        if (disposed || !coordinator.isCurrent(token)) return
        // Rendering only makes the page *visible*. Whether it counts as read
        // is decided by dwell time, tracked separately below.
        markVisible(targetPage)
      } catch (reason) {
        // A cancelled render is the expected outcome of fast navigation and
        // must not surface as an error to the student.
        if (isCancellation(reason)) return
        if (!disposed && coordinator.isCurrent(token)) {
          setInternalError(
            reason instanceof Error
              ? reason.message
              : 'The PDF could not be rendered. The file may be corrupt or password-protected.'
          )
        }
      } finally {
        if (!disposed && coordinator.isCurrent(token)) setRendering(false)
      }
    }
    render()
    return () => {
      disposed = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc, page, zoom, fitMode, getPage, coordinator])

  // Warm the neighbouring pages *after* the visible one is painted, at idle
  // priority. Preloading decodes a page but never marks it read.
  useEffect(() => {
    if (!doc || rendering) return
    let cancelled = false
    const handle = window.setTimeout(() => {
      const neighbours = pageWindow(page, doc.numPages).slice(1)
      neighbours.forEach((target) => {
        if (cancelled || pageCache.has(target)) return
        void getPage(target).catch(() => undefined)
      })
    }, 150)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [doc, page, rendering, getPage, pageCache])

  const clampedCurrent = Math.min(Math.max(1, page), Math.max(1, pageCount))

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div
        className="flex items-center justify-between gap-2 px-3 py-2.5 border-b flex-wrap"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex items-center gap-1.5">
          <IconButton
            onClick={() => goToPage(page - 1)}
            disabled={page <= 1}
            label="Previous page"
          >
            ‹
          </IconButton>
          <PageJump
            currentPage={clampedCurrent}
            pageCount={pageCount}
            onPageChange={goToPage}
          />
          <IconButton
            onClick={() => goToPage(page + 1)}
            disabled={page >= pageCount}
            label="Next page"
          >
            ›
          </IconButton>
        </div>
        <div className="flex items-center gap-1.5">
          <IconButton
            onClick={() => {
              setFitMode('custom')
              setZoom((z) => Math.max(0.5, z - 0.15))
            }}
            label="Zoom out"
            disabled={!doc}
          >
            −
          </IconButton>
          <span
            className="text-xs font-mono w-12 text-center"
            style={{ color: 'var(--muted-foreground)' }}
          >
            {fitMode === 'width' ? 'Fit' : `${Math.round(zoom * 100)}%`}
          </span>
          <IconButton
            onClick={() => {
              setFitMode('custom')
              setZoom((z) => Math.min(3, z + 0.15))
            }}
            label="Zoom in"
            disabled={!doc}
          >
            +
          </IconButton>
          <IconButton
            onClick={() => setFitMode((m) => (m === 'width' ? 'custom' : 'width'))}
            label={fitMode === 'width' ? 'Switch to manual zoom' : 'Fit to width'}
            disabled={!doc}
          >
            ⇔
          </IconButton>
        </div>
      </div>

      {/* Canvas / states */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto flex items-start justify-center p-4 scrollbar-thin"
        style={{ background: 'var(--tint-1)' }}
      >
        {!doc && !error ? (
          <PdfViewerLoading message={loadingMessage} />
        ) : error ? (
          <PdfViewerError message={error} onRetry={onRequestReload} />
        ) : doc ? (
          <motion.div
            key={`${page}-${zoom}-${fitMode}`}
            initial={{ opacity: 0.4 }}
            animate={{ opacity: rendering ? 0.6 : 1 }}
            transition={{ duration: 0.18 }}
            className="rounded-lg overflow-hidden shadow-lg"
            style={{ boxShadow: `0 8px 32px ${color}22` }}
          >
            <canvas ref={canvasRef} />
          </motion.div>
        ) : null}
      </div>
    </div>
  )
}

function PageJump({
  currentPage,
  pageCount,
  onPageChange,
}: {
  currentPage: number
  pageCount: number
  onPageChange: (page: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(String(currentPage))

  useEffect(() => {
    setDraft(String(currentPage))
  }, [currentPage])

  if (pageCount <= 1) {
    return (
      <span className="text-xs font-mono px-2" style={{ color: 'var(--muted-foreground)' }}>
        {currentPage} / {pageCount}
      </span>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="text-xs font-mono px-2 py-1 rounded-md"
        style={{ color: 'var(--muted-foreground)', background: 'var(--tint-2)' }}
        aria-label="Jump to page"
      >
        {currentPage} / {pageCount}
      </button>
      {open && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const next = Math.min(pageCount, Math.max(1, Number(draft) || 1))
            onPageChange(next)
            setOpen(false)
          }}
          className="absolute z-20 top-full mt-1 right-0 flex items-center gap-1.5 px-2 py-1.5 rounded-lg shadow-lg"
          style={{ background: 'var(--background)', border: '1px solid var(--border-subtle)' }}
        >
          <input
            type="number"
            min={1}
            max={pageCount}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="input-field w-16 px-2 py-1 rounded-md text-xs"
            autoFocus
          />
          <button
            type="submit"
            className="text-xs font-semibold px-2 py-1 rounded-md"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            Go
          </button>
        </form>
      )}
    </div>
  )
}

function PdfViewerLoading({ message }: { message?: string | null }) {
  return (
    <div className="flex flex-col items-center justify-center h-full w-full gap-3">
      <div
        className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
        style={{ borderColor: 'var(--tint-3)', borderTopColor: 'var(--primary)' }}
        aria-hidden="true"
      />
      <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
        {message ?? 'Loading document...'}
      </p>
    </div>
  )
}

function PdfViewerError({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div
      className="flex flex-col items-center justify-center h-full w-full gap-3 text-center px-6"
      role="alert"
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center text-xl"
        style={{ background: 'var(--tint-3)', color: 'var(--danger)' }}
        aria-hidden="true"
      >
        !
      </div>
      <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
        We couldn't open this PDF.
      </p>
      <p className="text-xs max-w-sm" style={{ color: 'var(--muted-foreground)' }}>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs font-semibold px-3 py-1.5 rounded-lg"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Try again
        </button>
      )}
    </div>
  )
}

function IconButton({
  children,
  onClick,
  disabled,
  label,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  label: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="w-7 h-7 rounded-lg flex items-center justify-center text-sm font-bold transition-opacity"
      style={{
        background: 'var(--tint-2)',
        color: 'var(--foreground)',
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {children}
    </button>
  )
}

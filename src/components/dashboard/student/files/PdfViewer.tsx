import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import type { PDFDocumentProxy } from 'pdfjs-dist'

interface PdfViewerProps {
  doc: PDFDocumentProxy | null
  currentPage: number
  onPageChange: (page: number) => void
  onPageRead: (page: number) => void
  color: string
  onRequestReload?: () => void
  errorMessage?: string | null
  loadingMessage?: string | null
}

type FitMode = 'width' | 'custom'

/**
 * Real PDF page rendering via pdf.js canvas output — genuine pagination,
 * genuine zoom, and genuine "resume exactly where you stopped" behavior
 * (the workspace passes in the student's real last-read `currentPage`).
 * Every page the student navigates to is reported back via `onPageRead`
 * so reading progress is driven entirely by real viewing activity.
 */
export default function PdfViewer({
  doc,
  currentPage,
  onPageChange,
  onPageRead,
  color,
  onRequestReload,
  errorMessage,
  loadingMessage,
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

  // Re-render whenever the page, the document, or the zoom changes.
  useEffect(() => {
    let cancelled = false
    async function render() {
      if (!doc || !canvasRef.current || !containerRef.current) return
      setRendering(true)
      setInternalError(null)
      try {
        const targetPage = Math.min(Math.max(1, currentPage), doc.numPages)
        const page = await doc.getPage(targetPage)
        if (cancelled) return
        const containerWidth = containerRef.current.clientWidth - 32
        const baseViewport = page.getViewport({ scale: 1 })
        const widthScale = containerWidth > 0 ? containerWidth / baseViewport.width : zoom
        const effectiveScale = fitMode === 'width' ? widthScale : zoom
        const viewport = page.getViewport({ scale: effectiveScale })
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
        await page.render({
          canvas,
          canvasContext: ctx,
          viewport,
          transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
        }).promise
        if (!cancelled) {
          onPageRead(targetPage)
        }
      } catch (reason) {
        if (!cancelled) {
          setInternalError(
            reason instanceof Error
              ? reason.message
              : 'The PDF could not be rendered. The file may be corrupt or password-protected.'
          )
        }
      } finally {
        if (!cancelled) setRendering(false)
      }
    }
    render()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc, currentPage, zoom, fitMode])

  const clampedCurrent = Math.min(Math.max(1, currentPage), Math.max(1, pageCount))

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div
        className="flex items-center justify-between gap-2 px-3 py-2.5 border-b flex-wrap"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex items-center gap-1.5">
          <IconButton
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            label="Previous page"
          >
            ‹
          </IconButton>
          <PageJump
            currentPage={clampedCurrent}
            pageCount={pageCount}
            onPageChange={onPageChange}
          />
          <IconButton
            onClick={() => onPageChange(Math.min(pageCount, currentPage + 1))}
            disabled={currentPage >= pageCount}
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
            key={`${currentPage}-${zoom}-${fitMode}`}
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

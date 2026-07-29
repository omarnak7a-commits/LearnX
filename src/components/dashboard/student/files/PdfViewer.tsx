import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import type { PDFDocumentProxy } from 'pdfjs-dist'

interface PdfViewerProps {
  doc: PDFDocumentProxy | null
  currentPage: number
  onPageChange: (page: number) => void
  onPageRead: (page: number) => void
  color: string
}

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
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [zoom, setZoom] = useState(1)
  const [rendering, setRendering] = useState(false)

  const pageCount = doc?.numPages ?? 0

  useEffect(() => {
    let cancelled = false
    async function render() {
      if (!doc || !canvasRef.current) return
      setRendering(true)
      try {
        const page = await doc.getPage(Math.min(Math.max(1, currentPage), doc.numPages))
        if (cancelled) return
        const viewport = page.getViewport({ scale: zoom * 1.4 })
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        canvas.width = viewport.width
        canvas.height = viewport.height
        await page.render({ canvas, canvasContext: ctx, viewport }).promise
        if (!cancelled) {
          onPageRead(currentPage)
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
  }, [doc, currentPage, zoom])

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
          <span className="text-xs font-mono px-2" style={{ color: 'var(--muted-foreground)' }}>
            {currentPage} / {pageCount}
          </span>
          <IconButton
            onClick={() => onPageChange(Math.min(pageCount, currentPage + 1))}
            disabled={currentPage >= pageCount}
            label="Next page"
          >
            ›
          </IconButton>
        </div>
        <div className="flex items-center gap-1.5">
          <IconButton onClick={() => setZoom((z) => Math.max(0.6, z - 0.15))} label="Zoom out">
            −
          </IconButton>
          <span
            className="text-xs font-mono w-10 text-center"
            style={{ color: 'var(--muted-foreground)' }}
          >
            {Math.round(zoom * 100)}%
          </span>
          <IconButton onClick={() => setZoom((z) => Math.min(2, z + 0.15))} label="Zoom in">
            +
          </IconButton>
        </div>
      </div>

      {/* Canvas */}
      <div
        className="flex-1 overflow-auto flex items-start justify-center p-4 scrollbar-thin"
        style={{ background: 'var(--tint-1)' }}
      >
        {!doc ? (
          <div
            className="flex items-center justify-center h-full text-sm"
            style={{ color: 'var(--muted-foreground)' }}
          >
            Loading document...
          </div>
        ) : (
          <motion.div
            key={currentPage}
            initial={{ opacity: 0.4 }}
            animate={{ opacity: rendering ? 0.6 : 1 }}
            className="rounded-lg overflow-hidden shadow-lg"
            style={{ boxShadow: `0 8px 32px ${color}22` }}
          >
            <canvas ref={canvasRef} />
          </motion.div>
        )}
      </div>
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

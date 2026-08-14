import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'

// Vite bundles the pdf.js worker as a real asset via the `?url` import
// convention; this avoids CORS/module-worker issues that plague CDN-hosted
// worker scripts and keeps everything self-contained in the app bundle.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString()

export interface ExtractedPage {
  page: number
  text: string
  wordCount: number
}

export interface ExtractedPdf {
  pageCount: number
  pages: ExtractedPage[]
  fullText: string
  wordCount: number
  thumbnailDataUrl: string | null
}

function countWords(text: string): number {
  const trimmed = text.trim()
  if (!trimmed) return 0
  return trimmed.split(/\s+/).length
}

/**
 * Loads a PDF from an ArrayBuffer/Blob and extracts real per-page text
 * plus a rendered thumbnail of the first page. This is the only place in
 * the app that touches pdf.js directly — everything downstream (AI
 * analysis, search, reading progress) works off the returned plain data.
 */
export async function extractPdf(data: ArrayBuffer): Promise<ExtractedPdf> {
  const loadingTask = pdfjsLib.getDocument({ data })
  const doc: PDFDocumentProxy = await loadingTask.promise

  const pages: ExtractedPage[] = []
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i)
    const content = await page.getTextContent()
    // Preserve the line boundaries reported by pdf.js. Source cleaning is
    // intentionally line-oriented (headers/footers are normally separate
    // text rows); flattening every item with spaces made a copyright footer
    // part of the same "line" as the lesson and caused the whole page to be
    // discarded as boilerplate.
    const text = content.items
      .map((item) => {
        if (!('str' in item)) return ''
        return `${item.str}${item.hasEOL ? '\n' : ' '}`
      })
      .join('')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/[ \t]{2,}/g, ' ')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    pages.push({ page: i, text, wordCount: countWords(text) })
  }

  const fullText = pages.map((p) => p.text).join('\n\n')

  let thumbnailDataUrl: string | null = null
  try {
    thumbnailDataUrl = await renderPageThumbnail(doc, 1)
  } catch {
    thumbnailDataUrl = null
  }

  return {
    pageCount: doc.numPages,
    pages,
    fullText,
    wordCount: countWords(fullText),
    thumbnailDataUrl,
  }
}

/** Renders a given page to a small PNG data URL for use as a card thumbnail. */
export async function renderPageThumbnail(
  doc: PDFDocumentProxy,
  pageNumber: number,
  targetWidth = 320
): Promise<string> {
  const page = await doc.getPage(pageNumber)
  const unscaledViewport = page.getViewport({ scale: 1 })
  const scale = targetWidth / unscaledViewport.width
  const viewport = page.getViewport({ scale })

  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(viewport.width)
  canvas.height = Math.ceil(viewport.height)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D context unavailable')

  await page.render({ canvas, canvasContext: ctx, viewport }).promise
  return canvas.toDataURL('image/png')
}

/** Loads a PDF document proxy for interactive viewing (paging, zoom, thumbnails on demand). */
export async function loadPdfDocument(data: ArrayBuffer): Promise<PDFDocumentProxy> {
  const loadingTask = pdfjsLib.getDocument({ data })
  return loadingTask.promise
}

/** Estimated reading time in minutes, based on an average academic reading pace of ~200 words/min. */
export function estimateReadingMinutes(wordCount: number): number {
  return Math.max(1, Math.round(wordCount / 200))
}

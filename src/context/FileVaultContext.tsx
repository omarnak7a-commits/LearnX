import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type {
  FileBookmark,
  StudentNote,
  VaultFile,
  VaultQuestionType,
  VaultQuizAttempt,
  VaultQuizQuestion,
} from '../types/fileVault'
import { readingPercent, isFullyRead } from '../types/fileVault'
import { getFileVaultStorage } from '../lib/fileVault/storage'
import { ensureSeeded } from '../lib/fileVault/seedLibrary'
import { extractPdf, estimateReadingMinutes, loadPdfDocument } from '../lib/fileVault/pdfEngine'
import { analyzeDocument, generateQuestions, hashString } from '../lib/fileVault/textAnalysis'
import { weekKeyFor, weekLabelFor } from '../lib/fileVault/weeks'
import type { PDFDocumentProxy } from 'pdfjs-dist'

const COURSE_COLORS: Record<string, { color: string; icon: string }> = {
  default: { color: '#2DD4BF', icon: '📄' },
}

const PALETTE: Array<{ color: string; icon: string }> = [
  { color: '#2DD4BF', icon: '📄' },
  { color: '#a855f7', icon: '📘' },
  { color: '#f59e0b', icon: '📙' },
  { color: '#38bdf8', icon: '📗' },
  { color: '#22c55e', icon: '📕' },
  { color: '#FF7E36', icon: '📓' },
]

function pickPalette(seed: string) {
  const idx = Math.abs(hashString(seed)) % PALETTE.length
  return PALETTE[idx] ?? COURSE_COLORS.default
}

interface FileVaultContextValue {
  files: VaultFile[]
  loading: boolean
  uploadingCount: number
  uploadProgress: Record<string, number>
  uploadFile: (
    file: globalThis.File,
    meta?: { course?: string; doctorName?: string }
  ) => Promise<void>
  deleteFile: (id: string) => Promise<void>
  toggleFavorite: (id: string) => Promise<void>
  togglePinned: (id: string) => Promise<void>
  addBookmark: (id: string, page: number, label: string) => Promise<void>
  removeBookmark: (id: string, bookmarkId: string) => Promise<void>
  addNote: (id: string, page: number, text: string) => Promise<void>
  markPageRead: (id: string, page: number) => Promise<void>
  setCurrentPage: (id: string, page: number) => Promise<void>
  addStudyTime: (id: string, seconds: number) => Promise<void>
  getPdfDocument: (id: string) => Promise<PDFDocumentProxy | null>
  generatePracticeQuiz: (id: string, count?: number) => VaultQuizQuestion[]
  generateExam: (id: string, count: number, types: VaultQuestionType[]) => VaultQuizQuestion[]
  recordAttempt: (
    id: string,
    kind: 'practice' | 'exam',
    scorePct: number,
    totalQuestions: number,
    correctCount: number,
    coveragePages: number[]
  ) => Promise<void>
}

const FileVaultContext = createContext<FileVaultContextValue | null>(null)

function reevaluateStatus(file: VaultFile): VaultFile {
  const pct = readingPercent(file)
  const status: VaultFile['status'] =
    pct >= 100
      ? 'completed'
      : pct > 0
        ? 'in-progress'
        : file.pagesRead.length > 0
          ? 'viewed'
          : 'not-started'
  return {
    ...file,
    progressPct: pct,
    status,
    completedAt: status === 'completed' ? (file.completedAt ?? Date.now()) : file.completedAt,
  }
}

export function FileVaultProvider({ children }: { children: ReactNode }) {
  const [files, setFiles] = useState<VaultFile[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({})
  const storage = useMemo(() => getFileVaultStorage(), [])
  const pdfDocCache = useRef<Map<string, PDFDocumentProxy>>(new Map())

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await ensureSeeded()
      const list = await storage.listFiles()
      if (!cancelled) {
        setFiles(list.sort((a, b) => b.uploadedAt - a.uploadedAt))
        setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [storage])

  const persist = useCallback(
    async (file: VaultFile) => {
      await storage.putFile(file)
      setFiles((prev) => {
        const idx = prev.findIndex((f) => f.id === file.id)
        if (idx === -1) return [file, ...prev]
        const next = [...prev]
        next[idx] = file
        return next
      })
    },
    [storage]
  )

  const uploadFile = useCallback(
    async (rawFile: globalThis.File, meta?: { course?: string; doctorName?: string }) => {
      const id = `file-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      setUploadProgress((prev) => ({ ...prev, [id]: 0 }))

      const arrayBuffer = await rawFile.arrayBuffer()
      setUploadProgress((prev) => ({ ...prev, [id]: 35 }))

      await storage.putBlob(id, new Blob([arrayBuffer], { type: 'application/pdf' }))
      setUploadProgress((prev) => ({ ...prev, [id]: 55 }))

      const extracted = await extractPdf(arrayBuffer.slice(0))
      setUploadProgress((prev) => ({ ...prev, [id]: 75 }))

      const title = rawFile.name.replace(/\.pdf$/i, '')
      const analysis = analyzeDocument(id, title, extracted.pages)
      setUploadProgress((prev) => ({ ...prev, [id]: 95 }))

      const now = Date.now()
      const palette = pickPalette(meta?.course ?? title)

      const file: VaultFile = {
        id,
        name: rawFile.name,
        title,
        course: meta?.course ?? 'Uncategorized',
        doctorName: meta?.doctorName ?? 'Self-uploaded',
        weekKey: weekKeyFor(new Date(now)),
        weekLabel: weekLabelFor(new Date(now)),
        uploadedAt: now,
        sizeBytes: rawFile.size,
        pageCount: extracted.pageCount,
        wordCount: extracted.wordCount,
        estimatedReadingMinutes: estimateReadingMinutes(extracted.wordCount),
        thumbnailDataUrl: extracted.thumbnailDataUrl,
        color: palette.color,
        icon: palette.icon,

        status: 'not-started',
        pagesRead: [],
        currentPage: 1,
        progressPct: 0,
        studyTimeSeconds: 0,
        lastViewedAt: null,
        completedAt: null,

        favorite: false,
        pinned: false,
        bookmarks: [],
        notes: [],
        tags: [],

        analysis,
        analysisState: 'ready',
        pagesText: extracted.pages,

        quizAttempts: [],
        examAttempts: [],
      }

      await persist(file)
      setUploadProgress((prev) => ({ ...prev, [id]: 100 }))
      setTimeout(() => {
        setUploadProgress((prev) => {
          const next = { ...prev }
          delete next[id]
          return next
        })
      }, 900)
    },
    [storage, persist]
  )

  const deleteFile = useCallback(
    async (id: string) => {
      await storage.deleteFile(id)
      await storage.deleteBlob(id)
      pdfDocCache.current.delete(id)
      setFiles((prev) => prev.filter((f) => f.id !== id))
    },
    [storage]
  )

  const mutate = useCallback(
    async (id: string, updater: (file: VaultFile) => VaultFile) => {
      const current = files.find((f) => f.id === id)
      if (!current) return
      const next = reevaluateStatus(updater(current))
      await persist(next)
    },
    [files, persist]
  )

  const toggleFavorite = useCallback(
    (id: string) => mutate(id, (f) => ({ ...f, favorite: !f.favorite })),
    [mutate]
  )

  const togglePinned = useCallback(
    (id: string) => mutate(id, (f) => ({ ...f, pinned: !f.pinned })),
    [mutate]
  )

  const addBookmark = useCallback(
    (id: string, page: number, label: string) =>
      mutate(id, (f) => {
        const bookmark: FileBookmark = {
          id: `bm-${Date.now()}`,
          page,
          label: label || `Page ${page}`,
          createdAt: Date.now(),
        }
        return { ...f, bookmarks: [...f.bookmarks, bookmark] }
      }),
    [mutate]
  )

  const removeBookmark = useCallback(
    (id: string, bookmarkId: string) =>
      mutate(id, (f) => ({ ...f, bookmarks: f.bookmarks.filter((b) => b.id !== bookmarkId) })),
    [mutate]
  )

  const addNote = useCallback(
    (id: string, page: number, text: string) =>
      mutate(id, (f) => {
        const note: StudentNote = { id: `note-${Date.now()}`, page, text, createdAt: Date.now() }
        return { ...f, notes: [...f.notes, note] }
      }),
    [mutate]
  )

  const markPageRead = useCallback(
    (id: string, page: number) =>
      mutate(id, (f) => {
        const pagesRead = f.pagesRead.includes(page) ? f.pagesRead : [...f.pagesRead, page]
        return { ...f, pagesRead, lastViewedAt: Date.now(), currentPage: page }
      }),
    [mutate]
  )

  const setCurrentPage = useCallback(
    (id: string, page: number) =>
      mutate(id, (f) => ({ ...f, currentPage: page, lastViewedAt: Date.now() })),
    [mutate]
  )

  const addStudyTime = useCallback(
    (id: string, seconds: number) =>
      mutate(id, (f) => ({ ...f, studyTimeSeconds: f.studyTimeSeconds + seconds })),
    [mutate]
  )

  const getPdfDocument = useCallback(
    async (id: string): Promise<PDFDocumentProxy | null> => {
      const cached = pdfDocCache.current.get(id)
      if (cached) return cached
      const blob = await storage.getBlob(id)
      if (!blob) return null
      const buffer = await blob.arrayBuffer()
      const doc = await loadPdfDocument(buffer)
      pdfDocCache.current.set(id, doc)
      return doc
    },
    [storage]
  )

  const generatePracticeQuiz = useCallback(
    (id: string, count = 6): VaultQuizQuestion[] => {
      const file = files.find((f) => f.id === id)
      if (!file || !file.analysis) return []
      // Practice quizzes ONLY draw from pages already viewed — never
      // generate questions from unread sections, per the spec.
      const allowedPages = new Set(file.pagesRead)
      if (allowedPages.size === 0) return []
      const seed = hashString(id) + file.pagesRead.length
      return generateQuestions(file.pagesText, allowedPages, seed, count)
    },
    [files]
  )

  const generateExam = useCallback(
    (id: string, count: number, types: VaultQuestionType[]): VaultQuizQuestion[] => {
      const file = files.find((f) => f.id === id)
      if (!file || !file.analysis) return []
      if (!isFullyRead(file)) return []
      const allowedPages = new Set(Array.from({ length: file.pageCount }, (_, i) => i + 1))
      const seed = hashString(id) + 7
      const all = generateQuestions(file.pagesText, allowedPages, seed, count * 2)
      const filtered = types.length > 0 ? all.filter((q) => types.includes(q.type)) : all
      return filtered.slice(0, count)
    },
    [files]
  )

  const recordAttempt = useCallback(
    (
      id: string,
      kind: 'practice' | 'exam',
      scorePct: number,
      totalQuestions: number,
      correctCount: number,
      coveragePages: number[]
    ) =>
      mutate(id, (f) => {
        const attempt: VaultQuizAttempt = {
          id: `attempt-${Date.now()}`,
          kind,
          takenAt: Date.now(),
          scorePct,
          totalQuestions,
          correctCount,
          coveragePages,
        }
        return kind === 'exam'
          ? { ...f, examAttempts: [attempt, ...f.examAttempts] }
          : { ...f, quizAttempts: [attempt, ...f.quizAttempts] }
      }),
    [mutate]
  )

  const uploadingCount = Object.keys(uploadProgress).length

  const value = useMemo<FileVaultContextValue>(
    () => ({
      files,
      loading,
      uploadingCount,
      uploadProgress,
      uploadFile,
      deleteFile,
      toggleFavorite,
      togglePinned,
      addBookmark,
      removeBookmark,
      addNote,
      markPageRead,
      setCurrentPage,
      addStudyTime,
      getPdfDocument,
      generatePracticeQuiz,
      generateExam,
      recordAttempt,
    }),
    [
      files,
      loading,
      uploadingCount,
      uploadProgress,
      uploadFile,
      deleteFile,
      toggleFavorite,
      togglePinned,
      addBookmark,
      removeBookmark,
      addNote,
      markPageRead,
      setCurrentPage,
      addStudyTime,
      getPdfDocument,
      generatePracticeQuiz,
      generateExam,
      recordAttempt,
    ]
  )

  return <FileVaultContext.Provider value={value}>{children}</FileVaultContext.Provider>
}

export function useFileVault() {
  const ctx = useContext(FileVaultContext)
  if (!ctx) throw new Error('useFileVault must be used within a FileVaultProvider')
  return ctx
}

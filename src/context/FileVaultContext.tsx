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
import { extractPdf, estimateReadingMinutes, loadPdfDocument } from '../lib/fileVault/pdfEngine'
import { analyzeDocument, generateQuestions, hashString } from '../lib/fileVault/textAnalysis'
import { weekKeyFor, weekLabelFor } from '../lib/fileVault/weeks'
import { vaultApi, apiVaultFileToFrontend, vaultFileToPatch } from '../lib/fileVault/apiClient'
import { aiApi } from '../lib/ai/apiClient'
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
  addToCollection: (id: string, collectionName: string) => Promise<void>
  removeFromCollection: (id: string, collectionName: string) => Promise<void>
  setExamDate: (id: string, examDate: number | null) => Promise<void>
  addBookmark: (id: string, page: number, label: string) => Promise<void>
  removeBookmark: (id: string, bookmarkId: string) => Promise<void>
  addNote: (id: string, page: number, text: string) => Promise<void>
  markPageRead: (id: string, page: number) => Promise<void>
  setCurrentPage: (id: string, page: number) => Promise<void>
  addStudyTime: (id: string, seconds: number) => Promise<void>
  getPdfDocument: (id: string) => Promise<PDFDocumentProxy | null>
  generatePracticeQuiz: (id: string, count?: number) => Promise<VaultQuizQuestion[]>
  generateExam: (
    id: string,
    count: number,
    types: VaultQuestionType[]
  ) => Promise<VaultQuizQuestion[]>
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
      try {
        // Primary source of truth: the real /api/v1/file-vault backend.
        const list = await vaultApi.list()
        if (cancelled) return
        const hydrated = await Promise.all(
          list.map(async (api) => {
            const base = apiVaultFileToFrontend(api)
            // hydrate locally-cached analysis (pages text, quiz attempts)
            const cached = await storage.getFile(api.id)
            return cached ? { ...base, ...cached, ...apiVaultFileToFrontend(api, cached) } : base
          })
        )
        setFiles(hydrated.sort((a, b) => b.uploadedAt - a.uploadedAt))
      } catch {
        // Backend unreachable — fall back to the local offline mirror.
        const list = await storage.listFiles()
        if (cancelled) return
        setFiles(list.sort((a, b) => b.uploadedAt - a.uploadedAt))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [storage])

  const persist = useCallback(
    async (file: VaultFile) => {
      // Push to the real backend (fire-and-forget; local state wins for UX,
      // and failures leave the offline mirror intact).
      try {
        await vaultApi.update(file.id, vaultFileToPatch(file))
      } catch {
        // ignore network failures — keep working offline
      }
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
      const localId = `file-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      setUploadProgress((prev) => ({ ...prev, [localId]: 0 }))

      const arrayBuffer = await rawFile.arrayBuffer()
      setUploadProgress((prev) => ({ ...prev, [localId]: 20 }))

      // Real upload path: presigned PUT to Supabase Storage, then metadata.
      let serverId = localId
      try {
        const init = await vaultApi.uploadInit(rawFile.name, 'application/pdf', rawFile.size)
        setUploadProgress((prev) => ({ ...prev, [localId]: 40 }))
        serverId = init.fileId
        await fetch(init.uploadUrl, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/pdf' },
          body: arrayBuffer,
        })
        await vaultApi.complete(init.fileId)
        setUploadProgress((prev) => ({ ...prev, [localId]: 55 }))
      } catch {
        // Backend unreachable — keep the local offline path.
        await storage.putBlob(localId, new Blob([arrayBuffer], { type: 'application/pdf' }))
      }
      setUploadProgress((prev) => ({ ...prev, [localId]: 70 }))

      const extracted = await extractPdf(arrayBuffer.slice(0))
      setUploadProgress((prev) => ({ ...prev, [localId]: 85 }))

      const title = rawFile.name.replace(/\.pdf$/i, '')
      // Keep the existing deterministic analyzer as an offline fallback, but
      // prefer the authenticated backend AI for files successfully stored in
      // the user's private File Vault namespace.
      let analysis = analyzeDocument(serverId, title, extracted.pages)
      if (serverId !== localId) {
        try {
          const generated = await aiApi.analyze({ fileId: serverId, flashcardCount: 10 })
          analysis = generated.analysis
        } catch {
          // Gemini/Groq unavailable: preserve the existing offline behavior.
        }
      }
      setUploadProgress((prev) => ({ ...prev, [localId]: 95 }))

      const now = Date.now()
      const palette = pickPalette(meta?.course ?? title)

      const file: VaultFile = {
        id: serverId,
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
        examDate: null,

        favorite: false,
        pinned: false,
        bookmarks: [],
        notes: [],
        tags: [],
        collections: [],

        analysis,
        analysisState: 'ready',
        pagesText: extracted.pages,

        quizAttempts: [],
        examAttempts: [],
      }

      if (serverId !== localId) {
        try {
          await vaultApi.update(serverId, {
            ...vaultFileToPatch(file),
            totalPages: extracted.pageCount,
          })
        } catch {
          // metadata push failed — local mirror still works
        }
      }
      await persist(file)
      setUploadProgress((prev) => ({ ...prev, [localId]: 100 }))
      setTimeout(() => {
        setUploadProgress((prev) => {
          const next = { ...prev }
          delete next[localId]
          return next
        })
      }, 900)
    },
    [storage, persist]
  )

  const deleteFile = useCallback(
    async (id: string) => {
      try {
        await vaultApi.remove(id)
      } catch {
        // backend unreachable — still delete locally
      }
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

  const addToCollection = useCallback(
    (id: string, collectionName: string) =>
      mutate(id, (f) =>
        f.collections.includes(collectionName)
          ? f
          : { ...f, collections: [...f.collections, collectionName] }
      ),
    [mutate]
  )

  const removeFromCollection = useCallback(
    (id: string, collectionName: string) =>
      mutate(id, (f) => ({ ...f, collections: f.collections.filter((c) => c !== collectionName) })),
    [mutate]
  )

  const setExamDate = useCallback(
    (id: string, examDate: number | null) => mutate(id, (f) => ({ ...f, examDate })),
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
    async (id: string, count = 6): Promise<VaultQuizQuestion[]> => {
      const file = files.find((f) => f.id === id)
      if (!file || !file.analysis) return []
      // Practice quizzes ONLY draw from pages already viewed — never
      // generate questions from unread sections, per the spec.
      const allowedPages = new Set(file.pagesRead)
      if (allowedPages.size === 0) return []
      try {
        const generated = await aiApi.quiz({
          fileId: id,
          count,
          kind: 'practice',
          allowedPages: [...allowedPages],
        })
        return generated.questions
      } catch {
        const seed = hashString(id) + file.pagesRead.length
        return generateQuestions(file.pagesText, allowedPages, seed, count)
      }
    },
    [files]
  )

  const generateExam = useCallback(
    async (
      id: string,
      count: number,
      types: VaultQuestionType[]
    ): Promise<VaultQuizQuestion[]> => {
      const file = files.find((f) => f.id === id)
      if (!file || !file.analysis || !isFullyRead(file)) return []
      const pageNumbers = Array.from({ length: file.pageCount }, (_, i) => i + 1)
      const allowedPages = new Set(pageNumbers)
      try {
        const generated = await aiApi.quiz({
          fileId: id,
          count,
          questionTypes: types,
          kind: 'exam',
          allowedPages: pageNumbers,
        })
        return generated.questions
      } catch {
        const seed = hashString(id) + 7
        const all = generateQuestions(file.pagesText, allowedPages, seed, count * 2)
        const filtered = types.length > 0 ? all.filter((q) => types.includes(q.type)) : all
        return filtered.slice(0, count)
      }
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
      addToCollection,
      removeFromCollection,
      setExamDate,
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
      addToCollection,
      removeFromCollection,
      setExamDate,
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

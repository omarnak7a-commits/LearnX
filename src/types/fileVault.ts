/**
 * Shared types for the Smart AI File Vault ("My Files").
 *
 * Every field here is produced by real, in-browser processing:
 *  - `pdfjs-dist` extracts genuine per-page text/word counts from the
 *    actual uploaded PDF (see `src/lib/fileVault/pdfEngine.ts`).
 *  - The extracted text is run through a deterministic, extractive
 *    text-analysis engine (see `src/lib/fileVault/textAnalysis.ts`) that
 *    produces summaries, key concepts, definitions, formulas, quiz
 *    questions, etc. — no hardcoded content, no LLM API calls.
 *  - Reading progress, favorites, bookmarks, and analysis results persist
 *    in IndexedDB (see `src/lib/fileVault/storage.ts`) behind a
 *    `FileVaultStorage` interface so a real backend can be swapped in
 *    later without touching any UI code.
 */

export type FileLearningStatus = 'not-started' | 'in-progress' | 'viewed' | 'completed'

export type FileDifficulty = 'easy' | 'medium' | 'hard'

export type VaultQuestionType = 'mcq' | 'true-false' | 'fill-blank' | 'short-answer'

export interface VaultQuizQuestion {
  id: string
  type: VaultQuestionType
  prompt: string
  options?: string[]
  correctAnswer: string
  explanation: string
  difficulty: FileDifficulty
  /** Which page(s) of the source PDF this question was generated from. */
  sourcePages: number[]
}

export interface VaultFlashcard {
  id: string
  question: string
  answer: string
  sourcePage: number
  masteredLevel: number // 0-5 spaced-repetition box, student-driven
}

export interface VaultDefinition {
  term: string
  definition: string
  sourcePage: number
}

export interface VaultMindMapNode {
  id: string
  label: string
  sourcePage?: number
  children: VaultMindMapNode[]
}

export interface VaultTimelineEntry {
  id: string
  label: string
  startPage: number
  endPage: number
}

export interface FileAiAnalysis {
  /** True once analysis has actually run against the extracted text. */
  ready: boolean
  executiveSummary: string
  shortSummary: string
  detailedSummary: string
  keyConcepts: string[]
  definitions: VaultDefinition[]
  formulas: string[]
  examTips: string[]
  importantQuestions: string[]
  learningObjectives: string[]
  difficultTopics: string[]
  revisionNotes: string[]
  flashcards: VaultFlashcard[]
  mindMap: VaultMindMapNode
  timeline: VaultTimelineEntry[]
  difficulty: FileDifficulty
  /** 0-100 composite score: how exam-ready the analysis judges this document to be, purely from content density/coverage — separate from the student's own reading-based readiness score. */
  contentDensityScore: number
}

export interface FilePageText {
  page: number
  text: string
  wordCount: number
}

export interface StudentNote {
  id: string
  page: number
  text: string
  createdAt: number
}

export interface FileBookmark {
  id: string
  page: number
  label: string
  createdAt: number
}

export interface VaultFile {
  id: string
  /** Original uploaded filename. */
  name: string
  /** Display title (filename without extension, editable later). */
  title: string
  course: string
  doctorName: string
  /** ISO week key, e.g. '2026-W05', used to group the timeline. */
  weekKey: string
  weekLabel: string
  uploadedAt: number
  sizeBytes: number
  pageCount: number
  wordCount: number
  estimatedReadingMinutes: number
  thumbnailDataUrl: string | null
  color: string
  icon: string

  // Reading progress — all real, driven by the PDF viewer.
  status: FileLearningStatus
  pagesRead: number[]
  currentPage: number
  progressPct: number
  studyTimeSeconds: number
  lastViewedAt: number | null
  completedAt: number | null

  // Organization
  favorite: boolean
  pinned: boolean
  bookmarks: FileBookmark[]
  notes: StudentNote[]
  tags: string[]

  // AI
  analysis: FileAiAnalysis | null
  analysisState: 'pending' | 'processing' | 'ready' | 'failed'
  /**
   * Real per-page extracted text, retained alongside the analysis so
   * quiz/exam generation can be re-run on demand scoped to exactly the
   * pages the student has actually read — without needing to re-parse
   * the PDF binary synchronously every time a quiz is requested.
   */
  pagesText: FilePageText[]

  // Exam/quiz history
  quizAttempts: VaultQuizAttempt[]
  examAttempts: VaultQuizAttempt[]
}

export interface VaultQuizAttempt {
  id: string
  kind: 'practice' | 'exam'
  takenAt: number
  scorePct: number
  totalQuestions: number
  correctCount: number
  coveragePages: number[]
}

export function readingPercent(file: VaultFile): number {
  if (file.pageCount === 0) return 0
  return Math.round((new Set(file.pagesRead).size / file.pageCount) * 100)
}

export function isFullyRead(file: VaultFile): boolean {
  return readingPercent(file) >= 100
}

/**
 * A simple, transparent "AI readiness" composite: reading completion
 * (60%), quiz/exam performance history (30%), and recency of study (10%).
 * Entirely derived from the student's own real activity on this file.
 */
export function aiReadinessScore(file: VaultFile): number {
  const readingScore = readingPercent(file)
  const attempts = [...file.quizAttempts, ...file.examAttempts]
  const avgQuizScore =
    attempts.length > 0 ? attempts.reduce((sum, a) => sum + a.scorePct, 0) / attempts.length : null
  const recencyScore = file.lastViewedAt
    ? Math.max(0, 100 - Math.floor((Date.now() - file.lastViewedAt) / (1000 * 60 * 60 * 24)) * 5)
    : 0

  if (avgQuizScore === null) {
    return Math.round(readingScore * 0.8 + recencyScore * 0.2)
  }
  return Math.round(readingScore * 0.6 + avgQuizScore * 0.3 + recencyScore * 0.1)
}

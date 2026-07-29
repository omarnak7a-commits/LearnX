import type { VaultFile, VaultQuizAttempt } from '../../types/fileVault'
import { extractPdf, estimateReadingMinutes } from './pdfEngine'
import { analyzeDocument } from './textAnalysis'
import { getFileVaultStorage } from './storage'
import { weekKeyFor, weekLabelFor } from './weeks'

interface SeedFileDef {
  filename: string
  title: string
  course: string
  doctorName: string
  color: string
  icon: string
  /** Days ago this file was "uploaded", to spread the demo library across a few weeks. */
  uploadedDaysAgo: number
  /** Fraction of pages to mark as already-read, to show varied statuses out of the box. */
  readFraction: number
  /** Days from now this file's exam is scheduled, or null for no exam. */
  examInDays: number | null
  /** Days ago this file was last opened (may differ from uploadedDaysAgo to simulate staleness). */
  lastViewedDaysAgo: number | null
  /** Simulated quiz/exam score history (percent), oldest first. */
  quizScores: number[]
}

const SEED_DEFS: SeedFileDef[] = [
  {
    filename: 'cell-biology-ch3.pdf',
    title: 'Cell Biology — Chapter 3',
    course: 'Cell Biology',
    doctorName: 'Dr. Amara Diallo',
    color: '#22c55e',
    icon: '🧬',
    uploadedDaysAgo: 3,
    readFraction: 1,
    examInDays: 6,
    lastViewedDaysAgo: 1,
    quizScores: [78, 88],
  },
  {
    filename: 'calculus-limits-derivatives.pdf',
    title: 'Calculus I — Limits & Derivatives',
    course: 'Calculus & Analysis',
    doctorName: 'Prof. Lena Kraus',
    color: '#a855f7',
    icon: '📐',
    uploadedDaysAgo: 3,
    readFraction: 0.65,
    examInDays: 2,
    lastViewedDaysAgo: 5,
    quizScores: [],
  },
  {
    filename: 'operating-systems-scheduling.pdf',
    title: 'Operating Systems — Process Scheduling',
    course: 'Operating Systems',
    doctorName: 'Dr. Sarah Novak',
    color: '#2DD4BF',
    icon: '💻',
    uploadedDaysAgo: 9,
    readFraction: 0.5,
    examInDays: null,
    lastViewedDaysAgo: 2,
    quizScores: [42],
  },
  {
    filename: 'physics-newtonian-mechanics.pdf',
    title: 'Physics — Newtonian Mechanics',
    course: 'Classical Mechanics',
    doctorName: 'Dr. Sarah Novak',
    color: '#f59e0b',
    icon: '⚛️',
    uploadedDaysAgo: 9,
    readFraction: 0,
    examInDays: 12,
    lastViewedDaysAgo: null,
    quizScores: [],
  },
]

const SEED_MARKER_KEY = 'learnx-file-vault-seeded-v1'
const DAY_MS = 24 * 60 * 60 * 1000

function isoWeekInfo(date: Date) {
  return { key: weekKeyFor(date), label: weekLabelFor(date) }
}

function buildQuizAttempts(
  scores: number[],
  kind: 'practice' | 'exam',
  anchorAt: number
): VaultQuizAttempt[] {
  return scores.map((scorePct, i) => ({
    id: `seed-attempt-${kind}-${i}-${scorePct}`,
    kind,
    takenAt: anchorAt - (scores.length - i) * DAY_MS,
    scorePct,
    totalQuestions: 8,
    correctCount: Math.round((scorePct / 100) * 8),
    coveragePages: [],
  }))
}

/**
 * Fetches a bundled demo PDF, runs it through the REAL extraction + AI
 * analysis pipeline (same code path as a user upload), and builds a
 * fully-populated VaultFile. Nothing about the analysis is hardcoded —
 * only the "which PDF / which course / how many days ago" scaffolding is
 * seeded so the library isn't empty on first visit.
 */
async function buildSeedFile(def: SeedFileDef): Promise<VaultFile> {
  const url = `${import.meta.env.BASE_URL}demo-files/${def.filename}`
  const response = await fetch(url)
  const arrayBuffer = await response.arrayBuffer()
  const extracted = await extractPdf(arrayBuffer.slice(0))

  const now = Date.now()
  const uploadedAt = now - def.uploadedDaysAgo * DAY_MS
  const { key: weekKey, label: weekLabel } = isoWeekInfo(new Date(uploadedAt))

  const readCount = Math.round(extracted.pageCount * def.readFraction)
  const pagesRead = Array.from({ length: readCount }, (_, i) => i + 1)
  const status: VaultFile['status'] =
    readCount === 0 ? 'not-started' : readCount >= extracted.pageCount ? 'completed' : 'in-progress'

  const analysis = analyzeDocument(def.filename, def.title, extracted.pages)

  const id = `seed-${def.filename.replace(/\.pdf$/, '')}`

  const lastViewedAt =
    def.lastViewedDaysAgo !== null
      ? now - def.lastViewedDaysAgo * DAY_MS
      : readCount > 0
        ? uploadedAt + 60 * 60 * 1000
        : null

  return {
    id,
    name: def.filename,
    title: def.title,
    course: def.course,
    doctorName: def.doctorName,
    weekKey,
    weekLabel,
    uploadedAt,
    sizeBytes: arrayBuffer.byteLength,
    pageCount: extracted.pageCount,
    wordCount: extracted.wordCount,
    estimatedReadingMinutes: estimateReadingMinutes(extracted.wordCount),
    thumbnailDataUrl: extracted.thumbnailDataUrl,
    color: def.color,
    icon: def.icon,

    status,
    pagesRead,
    currentPage: readCount > 0 ? readCount : 1,
    progressPct: extracted.pageCount > 0 ? Math.round((readCount / extracted.pageCount) * 100) : 0,
    studyTimeSeconds: readCount * 95,
    lastViewedAt,
    completedAt: status === 'completed' ? uploadedAt + 2 * 60 * 60 * 1000 : null,
    examDate: def.examInDays !== null ? now + def.examInDays * DAY_MS : null,

    favorite: def.readFraction === 1,
    pinned: false,
    bookmarks: [],
    notes: [],
    tags: [],
    collections: [],

    analysis,
    analysisState: 'ready',
    pagesText: extracted.pages,

    quizAttempts: buildQuizAttempts(def.quizScores, 'practice', now).slice(0, -1),
    examAttempts:
      def.quizScores.length > 0 ? buildQuizAttempts(def.quizScores.slice(-1), 'exam', now) : [],
  }
}

/**
 * Seeds the vault with real, fully-processed demo files on first run
 * only (guarded by a one-time marker in the storage's own file list —
 * if any files already exist, seeding is skipped entirely so it never
 * overwrites real user uploads).
 */
export async function ensureSeeded(): Promise<void> {
  const storage = getFileVaultStorage()
  await storage.init()
  const existing = await storage.listFiles()
  if (existing.length > 0) return

  let alreadySeeded = false
  try {
    alreadySeeded = sessionStorage.getItem(SEED_MARKER_KEY) === '1'
  } catch {
    alreadySeeded = false
  }
  if (alreadySeeded) return

  const results = await Promise.allSettled(SEED_DEFS.map(buildSeedFile))
  for (const result of results) {
    if (result.status === 'fulfilled') {
      await storage.putFile(result.value)
    }
  }

  try {
    sessionStorage.setItem(SEED_MARKER_KEY, '1')
  } catch {
    // ignore
  }
}

/**
 * The AI Study Hub engine — computes priority, recommendations, and the
 * daily/weekly study plan directly from real VaultFile state (reading
 * progress, quiz/exam history, difficulty, staleness, and any
 * student-set exam date). Nothing here is a separate "planner" module —
 * every signal comes from the files already in the library, and the
 * output is consumed entirely inside My Files, per the "merge Smart
 * Planner into My Files" spec.
 */
import type { VaultFile } from '../../types/fileVault'
import { readingPercent, isFullyRead, aiReadinessScore } from '../../types/fileVault'

export type FilePriority = 'high' | 'medium' | 'low'

export interface PriorityResult {
  level: FilePriority
  score: number
  reasons: string[]
}

const DAY_MS = 24 * 60 * 60 * 1000

export function daysSince(timestamp: number | null): number | null {
  if (!timestamp) return null
  return Math.floor((Date.now() - timestamp) / DAY_MS)
}

export function daysUntil(timestamp: number | null): number | null {
  if (!timestamp) return null
  return Math.ceil((timestamp - Date.now()) / DAY_MS)
}

/**
 * AI priority score (0-100, higher = more urgent) combining every signal
 * the spec lists: upcoming exams, reading progress, time since last
 * review, difficulty, weak-subject/quiz performance.
 */
export function computePriority(file: VaultFile): PriorityResult {
  let score = 0
  const reasons: string[] = []

  // Upcoming exam — the single strongest signal.
  const untilExam = daysUntil(file.examDate)
  if (untilExam !== null) {
    if (untilExam <= 1) {
      score += 45
      reasons.push('Exam is imminent')
    } else if (untilExam <= 3) {
      score += 35
      reasons.push(`Exam in ${untilExam} days`)
    } else if (untilExam <= 7) {
      score += 22
      reasons.push(`Exam in ${untilExam} days`)
    } else if (untilExam > 0) {
      score += 8
      reasons.push(`Exam in ${untilExam} days`)
    }
  }

  // Reading progress — unfinished, started documents are urgent; fully
  // unread documents less so than ones abandoned partway through.
  const pct = readingPercent(file)
  if (pct > 0 && pct < 100) {
    score += 18
    reasons.push('Reading in progress')
  } else if (pct === 0) {
    score += 6
  }

  // Time since last review — staleness decays priority upward.
  const staleDays = daysSince(file.lastViewedAt)
  if (staleDays !== null) {
    if (staleDays >= 7) {
      score += 20
      reasons.push(`Not reviewed in ${staleDays} days`)
    } else if (staleDays >= 3) {
      score += 10
      reasons.push(`Not reviewed in ${staleDays} days`)
    }
  }

  // Difficulty — harder documents deserve more attention.
  if (file.analysis?.difficulty === 'hard') {
    score += 12
    reasons.push('High difficulty content')
  } else if (file.analysis?.difficulty === 'medium') {
    score += 5
  }

  // Quiz/exam performance — weak scores raise priority (a "weak subject" signal).
  const attempts = [...file.quizAttempts, ...file.examAttempts]
  if (attempts.length > 0) {
    const avg = attempts.reduce((sum, a) => sum + a.scorePct, 0) / attempts.length
    if (avg < 50) {
      score += 20
      reasons.push('Low quiz performance')
    } else if (avg < 70) {
      score += 10
      reasons.push('Room to improve quiz scores')
    }
  }

  // Already completed and performing well caps priority low regardless of other factors.
  if (isFullyRead(file) && attempts.length > 0 && attempts[0].scorePct >= 80) {
    score = Math.min(score, 15)
  }

  score = Math.max(0, Math.min(100, score))
  const level: FilePriority = score >= 55 ? 'high' : score >= 28 ? 'medium' : 'low'
  return { level, score, reasons: reasons.slice(0, 3) }
}

export const priorityMeta: Record<FilePriority, { label: string; emoji: string; color: string }> = {
  high: { label: 'High Priority', emoji: '🔴', color: 'var(--danger)' },
  medium: { label: 'Medium Priority', emoji: '🟡', color: 'var(--warning)' },
  low: { label: 'Low Priority', emoji: '🟢', color: 'var(--success)' },
}

export type StudyRecommendationKind =
  | 'review-today'
  | 'continue-reading'
  | 'ready-for-quiz'
  | 'ready-for-exam'
  | 'needs-revision'
  | 'needs-flashcards'
  | 'needs-explanation'
  | 'start-reading'

/**
 * The exact recommendation vocabulary from the spec, chosen from real
 * per-file signals — never a static/random label.
 */
export function studyRecommendation(file: VaultFile): {
  kind: StudyRecommendationKind
  label: string
} {
  const pct = readingPercent(file)
  const attempts = [...file.quizAttempts, ...file.examAttempts]
  const avgScore =
    attempts.length > 0 ? attempts.reduce((s, a) => s + a.scorePct, 0) / attempts.length : null
  const staleDays = daysSince(file.lastViewedAt)

  if (avgScore !== null && avgScore < 55) {
    return { kind: 'needs-revision', label: 'Needs Revision' }
  }
  if (isFullyRead(file) && attempts.length === 0) {
    return { kind: 'ready-for-exam', label: 'Ready for Final Exam' }
  }
  if (isFullyRead(file) && avgScore !== null && avgScore >= 80) {
    return { kind: 'ready-for-exam', label: 'Ready for Final Exam' }
  }
  if (pct > 0 && pct < 100 && staleDays !== null && staleDays >= 5) {
    return { kind: 'review-today', label: 'Review Today' }
  }
  if (pct >= 40 && pct < 100) {
    return { kind: 'ready-for-quiz', label: 'Ready for Quiz' }
  }
  if (pct > 0 && pct < 100) {
    return { kind: 'continue-reading', label: 'Continue Reading' }
  }
  if (file.analysis && file.analysis.difficulty === 'hard' && pct === 0) {
    return { kind: 'needs-explanation', label: 'Needs AI Explanation' }
  }
  if (file.analysis && file.analysis.flashcards.length > 0 && pct === 0) {
    return { kind: 'needs-flashcards', label: 'Needs Flashcards' }
  }
  return { kind: 'start-reading', label: 'Continue Reading' }
}

/** Suggested single next action label + target workspace tab. */
export function nextSuggestedAction(file: VaultFile): {
  label: string
  tab: 'viewer' | 'quiz' | 'exam' | 'flashcards'
} {
  const rec = studyRecommendation(file)
  switch (rec.kind) {
    case 'ready-for-exam':
      return { label: 'Take AI Exam', tab: 'exam' }
    case 'ready-for-quiz':
      return { label: 'Take Practice Quiz', tab: 'quiz' }
    case 'needs-flashcards':
      return { label: 'Review Flashcards', tab: 'flashcards' }
    case 'needs-revision':
    case 'review-today':
      return { label: 'Review Now', tab: 'viewer' }
    default:
      return { label: 'Continue Reading', tab: 'viewer' }
  }
}

/** Recommended daily study minutes for this file — scaled by remaining
 * reading time and priority, so higher-urgency files get a bigger ask. */
export function recommendedStudyMinutes(file: VaultFile): number {
  const pct = readingPercent(file)
  const remainingFraction = Math.max(0, 1 - pct / 100)
  const baseMinutes = Math.max(5, Math.round(file.estimatedReadingMinutes * remainingFraction))
  const { level } = computePriority(file)
  if (level === 'high') return Math.max(baseMinutes, 20)
  if (level === 'medium') return Math.max(baseMinutes, 10)
  return Math.min(baseMinutes, 15)
}

/** Exam readiness — distinct from general AI Readiness: weighted more
 * heavily toward quiz/exam performance and less toward raw reading %,
 * since "ready for the exam" is fundamentally a performance question. */
export function examReadiness(file: VaultFile): number {
  const pct = readingPercent(file)
  const attempts = [...file.quizAttempts, ...file.examAttempts]
  if (attempts.length === 0) {
    return Math.round(pct * 0.6)
  }
  const avgScore = attempts.reduce((s, a) => s + a.scorePct, 0) / attempts.length
  return Math.round(pct * 0.35 + avgScore * 0.65)
}

export interface StudyPlanCard {
  id: string
  category: 'continue' | 'review' | 'practice' | 'read' | 'exam'
  categoryLabel: string
  icon: string
  fileId: string
  fileTitle: string
  actionLabel: string
  tab: 'viewer' | 'quiz' | 'exam' | 'flashcards'
}

/**
 * "Today's AI Study Plan" — one card per category, each pointing at the
 * single most relevant file for that category, ranked by priority.
 * Regenerates automatically from current file state every render; there
 * is no persisted "plan" object to keep in sync.
 */
export function buildTodaysStudyPlan(files: VaultFile[]): StudyPlanCard[] {
  const ranked = [...files].sort((a, b) => computePriority(b).score - computePriority(a).score)
  const cards: StudyPlanCard[] = []
  const used = new Set<string>()

  function pick(
    category: StudyPlanCard['category'],
    categoryLabel: string,
    icon: string,
    predicate: (f: VaultFile) => boolean,
    actionLabel: string,
    tab: StudyPlanCard['tab']
  ) {
    const file = ranked.find((f) => !used.has(f.id) && predicate(f))
    if (!file) return
    used.add(file.id)
    cards.push({
      id: `${category}-${file.id}`,
      category,
      categoryLabel,
      icon,
      fileId: file.id,
      fileTitle: file.title,
      actionLabel,
      tab,
    })
  }

  pick(
    'continue',
    'Continue',
    '▶️',
    (f) => readingPercent(f) > 0 && readingPercent(f) < 100,
    'Continue Reading',
    'viewer'
  )
  pick(
    'review',
    'Review',
    '🔁',
    (f) => {
      const stale = daysSince(f.lastViewedAt)
      return f.status !== 'not-started' && stale !== null && stale >= 3
    },
    'Review Now',
    'viewer'
  )
  pick('practice', 'Practice', '❓', (f) => readingPercent(f) >= 40, 'Practice Quiz', 'quiz')
  pick('read', 'Read', '📖', (f) => readingPercent(f) === 0, 'Start Reading', 'viewer')
  pick(
    'exam',
    'Upcoming Exam',
    '🎓',
    (f) => f.examDate !== null && (daysUntil(f.examDate) ?? 999) >= 0,
    'Prepare Now',
    'exam'
  )

  return cards
}

export interface StudyInsight {
  id: string
  text: string
  fileId?: string
}

/** AI Insights strip — sentence-form observations computed from real
 * per-file state, matching the spec's exact example phrasing style. */
export function buildStudyInsights(files: VaultFile[]): StudyInsight[] {
  const insights: StudyInsight[] = []

  for (const f of files) {
    const untilExam = daysUntil(f.examDate)
    if (untilExam !== null && untilExam >= 0 && untilExam <= 7) {
      const readiness = examReadiness(f)
      insights.push({
        id: `exam-${f.id}`,
        text:
          readiness >= 80
            ? `You are ready for the ${f.course} exam.`
            : `You are ${readiness}% prepared for the ${f.course} exam${untilExam <= 2 ? " — it's very close" : ''}.`,
        fileId: f.id,
      })
    }
  }

  for (const f of files) {
    const stale = daysSince(f.lastViewedAt)
    if (f.status !== 'not-started' && f.status !== 'completed' && stale !== null && stale >= 4) {
      insights.push({
        id: `stale-${f.id}`,
        text: `You haven't reviewed ${f.title} for ${stale} days.`,
        fileId: f.id,
      })
    }
  }

  const lowestScoring = [...files]
    .filter((f) => f.quizAttempts.length > 0 || f.examAttempts.length > 0)
    .sort((a, b) => {
      const aAvg =
        [...a.quizAttempts, ...a.examAttempts].reduce((s, x) => s + x.scorePct, 0) /
        (a.quizAttempts.length + a.examAttempts.length)
      const bAvg =
        [...b.quizAttempts, ...b.examAttempts].reduce((s, x) => s + x.scorePct, 0) /
        (b.quizAttempts.length + b.examAttempts.length)
      return aAvg - bAvg
    })[0]
  if (lowestScoring) {
    insights.push({
      id: `lowest-${lowestScoring.id}`,
      text: `${lowestScoring.title} has your lowest quiz score.`,
      fileId: lowestScoring.id,
    })
  }

  const inProgress = files.filter((f) => f.status === 'in-progress')
  for (const f of inProgress.slice(0, 1)) {
    insights.push({
      id: `progress-${f.id}`,
      text: `You have completed ${readingPercent(f)}% of ${f.course}.`,
      fileId: f.id,
    })
  }

  if (insights.length === 0 && files.length > 0) {
    const lowestReadiness = [...files].sort((a, b) => aiReadinessScore(a) - aiReadinessScore(b))[0]
    insights.push({
      id: `default-${lowestReadiness.id}`,
      text: `Start with ${lowestReadiness.title} — it has the most room to improve.`,
      fileId: lowestReadiness.id,
    })
  }

  return insights.slice(0, 5)
}

export type SmartGroupKey =
  | 'thisWeek'
  | 'nextWeek'
  | 'completed'
  | 'needsRevision'
  | 'recentlyViewed'
  | 'favorites'
  | 'upcomingExams'

export const smartGroupMeta: Record<SmartGroupKey, { label: string; icon: string }> = {
  thisWeek: { label: 'This Week', icon: '🗓️' },
  nextWeek: { label: 'Next Week', icon: '📆' },
  completed: { label: 'Completed', icon: '✅' },
  needsRevision: { label: 'Needs Revision', icon: '⚠️' },
  recentlyViewed: { label: 'Recently Viewed', icon: '🕒' },
  favorites: { label: 'Favorites', icon: '⭐' },
  upcomingExams: { label: 'Upcoming Exams', icon: '🎓' },
}

/** Groups files into the spec's smart categories. A file can appear in
 * multiple groups (e.g. both Favorites and Needs Revision) — these are
 * views/lenses on the same library, not mutually exclusive buckets. */
export function buildSmartGroups(files: VaultFile[]): Record<SmartGroupKey, VaultFile[]> {
  const now = Date.now()
  const weekMs = 7 * DAY_MS

  return {
    thisWeek: files.filter((f) => now - f.uploadedAt <= weekMs),
    nextWeek: files.filter(
      (f) =>
        f.examDate !== null &&
        (daysUntil(f.examDate) ?? -1) >= 0 &&
        (daysUntil(f.examDate) ?? 999) <= 14 &&
        (daysUntil(f.examDate) ?? 999) > 7
    ),
    completed: files.filter((f) => f.status === 'completed'),
    needsRevision: files.filter((f) => studyRecommendation(f).kind === 'needs-revision'),
    recentlyViewed: [...files]
      .filter((f) => f.lastViewedAt !== null)
      .sort((a, b) => (b.lastViewedAt ?? 0) - (a.lastViewedAt ?? 0))
      .slice(0, 6),
    favorites: files.filter((f) => f.favorite),
    upcomingExams: files
      .filter((f) => f.examDate !== null && (daysUntil(f.examDate) ?? -1) >= 0)
      .sort((a, b) => (a.examDate ?? 0) - (b.examDate ?? 0)),
  }
}

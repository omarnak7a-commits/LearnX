/** Authenticated client for LearnX's backend-only Gemini/Groq AI layer. */

import { ApiError, apiFetch } from '../apiClient'
import { getAiLanguage, type AiLanguage } from './language'
import type {
  FileAiAnalysis,
  VaultFlashcard,
  VaultMindMapNode,
  VaultQuestionType,
  VaultQuizQuestion,
} from '../../types/fileVault'

export interface AIProviderMetadata {
  /** 'deterministic' = LearnX's provider-free study-map writer (same quality gates). */
  provider: 'gemini' | 'groq' | 'deterministic'
  model: string
  fallbackUsed: boolean
}

export interface AIChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AIChatResponse extends AIProviderMetadata {
  answer: string
  citations: Array<{ page: number; label: string }>
}

interface AISourceInput {
  fileId?: string
  sourceText?: string
  sourceTitle?: string
  language?: AiLanguage
}

function withLanguage<T extends { language?: AiLanguage }>(input: T): T & { language: AiLanguage } {
  return { ...input, language: input.language ?? getAiLanguage() }
}

export interface AISummaryResponse extends AIProviderMetadata {
  summary: string
  keyPoints: string[]
  keyTopics: string[]
  importantQuestions: string[]
}

export interface AITopicsResponse extends AIProviderMetadata {
  keyTopics: Array<{
    name: string
    explanation: string
    sourcePages: number[]
    importance: 'high' | 'medium' | 'low'
  }>
  importantQuestions: string[]
}

/**
 * Stage-by-stage view of the quiz generation funnel, returned only when the
 * caller explicitly asks for it (`diagnostics: true`).
 *
 * Exists because "could only verify 1" is unactionable on its own: it cannot
 * distinguish a thin PDF from a page-scoping mistake from an over-strict
 * validator. Counts and rejection reasons only — never prompts, document text,
 * credentials or provider configuration.
 *
 * Fields mirror the backend's `AIQuizDiagnostics`. Everything the backend
 * defaults is optional here so an older backend (or a trimmed payload) cannot
 * break a client that reads it.
 *
 * NOTE ON CASING — these keys are snake_case, unlike every other AI response.
 * The backend's `AIQuizDiagnostics` extends plain pydantic `BaseModel` rather
 * than the camelCase-aliasing `AIBaseModel` the other schemas use, so the wire
 * payload really is `extracted_pages` / `pages_used` / `understanding_source`.
 * Verified against the live `/api/v1/ai/quiz` response on both the 200 and the
 * 422 path. Typing these as camelCase would compile and then silently read
 * `undefined` at runtime, which is exactly the class of bug this whole change
 * exists to expose — so the contract is mirrored here as it actually is.
 */
export interface AIQuizDiagnostics {
  requested: number
  extracted_pages: number
  /** Pages whose text survived extraction AND boilerplate cleaning. */
  pages_used: number
  /** Pages that yielded some extractable text. */
  text_pages?: number
  /** Pages with (almost) no text but embedded imagery — scans, diagrams, slides. */
  image_only_pages?: number
  /** Pages extracted then discarded by cleaning: content lost, not absent. */
  pages_dropped_in_cleaning?: number
  concepts: number
  evidence_items: number
  relationships?: number
  plans: number
  candidates_generated: number
  accepted: number
  rejected: number
  provider_errors?: number
  rejections?: Record<string, number>
  /** Concepts the provider proposed before verification. */
  concepts_proposed_by_provider?: number
  /** Why proposed concepts were dropped, keyed by gate. */
  concepts_dropped_in_filtering?: Record<string, number>
  /** "provider" or "deterministic". The latter after a successful provider
   *  call means the provider's study map was discarded. */
  understanding_source?: string
  /** Provider call outcomes, e.g. understanding_calls / writer_failed. */
  provider_calls?: Record<string, number>
  plans_by_type?: Record<string, number>
  /** Candidates the writers actually produced, by plan type. */
  candidates_by_type?: Record<string, number>
  /** Rejected candidates by plan type (what candidates_by_type used to mean). */
  rejected_by_type?: Record<string, number>
  grounding_rejected?: number
  diversity_rejected?: number
  /** One entry per dropped candidate: stage, reason, concept, pages, type. */
  rejection_details?: Array<Record<string, unknown>>
  /** Per-page extraction quality, capped so the payload stays small. */
  page_quality?: string[]
  /** ── Candidate-funnel instrumentation (plans → candidates) ── */
  plans_created?: number
  plans_attempted?: number
  plans_skipped?: number
  plans_skipped_reason?: Record<string, number>
  provider_candidates_returned?: number
  provider_candidates_dropped?: number
  deterministic_candidates_attempted?: number
  deterministic_candidates_returned?: number
  deterministic_candidates_dropped?: number
  deterministic_drop_reasons?: Record<string, number>
  deterministic_targets_writable?: number
  candidate_generation_errors?: number
  candidate_generation_empty?: number
  /** Per-round top-up accounting with a stop_reason per round. */
  topup_rounds?: Array<Record<string, unknown>>
  /** ── Quality metrics (Section 17) ── */
  provider_candidates?: number
  deterministic_candidates?: number
  quality_generated?: number
  quality_passed?: number
  quality_rejected?: number
  grounding_passed?: number
  validation_passed?: number
  validation_rejected?: number
  duplicate_rejected?: number
  ambiguity_rejected?: number
  provider_model_used?: string
  provider_fallback_used?: boolean
}

export interface AIQuizResponse extends AIProviderMetadata {
  questions: VaultQuizQuestion[]
  /** Present only when the request set `diagnostics: true`. */
  diagnostics?: AIQuizDiagnostics
}

export interface AIFlashcardsResponse extends AIProviderMetadata {
  flashcards: VaultFlashcard[]
}

export interface AIMindMapResponse extends AIProviderMetadata {
  mindMap: VaultMindMapNode
}

export interface AIAnalyzeResponse extends AIProviderMetadata {
  analysis: FileAiAnalysis
}

/**
 * Build the opt-in `diagnostics` fragment for a quiz request body.
 *
 * Spread into the request so the key is present ONLY when diagnostics were
 * explicitly asked for. The backend keeps the response contract byte-identical
 * for callers that do not ask, so emitting `diagnostics: false` on every normal
 * exam would be a silent API change. Keeping that rule in one tested place
 * means the debugging path cannot drift from the production one.
 */
export function diagnosticsFragment(options?: { diagnostics?: boolean }): {
  diagnostics?: true
} {
  return options?.diagnostics ? { diagnostics: true } : {}
}

/**
 * Read the generation funnel off a failed quiz request.
 *
 * When a quiz is requested with `diagnostics: true` and the backend cannot
 * find enough material, it returns 422 with `diagnostics` as a sibling of
 * `detail`. `ApiError` preserves that body, so a shortfall can be explained
 * instead of just reported. Returns `undefined` for any other error shape.
 */
export function quizDiagnosticsFromError(error: unknown): AIQuizDiagnostics | undefined {
  if (!(error instanceof ApiError)) return undefined
  const body = error.body
  if (typeof body !== 'object' || body === null) return undefined
  const diagnostics = (body as { diagnostics?: unknown }).diagnostics
  if (typeof diagnostics !== 'object' || diagnostics === null) return undefined
  return diagnostics as AIQuizDiagnostics
}

export const aiApi = {
  chat: (input: {
    message: string
    mode?: 'socratic' | 'direct' | 'mentor'
    history?: AIChatMessage[]
    fileId?: string
    sourceText?: string
    sourceTitle?: string
    language?: AiLanguage
  }) =>
    apiFetch<AIChatResponse>('/api/v1/ai/chat', {
      method: 'POST',
      body: withLanguage(input),
    }),

  summarize: (input: AISourceInput & { detail?: 'short' | 'detailed' | 'exam' }) =>
    apiFetch<AISummaryResponse>('/api/v1/ai/summarize', { method: 'POST', body: input }),

  topics: (input: AISourceInput & { count?: number }) =>
    apiFetch<AITopicsResponse>('/api/v1/ai/topics', { method: 'POST', body: input }),

  quiz: (
    input: AISourceInput & {
      count?: number
      questionTypes?: VaultQuestionType[]
      difficulty?: 'easy' | 'medium' | 'hard' | 'mixed'
      kind?: 'practice' | 'exam'
      /** Which part of the PDF to source from. Defaults to the whole document. */
      scope?: 'document' | 'pages-read'
      allowedPages?: number[]
      /**
       * Ask the backend to return the generation funnel alongside the quiz
       * (and alongside a 422 shortfall). Opt-in: the key is omitted entirely
       * unless explicitly set, so the request body for every normal caller
       * stays byte-identical to what it was before diagnostics existed.
       */
      diagnostics?: boolean
    }
  ) => apiFetch<AIQuizResponse>('/api/v1/ai/quiz', { method: 'POST', body: input }),

  flashcards: (
    input: AISourceInput & {
      count?: number
      difficulty?: 'easy' | 'medium' | 'hard' | 'mixed'
    }
  ) => apiFetch<AIFlashcardsResponse>('/api/v1/ai/flashcards', { method: 'POST', body: input }),

  mindMap: (input: AISourceInput & { maxDepth?: number }) =>
    apiFetch<AIMindMapResponse>('/api/v1/ai/mind-map', { method: 'POST', body: input }),

  explain: (
    input: AISourceInput & {
      topic: string
      level?: 'beginner' | 'intermediate' | 'advanced'
    }
  ) =>
    apiFetch<{
      explanation: string
      keyPoints: string[]
      examples: string[]
      commonMistakes: string[]
      sourcePages: number[]
    } & AIProviderMetadata>('/api/v1/ai/explain', { method: 'POST', body: input }),

  analyze: (input: AISourceInput & { flashcardCount?: number }) =>
    apiFetch<AIAnalyzeResponse>('/api/v1/ai/analyze', { method: 'POST', body: input }),
}

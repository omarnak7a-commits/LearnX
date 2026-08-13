/** Authenticated client for LearnX's backend-only Gemini/Groq AI layer. */

import { apiFetch } from '../apiClient'
import { getAiLanguage, type AiLanguage } from './language'
import type {
  FileAiAnalysis,
  VaultFlashcard,
  VaultMindMapNode,
  VaultQuestionType,
  VaultQuizQuestion,
} from '../../types/fileVault'

export interface AIProviderMetadata {
  provider: 'gemini' | 'groq'
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

export interface AIQuizResponse extends AIProviderMetadata {
  questions: VaultQuizQuestion[]
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
      allowedPages?: number[]
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

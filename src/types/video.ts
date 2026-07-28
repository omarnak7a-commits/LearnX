/**
 * Shared types for the LearnX AI Video Intelligence feature.
 *
 * These model the output of the AI processing pipeline described in the
 * product spec. In this frontend-only build the data is produced by
 * `src/data/videoIntelligenceMock.ts` instead of a real inference backend —
 * see `backend/` for the reference architecture these shapes map onto.
 */

export type PipelineStageId =
  | 'upload'
  | 'virus-scan'
  | 'metadata'
  | 'audio-extraction'
  | 'speech-detection'
  | 'vad'
  | 'diarization'
  | 'silence-detection'
  | 'scene-detection'
  | 'ocr'
  | 'transcription'
  | 'topic-detection'
  | 'chapter-detection'
  | 'concept-extraction'
  | 'summary'
  | 'flashcards'
  | 'quiz'
  | 'mindmap'
  | 'notes'
  | 'workspace-ready'

export type PipelineStageStatus = 'pending' | 'active' | 'done' | 'skipped' | 'error'

export interface PipelineStage {
  id: PipelineStageId
  label: string
  description: string
  status: PipelineStageStatus
  /** 0-100, only meaningful while status === 'active' */
  progress?: number
  durationMs?: number
}

export type VideoSourceType =
  | 'upload'
  | 'zoom'
  | 'teams'
  | 'meet'
  | 'screen-recording'
  | 'lecture'

export type VideoProcessingState = 'queued' | 'processing' | 'ready' | 'failed'

export interface SilenceSegment {
  id: string
  startSec: number
  endSec: number
  /** Why the AI flagged this window. */
  reason:
    | 'dead-air'
    | 'setup-time'
    | 'waiting'
    | 'repeated-pause'
    | 'idle-moment'
    | 'meaningful-pause'
  /** Whether this segment was cut from the optimized video. Meaningful pauses are always false. */
  removed: boolean
  confidence: number
}

export interface ChapterConcept {
  term: string
  definition: string
}

export interface Chapter {
  id: string
  index: number
  title: string
  startSec: number
  endSec: number
  difficulty: 'easy' | 'medium' | 'hard'
  confidence: number
  examImportance: number
  estimatedStudyMinutes: number
  keyConcepts: ChapterConcept[]
  formulas: string[]
  examTips: string[]
}

export interface TranscriptSegment {
  id: string
  startSec: number
  endSec: number
  speaker: string
  text: string
  chapterId: string
  highlighted?: boolean
}

export type SummaryLevel = 'quick' | 'detailed' | 'bullet' | 'exam' | 'revision' | 'one-minute'

export interface SummaryContent {
  level: SummaryLevel
  label: string
  points: string[]
}

export interface Flashcard {
  id: string
  chapterId: string
  question: string
  answer: string
  difficulty: 'easy' | 'medium' | 'hard'
  favorite: boolean
  masteredLevel: number // 0-5 spaced repetition box
}

export type QuizQuestionType = 'mcq' | 'true-false' | 'short-answer' | 'fill-blank'

export interface QuizQuestion {
  id: string
  chapterId: string
  type: QuizQuestionType
  prompt: string
  options?: string[]
  correctAnswer: string
  explanation: string
  difficulty: 'easy' | 'medium' | 'hard'
}

export interface MindMapNode {
  id: string
  label: string
  children: MindMapNode[]
}

export interface ChatCitation {
  chapterId: string
  chapterTitle: string
  timestampSec: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  citations?: ChatCitation[]
}

export interface VideoStats {
  originalDurationSec: number
  optimizedDurationSec: number
  minutesSaved: number
  percentRemoved: number
  learningEfficiencyScore: number
}

export interface VideoLecture {
  id: string
  title: string
  course: string
  sourceType: VideoSourceType
  uploadedAt: string
  thumbnailGradient: [string, string]
  state: VideoProcessingState
  currentStageIndex: number
  pipeline: PipelineStage[]
  durationSec: number
  stats: VideoStats
  silenceSegments: SilenceSegment[]
  chapters: Chapter[]
  transcript: TranscriptSegment[]
  summaries: SummaryContent[]
  flashcards: Flashcard[]
  quiz: QuizQuestion[]
  mindMap: MindMapNode
  chat: ChatMessage[]
  /** Demo-only playable source; see component comments. */
  demoVideoUrl?: string
}

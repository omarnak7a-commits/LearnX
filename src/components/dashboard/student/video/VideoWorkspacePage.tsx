import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { VideoLecture } from '../../../../types/video'
import VideoPlayer from './VideoPlayer'
import ChaptersPanel from './ChaptersPanel'
import TranscriptPanel from './TranscriptPanel'
import SummaryPanel from './SummaryPanel'
import FlashcardsPanel from './FlashcardsPanel'
import QuizPanel from './QuizPanel'
import MindMapPanel from './MindMapPanel'
import VideoChatPanel from './VideoChatPanel'
import SilenceComparison from './SilenceComparison'
import PipelineTimeline from './PipelineTimeline'

interface VideoWorkspacePageProps {
  lecture: VideoLecture
  onBack: () => void
}

type Tab = 'chapters' | 'transcript' | 'summary' | 'flashcards' | 'quiz' | 'mindmap' | 'chat'

const TABS: Array<{ id: Tab; label: string; icon: string }> = [
  { id: 'chapters', label: 'Chapters', icon: '📑' },
  { id: 'transcript', label: 'Transcript', icon: '📝' },
  { id: 'summary', label: 'Summary', icon: '💡' },
  { id: 'flashcards', label: 'Flashcards', icon: '🗂️' },
  { id: 'quiz', label: 'Quiz', icon: '❓' },
  { id: 'mindmap', label: 'Mind Map', icon: '🧠' },
  { id: 'chat', label: 'Ask AI', icon: '✨' },
]

export default function VideoWorkspacePage({ lecture, onBack }: VideoWorkspacePageProps) {
  const [mode, setMode] = useState<'original' | 'optimized'>('optimized')
  const [currentTime, setCurrentTime] = useState(0)
  const [tab, setTab] = useState<Tab>('chapters')

  const activeChapter = useMemo(
    () => [...lecture.chapters].reverse().find((c) => currentTime >= c.startSec),
    [lecture.chapters, currentTime]
  )

  if (lecture.state !== 'ready') {
    return (
      <div className="space-y-5">
        <button onClick={onBack} className="text-xs font-semibold flex items-center gap-1.5" style={{ color: 'var(--primary)' }}>
          ← Back to Video Intelligence
        </button>
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-base font-bold" style={{ color: 'var(--foreground)' }}>
              {lecture.title}
            </h2>
          </div>
          <p className="text-xs mb-6" style={{ color: 'var(--muted-foreground)' }}>
            {lecture.course} · {lecture.state === 'processing' ? 'AI is analyzing this lecture now' : 'Waiting in the processing queue'}
          </p>
          <PipelineTimeline stages={lecture.pipeline} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button onClick={onBack} className="text-xs font-semibold flex items-center gap-1.5" style={{ color: 'var(--primary)' }}>
          ← Back to Video Intelligence
        </button>
      </div>

      <div>
        <h2 className="text-lg font-bold" style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}>
          {lecture.title}
        </h2>
        <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
          {lecture.course}
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_400px] gap-5 items-start">
        <div className="space-y-5">
          <VideoPlayer
            lecture={lecture}
            mode={mode}
            onModeChange={setMode}
            currentTime={currentTime}
            onTimeChange={setCurrentTime}
            activeChapter={activeChapter}
          />
          <SilenceComparison stats={lecture.stats} segments={lecture.silenceSegments} />
        </div>

        {/* Tabbed workspace */}
        <div className="glass-card p-5 sticky top-6">
          <div className="flex items-center gap-1 mb-4 overflow-x-auto scrollbar-thin pb-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className="relative flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
                style={{
                  background: tab === t.id ? 'var(--primary)' : 'transparent',
                  color: tab === t.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                }}
              >
                <span>{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              {tab === 'chapters' && (
                <ChaptersPanel
                  chapters={lecture.chapters}
                  activeChapterId={activeChapter?.id}
                  onJump={setCurrentTime}
                />
              )}
              {tab === 'transcript' && (
                <TranscriptPanel segments={lecture.transcript} currentTime={currentTime} onJump={setCurrentTime} />
              )}
              {tab === 'summary' && <SummaryPanel summaries={lecture.summaries} />}
              {tab === 'flashcards' && <FlashcardsPanel flashcards={lecture.flashcards} />}
              {tab === 'quiz' && <QuizPanel questions={lecture.quiz} />}
              {tab === 'mindmap' && <MindMapPanel root={lecture.mindMap} />}
              {tab === 'chat' && <VideoChatPanel lecture={lecture} onJump={setCurrentTime} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

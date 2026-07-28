import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import type { VideoLecture, VideoSourceType } from '../../../../types/video'
import { mockLectures, PIPELINE_STAGE_DEFS } from '../../../../data/videoIntelligenceMock'
import VideoUploadZone from './VideoUploadZone'
import LectureCard from './LectureCard'
import VideoWorkspacePage from './VideoWorkspacePage'
import StatCard from '../../shared/StatCard'
import EmptyState from '../../shared/EmptyState'

function buildQueuedLecture(name: string, sourceType: VideoSourceType): VideoLecture {
  const gradients: Array<[string, string]> = [
    ['#2DD4BF', '#0d9488'],
    ['#f59e0b', '#ea580c'],
    ['#a855f7', '#7e22ce'],
    ['#38bdf8', '#0369a1'],
  ]
  const gradient = gradients[Math.floor(Math.random() * gradients.length)]
  const duration = 900 + Math.floor(Math.random() * 1800)
  return {
    id: `lec-${Date.now()}`,
    title: name.replace(/\.[^.]+$/, ''),
    course: 'Uncategorized · will auto-detect',
    sourceType,
    uploadedAt: 'Just now',
    thumbnailGradient: gradient,
    state: 'queued',
    currentStageIndex: 0,
    pipeline: PIPELINE_STAGE_DEFS.map((def) => ({ ...def, status: 'pending' })),
    durationSec: duration,
    stats: { originalDurationSec: duration, optimizedDurationSec: 0, minutesSaved: 0, percentRemoved: 0, learningEfficiencyScore: 0 },
    silenceSegments: [],
    chapters: [],
    transcript: [],
    summaries: [],
    flashcards: [],
    quiz: [],
    mindMap: { id: 'root', label: name, children: [] },
    chat: [],
  }
}

/**
 * AI Video Intelligence — the "Watch Less. Learn More." feature. Lists
 * uploaded lectures at every stage (queued/processing/ready), lets the
 * student upload new ones, and opens the full workspace (player, chapters,
 * transcript, summaries, flashcards, quiz, mind map, AI chat) for anything
 * fully processed.
 */
export default function VideoIntelligencePage() {
  const [lectures, setLectures] = useState<VideoLecture[]>(mockLectures)
  const [openId, setOpenId] = useState<string | null>(null)

  // Simulate background pipeline progress for queued/processing lectures.
  useEffect(() => {
    const interval = setInterval(() => {
      setLectures((prev) =>
        prev.map((lec) => {
          if (lec.state === 'ready' || lec.state === 'failed') return lec

          const stages = [...lec.pipeline]
          let stageIdx = stages.findIndex((s) => s.status === 'active')
          if (stageIdx === -1) stageIdx = stages.findIndex((s) => s.status === 'pending')
          if (stageIdx === -1) return lec

          const stage = { ...stages[stageIdx] }
          const nextProgress = (stage.progress ?? 0) + 8 + Math.random() * 14

          if (nextProgress >= 100) {
            stages[stageIdx] = { ...stage, status: 'done', progress: 100 }
            const isLast = stageIdx === stages.length - 1
            if (!isLast) {
              stages[stageIdx + 1] = { ...stages[stageIdx + 1], status: 'active', progress: 0 }
            }
            return {
              ...lec,
              pipeline: stages,
              currentStageIndex: stageIdx + 1,
              state: isLast ? 'ready' : ('processing' as const),
            }
          }

          stages[stageIdx] = { ...stage, status: 'active', progress: nextProgress }
          return { ...lec, pipeline: stages, state: 'processing' as const }
        })
      )
    }, 900)
    return () => clearInterval(interval)
  }, [])

  function handleUpload(file: { name: string; sourceType: VideoSourceType; sizeLabel: string }) {
    const lecture = buildQueuedLecture(file.name, file.sourceType)
    setLectures((prev) => [lecture, ...prev])
  }

  const open = lectures.find((l) => l.id === openId)
  if (open) {
    return <VideoWorkspacePage lecture={open} onBack={() => setOpenId(null)} />
  }

  const readyLectures = lectures.filter((l) => l.state === 'ready')
  const totalMinutesSaved = readyLectures.reduce((sum, l) => sum + l.stats.minutesSaved, 0)
  const avgEfficiency =
    readyLectures.length > 0
      ? Math.round(readyLectures.reduce((sum, l) => sum + l.stats.learningEfficiencyScore, 0) / readyLectures.length)
      : 0

  return (
    <div className="space-y-5">
      {/* Hero */}
      <motion.div
        className="glass-card p-6 relative overflow-hidden"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div
          className="absolute -top-16 -right-16 w-56 h-56 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(45,212,191,0.12) 0%, transparent 70%)' }}
        />
        <div className="relative flex items-center justify-between flex-wrap gap-4">
          <div>
            <p
              className="text-xs tracking-[0.2em] uppercase font-semibold mb-2"
              style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}
            >
              AI Video Intelligence
            </p>
            <h2
              className="text-2xl font-black leading-tight"
              style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
            >
              Watch Less. <span className="text-gradient">Learn More.</span>
            </h2>
            <p className="text-sm mt-2 max-w-lg" style={{ color: 'var(--muted-foreground)' }}>
              Upload any lecture and the AI turns it into chapters, a searchable transcript,
              summaries, flashcards, quizzes, a mind map — and trims out the dead air.
            </p>
          </div>
        </div>
      </motion.div>

      {/* Aggregate stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="🎬" label="Lectures processed" value={readyLectures.length} color="#2DD4BF" delay={0} />
        <StatCard icon="⏱️" label="Minutes saved" value={Math.round(totalMinutesSaved)} suffix="m" color="#FF7E36" delay={0.05} />
        <StatCard icon="⚡" label="Avg. efficiency score" value={avgEfficiency} color="#38bdf8" delay={0.1} />
        <StatCard icon="🗂️" label="In queue" value={lectures.filter((l) => l.state !== 'ready').length} color="#a855f7" delay={0.15} />
      </div>

      <VideoUploadZone onUpload={handleUpload} />

      <div>
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          Your Lectures
        </h3>
        {lectures.length === 0 ? (
          <div className="glass-card">
            <EmptyState icon="🎬" title="No lectures yet" body="Upload your first recorded lecture to get started." />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {lectures.map((lec, i) => (
              <LectureCard key={lec.id} lecture={lec} onOpen={() => setOpenId(lec.id)} delay={i * 0.05} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

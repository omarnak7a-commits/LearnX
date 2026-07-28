import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Chapter, VideoLecture } from '../../../../types/video'
import { formatTimestamp } from '../../../../data/videoIntelligenceMock'

interface VideoPlayerProps {
  lecture: VideoLecture
  mode: 'original' | 'optimized'
  onModeChange: (mode: 'original' | 'optimized') => void
  currentTime: number
  onTimeChange: (t: number) => void
  activeChapter: Chapter | undefined
}

const SPEEDS = [0.75, 1, 1.25, 1.5, 2]

/**
 * Premium custom video player. When the lecture has a real playable source
 * (`demoVideoUrl`) it drives an actual <video> element; otherwise — since
 * this is a frontend-only build with no rendered lecture media — it falls
 * back to a cinematic simulated timeline driven by the same clock, so every
 * other panel (chapters, transcript auto-scroll, silence markers) still
 * behaves identically to a real playback session.
 */
export default function VideoPlayer({
  lecture,
  mode,
  onModeChange,
  currentTime,
  onTimeChange,
  activeChapter,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [speedMenuOpen, setSpeedMenuOpen] = useState(false)
  const [showSkipHint, setShowSkipHint] = useState<'cut' | null>(null)
  const [duration, setDuration] = useState(
    mode === 'optimized' ? lecture.stats.optimizedDurationSec : lecture.stats.originalDurationSec
  )

  const hasRealVideo = Boolean(lecture.demoVideoUrl)

  useEffect(() => {
    setDuration(mode === 'optimized' ? lecture.stats.optimizedDurationSec : lecture.stats.originalDurationSec)
  }, [mode, lecture])

  // Simulated clock when there's no real <video> element to drive time.
  useEffect(() => {
    if (hasRealVideo || !playing) return
    const interval = setInterval(() => {
      onTimeChange(Math.min(duration, currentTime + speed))
    }, 1000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed, hasRealVideo, duration])

  useEffect(() => {
    if (!hasRealVideo || !videoRef.current) return
    if (playing) videoRef.current.play().catch(() => {})
    else videoRef.current.pause()
  }, [playing, hasRealVideo])

  useEffect(() => {
    if (!hasRealVideo || !videoRef.current) return
    videoRef.current.playbackRate = speed
  }, [speed, hasRealVideo])

  // Skip removed silence segments in optimized mode (real video only).
  useEffect(() => {
    if (mode !== 'optimized') return
    const cut = lecture.silenceSegments.find(
      (s) => s.removed && currentTime >= s.startSec && currentTime < s.endSec
    )
    if (cut) {
      setShowSkipHint('cut')
      onTimeChange(cut.endSec)
      if (hasRealVideo && videoRef.current) videoRef.current.currentTime = cut.endSec
      setTimeout(() => setShowSkipHint(null), 900)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTime, mode])

  function togglePlay() {
    setPlaying((p) => !p)
  }

  function seekTo(t: number) {
    const clamped = Math.max(0, Math.min(duration, t))
    onTimeChange(clamped)
    if (hasRealVideo && videoRef.current) videoRef.current.currentTime = clamped
  }

  const progressPct = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="glass-card overflow-hidden">
      {/* Screen */}
      <div
        className="relative aspect-video flex items-center justify-center overflow-hidden"
        style={{ background: '#050709' }}
      >
        {hasRealVideo ? (
          <video
            ref={videoRef}
            src={lecture.demoVideoUrl}
            className="w-full h-full object-cover"
            onTimeUpdate={(e) => onTimeChange(e.currentTarget.currentTime)}
            onLoadedMetadata={(e) => {
              if (mode === 'original') setDuration(e.currentTarget.duration)
            }}
            onClick={togglePlay}
            playsInline
          />
        ) : (
          <SimulatedScreen playing={playing} progressPct={progressPct} gradient={lecture.thumbnailGradient} />
        )}

        {/* Skip-cut toast */}
        <AnimatePresence>
          {showSkipHint && (
            <motion.div
              className="absolute top-4 right-4 px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5"
              style={{ background: 'rgba(45,212,191,0.9)', color: '#052018' }}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              ⏩ Skipped dead air
            </motion.div>
          )}
        </AnimatePresence>

        {/* Center play button */}
        {!playing && (
          <motion.button
            onClick={togglePlay}
            className="absolute inset-0 flex items-center justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <motion.span
              className="w-16 h-16 rounded-full flex items-center justify-center text-2xl"
              style={{ background: 'rgba(255,255,255,0.14)', backdropFilter: 'blur(8px)', color: '#fff' }}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.95 }}
            >
              ▶
            </motion.span>
          </motion.button>
        )}

        {/* Chapter label */}
        {activeChapter && (
          <div
            className="absolute top-4 left-4 px-3 py-1.5 rounded-full text-xs font-medium"
            style={{ background: 'rgba(0,0,0,0.5)', color: '#fff' }}
          >
            Ch. {activeChapter.index} · {activeChapter.title}
          </div>
        )}

        {/* Original/Optimized badge */}
        <div
          className="absolute top-4 right-4 px-3 py-1.5 rounded-full text-xs font-bold"
          style={{
            background: mode === 'optimized' ? 'rgba(45,212,191,0.9)' : 'rgba(255,255,255,0.15)',
            color: mode === 'optimized' ? '#052018' : '#fff',
            backdropFilter: 'blur(8px)',
          }}
        >
          {mode === 'optimized' ? '⚡ AI Optimized' : 'Original'}
        </div>
      </div>

      {/* Controls */}
      <div className="p-4">
        {/* Timeline */}
        <div className="relative mb-3 group/timeline">
          <div
            className="relative h-1.5 rounded-full overflow-hidden cursor-pointer"
            style={{ background: 'var(--tint-3)' }}
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect()
              const pct = (e.clientX - rect.left) / rect.width
              seekTo(pct * duration)
            }}
          >
            {/* Removed-silence markers (original mode only) */}
            {mode === 'original' &&
              lecture.silenceSegments
                .filter((s) => s.removed)
                .map((s) => (
                  <div
                    key={s.id}
                    className="absolute top-0 bottom-0"
                    style={{
                      left: `${(s.startSec / duration) * 100}%`,
                      width: `${((s.endSec - s.startSec) / duration) * 100}%`,
                      background: 'rgba(239,68,68,0.35)',
                    }}
                  />
                ))}
            {/* Chapter dividers */}
            {lecture.chapters.map((c) => (
              <div
                key={c.id}
                className="absolute top-0 bottom-0 w-px"
                style={{ left: `${(c.startSec / duration) * 100}%`, background: 'rgba(255,255,255,0.25)' }}
              />
            ))}
            <motion.div
              className="h-full rounded-full"
              style={{ background: 'linear-gradient(90deg, var(--primary), var(--secondary))' }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.15 }}
            />
          </div>
          <div
            className="absolute -top-1 w-3.5 h-3.5 rounded-full shadow opacity-0 group-hover/timeline:opacity-100 transition-opacity pointer-events-none"
            style={{ left: `calc(${progressPct}% - 7px)`, background: 'var(--primary)' }}
          />
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={togglePlay}
            className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            aria-label={playing ? 'Pause' : 'Play'}
          >
            {playing ? '❚❚' : '▶'}
          </button>

          <span className="text-xs font-mono flex-shrink-0" style={{ color: 'var(--muted-foreground)' }}>
            {formatTimestamp(currentTime)} / {formatTimestamp(duration)}
          </span>

          {/* Original / Optimized toggle */}
          <div className="flex items-center gap-1 p-1 rounded-lg flex-shrink-0" style={{ background: 'var(--muted)' }}>
            {(['original', 'optimized'] as const).map((m) => (
              <button
                key={m}
                onClick={() => onModeChange(m)}
                disabled={m === 'optimized' && lecture.stats.optimizedDurationSec === 0}
                className="relative px-3 py-1 rounded-md text-xs font-semibold transition-colors disabled:opacity-40"
                style={{
                  background: mode === m ? 'var(--primary)' : 'transparent',
                  color: mode === m ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                }}
              >
                {m === 'original' ? 'Original' : '⚡ Optimized'}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2 flex-shrink-0">
            {/* Speed control */}
            <div className="relative">
              <button
                onClick={() => setSpeedMenuOpen((v) => !v)}
                className="text-xs font-mono px-2.5 py-1.5 rounded-lg input-field"
                style={{ color: 'var(--foreground)' }}
              >
                {speed}×
              </button>
              <AnimatePresence>
                {speedMenuOpen && (
                  <motion.div
                    className="surface-popover absolute bottom-full right-0 mb-2 rounded-xl overflow-hidden py-1 w-20"
                    initial={{ opacity: 0, y: 6, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.95 }}
                  >
                    {SPEEDS.map((s) => (
                      <button
                        key={s}
                        onClick={() => {
                          setSpeed(s)
                          setSpeedMenuOpen(false)
                        }}
                        className="w-full text-center text-xs py-1.5 font-mono transition-colors"
                        style={{
                          background: s === speed ? 'rgba(45,212,191,0.12)' : 'transparent',
                          color: s === speed ? 'var(--primary)' : 'var(--foreground)',
                        }}
                      >
                        {s}×
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button
              className="w-8 h-8 rounded-lg flex items-center justify-center input-field flex-shrink-0"
              style={{ color: 'var(--muted-foreground)' }}
              aria-label="Picture in picture"
              title="Picture in Picture"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="14" rx="2" />
                <rect x="12" y="10" width="7" height="5" rx="1" fill="currentColor" />
              </svg>
            </button>
            <button
              className="w-8 h-8 rounded-lg flex items-center justify-center input-field flex-shrink-0"
              style={{ color: 'var(--muted-foreground)' }}
              aria-label="Fullscreen"
              title="Fullscreen"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Cinematic animated placeholder for lectures without a bound demo source. */
function SimulatedScreen({
  playing,
  progressPct,
  gradient,
}: {
  playing: boolean
  progressPct: number
  gradient: [string, string]
}) {
  return (
    <div
      className="absolute inset-0 flex items-center justify-center overflow-hidden"
      style={{ background: `linear-gradient(135deg, ${gradient[0]}18, ${gradient[1]}18)` }}
    >
      <div className="absolute inset-0 bg-grid opacity-20" />
      <div className="flex items-end gap-1 h-16 relative z-10">
        {Array.from({ length: 28 }, (_, i) => {
          const h = 8 + ((Math.sin(i * 1.7) + 1) / 2) * 48
          return (
            <motion.div
              key={i}
              className="w-1.5 rounded-full"
              style={{ background: gradient[0] }}
              animate={
                playing
                  ? { height: [h * 0.4, h, h * 0.4], opacity: [0.4, 0.9, 0.4] }
                  : { height: h * 0.35, opacity: 0.3 }
              }
              transition={{ duration: 1 + (i % 5) * 0.15, repeat: playing ? Infinity : 0, ease: 'easeInOut' }}
            />
          )
        })}
      </div>
      <div
        className="absolute bottom-3 left-3 right-3 h-0.5 rounded-full overflow-hidden"
        style={{ background: 'rgba(255,255,255,0.15)' }}
      >
        <div className="h-full rounded-full" style={{ width: `${progressPct}%`, background: gradient[0] }} />
      </div>
    </div>
  )
}

import { motion } from 'framer-motion'
import type { VideoLecture } from '../../../../types/video'
import { formatDuration } from '../../../../data/videoIntelligenceMock'
import Badge from '../../../ui/Badge'

const sourceIcon: Record<VideoLecture['sourceType'], string> = {
  upload: '⬆️',
  zoom: '🎥',
  teams: '🟣',
  meet: '📹',
  'screen-recording': '🖥️',
  lecture: '🎓',
}

const stateLabel: Record<VideoLecture['state'], { text: string; tone: 'primary' | 'warning' | 'success' | 'danger' }> = {
  queued: { text: 'Queued', tone: 'warning' },
  processing: { text: 'Processing', tone: 'primary' },
  ready: { text: 'Ready', tone: 'success' },
  failed: { text: 'Failed', tone: 'danger' },
}

interface LectureCardProps {
  lecture: VideoLecture
  onOpen: () => void
  delay?: number
}

export default function LectureCard({ lecture, onOpen, delay = 0 }: LectureCardProps) {
  const activeStage = lecture.pipeline.find((s) => s.status === 'active')
  const st = stateLabel[lecture.state]

  return (
    <motion.button
      onClick={onOpen}
      className="glass-card p-0 text-left overflow-hidden group w-full"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -3 }}
    >
      {/* Thumbnail */}
      <div
        className="relative h-28 flex items-center justify-center overflow-hidden"
        style={{
          background: `linear-gradient(135deg, ${lecture.thumbnailGradient[0]}, ${lecture.thumbnailGradient[1]})`,
        }}
      >
        <div className="absolute inset-0 bg-grid-fine opacity-20" />
        <span className="text-3xl relative z-10 opacity-90">
          {lecture.state === 'ready' ? '▶' : sourceIcon[lecture.sourceType]}
        </span>
        <span
          className="absolute bottom-2 right-2 text-xs px-1.5 py-0.5 rounded font-mono"
          style={{ background: 'rgba(0,0,0,0.5)', color: '#fff' }}
        >
          {formatDuration(lecture.durationSec)}
        </span>
        {lecture.state === 'ready' && lecture.stats.percentRemoved > 0 && (
          <span
            className="absolute top-2 left-2 text-xs px-1.5 py-0.5 rounded-md font-semibold"
            style={{ background: 'rgba(0,0,0,0.5)', color: '#5eead4' }}
          >
            −{lecture.stats.percentRemoved}% trimmed
          </span>
        )}
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <p className="text-sm font-semibold leading-snug truncate" style={{ color: 'var(--foreground)' }}>
            {lecture.title}
          </p>
        </div>
        <p className="text-xs mb-3 truncate" style={{ color: 'var(--muted-foreground)' }}>
          {lecture.course}
        </p>

        <div className="flex items-center justify-between gap-2">
          <Badge tone={st.tone} size="xs" pulse={lecture.state === 'processing'}>
            {st.text}
          </Badge>
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {lecture.uploadedAt}
          </span>
        </div>

        {lecture.state !== 'ready' && (
          <div className="mt-3">
            <p className="text-xs mb-1.5 truncate" style={{ color: 'var(--muted-foreground)' }}>
              {activeStage ? activeStage.label : 'Waiting in queue…'}
            </p>
            <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
              <motion.div
                className="h-full rounded-full"
                style={{ background: 'linear-gradient(90deg, var(--primary), var(--secondary))' }}
                animate={{
                  width: `${
                    ((lecture.currentStageIndex + (activeStage?.progress ?? 0) / 100) /
                      lecture.pipeline.length) *
                    100
                  }%`,
                }}
                transition={{ duration: 0.4 }}
              />
            </div>
          </div>
        )}
      </div>
    </motion.button>
  )
}

import { motion } from 'framer-motion'
import type { PipelineStage } from '../../../../types/video'

interface PipelineTimelineProps {
  stages: PipelineStage[]
  compact?: boolean
}

const statusIcon: Record<PipelineStage['status'], string> = {
  pending: '',
  active: '',
  done: '✓',
  skipped: '—',
  error: '!',
}

/** Vertical pipeline visualization used while a lecture is queued/processing. */
export default function PipelineTimeline({ stages, compact = false }: PipelineTimelineProps) {
  return (
    <div className="relative pl-1">
      {stages.map((stage, i) => {
        const isLast = i === stages.length - 1
        return (
          <div key={stage.id} className="relative flex gap-3 pb-4 last:pb-0">
            {!isLast && (
              <span
                className="absolute left-[9px] top-5 bottom-0 w-px"
                style={{
                  background:
                    stage.status === 'done' ? 'var(--primary)' : 'var(--border-subtle)',
                  opacity: stage.status === 'done' ? 0.5 : 1,
                }}
              />
            )}
            <div className="relative flex-shrink-0 w-5 h-5 mt-0.5">
              {stage.status === 'active' ? (
                <motion.span
                  className="absolute inset-0 rounded-full"
                  style={{ border: '2px solid var(--primary)', borderTopColor: 'transparent' }}
                  animate={{ rotate: 360 }}
                  transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
                />
              ) : (
                <span
                  className="absolute inset-0 rounded-full flex items-center justify-center text-[10px] font-bold"
                  style={{
                    background:
                      stage.status === 'done'
                        ? 'var(--primary)'
                        : stage.status === 'error'
                          ? 'var(--danger)'
                          : 'var(--tint-4)',
                    color:
                      stage.status === 'done' || stage.status === 'error'
                        ? 'var(--primary-foreground)'
                        : 'var(--muted-foreground)',
                  }}
                >
                  {statusIcon[stage.status]}
                </span>
              )}
            </div>
            <div className="flex-1 min-w-0 pt-0.5">
              <div className="flex items-center justify-between gap-2">
                <p
                  className={`font-medium truncate ${compact ? 'text-xs' : 'text-sm'}`}
                  style={{
                    color:
                      stage.status === 'pending' ? 'var(--muted-foreground)' : 'var(--foreground)',
                  }}
                >
                  {stage.label}
                </p>
                {stage.status === 'active' && stage.progress !== undefined && (
                  <span
                    className="text-xs font-mono flex-shrink-0"
                    style={{ color: 'var(--primary)' }}
                  >
                    {Math.round(stage.progress)}%
                  </span>
                )}
              </div>
              {!compact && (
                <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                  {stage.description}
                </p>
              )}
              {stage.status === 'active' && (
                <div
                  className="h-1 rounded-full overflow-hidden mt-2"
                  style={{ background: 'var(--tint-3)' }}
                >
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: 'linear-gradient(90deg, var(--primary), var(--secondary))' }}
                    animate={{ width: `${stage.progress ?? 0}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

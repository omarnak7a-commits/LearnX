import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import type { SilenceSegment, VideoStats } from '../../../../types/video'
import { formatDuration } from '../../../../data/videoIntelligenceMock'

interface SilenceComparisonProps {
  stats: VideoStats
  segments: SilenceSegment[]
}

const reasonLabel: Record<SilenceSegment['reason'], string> = {
  'dead-air': 'Dead air',
  'setup-time': 'Setup time',
  waiting: 'Waiting',
  'repeated-pause': 'Repeated pause',
  'idle-moment': 'Idle moment',
  'meaningful-pause': 'Meaningful pause (kept)',
}

function useCountUp(target: number, decimals = 0) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    let raf: number
    const start = performance.now()
    const duration = 1200
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      const val = target * eased
      el.textContent = decimals > 0 ? val.toFixed(decimals) : Math.round(val).toString()
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, decimals])
  return ref
}

function StatBlock({ label, value, suffix, color }: { label: string; value: number; suffix: string; color: string }) {
  const ref = useCountUp(value, suffix === 'h' ? 1 : 0)
  return (
    <div className="p-4 rounded-xl" style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}>
      <p className="text-2xl font-black" style={{ fontFamily: 'Orbitron, sans-serif', color }}>
        <span ref={ref}>0</span>
        {suffix}
      </p>
      <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
    </div>
  )
}

export default function SilenceComparison({ stats, segments }: SilenceComparisonProps) {
  const [hoveredSegment, setHoveredSegment] = useState<string | null>(null)
  const removedCount = segments.filter((s) => s.removed).length
  const keptCount = segments.filter((s) => !s.removed).length

  return (
    <div className="glass-card p-6">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
            ✂️ Smart Lecture Trimming
          </h3>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            AI distinguishes meaningful pauses from dead time — nothing educational is ever removed.
          </p>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        <StatBlock label="Original" value={stats.originalDurationSec / 60} suffix="m" color="var(--muted-foreground)" />
        <StatBlock label="Optimized" value={stats.optimizedDurationSec / 60} suffix="m" color="var(--primary)" />
        <StatBlock label="Minutes saved" value={stats.minutesSaved} suffix="m" color="var(--accent)" />
        <StatBlock label="Removed" value={stats.percentRemoved} suffix="%" color="var(--warning)" />
        <StatBlock label="Efficiency score" value={stats.learningEfficiencyScore} suffix="" color="var(--success)" />
      </div>

      {/* Visual before/after bar */}
      <div className="mb-5">
        <p className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
          Original timeline · {formatDuration(stats.originalDurationSec)}
        </p>
        <div className="relative h-8 rounded-lg overflow-hidden mb-4" style={{ background: 'var(--tint-2)' }}>
          {segments.map((s) => (
            <motion.div
              key={s.id}
              className="absolute top-0 bottom-0 cursor-pointer"
              style={{
                left: `${(s.startSec / stats.originalDurationSec) * 100}%`,
                width: `${((s.endSec - s.startSec) / stats.originalDurationSec) * 100}%`,
                background: s.removed ? 'rgba(239,68,68,0.55)' : 'rgba(34,197,94,0.5)',
                outline: hoveredSegment === s.id ? '2px solid #fff' : 'none',
              }}
              onMouseEnter={() => setHoveredSegment(s.id)}
              onMouseLeave={() => setHoveredSegment(null)}
              whileHover={{ scaleY: 1.15 }}
            />
          ))}
          {hoveredSegment && (
            <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-xs px-2 py-1 rounded surface-tooltip whitespace-nowrap z-10">
              {reasonLabel[segments.find((s) => s.id === hoveredSegment)!.reason]}
            </div>
          )}
        </div>

        <p className="text-xs font-semibold mb-2" style={{ color: 'var(--primary)' }}>
          Optimized timeline · {formatDuration(stats.optimizedDurationSec)}
        </p>
        <div className="relative h-8 rounded-lg overflow-hidden" style={{ background: 'var(--tint-2)' }}>
          <motion.div
            className="absolute inset-y-0 left-0 rounded-lg"
            style={{ background: 'linear-gradient(90deg, var(--primary), var(--secondary))' }}
            initial={{ width: 0 }}
            animate={{ width: `${(stats.optimizedDurationSec / stats.originalDurationSec) * 100}%` }}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs flex-wrap" style={{ color: 'var(--muted-foreground)' }}>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: 'rgba(239,68,68,0.55)' }} /> Removed ({removedCount})
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: 'rgba(34,197,94,0.5)' }} /> Kept — meaningful pause ({keptCount})
        </span>
      </div>
    </div>
  )
}

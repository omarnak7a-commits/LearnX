import { motion } from 'framer-motion'

interface HeatmapGridProps {
  /** 0-1 intensity values, grouped in rows (weeks). */
  data: number[][]
  color?: string
  cellSize?: number
}

/** Generic activity/engagement heatmap grid (GitHub-style), theme-aware. */
export default function HeatmapGrid({ data, color = '#2DD4BF', cellSize = 13 }: HeatmapGridProps) {
  function alpha(v: number) {
    if (v <= 0) return 'var(--tint-3)'
    const a = 0.15 + v * 0.75
    return `color-mix(in srgb, ${color} ${Math.round(a * 100)}%, transparent)`
  }

  return (
    <div className="flex gap-1">
      {data.map((col, ci) => (
        <div key={ci} className="flex flex-col gap-1">
          {col.map((v, ri) => (
            <motion.div
              key={ri}
              style={{
                width: cellSize,
                height: cellSize,
                borderRadius: 3,
                background: alpha(v),
              }}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{
                delay: (ci * col.length + ri) * 0.006,
                duration: 0.25,
              }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

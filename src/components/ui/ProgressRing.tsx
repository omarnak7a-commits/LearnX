import { motion } from 'framer-motion'

interface ProgressRingProps {
  pct: number
  color?: string
  size?: number
  strokeWidth?: number
  label?: string
  valueLabel?: string
  delay?: number
  trackColor?: string
}

/** Reusable animated circular progress indicator used across student & doctor dashboards. */
export default function ProgressRing({
  pct,
  color = 'var(--primary)',
  size = 88,
  strokeWidth = 7,
  label,
  valueLabel,
  delay = 0.3,
  trackColor = 'var(--border-subtle)',
}: ProgressRingProps) {
  const r = size / 2 - strokeWidth - 2
  const circ = 2 * Math.PI * r
  const clamped = Math.max(0, Math.min(100, pct))

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="flex-shrink-0">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={trackColor}
        strokeWidth={strokeWidth}
      />
      <motion.circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circ}
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ * (1 - clamped / 100) }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay }}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x={size / 2}
        y={label ? size / 2 - 4 : size / 2 + 5}
        textAnchor="middle"
        fontSize={size * 0.19}
        fontWeight="900"
        fill={color}
        fontFamily="Orbitron, sans-serif"
      >
        {valueLabel ?? `${Math.round(clamped)}%`}
      </text>
      {label && (
        <text
          x={size / 2}
          y={size / 2 + 12}
          textAnchor="middle"
          fontSize={size * 0.09}
          fill="var(--muted-foreground)"
          fontFamily="Inter, sans-serif"
        >
          {label}
        </text>
      )}
    </svg>
  )
}

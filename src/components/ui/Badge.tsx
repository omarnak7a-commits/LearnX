import { motion } from 'framer-motion'

type BadgeTone = 'primary' | 'accent' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const toneMap: Record<BadgeTone, { bg: string; fg: string; border: string }> = {
  primary: {
    bg: 'rgba(45,212,191,0.12)',
    fg: 'var(--primary)',
    border: 'rgba(45,212,191,0.24)',
  },
  accent: {
    bg: 'rgba(255,126,54,0.12)',
    fg: 'var(--accent)',
    border: 'rgba(255,126,54,0.24)',
  },
  success: {
    bg: 'var(--success-soft)',
    fg: 'var(--success)',
    border: 'transparent',
  },
  warning: {
    bg: 'var(--warning-soft)',
    fg: 'var(--warning)',
    border: 'transparent',
  },
  danger: {
    bg: 'var(--danger-soft)',
    fg: 'var(--danger)',
    border: 'transparent',
  },
  info: { bg: 'var(--info-soft)', fg: 'var(--info)', border: 'transparent' },
  neutral: {
    bg: 'var(--muted)',
    fg: 'var(--muted-foreground)',
    border: 'transparent',
  },
}

interface BadgeProps {
  children: React.ReactNode
  tone?: BadgeTone
  size?: 'xs' | 'sm'
  mono?: boolean
  className?: string
  pulse?: boolean
}

export default function Badge({
  children,
  tone = 'neutral',
  size = 'sm',
  mono = false,
  className = '',
  pulse = false,
}: BadgeProps) {
  const t = toneMap[tone]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${
        size === 'xs' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2.5 py-1'
      } ${className}`}
      style={{
        background: t.bg,
        color: t.fg,
        border: t.border !== 'transparent' ? `1px solid ${t.border}` : undefined,
        fontFamily: mono ? 'JetBrains Mono, monospace' : undefined,
      }}
    >
      {pulse && (
        <motion.span
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: t.fg }}
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
      {children}
    </span>
  )
}

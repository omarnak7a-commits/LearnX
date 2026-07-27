import { motion } from 'framer-motion'

interface EmptyStateProps {
  icon?: string
  title: string
  body?: string
  action?: React.ReactNode
  compact?: boolean
}

/** Consistent, animated placeholder for sections without data yet. */
export default function EmptyState({
  icon = '✨',
  title,
  body,
  action,
  compact = false,
}: EmptyStateProps) {
  return (
    <motion.div
      className="flex flex-col items-center justify-center text-center"
      style={{ padding: compact ? '2rem 1rem' : '3.5rem 1.5rem' }}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <motion.span
        className="block mb-3"
        style={{ fontSize: compact ? 28 : 40 }}
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      >
        {icon}
      </motion.span>
      <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
        {title}
      </p>
      {body && (
        <p className="text-xs mt-1.5 max-w-xs" style={{ color: 'var(--muted-foreground)' }}>
          {body}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </motion.div>
  )
}

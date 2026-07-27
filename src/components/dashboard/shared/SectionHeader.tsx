import { motion } from 'framer-motion'

interface SectionHeaderProps {
  title: string
  subtitle?: string
  action?: React.ReactNode
  icon?: string
}

/** Consistent header used at the top of every dashboard section/card group. */
export default function SectionHeader({ title, subtitle, action, icon }: SectionHeaderProps) {
  return (
    <motion.div
      className="flex items-center justify-between mb-5 gap-4 flex-wrap"
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div>
        <h2
          className="text-lg font-bold flex items-center gap-2"
          style={{
            fontFamily: 'Orbitron, sans-serif',
            color: 'var(--foreground)',
            letterSpacing: '-0.01em',
          }}
        >
          {icon && <span className="text-base">{icon}</span>}
          {title}
        </h2>
        {subtitle && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            {subtitle}
          </p>
        )}
      </div>
      {action}
    </motion.div>
  )
}

import { motion } from 'framer-motion'

interface TabsProps {
  tabs: string[]
  active: string
  onChange: (tab: string) => void
  layoutId?: string
}

/** Shared pill-tab switcher with shared-layout sliding indicator. */
export default function Tabs({ tabs, active, onChange, layoutId = 'tab-indicator' }: TabsProps) {
  return (
    <div
      className="flex items-center gap-1 p-1 rounded-xl w-fit"
      style={{ background: 'var(--muted)' }}
    >
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className="relative px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors z-0"
          style={{
            color: active === tab ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
          }}
        >
          {active === tab && (
            <motion.span
              layoutId={layoutId}
              className="absolute inset-0 rounded-lg -z-10"
              style={{ background: 'var(--primary)' }}
              transition={{ type: 'spring', stiffness: 400, damping: 32 }}
            />
          )}
          {tab}
        </button>
      ))}
    </div>
  )
}

import { motion } from 'framer-motion'

interface Action {
  icon: string
  label: string
  color: string
  id: string
}

const actions: Action[] = [
  { id: 'upload', icon: '📤', label: 'Upload File', color: '#2DD4BF' },
  { id: 'ask-ai', icon: '🤖', label: 'Ask AI', color: '#5eead4' },
  { id: 'quiz', icon: '❓', label: 'Generate Quiz', color: '#a855f7' },
  { id: 'flashcards', icon: '🗂️', label: 'Flashcards', color: '#f59e0b' },
  { id: 'mindmap', icon: '🧠', label: 'Mind Map', color: '#38bdf8' },
  { id: 'notes', icon: '📝', label: 'Create Notes', color: '#22c55e' },
  { id: 'timer', icon: '⏱️', label: 'Study Timer', color: '#FF7E36' },
]

interface QuickActionsProps {
  onAction?: (id: string) => void
}

export default function QuickActions({ onAction }: QuickActionsProps) {
  return (
    <motion.div
      className="glass-card p-5 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
        Quick Actions
      </h3>
      <div className="grid grid-cols-4 sm:grid-cols-7 lg:grid-cols-4 xl:grid-cols-7 gap-2.5">
        {actions.map((a, i) => (
          <motion.button
            key={a.id}
            onClick={() => onAction?.(a.id)}
            className="flex flex-col items-center gap-2 py-3.5 rounded-xl transition-colors"
            style={{
              background: 'var(--tint-1)',
              border: '1px solid var(--border-subtle)',
            }}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              delay: 0.1 + i * 0.05,
              type: 'spring',
              stiffness: 300,
              damping: 22,
            }}
            whileHover={{ y: -3, borderColor: `${a.color}55` }}
            whileTap={{ scale: 0.94 }}
          >
            <span
              className="w-9 h-9 rounded-lg flex items-center justify-center text-base"
              style={{ background: `${a.color}18` }}
            >
              {a.icon}
            </span>
            <span
              className="text-[10.5px] font-medium text-center leading-tight"
              style={{ color: 'var(--foreground)' }}
            >
              {a.label}
            </span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  )
}

import { motion } from 'framer-motion'

interface FileItem {
  name: string
  meta: string
  icon: string
  color: string
}

const files: FileItem[] = [
  {
    name: 'Thermodynamics Ch.12.pdf',
    meta: '32 flashcards generated · 2h ago',
    icon: '📄',
    color: '#2DD4BF',
  },
  {
    name: 'Organic Chem Lecture 9.mp4',
    meta: 'Transcribed & indexed · 5h ago',
    icon: '🎬',
    color: '#a855f7',
  },
  {
    name: 'Calculus Problem Set 6.docx',
    meta: 'Summary ready · Yesterday',
    icon: '📝',
    color: '#f59e0b',
  },
  {
    name: 'Cell Biology Slides.pptx',
    meta: 'Quiz generated · 2 days ago',
    icon: '📊',
    color: '#22c55e',
  },
]

const conversations = [
  { title: "Explain Newton's Second Law simply", time: '10m ago' },
  { title: 'Quiz me on Cell Division', time: '1h ago' },
  { title: 'Summarize Chapter 7 Calculus', time: 'Yesterday' },
]

/** Recent Uploads + Recent AI Conversations, side by side. */
export default function RecentActivityPanels() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <motion.div
        className="glass-card p-6 h-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h3
          className="text-sm font-bold mb-4 flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          📁 Recent Uploads
        </h3>
        <div className="space-y-2">
          {files.map((f, i) => (
            <motion.div
              key={f.name}
              className="flex items-center gap-3 p-3 rounded-xl transition-colors cursor-pointer"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.06 * i }}
              whileHover={{ x: 2 }}
            >
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                style={{ background: `${f.color}18` }}
              >
                {f.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium truncate" style={{ color: 'var(--foreground)' }}>
                  {f.name}
                </p>
                <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                  {f.meta}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      <motion.div
        className="glass-card p-6 h-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.05 }}
      >
        <h3
          className="text-sm font-bold mb-4 flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          🤖 Recent AI Conversations
        </h3>
        <div className="space-y-2">
          {conversations.map((c, i) => (
            <motion.div
              key={c.title}
              className="flex items-center gap-3 p-3 rounded-xl transition-colors cursor-pointer"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.06 * i }}
              whileHover={{ x: 2 }}
            >
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                style={{ background: 'rgba(45,212,191,0.12)' }}
              >
                💬
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium truncate" style={{ color: 'var(--foreground)' }}>
                  {c.title}
                </p>
                <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                  {c.time}
                </p>
              </div>
              <span className="text-xs flex-shrink-0" style={{ color: 'var(--primary)' }}>
                →
              </span>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

import { motion } from 'framer-motion'
import EmptyState from './EmptyState'

interface Conversation {
  id: number
  name: string
  preview: string
  time: string
  unread?: boolean
}

const conversations: Conversation[] = [
  {
    id: 1,
    name: 'Amelia Torres',
    preview: 'Thank you for the feedback on my project!',
    time: '10m',
    unread: true,
  },
  {
    id: 2,
    name: 'CS201 — Study Group',
    preview: 'Can we get an extension on the lab report?',
    time: '1h',
    unread: true,
  },
  {
    id: 3,
    name: 'Ravi Malhotra',
    preview: 'Uploaded my revised submission.',
    time: '3h',
  },
  {
    id: 4,
    name: 'Academic Office',
    preview: 'Reminder: grade submission deadline Friday.',
    time: '1d',
  },
]

export default function MessagesPage() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">
      <motion.div
        className="glass-card overflow-hidden"
        initial={{ opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <input
            placeholder="Search messages..."
            className="input-field w-full px-3.5 py-2 rounded-lg text-xs"
          />
        </div>
        <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
          {conversations.map((c, i) => (
            <motion.button
              key={c.id}
              className="w-full flex items-center gap-3 px-5 py-3.5 text-left transition-colors"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.05 }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{
                  background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
                  color: 'var(--primary-foreground)',
                }}
              >
                {c.name
                  .split(' ')
                  .map((w) => w[0])
                  .slice(0, 2)
                  .join('')}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p
                    className="text-xs font-semibold truncate"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {c.name}
                  </p>
                  <span
                    className="text-xs flex-shrink-0"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {c.time}
                  </span>
                </div>
                <p
                  className="text-xs truncate mt-0.5"
                  style={{
                    color: c.unread ? 'var(--foreground)' : 'var(--muted-foreground)',
                  }}
                >
                  {c.preview}
                </p>
              </div>
              {c.unread && (
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: 'var(--primary)' }}
                />
              )}
            </motion.button>
          ))}
        </div>
      </motion.div>

      <motion.div
        className="glass-card flex flex-col"
        style={{ minHeight: 420 }}
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <div
          className="px-5 py-4 border-b flex items-center gap-3"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold"
            style={{
              background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
              color: 'var(--primary-foreground)',
            }}
          >
            AT
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
              Amelia Torres
            </p>
            <p className="text-xs" style={{ color: 'var(--primary)' }}>
              ● Active now
            </p>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <EmptyState
            icon="💬"
            title="Select a conversation"
            body="Choose a thread from the list to start messaging."
            compact
          />
        </div>
      </motion.div>
    </div>
  )
}

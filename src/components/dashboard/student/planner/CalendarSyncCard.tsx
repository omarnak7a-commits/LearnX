import { useState } from 'react'
import { motion } from 'framer-motion'

const providers = [
  { id: 'google', label: 'Google Calendar', icon: '🗓️' },
  { id: 'outlook', label: 'Microsoft Outlook', icon: '📧' },
  { id: 'apple', label: 'Apple Calendar', icon: '📆' },
]

export default function CalendarSyncCard() {
  const [connected, setConnected] = useState<Record<string, boolean>>({})

  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--foreground)' }}>
        Sync your calendar
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
        Push your AI study plan into the calendar you already use.
      </p>
      <div className="space-y-2">
        {providers.map((p) => {
          const isConnected = connected[p.id]
          return (
            <div
              key={p.id}
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{ background: 'var(--tint-1)' }}
            >
              <span className="text-lg flex-shrink-0">{p.icon}</span>
              <p className="text-sm font-medium flex-1" style={{ color: 'var(--foreground)' }}>
                {p.label}
              </p>
              <motion.button
                onClick={() => setConnected((prev) => ({ ...prev, [p.id]: !prev[p.id] }))}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg flex-shrink-0"
                style={{
                  background: isConnected ? 'var(--success-soft)' : 'var(--primary)',
                  color: isConnected ? 'var(--success)' : 'var(--primary-foreground)',
                }}
                whileTap={{ scale: 0.95 }}
              >
                {isConnected ? '✓ Connected' : 'Connect'}
              </motion.button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

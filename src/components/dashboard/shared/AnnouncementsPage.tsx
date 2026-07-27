import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import EmptyState from './EmptyState'

interface Announcement {
  id: number
  title: string
  body: string
  course: string
  time: string
  color: string
}

const seed: Announcement[] = [
  {
    id: 1,
    title: 'Midterm exam schedule released',
    body: 'The CS201 midterm will be held Aug 8, 10am–12pm in Hall B.',
    course: 'CS201',
    time: '2h ago',
    color: '#2DD4BF',
  },
  {
    id: 2,
    title: 'Assignment 3 deadline extended',
    body: 'Due to popular request, the ER Diagram assignment is now due Aug 6.',
    course: 'CS310',
    time: '1d ago',
    color: '#f59e0b',
  },
  {
    id: 3,
    title: 'Guest lecture next week',
    body: "We'll have an industry guest speaker on distributed systems.",
    course: 'CS420',
    time: '3d ago',
    color: '#a855f7',
  },
]

export default function AnnouncementsPage() {
  const [announcements, setAnnouncements] = useState(seed)
  const [draft, setDraft] = useState('')

  function post() {
    if (!draft.trim()) return
    setAnnouncements((prev) => [
      {
        id: Date.now(),
        title: draft,
        body: 'Posted to all enrolled students.',
        course: 'All courses',
        time: 'Just now',
        color: '#2DD4BF',
      },
      ...prev,
    ])
    setDraft('')
  }

  return (
    <div className="space-y-5">
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          New announcement
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write an announcement for your students..."
            className="input-field flex-1 px-4 py-2.5 rounded-xl text-sm"
          />
          <button
            onClick={post}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold flex-shrink-0"
            style={{
              background: 'var(--primary)',
              color: 'var(--primary-foreground)',
            }}
          >
            Post
          </button>
        </div>
      </motion.div>

      <div className="space-y-3">
        <AnimatePresence initial={false}>
          {announcements.map((a, i) => (
            <motion.div
              key={a.id}
              className="glass-card p-5"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ delay: i === 0 ? 0 : 0.04 * i }}
            >
              <div className="flex items-start gap-3">
                <span
                  className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                  style={{ background: a.color }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                      {a.title}
                    </p>
                    <span
                      className="text-xs flex-shrink-0"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {a.time}
                    </span>
                  </div>
                  <p
                    className="text-xs mt-1 leading-relaxed"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {a.body}
                  </p>
                  <span
                    className="inline-block mt-2 text-xs px-2 py-0.5 rounded-md font-mono"
                    style={{ background: `${a.color}18`, color: a.color }}
                  >
                    {a.course}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {announcements.length === 0 && (
          <EmptyState
            icon="📣"
            title="No announcements yet"
            body="Post your first announcement above."
          />
        )}
      </div>
    </div>
  )
}

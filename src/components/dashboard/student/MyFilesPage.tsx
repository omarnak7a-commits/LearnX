import { motion } from 'framer-motion'
import DropZone from '../shared/DropZone'

interface FileRow {
  name: string
  type: string
  size: string
  date: string
  icon: string
  color: string
}

const rows: FileRow[] = [
  {
    name: 'Thermodynamics Ch.12.pdf',
    type: 'PDF',
    size: '4.2 MB',
    date: '2h ago',
    icon: '📄',
    color: '#2DD4BF',
  },
  {
    name: 'Organic Chem Lecture 9.mp4',
    type: 'Video',
    size: '182 MB',
    date: '5h ago',
    icon: '🎬',
    color: '#a855f7',
  },
  {
    name: 'Calculus Problem Set 6.docx',
    type: 'DOCX',
    size: '860 KB',
    date: 'Yesterday',
    icon: '📝',
    color: '#f59e0b',
  },
  {
    name: 'Cell Biology Slides.pptx',
    type: 'PPTX',
    size: '12.1 MB',
    date: '2 days ago',
    icon: '📊',
    color: '#22c55e',
  },
  {
    name: 'Physics Past Papers.zip',
    type: 'Archive',
    size: '28.4 MB',
    date: '4 days ago',
    icon: '🗂️',
    color: '#38bdf8',
  },
]

export default function MyFilesPage() {
  return (
    <div className="space-y-5">
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          Upload materials
        </h3>
        <DropZone />
      </motion.div>

      <motion.div
        className="glass-card overflow-hidden"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            All files
          </h3>
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {rows.length} files
          </span>
        </div>
        <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
          {rows.map((r, i) => (
            <motion.div
              key={r.name}
              className="flex items-center gap-3 px-6 py-3.5 transition-colors"
              style={{ borderColor: 'var(--border-subtle)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.04 * i }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <span
                className="w-9 h-9 rounded-lg flex items-center justify-center text-base flex-shrink-0"
                style={{ background: `${r.color}18` }}
              >
                {r.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate" style={{ color: 'var(--foreground)' }}>
                  {r.name}
                </p>
              </div>
              <span
                className="text-xs hidden sm:block w-16"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {r.type}
              </span>
              <span
                className="text-xs hidden sm:block w-16"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {r.size}
              </span>
              <span
                className="text-xs w-20 text-right"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {r.date}
              </span>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

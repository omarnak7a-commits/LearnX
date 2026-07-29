import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface FileEntry {
  id: number
  name: string
  size: string
  progress: number
  status: 'uploading' | 'done' | 'error'
  type: string
}

const typeIcon: Record<string, string> = {
  pdf: '📄',
  ppt: '📊',
  docx: '📝',
  video: '🎬',
  default: '📁',
}

interface DropZoneProps {
  title?: string
  subtitle?: string
  accept?: string
}

/** Beautiful drag-and-drop upload surface, reused for student uploads and
 * doctor course-material uploads. Simulates upload progress for the demo. */
export default function DropZone({
  title = 'Drag & drop files here',
  subtitle = 'PDF, PPT, DOCX, or video — up to 500MB',
  accept = '.pdf,.ppt,.pptx,.doc,.docx,.mp4,.mov',
}: DropZoneProps) {
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState<FileEntry[]>([])

  function addFiles(list: FileList | null) {
    if (!list) return
    const entries: FileEntry[] = Array.from(list).map((f, i) => ({
      id: Date.now() + i,
      name: f.name,
      size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
      progress: 0,
      status: 'uploading',
      type: f.name.split('.').pop()?.toLowerCase().includes('pdf')
        ? 'pdf'
        : f.name.match(/ppt/i)
          ? 'ppt'
          : f.name.match(/docx?|doc/i)
            ? 'docx'
            : f.name.match(/mp4|mov|mkv/i)
              ? 'video'
              : 'default',
    }))
    setFiles((prev) => [...entries, ...prev])
    entries.forEach((entry) => simulateUpload(entry.id))
  }

  function simulateUpload(id: number) {
    const tick = () => {
      setFiles((prev) =>
        prev.map((f) => {
          if (f.id !== id || f.status !== 'uploading') return f
          const next = Math.min(100, f.progress + Math.random() * 22 + 8)
          return {
            ...f,
            progress: next,
            status: next >= 100 ? 'done' : 'uploading',
          }
        })
      )
    }
    const interval = setInterval(() => {
      tick()
    }, 260)
    setTimeout(() => clearInterval(interval), 2200)
  }

  return (
    <div>
      <motion.label
        htmlFor="dropzone-input"
        className="relative flex flex-col items-center justify-center gap-3 rounded-2xl px-6 py-10 cursor-pointer text-center transition-colors"
        style={{
          border: `2px dashed ${dragging ? 'var(--primary)' : 'var(--border)'}`,
          background: dragging ? 'rgba(45,212,191,0.06)' : 'var(--tint-1)',
        }}
        animate={{ scale: dragging ? 1.01 : 1 }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          addFiles(e.dataTransfer.files)
        }}
      >
        <input
          id="dropzone-input"
          type="file"
          multiple
          accept={accept}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
        <motion.div
          className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
          style={{ background: 'rgba(45,212,191,0.12)' }}
          animate={{ y: dragging ? -4 : [0, -4, 0] }}
          transition={
            dragging ? { duration: 0.2 } : { duration: 2.4, repeat: Infinity, ease: 'easeInOut' }
          }
        >
          ⬆️
        </motion.div>
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
            {title}
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            {subtitle}
          </p>
        </div>
        <span
          className="text-xs font-semibold px-4 py-2 rounded-full"
          style={{
            background: 'var(--primary)',
            color: 'var(--primary-foreground)',
          }}
        >
          Browse files
        </span>
      </motion.label>

      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          <AnimatePresence initial={false}>
            {files.map((f) => (
              <motion.div
                key={f.id}
                className="flex items-center gap-3 px-4 py-3 rounded-xl"
                style={{
                  background: 'var(--tint-1)',
                  border: '1px solid var(--border-subtle)',
                }}
                initial={{ opacity: 0, height: 0, y: -8 }}
                animate={{ opacity: 1, height: 'auto', y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <span className="text-lg flex-shrink-0">
                  {typeIcon[f.type] ?? typeIcon.default}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p
                      className="text-xs font-medium truncate"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {f.name}
                    </p>
                    <span
                      className="text-xs flex-shrink-0"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {f.size}
                    </span>
                  </div>
                  <div
                    className="h-1.5 rounded-full overflow-hidden mt-1.5"
                    style={{ background: 'var(--tint-3)' }}
                  >
                    <motion.div
                      className="h-full rounded-full"
                      style={{
                        background:
                          f.status === 'done'
                            ? 'var(--success)'
                            : 'linear-gradient(90deg, var(--primary), var(--secondary))',
                      }}
                      animate={{ width: `${f.progress}%` }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                </div>
                {f.status === 'done' ? (
                  <span className="text-xs flex-shrink-0" style={{ color: 'var(--success)' }}>
                    ✓
                  </span>
                ) : (
                  <span
                    className="text-xs flex-shrink-0 font-mono"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {Math.round(f.progress)}%
                  </span>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}

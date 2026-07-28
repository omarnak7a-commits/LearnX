import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { VideoSourceType } from '../../../../types/video'

interface VideoUploadZoneProps {
  onUpload: (file: { name: string; sourceType: VideoSourceType; sizeLabel: string }) => void
}

const sourceOptions: Array<{ id: VideoSourceType; label: string; icon: string }> = [
  { id: 'upload', label: 'Upload file', icon: '⬆️' },
  { id: 'zoom', label: 'Zoom recording', icon: '🎥' },
  { id: 'teams', label: 'Teams recording', icon: '🟣' },
  { id: 'meet', label: 'Google Meet', icon: '📹' },
  { id: 'screen-recording', label: 'Screen recording', icon: '🖥️' },
]

/**
 * Drag-and-drop / chunked upload surface for the AI Video Intelligence
 * feature. Supports MP4/MOV/AVI/MKV/WEBM. Simulates a resumable, chunked
 * upload with a visible progress bar — matching the "large files must be
 * processed asynchronously with visible progress" requirement — and, on
 * completion, hands the new lecture off to the processing pipeline.
 */
export default function VideoUploadZone({ onUpload }: VideoUploadZoneProps) {
  const [dragging, setDragging] = useState(false)
  const [source, setSource] = useState<VideoSourceType>('upload')
  const [uploading, setUploading] = useState<{ name: string; progress: number; sizeLabel: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return
    const file = list[0]
    const sizeLabel = `${(file.size / (1024 * 1024)).toFixed(0)} MB`
    setUploading({ name: file.name, progress: 0, sizeLabel })
    simulateChunkedUpload(file.name, sizeLabel)
  }

  function simulateChunkedUpload(name: string, sizeLabel: string) {
    let progress = 0
    const interval = setInterval(() => {
      progress = Math.min(100, progress + Math.random() * 14 + 6)
      setUploading((prev) => (prev ? { ...prev, progress } : prev))
      if (progress >= 100) {
        clearInterval(interval)
        setTimeout(() => {
          onUpload({ name, sourceType: source, sizeLabel })
          setUploading(null)
        }, 400)
      }
    }, 350)
  }

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
            🎬 Upload a Lecture
          </h3>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            MP4, MOV, AVI, MKV, WEBM · Zoom, Teams, Meet & screen recordings · resumable uploads up to several GB
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {sourceOptions.map((s) => (
          <button
            key={s.id}
            onClick={() => setSource(s.id)}
            className="text-xs px-3 py-1.5 rounded-full font-medium transition-colors flex items-center gap-1.5"
            style={{
              background: source === s.id ? 'rgba(45,212,191,0.12)' : 'var(--tint-2)',
              color: source === s.id ? 'var(--primary)' : 'var(--muted-foreground)',
              border: `1px solid ${source === s.id ? 'rgba(45,212,191,0.3)' : 'transparent'}`,
            }}
          >
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {uploading ? (
          <motion.div
            key="uploading"
            className="rounded-2xl p-6"
            style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="flex items-center gap-3 mb-3">
              <motion.span
                className="text-xl"
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
              >
                ⏳
              </motion.span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate" style={{ color: 'var(--foreground)' }}>
                  {uploading.name}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {uploading.sizeLabel} · uploading in chunks…
                </p>
              </div>
              <span className="text-sm font-mono flex-shrink-0" style={{ color: 'var(--primary)' }}>
                {Math.round(uploading.progress)}%
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
              <motion.div
                className="h-full rounded-full"
                style={{ background: 'linear-gradient(90deg, var(--primary), var(--secondary))' }}
                animate={{ width: `${uploading.progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </motion.div>
        ) : (
          <motion.label
            key="dropzone"
            htmlFor="video-upload-input"
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
              handleFiles(e.dataTransfer.files)
            }}
          >
            <input
              ref={inputRef}
              id="video-upload-input"
              type="file"
              accept=".mp4,.mov,.avi,.mkv,.webm,video/*"
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <motion.div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
              style={{ background: 'rgba(45,212,191,0.12)' }}
              animate={{ y: [0, -4, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
            >
              🎬
            </motion.div>
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                Drag & drop a lecture video, or click to browse
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                The AI pipeline starts automatically once the upload completes
              </p>
            </div>
            <span
              className="text-xs font-semibold px-4 py-2 rounded-full"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              Browse files
            </span>
          </motion.label>
        )}
      </AnimatePresence>
    </div>
  )
}

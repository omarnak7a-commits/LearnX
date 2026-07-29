import { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useFileVault } from '../../../../context/FileVaultContext'

const courseOptions = [
  'Cell Biology',
  'Calculus & Analysis',
  'Operating Systems',
  'Classical Mechanics',
  'Organic Chemistry II',
  'Data Structures & Algorithms',
  'Uncategorized',
]

/**
 * Real PDF upload surface for the Smart AI File Vault. Every dropped/
 * selected file is genuinely parsed with pdf.js and run through the
 * extractive AI analysis engine the moment it lands — students never
 * press a "Generate" button, matching the spec's "generate automatically
 * after upload" requirement.
 */
export default function FileUploadZone() {
  const { uploadFile, uploadProgress } = useFileVault()
  const [dragging, setDragging] = useState(false)
  const [course, setCourse] = useState(courseOptions[0])
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFiles(list: FileList | null) {
    if (!list) return
    const pdfFiles = Array.from(list).filter(
      (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
    )
    for (const file of pdfFiles) {
      await uploadFile(file, { course, doctorName: 'Self-uploaded' })
    }
  }

  const activeUploads = Object.entries(uploadProgress)

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h3
            className="text-sm font-bold flex items-center gap-2"
            style={{ color: 'var(--foreground)' }}
          >
            📚 Upload a Document
          </h3>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            Every PDF becomes a full AI learning workspace the moment it's uploaded.
          </p>
        </div>
        <select
          value={course}
          onChange={(e) => setCourse(e.target.value)}
          className="input-field px-3 py-2 rounded-lg text-xs"
        >
          {courseOptions.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <motion.label
        htmlFor="file-vault-input"
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
          id="file-vault-input"
          ref={inputRef}
          type="file"
          multiple
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
        <motion.div
          className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
          style={{ background: 'rgba(45,212,191,0.12)' }}
          animate={{ y: dragging ? -4 : [0, -4, 0] }}
          transition={
            dragging ? { duration: 0.2 } : { duration: 2.4, repeat: Infinity, ease: 'easeInOut' }
          }
        >
          📄
        </motion.div>
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
            Drag & drop PDF lecture notes here
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            PDF only — AI extracts real text, generates summaries, flashcards, and quizzes instantly
          </p>
        </div>
        <span
          className="text-xs font-semibold px-4 py-2 rounded-full"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Browse files
        </span>
      </motion.label>

      {activeUploads.length > 0 && (
        <div className="mt-4 space-y-2">
          <AnimatePresence initial={false}>
            {activeUploads.map(([id, progress]) => (
              <motion.div
                key={id}
                className="flex items-center gap-3 px-4 py-3 rounded-xl"
                style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
                initial={{ opacity: 0, height: 0, y: -8 }}
                animate={{ opacity: 1, height: 'auto', y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <span className="text-lg flex-shrink-0">🧠</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>
                    {progress < 55
                      ? 'Reading file...'
                      : progress < 75
                        ? 'Extracting text...'
                        : progress < 95
                          ? 'Running AI analysis...'
                          : 'Finalizing workspace...'}
                  </p>
                  <div
                    className="h-1.5 rounded-full overflow-hidden mt-1.5"
                    style={{ background: 'var(--tint-3)' }}
                  >
                    <motion.div
                      className="h-full rounded-full"
                      style={{
                        background: 'linear-gradient(90deg, var(--primary), var(--secondary))',
                      }}
                      animate={{ width: `${progress}%` }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                </div>
                <span
                  className="text-xs flex-shrink-0 font-mono"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  {Math.round(progress)}%
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}

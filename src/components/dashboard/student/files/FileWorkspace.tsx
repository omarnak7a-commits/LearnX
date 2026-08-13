import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import type { VaultFile, VaultQuestionType, VaultQuizQuestion } from '../../../../types/fileVault'
import { readingPercent, isFullyRead } from '../../../../types/fileVault'
import { useFileVault } from '../../../../context/FileVaultContext'
import { useXp } from '../../../../context/XpContext'
import { useChallenges } from '../../../../context/ChallengesContext'
import type { WorkspaceTab } from './FileCard'
import PdfViewer from './PdfViewer'
import QuizRunner from './QuizRunner'
import { answerAboutFile } from './fileChatEngine'
import { aiApi } from '../../../../lib/ai/apiClient'
import { aiWelcomeMessage } from '../../../../lib/ai/language'
import { useAiLanguage } from '../../../../hooks/useAiLanguage'
import { formatRelativeTime, formatStudyTime, pagesRemaining } from './fileVaultFormat'
import Badge from '../../../ui/Badge'

interface FileWorkspaceProps {
  file: VaultFile
  initialTab?: WorkspaceTab
  onBack: () => void
}

const TABS: Array<{ id: WorkspaceTab; label: string; icon: string }> = [
  { id: 'viewer', label: 'PDF Viewer', icon: '📖' },
  { id: 'chat', label: 'AI Chat', icon: '✨' },
  { id: 'summary', label: 'Summary', icon: '💡' },
  { id: 'topics', label: 'Topics', icon: '🏷️' },
  { id: 'notes', label: 'Notes', icon: '📝' },
  { id: 'flashcards', label: 'Flashcards', icon: '🗂️' },
  { id: 'mindmap', label: 'Mind Map', icon: '🧠' },
  { id: 'quiz', label: 'Practice Quiz', icon: '❓' },
  { id: 'exam', label: 'Exam', icon: '🎓' },
  { id: 'stats', label: 'Statistics', icon: '📊' },
]

/**
 * The full "opening a PDF" experience — everything from the spec's File
 * Details Panel section in one tabbed workspace, all reading/updating
 * the same real VaultFile record in real time via useFileVault().
 */
export default function FileWorkspace({ file, initialTab = 'viewer', onBack }: FileWorkspaceProps) {
  const {
    getPdfDocument,
    markPageRead,
    setCurrentPage,
    addStudyTime,
    addNote,
    addBookmark,
    removeBookmark,
    generatePracticeQuiz,
    generateExam,
    recordAttempt,
  } = useFileVault()
  const { award, recordStudyMinutes } = useXp()
  const { recordProgress } = useChallenges()
  const [tab, setTab] = useState<WorkspaceTab>(initialTab)
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null)
  const sessionStartRef = useRef(Date.now())

  useEffect(() => {
    let cancelled = false
    getPdfDocument(file.id).then((d) => {
      if (!cancelled) setDoc(d)
    })
    return () => {
      cancelled = true
    }
  }, [file.id, getPdfDocument])

  // Track real study time spent in this workspace and flush it on unmount —
  // both into the File Vault's per-file stats and the Global XP System's
  // "Study 30 Minutes" award (spec Feature 2), plus daily/weekly
  // "study-minutes" challenge progress.
  useEffect(() => {
    sessionStartRef.current = Date.now()
    return () => {
      const elapsed = Math.round((Date.now() - sessionStartRef.current) / 1000)
      if (elapsed > 2) {
        addStudyTime(file.id, elapsed)
        recordStudyMinutes(elapsed / 60)
        recordProgress('study-minutes', elapsed / 60)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file.id])

  const pct = readingPercent(file)
  const fullyRead = isFullyRead(file)
  const remaining = pagesRemaining(file)

  return (
    <div className="space-y-5">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs font-semibold"
        style={{ color: 'var(--muted-foreground)' }}
      >
        ← Back to My Files
      </button>

      <motion.div
        className="glass-card p-5 flex flex-col sm:flex-row gap-4"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h2
              className="text-base font-bold"
              style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
            >
              {file.title}
            </h2>
            <Badge tone="neutral" size="xs">
              {file.course}
            </Badge>
          </div>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {file.doctorName} · {file.pageCount} pages · {pct}% read ({remaining} pages remaining) ·
            Last viewed {formatRelativeTime(file.lastViewedAt)}
          </p>
        </div>
      </motion.div>

      <div className="flex items-center gap-1 overflow-x-auto scrollbar-thin pb-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex-shrink-0 flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
            style={{
              background: tab === t.id ? 'var(--primary)' : 'var(--tint-2)',
              color: tab === t.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
            }}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {tab === 'viewer' && (
            <div className="glass-card overflow-hidden" style={{ height: 640 }}>
              <PdfViewer
                doc={doc}
                currentPage={file.currentPage}
                onPageChange={(page) => setCurrentPage(file.id, page)}
                onPageRead={(page) => {
                  markPageRead(file.id, page)
                  recordProgress('pdf-read')
                }}
                color={file.color}
              />
            </div>
          )}

          {tab === 'chat' && <FileChatPanel file={file} />}
          {tab === 'summary' && <FileSummaryPanel file={file} />}
          {tab === 'topics' && <FileTopicsPanel file={file} />}
          {tab === 'notes' && (
            <FileNotesPanel
              file={file}
              onAddNote={(text) => {
                addNote(file.id, file.currentPage, text)
                award('upload-notes', {
                  detail: file.title,
                  dedupeKey: `note-${file.id}-${Date.now()}`,
                })
                recordProgress('notes-uploaded')
              }}
              onAddBookmark={(label) => addBookmark(file.id, file.currentPage, label)}
              onRemoveBookmark={(id) => removeBookmark(file.id, id)}
            />
          )}
          {tab === 'flashcards' && <FileFlashcardsPanel file={file} />}
          {tab === 'mindmap' && <FileMindMapPanel file={file} />}

          {tab === 'quiz' && (
            <div className="glass-card p-6">
              {pct === 0 ? (
                <EmptyMessage text="Read at least one page before generating a practice quiz." />
              ) : (
                <PracticeQuizPanel
                  file={file}
                  onGenerate={() => generatePracticeQuiz(file.id, 6)}
                  onExit={() => setTab('viewer')}
                  onComplete={({ scorePct, totalQuestions, correctCount }) => {
                    recordAttempt(
                      file.id,
                      'practice',
                      scorePct,
                      totalQuestions,
                      correctCount,
                      file.pagesRead
                    )
                    award('quiz-complete', {
                      detail: file.title,
                      dedupeKey: `quiz-${file.id}-${Date.now()}`,
                    })
                    recordProgress('quiz-complete')
                    if (scorePct > 90) {
                      award('quiz-high-score', {
                        detail: file.title,
                        dedupeKey: `quiz-high-${file.id}-${Date.now()}`,
                      })
                      recordProgress('quiz-high-score')
                    }
                  }}
                />
              )}
            </div>
          )}

          {tab === 'exam' && (
            <div className="glass-card p-6">
              {!fullyRead ? (
                <EmptyMessage text="Finish reading this document to unlock the full AI Exam." />
              ) : (
                <ExamSetup
                  file={file}
                  onExit={() => setTab('viewer')}
                  onGenerate={generateExam}
                  onRecordAttempt={(
                    id,
                    kind,
                    scorePct,
                    totalQuestions,
                    correctCount,
                    coveragePages
                  ) => {
                    recordAttempt(id, kind, scorePct, totalQuestions, correctCount, coveragePages)
                    award('quiz-complete', {
                      detail: file.title,
                      dedupeKey: `exam-${file.id}-${Date.now()}`,
                    })
                    recordProgress('quiz-complete')
                    if (scorePct > 90) {
                      award('quiz-high-score', {
                        detail: file.title,
                        dedupeKey: `exam-high-${file.id}-${Date.now()}`,
                      })
                      recordProgress('quiz-high-score')
                    }
                  }}
                />
              )}
            </div>
          )}

          {tab === 'stats' && <FileStatsPanel file={file} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function EmptyMessage({ text }: { text: string }) {
  return (
    <p className="text-sm text-center py-8" style={{ color: 'var(--muted-foreground)' }}>
      {text}
    </p>
  )
}

function PracticeQuizPanel({
  file,
  onGenerate,
  onExit,
  onComplete,
}: {
  file: VaultFile
  onGenerate: () => Promise<VaultQuizQuestion[]>
  onExit: () => void
  onComplete: (result: {
    scorePct: number
    totalQuestions: number
    correctCount: number
  }) => void
}) {
  const [questions, setQuestions] = useState<VaultQuizQuestion[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setQuestions(null)
    setError(null)
    onGenerate()
      .then((generated) => {
        if (!cancelled) setQuestions(generated)
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : 'Could not generate this quiz.')
        }
      })
    return () => {
      cancelled = true
    }
    // Regenerate only when this file changes or the user explicitly retries.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file.id, attempt])

  if (error) {
    return (
      <div className="text-center py-8">
        <EmptyMessage text={error} />
        <button
          onClick={() => setAttempt((value) => value + 1)}
          className="text-xs font-semibold"
          style={{ color: 'var(--primary)' }}
        >
          Try again
        </button>
      </div>
    )
  }
  if (questions === null) return <EmptyMessage text="AI is generating a grounded practice quiz…" />

  return (
    <QuizRunner
      title="Practice Quiz (Covered Topics Only)"
      questions={questions}
      accentColor={file.color}
      onExit={onExit}
      onComplete={onComplete}
    />
  )
}

function FileChatPanel({ file }: { file: VaultFile }) {
  const { language } = useAiLanguage()
  const welcome = aiWelcomeMessage('file', language, file.title)
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([
    { role: 'assistant', text: welcome },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    setMessages((prev) => {
      if (prev.length === 1 && prev[0]?.role === 'assistant') {
        return [{ role: 'assistant', text: welcome }]
      }
      return prev
    })
  }, [welcome])

  async function send(text: string) {
    const message = text.trim()
    if (!message || sending) return
    const history = messages.slice(-20).map((item) => ({ role: item.role, content: item.text }))
    setMessages((prev) => [...prev, { role: 'user', text: message }])
    setInput('')
    setSending(true)
    try {
      const response = await aiApi.chat({
        message,
        fileId: file.id,
        history,
        language,
      })
      setMessages((prev) => [...prev, { role: 'assistant', text: response.answer }])
    } catch {
      // Preserve the existing local, document-grounded engine for offline
      // sessions while preferring Gemini/Groq whenever the backend is live.
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: answerAboutFile(message, file) },
      ])
    } finally {
      setSending(false)
    }
  }

  const suggestions = [
    'Explain this lecture',
    'Summarize this chapter',
    'Create exam questions',
    'Find important topics',
  ]

  return (
    <div className="glass-card p-5 flex flex-col" style={{ height: 500 }}>
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3 mb-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[85%] px-3 py-2 rounded-xl text-sm leading-relaxed"
              style={{
                background: m.role === 'user' ? 'rgba(45,212,191,0.15)' : 'var(--tint-3)',
                color: 'var(--foreground)',
                borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              }}
            >
              {m.text}
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => void send(s)}
            className="text-xs px-2.5 py-1 rounded-full"
            style={{
              background: 'rgba(45,212,191,0.08)',
              color: 'var(--primary)',
              border: '1px solid rgba(45,212,191,0.2)',
            }}
          >
            {s}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void send(input)
        }}
        className="flex items-center gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={language === 'ar' ? `اسأل عن ${file.title}...` : `Ask about ${file.title}...`}
          dir={language === 'ar' ? 'rtl' : 'ltr'}
          className="input-field flex-1 px-3.5 py-2.5 rounded-lg text-sm"
        />
        <button
          type="submit"
          disabled={sending}
          className="px-4 py-2.5 rounded-lg text-sm font-semibold flex-shrink-0"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Send
        </button>
      </form>
    </div>
  )
}

function FileSummaryPanel({ file }: { file: VaultFile }) {
  const [level, setLevel] = useState<'exec' | 'short' | 'detailed'>('short')
  if (!file.analysis) return <EmptyMessage text="AI analysis is still processing." />
  const a = file.analysis
  const text =
    level === 'exec' ? a.executiveSummary : level === 'short' ? a.shortSummary : a.detailedSummary

  return (
    <div className="space-y-4">
      <div className="glass-card p-5">
        <div className="flex items-center gap-1.5 mb-4">
          {(['exec', 'short', 'detailed'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLevel(l)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg"
              style={{
                background: level === l ? 'var(--primary)' : 'var(--tint-2)',
                color: level === l ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              {l === 'exec' ? 'Executive' : l === 'short' ? 'Short' : 'Detailed'}
            </button>
          ))}
        </div>
        <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
          {text}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card p-5">
          <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            🎯 Learning Objectives
          </p>
          <ul className="space-y-1.5">
            {a.learningObjectives.map((o, i) => (
              <li
                key={i}
                className="text-xs flex items-start gap-2"
                style={{ color: 'var(--muted-foreground)' }}
              >
                <span style={{ color: 'var(--primary)' }}>▸</span> {o}
              </li>
            ))}
          </ul>
        </div>
        <div className="glass-card p-5">
          <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            🎓 Exam Tips
          </p>
          <ul className="space-y-1.5">
            {a.examTips.map((t, i) => (
              <li key={i} className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="glass-card p-5">
        <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
          📝 Revision Notes
        </p>
        <ul className="space-y-1.5">
          {a.revisionNotes.slice(0, 6).map((n, i) => (
            <li key={i} className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              • {n}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function FileTopicsPanel({ file }: { file: VaultFile }) {
  if (!file.analysis) return <EmptyMessage text="AI analysis is still processing." />
  const a = file.analysis
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="glass-card p-5">
        <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
          🏷️ Key Concepts
        </p>
        <div className="flex flex-wrap gap-1.5">
          {a.keyConcepts.map((c) => (
            <span
              key={c}
              className="text-xs px-2.5 py-1 rounded-full"
              style={{ background: `${file.color}18`, color: file.color }}
            >
              {c}
            </span>
          ))}
        </div>
      </div>
      <div className="glass-card p-5">
        <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
          ⚠️ Difficult Topics
        </p>
        <ul className="space-y-1.5">
          {a.difficultTopics.map((t, i) => (
            <li key={i} className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {t}
            </li>
          ))}
        </ul>
      </div>
      <div className="glass-card p-5 md:col-span-2">
        <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
          📖 Important Definitions
        </p>
        <div className="space-y-2">
          {a.definitions.map((d, i) => (
            <div key={i} className="p-2.5 rounded-lg" style={{ background: 'var(--tint-1)' }}>
              <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
                {d.term}{' '}
                <span style={{ color: 'var(--muted-foreground)', fontWeight: 400 }}>
                  (p.{d.sourcePage})
                </span>
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                {d.definition}
              </p>
            </div>
          ))}
        </div>
      </div>
      {a.formulas.length > 0 && (
        <div className="glass-card p-5 md:col-span-2">
          <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            🧮 Formulas
          </p>
          <div className="flex flex-wrap gap-2">
            {a.formulas.map((f, i) => (
              <span
                key={i}
                className="text-xs px-2.5 py-1 rounded-lg font-mono"
                style={{ background: 'var(--tint-2)', color: 'var(--foreground)' }}
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function FileNotesPanel({
  file,
  onAddNote,
  onAddBookmark,
  onRemoveBookmark,
}: {
  file: VaultFile
  onAddNote: (text: string) => void
  onAddBookmark: (label: string) => void
  onRemoveBookmark: (id: string) => void
}) {
  const [noteText, setNoteText] = useState('')
  const [bookmarkLabel, setBookmarkLabel] = useState('')

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="glass-card p-5">
        <p className="text-xs font-bold mb-3" style={{ color: 'var(--foreground)' }}>
          📝 Your Notes (Page {file.currentPage})
        </p>
        <div className="flex gap-2 mb-3">
          <input
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Write a note for this page..."
            className="input-field flex-1 px-3 py-2 rounded-lg text-xs"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && noteText.trim()) {
                onAddNote(noteText.trim())
                setNoteText('')
              }
            }}
          />
          <button
            onClick={() => {
              if (noteText.trim()) {
                onAddNote(noteText.trim())
                setNoteText('')
              }
            }}
            className="text-xs font-semibold px-3 py-2 rounded-lg"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            Add
          </button>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
          {file.notes.length === 0 ? (
            <EmptyMessage text="No notes yet." />
          ) : (
            [...file.notes].reverse().map((n) => (
              <div key={n.id} className="p-2.5 rounded-lg" style={{ background: 'var(--tint-1)' }}>
                <p className="text-xs" style={{ color: 'var(--foreground)' }}>
                  {n.text}
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  Page {n.page} · {formatRelativeTime(n.createdAt)}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="glass-card p-5">
        <p className="text-xs font-bold mb-3" style={{ color: 'var(--foreground)' }}>
          🔖 Bookmarks
        </p>
        <div className="flex gap-2 mb-3">
          <input
            value={bookmarkLabel}
            onChange={(e) => setBookmarkLabel(e.target.value)}
            placeholder={`Bookmark page ${file.currentPage}...`}
            className="input-field flex-1 px-3 py-2 rounded-lg text-xs"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onAddBookmark(bookmarkLabel.trim())
                setBookmarkLabel('')
              }
            }}
          />
          <button
            onClick={() => {
              onAddBookmark(bookmarkLabel.trim())
              setBookmarkLabel('')
            }}
            className="text-xs font-semibold px-3 py-2 rounded-lg"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            Save
          </button>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
          {file.bookmarks.length === 0 ? (
            <EmptyMessage text="No bookmarks yet." />
          ) : (
            [...file.bookmarks].reverse().map((b) => (
              <div
                key={b.id}
                className="flex items-center justify-between p-2.5 rounded-lg"
                style={{ background: 'var(--tint-1)' }}
              >
                <div>
                  <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>
                    {b.label}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    Page {b.page}
                  </p>
                </div>
                <button
                  onClick={() => onRemoveBookmark(b.id)}
                  className="text-xs"
                  style={{ color: 'var(--danger)' }}
                >
                  ✕
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function FileFlashcardsPanel({ file }: { file: VaultFile }) {
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const cards = file.analysis?.flashcards ?? []
  if (cards.length === 0) return <EmptyMessage text="No flashcards generated yet." />
  const card = cards[index]

  return (
    <div className="glass-card p-6">
      <p className="text-xs mb-3 text-center" style={{ color: 'var(--muted-foreground)' }}>
        Card {index + 1} of {cards.length} · from page {card.sourcePage}
      </p>
      <motion.button
        onClick={() => setFlipped((f) => !f)}
        className="w-full aspect-[3/2] max-w-md mx-auto flex rounded-2xl items-center justify-center p-6 text-center cursor-pointer"
        style={{ background: 'var(--tint-2)', border: '1px solid var(--border-subtle)' }}
        whileTap={{ scale: 0.98 }}
      >
        <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
          {flipped ? card.answer : card.question}
        </p>
      </motion.button>
      <p className="text-xs text-center mt-2" style={{ color: 'var(--muted-foreground)' }}>
        Tap card to {flipped ? 'see question' : 'reveal answer'}
      </p>
      <div className="flex items-center justify-center gap-3 mt-4">
        <button
          onClick={() => {
            setFlipped(false)
            setIndex((i) => Math.max(0, i - 1))
          }}
          className="text-xs font-semibold px-4 py-2 rounded-lg"
          style={{ background: 'var(--tint-2)', color: 'var(--foreground)' }}
        >
          ← Prev
        </button>
        <button
          onClick={() => {
            setFlipped(false)
            setIndex((i) => Math.min(cards.length - 1, i + 1))
          }}
          className="text-xs font-semibold px-4 py-2 rounded-lg"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          Next →
        </button>
      </div>
    </div>
  )
}

function FileMindMapPanel({ file }: { file: VaultFile }) {
  if (!file.analysis) return <EmptyMessage text="AI analysis is still processing." />
  const root = file.analysis.mindMap
  return (
    <div className="glass-card p-6 space-y-3">
      <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
        {root.label}
      </p>
      {root.children.map((node, i) => (
        <div
          key={node.id}
          className="pl-4"
          style={{ borderLeft: '2px solid var(--border-subtle)' }}
        >
          <p
            className="text-sm font-semibold mb-1.5"
            style={{ color: ['#2DD4BF', '#a855f7', '#f59e0b', '#38bdf8'][i % 4] }}
          >
            {node.label}{' '}
            {node.sourcePage && (
              <span style={{ color: 'var(--muted-foreground)', fontWeight: 400 }}>
                (p.{node.sourcePage})
              </span>
            )}
          </p>
          <div className="space-y-1 pl-3">
            {node.children.map((child) => (
              <p key={child.id} className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                • {child.label}
              </p>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function ExamSetup({
  file,
  onExit,
  onGenerate,
  onRecordAttempt,
}: {
  file: VaultFile
  onExit: () => void
  onGenerate: (
    id: string,
    count: number,
    types: VaultQuestionType[]
  ) => Promise<VaultQuizQuestion[]>
  onRecordAttempt: (
    id: string,
    kind: 'practice' | 'exam',
    scorePct: number,
    totalQuestions: number,
    correctCount: number,
    coveragePages: number[]
  ) => void
}) {
  const [started, setStarted] = useState(false)
  const [count, setCount] = useState(8)
  const [types, setTypes] = useState<VaultQuestionType[]>([
    'mcq',
    'true-false',
    'fill-blank',
    'short-answer',
  ])
  const [questions, setQuestions] = useState<VaultQuizQuestion[]>([])
  const [generating, setGenerating] = useState(false)
  const [generationError, setGenerationError] = useState<string | null>(null)

  const allTypes: Array<{ id: VaultQuestionType; label: string }> = [
    { id: 'mcq', label: 'Multiple Choice' },
    { id: 'true-false', label: 'True / False' },
    { id: 'fill-blank', label: 'Fill in the Blank' },
    { id: 'short-answer', label: 'Short Answer' },
  ]

  function toggleType(t: VaultQuestionType) {
    setTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]))
  }

  if (started) {
    return (
      <QuizRunner
        title="AI Exam"
        questions={questions}
        accentColor="var(--accent)"
        onExit={onExit}
        onComplete={({ scorePct, totalQuestions, correctCount }) =>
          onRecordAttempt(
            file.id,
            'exam',
            scorePct,
            totalQuestions,
            correctCount,
            Array.from({ length: file.pageCount }, (_, i) => i + 1)
          )
        }
      />
    )
  }

  return (
    <div>
      <p className="text-sm font-bold mb-1" style={{ color: 'var(--foreground)' }}>
        🎓 Take AI Exam
      </p>
      <p className="text-xs mb-5" style={{ color: 'var(--muted-foreground)' }}>
        Generated entirely from "{file.title}" — no outside material. Choose your question mix.
      </p>

      <div className="space-y-4 max-w-md">
        <div>
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
            Question Types
          </p>
          <div className="flex flex-wrap gap-1.5">
            {allTypes.map((t) => (
              <button
                key={t.id}
                onClick={() => toggleType(t.id)}
                className="text-xs px-3 py-1.5 rounded-lg font-medium"
                style={{
                  background: types.includes(t.id) ? 'var(--accent)' : 'var(--tint-2)',
                  color: types.includes(t.id)
                    ? 'var(--accent-foreground)'
                    : 'var(--muted-foreground)',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
            Number of Questions: {count}
          </p>
          <input
            type="range"
            min={4}
            max={12}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-full"
          />
        </div>

        {generationError && (
          <p className="text-xs" style={{ color: 'var(--danger)' }}>
            {generationError}
          </p>
        )}
        <button
          onClick={async () => {
            setGenerating(true)
            setGenerationError(null)
            try {
              const generated = await onGenerate(file.id, count, types)
              setQuestions(generated)
              setStarted(true)
            } catch (error) {
              setGenerationError(
                error instanceof Error ? error.message : 'Could not generate this exam.'
              )
            } finally {
              setGenerating(false)
            }
          }}
          disabled={types.length === 0 || generating}
          className="text-sm font-semibold px-5 py-2.5 rounded-full"
          style={{
            background: 'var(--accent)',
            color: 'var(--accent-foreground)',
            opacity: types.length === 0 || generating ? 0.5 : 1,
          }}
        >
          {generating ? 'Generating Exam…' : 'Generate & Start Exam'}
        </button>
      </div>
    </div>
  )
}

function FileStatsPanel({ file }: { file: VaultFile }) {
  const pct = readingPercent(file)
  const attempts = [...file.quizAttempts, ...file.examAttempts].sort(
    (a, b) => b.takenAt - a.takenAt
  )

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile label="Pages Read" value={`${new Set(file.pagesRead).size}/${file.pageCount}`} />
        <StatTile label="Reading %" value={`${pct}%`} />
        <StatTile label="Study Time" value={formatStudyTime(file.studyTimeSeconds)} />
        <StatTile label="Last Viewed" value={formatRelativeTime(file.lastViewedAt)} />
      </div>

      <div className="glass-card p-5">
        <p className="text-xs font-bold mb-3" style={{ color: 'var(--foreground)' }}>
          📊 Quiz & Exam History
        </p>
        {attempts.length === 0 ? (
          <EmptyMessage text="No quiz or exam attempts yet." />
        ) : (
          <div className="space-y-2">
            {attempts.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between p-2.5 rounded-lg"
                style={{ background: 'var(--tint-1)' }}
              >
                <div>
                  <p className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
                    {a.kind === 'exam' ? '🎓 AI Exam' : '❓ Practice Quiz'}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    {formatRelativeTime(a.takenAt)} · {a.correctCount}/{a.totalQuestions} correct
                  </p>
                </div>
                <span
                  className="text-sm font-bold"
                  style={{ color: a.scorePct >= 70 ? 'var(--success)' : 'var(--danger)' }}
                >
                  {a.scorePct}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-card p-4">
      <p
        className="text-xl font-black"
        style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--primary)' }}
      >
        {value}
      </p>
      <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
    </div>
  )
}

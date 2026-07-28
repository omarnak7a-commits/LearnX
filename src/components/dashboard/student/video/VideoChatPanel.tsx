import { useState } from 'react'
import { motion } from 'framer-motion'
import type { ChatMessage, VideoLecture } from '../../../../types/video'
import { formatTimestamp } from '../../../../data/videoIntelligenceMock'

interface VideoChatPanelProps {
  lecture: VideoLecture
  onJump: (t: number) => void
}

const suggestions = [
  'Summarize this lecture',
  'What are the important formulas?',
  'Generate a quiz from this lecture',
  'What might appear on the exam?',
]

function generateAnswer(question: string, lecture: VideoLecture): ChatMessage {
  const lower = question.toLowerCase()

  if (lower.includes('summar')) {
    const s = lecture.summaries.find((s) => s.level === 'quick')
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: s ? s.points.join(' ') : 'This lecture hasn\u2019t finished processing yet.',
      citations: lecture.chapters.slice(0, 2).map((c) => ({ chapterId: c.id, chapterTitle: c.title, timestampSec: c.startSec })),
    }
  }

  if (lower.includes('formula')) {
    const formulas = lecture.chapters.flatMap((c) => c.formulas.map((f) => ({ f, c })))
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      text:
        formulas.length > 0
          ? `Key formulas from this lecture: ${formulas.map((x) => x.f).join(', ')}.`
          : 'No formulas were detected in this lecture.',
      citations: formulas.slice(0, 3).map((x) => ({ chapterId: x.c.id, chapterTitle: x.c.title, timestampSec: x.c.startSec })),
    }
  }

  if (lower.includes('quiz') || lower.includes('practice')) {
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: `I've already generated ${lecture.quiz.length} practice questions from this lecture — open the Quiz tab to try them, or ask me for more on a specific chapter.`,
    }
  }

  if (lower.includes('exam')) {
    const highImportance = lecture.chapters.filter((c) => c.examImportance >= 80)
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      text:
        highImportance.length > 0
          ? `Based on emphasis and phrasing, these chapters carry the highest exam weight: ${highImportance.map((c) => c.title).join(', ')}.`
          : 'This lecture doesn\u2019t show strong exam signals yet — check back after more materials are linked.',
      citations: highImportance.map((c) => ({ chapterId: c.id, chapterTitle: c.title, timestampSec: c.startSec })),
    }
  }

  const chapterMatch = lecture.chapters.find((c) => lower.includes(c.title.toLowerCase().slice(0, 8)) || lower.includes(`chapter ${c.index}`))
  if (chapterMatch) {
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: `${chapterMatch.title}: ${chapterMatch.keyConcepts.map((k) => `${k.term} — ${k.definition}`).join(' ')}`,
      citations: [{ chapterId: chapterMatch.id, chapterTitle: chapterMatch.title, timestampSec: chapterMatch.startSec }],
    }
  }

  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    text: "I can only answer using this lecture's content. Try asking me to explain a specific chapter, summarize the lecture, or pull out formulas and exam tips.",
  }
}

export default function VideoChatPanel({ lecture, onJump }: VideoChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(lecture.chat)
  const [input, setInput] = useState('')

  function send(text: string) {
    if (!text.trim()) return
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', text }
    const answer = generateAnswer(text, lecture)
    setMessages((prev) => [...prev, userMsg, answer])
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3 mb-3 max-h-[420px] pr-1">
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div
              className="max-w-[88%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
              style={{
                background: msg.role === 'user' ? 'var(--primary)' : 'var(--tint-2)',
                color: msg.role === 'user' ? 'var(--primary-foreground)' : 'var(--foreground)',
                borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
              }}
            >
              <p>{msg.text}</p>
              {msg.citations && msg.citations.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {msg.citations.map((c, i) => (
                    <button
                      key={i}
                      onClick={() => onJump(c.timestampSec)}
                      className="text-xs px-2 py-0.5 rounded-full font-mono"
                      style={{ background: 'rgba(45,212,191,0.16)', color: 'var(--primary)' }}
                    >
                      {c.chapterTitle} · {formatTimestamp(c.timestampSec)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => send(s)}
            className="text-xs px-2.5 py-1 rounded-full transition-all hover:scale-105"
            style={{ background: 'rgba(45,212,191,0.08)', color: 'var(--primary)', border: '1px solid rgba(45,212,191,0.2)' }}
          >
            {s}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
        className="flex items-center gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this lecture..."
          className="input-field flex-1 px-4 py-2.5 rounded-xl text-sm"
        />
        <button
          type="submit"
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: input.trim() ? 'var(--primary)' : 'var(--tint-3)',
            color: input.trim() ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </form>
    </div>
  )
}

import { useState } from 'react'
import { motion } from 'framer-motion'

const suggestions = [
  "Explain Newton's Second Law simply",
  'Quiz me on Cell Division',
  'Summarize Chapter 7 Calculus',
  'Make a study plan for tomorrow',
  'What are my weakest topics?',
]

const initialHistory = [
  {
    role: 'assistant',
    text: "Hi Alex! 👋 I'm your AI Tutor. Ready to help you crush today's goals. What would you like to work on?",
  },
]

/** Full-page AI Tutor workspace (larger surface than the floating FAB panel). */
export default function AITutorPage() {
  const [messages, setMessages] = useState(initialHistory)
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<'Socratic' | 'Direct' | 'Mentor'>('Direct')

  function send(text: string) {
    if (!text.trim()) return
    setMessages((prev) => [
      ...prev,
      { role: 'user', text },
      {
        role: 'assistant',
        text: `Great question about "${text.slice(0, 48)}${
          text.length > 48 ? '…' : ''
        }". Here's a ${mode.toLowerCase()}-mode explanation, broken into clear steps so it sticks. 🎯`,
      },
    ])
    setInput('')
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-5">
      <motion.div
        className="glass-card flex flex-col overflow-hidden"
        style={{ minHeight: 520 }}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div
          className="flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🤖</span>
            <div>
              <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
                AI Tutor
              </p>
              <p className="text-xs" style={{ color: 'var(--primary)' }}>
                ● Online · adapts to your learning style
              </p>
            </div>
          </div>
          <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--muted)' }}>
            {(['Socratic', 'Direct', 'Mentor'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className="px-2.5 py-1 rounded-md text-xs font-medium transition-all"
                style={{
                  background: mode === m ? 'var(--primary)' : 'transparent',
                  color: mode === m ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                }}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-3 scrollbar-thin">
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div
                className="max-w-[75%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
                style={{
                  background: msg.role === 'user' ? 'var(--primary)' : 'var(--tint-2)',
                  color: msg.role === 'user' ? 'var(--primary-foreground)' : 'var(--foreground)',
                  borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                }}
              >
                {msg.text}
              </div>
            </motion.div>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          className="flex items-center gap-2 px-4 py-3.5 border-t"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask your tutor anything..."
            className="input-field flex-1 px-4 py-2.5 rounded-xl text-sm"
          />
          <button
            type="submit"
            className="w-10 h-10 rounded-xl flex items-center justify-center transition-all flex-shrink-0"
            style={{
              background: input.trim() ? 'var(--primary)' : 'var(--tint-3)',
              color: input.trim() ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </form>
      </motion.div>

      <div className="flex flex-col gap-4">
        <motion.div
          className="glass-card p-5"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <p className="text-xs font-bold mb-3" style={{ color: 'var(--foreground)' }}>
            Try asking
          </p>
          <div className="flex flex-col gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="text-left text-xs px-3 py-2.5 rounded-xl transition-colors"
                style={{
                  background: 'var(--tint-1)',
                  color: 'var(--foreground)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(45,212,191,0.1)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--tint-1)')}
              >
                {s}
              </button>
            ))}
          </div>
        </motion.div>

        <motion.div
          className="glass-card p-5"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <p className="text-xs font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            Generate
          </p>
          <div className="grid grid-cols-2 gap-2">
            {['Quiz', 'Flashcards', 'Mind Map', 'Notes'].map((g) => (
              <button
                key={g}
                className="text-xs font-medium px-2.5 py-2 rounded-lg text-center transition-colors"
                style={{
                  background: 'rgba(45,212,191,0.08)',
                  color: 'var(--primary)',
                }}
              >
                {g}
              </button>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

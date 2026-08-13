import { useState } from 'react'
import { motion } from 'framer-motion'
import Badge from '../../ui/Badge'

interface Capability {
  icon: string
  title: string
  desc: string
  color: string
}

const capabilities: Capability[] = [
  {
    icon: '❓',
    title: 'Generate Quizzes',
    desc: 'Auto-build quizzes from lecture materials',
    color: '#2DD4BF',
  },
  {
    icon: '📚',
    title: 'Draft a Syllabus',
    desc: 'Outline modules and learning outcomes',
    color: '#a855f7',
  },
  {
    icon: '📄',
    title: 'Summarize Lectures',
    desc: 'Turn recordings/slides into concise notes',
    color: '#38bdf8',
  },
  {
    icon: '🧩',
    title: 'Analyze Weak Topics',
    desc: 'Surface class-wide knowledge gaps',
    color: '#FF7E36',
  },
  {
    icon: '💡',
    title: 'Teaching Suggestions',
    desc: 'Get AI-recommended pacing & format changes',
    color: '#22c55e',
  },
]

const history = [
  {
    role: 'assistant',
    text: "Hi Dr. Novak 👋 I'm your AI Teaching Assistant. I can generate quizzes, summarize lectures, and outline a syllabus — what would you like to work on?",
  },
]

export default function AITeachingAssistant() {
  const [messages, setMessages] = useState(history)
  const [input, setInput] = useState('')

  function send(text: string) {
    if (!text.trim()) return
    setMessages((prev) => [
      ...prev,
      { role: 'user', text },
      {
        role: 'assistant',
        text: `On it — drafting "${text.slice(0, 44)}${
          text.length > 44 ? '…' : ''
        }" now. I'll pull from your CS201 materials to keep it aligned with the syllabus. 📚`,
      },
    ])
    setInput('')
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-5">
      <motion.div
        className="glass-card flex flex-col overflow-hidden"
        style={{ minHeight: 460 }}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div
          className="flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center gap-2.5">
            <span className="text-xl">✨</span>
            <div>
              <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
                AI Teaching Assistant
              </p>
              <p className="text-xs" style={{ color: 'var(--primary)' }}>
                ● Online · CS201, MATH210, CS310, CS420
              </p>
            </div>
          </div>
          <Badge tone="primary" size="xs" pulse>
            Active
          </Badge>
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
            placeholder="e.g. Generate a 10-question quiz on recursion"
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

      <motion.div
        className="glass-card p-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <p className="text-xs font-bold mb-3" style={{ color: 'var(--foreground)' }}>
          Capabilities
        </p>
        <div className="grid grid-cols-1 gap-2">
          {capabilities.map((c, i) => (
            <motion.button
              key={c.title}
              onClick={() => send(c.title)}
              className="flex items-center gap-3 p-3 rounded-xl text-left transition-colors"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.05 * i }}
              whileHover={{ x: 2, background: `${c.color}12` }}
            >
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                style={{ background: `${c.color}18` }}
              >
                {c.icon}
              </span>
              <div className="min-w-0">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {c.title}
                </p>
                <p className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>
                  {c.desc}
                </p>
              </div>
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

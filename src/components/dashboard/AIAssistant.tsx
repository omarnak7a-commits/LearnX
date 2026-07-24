import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const suggestMessages = [
  'Explain Newton\'s Second Law simply',
  'Quiz me on Cell Division',
  'Summarize Chapter 7 Calculus',
  'Make a study plan for tomorrow',
]

const chatHistory = [
  { role: 'assistant', text: "Hi Alex! 👋 I'm your AI Tutor. Ready to help you crush today's goals. What would you like to work on?" },
]

export default function AIAssistant() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState(chatHistory)
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<'Socratic' | 'Direct' | 'Mentor'>('Direct')

  function send(text: string) {
    if (!text.trim()) return
    setMessages(prev => [
      ...prev,
      { role: 'user', text },
      { role: 'assistant', text: `Great question about "${text.slice(0, 40)}...". Let me break this down for you in ${mode} mode — I'll have a detailed answer ready shortly. 🎯` },
    ])
    setInput('')
  }

  return (
    <>
      {/* FAB */}
      <div className="fixed bottom-6 right-6 z-40">
        {/* Pulse rings */}
        {!open && (
          <>
            <div
              className="absolute inset-0 rounded-full animate-pulse-ring"
              style={{ background: 'rgba(45,212,191,0.25)' }}
            />
            <div
              className="absolute inset-0 rounded-full animate-pulse-ring"
              style={{ background: 'rgba(45,212,191,0.15)', animationDelay: '0.5s' }}
            />
          </>
        )}

        <motion.button
          onClick={() => setOpen(v => !v)}
          className="relative w-14 h-14 rounded-full flex items-center justify-center text-xl animate-glow-pulse"
          style={{ background: 'linear-gradient(135deg, #2DD4BF, #14B8A6)', color: '#0A0D14' }}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          aria-label="Open AI Assistant"
        >
          {open ? '✕' : '🤖'}
        </motion.button>
      </div>

      {/* Chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed bottom-24 right-6 z-40 w-80 sm:w-96 rounded-2xl overflow-hidden flex flex-col"
            style={{
              background: '#111827',
              border: '1px solid rgba(45,212,191,0.2)',
              maxHeight: '60vh',
              boxShadow: '0 24px 80px rgba(0,0,0,0.6), 0 0 40px rgba(45,212,191,0.1)',
            }}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 320, damping: 28 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
              <div className="flex items-center gap-2">
                <span className="text-lg">🤖</span>
                <div>
                  <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>AI Tutor</p>
                  <p className="text-xs" style={{ color: '#2DD4BF' }}>● Online</p>
                </div>
              </div>

              {/* Mode switcher */}
              <div className="flex gap-1">
                {(['Socratic', 'Direct', 'Mentor'] as const).map(m => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className="px-2 py-0.5 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: mode === m ? 'rgba(45,212,191,0.15)' : 'transparent',
                      color: mode === m ? '#2DD4BF' : '#64748B',
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin" style={{ maxHeight: 260 }}>
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className="max-w-[85%] px-3 py-2 rounded-xl text-sm leading-relaxed"
                    style={{
                      background: msg.role === 'user' ? 'rgba(45,212,191,0.15)' : 'rgba(255,255,255,0.06)',
                      color: 'var(--foreground)',
                      borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                    }}
                  >
                    {msg.text}
                  </div>
                </div>
              ))}
            </div>

            {/* Suggestions */}
            <div className="px-4 pt-2 flex flex-wrap gap-1.5 border-t" style={{ borderColor: 'rgba(45,212,191,0.1)' }}>
              {suggestMessages.slice(0, 2).map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-2.5 py-1 rounded-full transition-all hover:scale-105"
                  style={{ background: 'rgba(45,212,191,0.08)', color: '#2DD4BF', border: '1px solid rgba(45,212,191,0.2)' }}
                >
                  {s.length > 24 ? s.slice(0, 22) + '…' : s}
                </button>
              ))}
            </div>

            {/* Input */}
            <form
              onSubmit={e => { e.preventDefault(); send(input) }}
              className="flex items-center gap-2 px-4 py-3"
            >
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Ask your tutor anything..."
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: 'var(--foreground)' }}
              />
              <button
                type="submit"
                className="w-8 h-8 rounded-full flex items-center justify-center transition-all hover:scale-110"
                style={{ background: input.trim() ? '#2DD4BF' : 'rgba(255,255,255,0.08)', color: input.trim() ? '#0A0D14' : '#64748B' }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

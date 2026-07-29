import { useMemo, useRef, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import type { TranscriptSegment } from '../../../../types/video'
import { formatTimestamp } from '../../../../data/videoIntelligenceMock'

interface TranscriptPanelProps {
  segments: TranscriptSegment[]
  currentTime: number
  onJump: (t: number) => void
}

const LANGUAGES = ['English', 'Arabic', 'Spanish', 'French']

export default function TranscriptPanel({ segments, currentTime, onJump }: TranscriptPanelProps) {
  const [query, setQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const [language, setLanguage] = useState('English')
  const [langMenuOpen, setLangMenuOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const activeRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const activeId = useMemo(() => {
    const active = [...segments].reverse().find((s) => currentTime >= s.startSec)
    return active?.id
  }, [segments, currentTime])

  useEffect(() => {
    if (autoScroll && activeRef.current && containerRef.current) {
      activeRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [activeId, autoScroll])

  const filtered = query.trim()
    ? segments.filter((s) => s.text.toLowerCase().includes(query.toLowerCase()))
    : segments

  function copyAll() {
    const text = segments.map((s) => `[${formatTimestamp(s.startSec)}] ${s.speaker}: ${s.text}`).join('\n\n')
    navigator.clipboard?.writeText(text).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  function highlight(text: string) {
    if (!query.trim()) return text
    const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} style={{ background: 'rgba(255,126,54,0.35)', color: 'inherit', borderRadius: 3 }}>
          {part}
        </mark>
      ) : (
        <span key={i}>{part}</span>
      )
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <div className="input-field flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs flex-1 min-w-[140px]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search transcript..."
            className="flex-1 bg-transparent outline-none"
            style={{ color: 'var(--foreground)' }}
          />
        </div>

        <button
          onClick={() => setAutoScroll((v) => !v)}
          className="text-xs px-2.5 py-1.5 rounded-lg font-medium transition-colors flex-shrink-0"
          style={{
            background: autoScroll ? 'rgba(45,212,191,0.12)' : 'var(--tint-2)',
            color: autoScroll ? 'var(--primary)' : 'var(--muted-foreground)',
          }}
        >
          Auto-scroll
        </button>

        <div className="relative flex-shrink-0">
          <button
            onClick={() => setLangMenuOpen((v) => !v)}
            className="text-xs px-2.5 py-1.5 rounded-lg input-field flex items-center gap-1"
          >
            🌐 {language}
          </button>
          {langMenuOpen && (
            <motion.div
              className="surface-popover absolute right-0 top-full mt-1 rounded-lg overflow-hidden py-1 w-32 z-20"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {LANGUAGES.map((l) => (
                <button
                  key={l}
                  onClick={() => {
                    setLanguage(l)
                    setLangMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs"
                  style={{ color: l === language ? 'var(--primary)' : 'var(--foreground)' }}
                >
                  {l}
                </button>
              ))}
            </motion.div>
          )}
        </div>

        <button
          onClick={copyAll}
          className="text-xs px-2.5 py-1.5 rounded-lg input-field flex-shrink-0"
          style={{ color: copied ? 'var(--success)' : 'var(--muted-foreground)' }}
        >
          {copied ? '✓ Copied' : 'Copy all'}
        </button>
      </div>

      {language !== 'English' && (
        <div
          className="text-xs px-3 py-2 rounded-lg mb-3"
          style={{ background: 'rgba(45,212,191,0.08)', color: 'var(--primary)' }}
        >
          Showing simulated {language} translation preview — full transcript translation runs via the AI pipeline.
        </div>
      )}

      {/* Segments */}
      <div ref={containerRef} className="flex-1 overflow-y-auto scrollbar-thin pr-1 space-y-3 max-h-[520px]">
        {filtered.map((seg) => {
          const isActive = seg.id === activeId
          return (
            <div
              key={seg.id}
              ref={isActive ? activeRef : undefined}
              onClick={() => onJump(seg.startSec)}
              className="flex gap-3 p-2.5 rounded-xl cursor-pointer transition-colors"
              style={{ background: isActive ? 'rgba(45,212,191,0.08)' : 'transparent' }}
            >
              <button
                className="text-xs font-mono flex-shrink-0 h-fit px-1.5 py-0.5 rounded"
                style={{
                  background: isActive ? 'var(--primary)' : 'var(--tint-3)',
                  color: isActive ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                }}
              >
                {formatTimestamp(seg.startSec)}
              </button>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold mb-0.5" style={{ color: 'var(--primary)' }}>
                  {seg.speaker}
                </p>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
                  {highlight(seg.text)}
                </p>
              </div>
            </div>
          )
        })}
        {filtered.length === 0 && (
          <p className="text-xs text-center py-8" style={{ color: 'var(--muted-foreground)' }}>
            No matches for “{query}”.
          </p>
        )}
      </div>
    </div>
  )
}

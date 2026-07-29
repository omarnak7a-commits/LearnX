import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export interface SearchableOption {
  id: string
  label: string
  sublabel?: string
  icon?: string
}

interface SearchableSelectProps {
  label: string
  placeholder?: string
  options: SearchableOption[]
  value: string | null
  onChange: (id: string) => void
  disabled?: boolean
  required?: boolean
  emptyMessage?: string
}

/**
 * Searchable dropdown used across Onboarding, Profile editing, and
 * Ranking filters — matches the spec's explicit "Support searchable
 * dropdowns" requirement (University ▼ Cairo University, Faculty ▼
 * Faculty of Engineering, etc.) with the existing `.input-field` /
 * `.surface-popover` visual language instead of inventing a new control.
 */
export default function SearchableSelect({
  label,
  placeholder = 'Search…',
  options,
  value,
  onChange,
  disabled = false,
  required = false,
  emptyMessage = 'No matches',
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  const selected = options.find((o) => o.id === value) ?? null

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const filtered =
    query.trim().length === 0
      ? options
      : options.filter((o) => o.label.toLowerCase().includes(query.trim().toLowerCase()))

  return (
    <div ref={containerRef} className="relative">
      <label
        className="text-xs font-medium mb-1.5 flex items-center gap-1"
        style={{ color: 'var(--muted-foreground)' }}
      >
        {label}
        {required && <span style={{ color: 'var(--danger)' }}>*</span>}
      </label>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="input-field w-full px-4 py-2.5 rounded-xl text-sm flex items-center justify-between gap-2 text-left"
        style={{ opacity: disabled ? 0.6 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
      >
        <span
          className="truncate"
          style={{ color: selected ? 'var(--foreground)' : 'var(--muted-foreground)' }}
        >
          {selected ? (
            <>
              {selected.icon && <span className="mr-1.5">{selected.icon}</span>}
              {selected.label}
            </>
          ) : (
            placeholder
          )}
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{
            color: 'var(--muted-foreground)',
            flexShrink: 0,
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s ease',
          }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      <AnimatePresence>
        {open && !disabled && (
          <motion.div
            className="surface-popover absolute left-0 right-0 mt-2 rounded-xl overflow-hidden"
            style={{ top: '100%', zIndex: 40 }}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          >
            <div className="p-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type to search…"
                className="w-full px-3 py-2 rounded-lg text-sm bg-transparent outline-none"
                style={{ color: 'var(--foreground)', background: 'var(--muted)' }}
              />
            </div>
            <div className="max-h-56 overflow-y-auto scrollbar-thin">
              {filtered.length === 0 ? (
                <p className="px-4 py-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {emptyMessage}
                </p>
              ) : (
                filtered.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => {
                      onChange(option.id)
                      setOpen(false)
                      setQuery('')
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left transition-colors"
                    style={{
                      background: option.id === value ? 'rgba(45,212,191,0.1)' : 'transparent',
                      color: option.id === value ? 'var(--primary)' : 'var(--foreground)',
                    }}
                    onMouseEnter={(e) => {
                      if (option.id !== value)
                        e.currentTarget.style.background = 'var(--surface-hover)'
                    }}
                    onMouseLeave={(e) => {
                      if (option.id !== value) e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    {option.icon && <span>{option.icon}</span>}
                    <span className="flex-1 min-w-0 truncate">{option.label}</span>
                    {option.sublabel && (
                      <span
                        className="text-xs flex-shrink-0"
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        {option.sublabel}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

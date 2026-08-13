import type { AiLanguage } from '../../../lib/ai/language'

interface AiLanguageToggleProps {
  value: AiLanguage
  onChange: (language: AiLanguage) => void
}

const OPTIONS: Array<{ id: AiLanguage; label: string; title: string }> = [
  { id: 'ar', label: 'ع', title: 'العربية' },
  { id: 'en', label: 'EN', title: 'English' },
]

export default function AiLanguageToggle({ value, onChange }: AiLanguageToggleProps) {
  return (
    <div
      className="flex gap-0.5 p-0.5 rounded-lg"
      style={{ background: 'var(--muted)' }}
      role="group"
      aria-label="AI language"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.id}
          type="button"
          title={option.title}
          onClick={() => onChange(option.id)}
          className="min-w-7 px-2 py-0.5 rounded-md text-[10px] font-bold transition-colors"
          style={{
            background: value === option.id ? 'var(--primary)' : 'transparent',
            color: value === option.id ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

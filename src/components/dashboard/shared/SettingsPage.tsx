import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Role } from '../Sidebar'

interface SettingsPageProps {
  role: Role
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

function ToggleRow({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string
  desc?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between py-3.5">
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
          {label}
        </p>
        {desc && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            {desc}
          </p>
        )}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className="relative w-11 h-6 rounded-full flex-shrink-0 transition-colors"
        style={{ background: checked ? 'var(--primary)' : 'var(--tint-5)' }}
      >
        <motion.span
          className="absolute top-0.5 w-5 h-5 rounded-full"
          style={{ background: '#fff' }}
          animate={{ left: checked ? 22 : 2 }}
          transition={{ type: 'spring', stiffness: 500, damping: 32 }}
        />
      </button>
    </div>
  )
}

export default function SettingsPage({ role, theme, onToggleTheme }: SettingsPageProps) {
  const [notifs, setNotifs] = useState(true)
  const [emailDigest, setEmailDigest] = useState(true)
  const [soundFx, setSoundFx] = useState(false)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5">
      <motion.div
        className="glass-card p-6 flex flex-col items-center text-center"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold mb-4"
          style={{
            background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
            color: 'var(--primary-foreground)',
          }}
        >
          {role === 'doctor' ? 'DR' : 'AC'}
        </div>
        <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          {role === 'doctor' ? 'Dr. Sarah Novak' : 'Alex Chen'}
        </p>
        <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
          {role === 'doctor' ? 'Professor · Computer Science' : 'Comp Sci · Year 2'}
        </p>
        <button
          className="mt-4 text-xs font-semibold px-4 py-2 rounded-full"
          style={{
            background: 'rgba(45,212,191,0.1)',
            color: 'var(--primary)',
          }}
        >
          Change photo
        </button>
      </motion.div>

      <div className="space-y-5">
        <motion.div
          className="glass-card p-6"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--foreground)' }}>
            Appearance
          </h3>
          <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>
            Choose how LearnX looks on this device.
          </p>
          <div className="flex items-center justify-between py-3.5">
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                Theme
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                Currently using {theme} mode
              </p>
            </div>
            <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--muted)' }}>
              {(['dark', 'light'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    if (t !== theme) onToggleTheme()
                  }}
                  className="px-3 py-1.5 rounded-md text-xs font-semibold capitalize transition-colors"
                  style={{
                    background: theme === t ? 'var(--primary)' : 'transparent',
                    color: theme === t ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </motion.div>

        <motion.div
          className="glass-card p-6 divide-y"
          style={{ borderColor: 'var(--border-subtle)' }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <h3 className="text-sm font-bold pb-3" style={{ color: 'var(--foreground)' }}>
            Notifications
          </h3>
          <ToggleRow
            label="Push notifications"
            desc="Get notified about deadlines and messages"
            checked={notifs}
            onChange={setNotifs}
          />
          <ToggleRow
            label="Weekly email digest"
            desc="Summary of your progress every Monday"
            checked={emailDigest}
            onChange={setEmailDigest}
          />
          <ToggleRow
            label="Sound effects"
            desc="Play a sound on XP gain and achievements"
            checked={soundFx}
            onChange={setSoundFx}
          />
        </motion.div>

        <motion.div
          className="glass-card p-6"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--danger)' }}>
            Danger zone
          </h3>
          <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
            These actions are irreversible.
          </p>
          <button
            className="text-xs font-semibold px-4 py-2 rounded-lg"
            style={{ background: 'var(--danger-soft)', color: 'var(--danger)' }}
          >
            Delete account
          </button>
        </motion.div>
      </div>
    </div>
  )
}

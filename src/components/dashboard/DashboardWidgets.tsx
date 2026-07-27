import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import ProgressRing from '../ui/ProgressRing'

/* ─── Greeting + Goal Ring ─── */

export function GreetingWidget() {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const emoji = hour < 12 ? '☀️' : hour < 17 ? '🌤️' : '🌙'

  return (
    <motion.div
      className="glass-card p-6 h-full flex flex-col"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
    >
      <div className="mb-5">
        <p className="text-xs mb-0.5" style={{ color: 'var(--muted-foreground)' }}>
          {greeting} {emoji}
        </p>
        <h2
          className="text-xl font-bold leading-none"
          style={{
            color: 'var(--foreground)',
            fontFamily: 'Orbitron, sans-serif',
            letterSpacing: '-0.01em',
          }}
        >
          Alex Chen
        </h2>
        <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
          Imperial College · Comp Sci Y2
        </p>
      </div>

      <div className="flex items-center gap-4 mb-5">
        <ProgressRing pct={68} color="var(--primary)" size={88} label="daily goal" />
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
            3 of 5 tasks
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            2h 18m remaining
          </p>
          <p className="text-xs mt-2" style={{ color: 'var(--primary)' }}>
            Exam in 12 days
          </p>
        </div>
      </div>

      {/* AI insight */}
      <div
        className="mt-auto p-3 rounded-xl"
        style={{
          background: 'rgba(45,212,191,0.06)',
          border: '1px solid rgba(45,212,191,0.14)',
        }}
      >
        <p className="text-xs leading-relaxed" style={{ color: 'rgba(45,212,191,0.85)' }}>
          💡 Newton's Laws retention is at 61% — consider one more review session before Friday.
        </p>
      </div>
    </motion.div>
  )
}

/* ─── Focus Score Chart ─── */

const chartData = [
  { day: 'Mon', score: 71, prev: 62 },
  { day: 'Tue', score: 83, prev: 70 },
  { day: 'Wed', score: 68, prev: 65 },
  { day: 'Thu', score: 90, prev: 78 },
  { day: 'Fri', score: 87, prev: 80 },
  { day: 'Sat', score: 94, prev: 82 },
  { day: 'Sun', score: 89, prev: 77 },
]

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value: number }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="px-3 py-2.5 rounded-xl text-xs"
      style={{
        background: 'var(--surface-3)',
        border: '1px solid rgba(45,212,191,0.2)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      }}
    >
      <p style={{ color: 'var(--muted-foreground)', marginBottom: 4 }}>{label}</p>
      <p
        className="font-bold"
        style={{ color: 'var(--primary)', fontFamily: 'Orbitron, sans-serif' }}
      >
        {payload[0]?.value} / 100
      </p>
      {payload[1] && (
        <p style={{ color: 'var(--tint-7)', marginTop: 2, fontSize: 9 }}>
          vs {payload[1].value} last week
        </p>
      )}
    </div>
  )
}

export function FocusChart() {
  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15 }}
    >
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Focus Score
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            Peak performance: <span style={{ color: 'var(--foreground)' }}>Saturday 10am–12pm</span>
          </p>
        </div>
        <div className="text-right">
          <p
            className="text-4xl font-black leading-none text-gradient"
            style={{ fontFamily: 'Orbitron, sans-serif' }}
          >
            94
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--primary)' }}>
            ↑ +12 vs last week
          </p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={130}>
        <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -30 }}>
          <defs>
            <linearGradient id="focusGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.28} />
              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="prevGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.06} />
              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke="var(--tint-2)" vertical={false} />
          <XAxis
            dataKey="day"
            tick={{
              fill: 'var(--muted-foreground)',
              fontSize: 10,
              fontFamily: 'Inter',
            }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: 'var(--muted-foreground)', fontSize: 9 }}
            axisLine={false}
            tickLine={false}
            domain={[50, 100]}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="prev"
            stroke="rgba(45,212,191,0.18)"
            strokeWidth={1.5}
            fill="url(#prevGrad)"
            dot={false}
            strokeDasharray="3 3"
          />
          <Area
            type="monotone"
            dataKey="score"
            stroke="var(--primary)"
            strokeWidth={2.5}
            fill="url(#focusGrad)"
            dot={false}
            activeDot={{
              r: 5,
              fill: 'var(--primary)',
              stroke: '#060810',
              strokeWidth: 2,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

/* ─── Study Plan Cards ─── */

const initialTasks = [
  {
    id: 1,
    task: 'Derive the Euler-Lagrange equation from first principles',
    subject: 'Mathematics',
    color: '#2DD4BF',
    xp: 120,
    done: true,
    time: '45 min',
    chapter: 'Chapter 9: Variational Calculus',
  },
  {
    id: 2,
    task: 'Memorise the 8 Krebs cycle intermediates',
    subject: 'Biology',
    color: '#22c55e',
    xp: 80,
    done: true,
    time: '20 min',
    chapter: 'Chapter 11: Cellular Respiration',
  },
  {
    id: 3,
    task: "Newton's Laws practice — inclined planes with friction",
    subject: 'Physics',
    color: '#a855f7',
    xp: 200,
    done: false,
    time: '60 min',
    chapter: 'Chapter 7: Classical Mechanics',
  },
  {
    id: 4,
    task: 'SN1 vs SN2 reaction mechanisms — key differences',
    subject: 'Chemistry',
    color: '#f59e0b',
    xp: 150,
    done: false,
    time: '35 min',
    chapter: 'Chapter 14: Organic Chemistry',
  },
  {
    id: 5,
    task: 'Read: Aggregate demand and supply model',
    subject: 'Economics',
    color: '#FF7E36',
    xp: 60,
    done: false,
    time: '25 min',
    chapter: 'Chapter 3: Macroeconomics',
  },
]

export function StudyPlanCards() {
  const [tasks, setTasks] = useState(initialTasks)
  const [expanded, setExpanded] = useState<number | null>(null)

  const done = tasks.filter((t) => t.done).length
  const progress = (done / tasks.length) * 100

  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Today's Study Plan
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            AI-generated · Mon 21 Jul · 5 tasks
          </p>
        </div>
        <span
          className="text-xs px-2.5 py-1 rounded-full font-mono"
          style={{
            background: 'rgba(45,212,191,0.1)',
            color: 'var(--primary)',
            fontFamily: 'JetBrains Mono, monospace',
          }}
        >
          {done}/{tasks.length}
        </span>
      </div>

      {/* Progress */}
      <div
        className="h-1 rounded-full mb-5 overflow-hidden"
        style={{ background: 'var(--tint-2)' }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{
            background: 'linear-gradient(90deg, #2DD4BF, var(--secondary))',
          }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>

      <div className="space-y-2">
        {tasks.map((task, i) => {
          const isExpanded = expanded === task.id
          return (
            <motion.div
              key={task.id}
              className="rounded-xl overflow-hidden"
              style={{
                background: task.done ? 'rgba(45,212,191,0.04)' : 'var(--tint-1)',
                border: `1px solid ${task.done ? 'rgba(45,212,191,0.12)' : 'var(--tint-2)'}`,
              }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 + i * 0.07, duration: 0.4 }}
            >
              <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                onClick={() => setExpanded(isExpanded ? null : task.id)}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setTasks((prev) =>
                      prev.map((t) => (t.id === task.id ? { ...t, done: !t.done } : t))
                    )
                  }}
                  className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center transition-all"
                  style={{
                    background: task.done ? 'rgba(45,212,191,0.15)' : 'transparent',
                    border: `1.5px solid ${task.done ? 'var(--primary)' : 'var(--tint-6)'}`,
                  }}
                >
                  {task.done && (
                    <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
                      <path
                        d="M2 5l2.5 2.5 4-4"
                        stroke="var(--primary)"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  )}
                </button>

                <span
                  className="text-xs px-2 py-0.5 rounded font-semibold flex-shrink-0"
                  style={{
                    background: `${task.color}15`,
                    color: task.color,
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 9,
                  }}
                >
                  {task.subject.slice(0, 4).toUpperCase()}
                </span>

                <span
                  className="text-sm flex-1 min-w-0 truncate"
                  style={{
                    color: task.done ? 'var(--muted-foreground)' : 'var(--foreground)',
                    textDecoration: task.done ? 'line-through' : 'none',
                  }}
                >
                  {task.task}
                </span>

                <span
                  className="text-xs flex-shrink-0"
                  style={{
                    color: task.done ? 'rgba(255,126,54,0.4)' : 'var(--accent)',
                    fontFamily: 'JetBrains Mono, monospace',
                  }}
                >
                  +{task.xp}
                </span>
              </div>

              {isExpanded && (
                <motion.div
                  className="px-4 pb-3 flex items-center gap-4"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className="flex-1">
                    <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                      📚 {task.chapter}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      ⏱ {task.time} estimated
                    </p>
                  </div>
                  {!task.done && (
                    <button
                      className="text-xs px-3 py-1.5 rounded-lg font-medium transition-all"
                      style={{
                        background: `${task.color}15`,
                        color: task.color,
                      }}
                    >
                      Start →
                    </button>
                  )}
                </motion.div>
              )}
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

/* ─── Streaks & XP ─── */

const heatmapWeeks = [
  [true, true, true, false, true, true, true],
  [true, true, false, true, true, true, true],
  [true, true, true, true, true, true, false],
  [false, true, true, true, true, true, true],
]

export function StreaksXP() {
  return (
    <motion.div
      className="glass-card p-6 h-full flex flex-col gap-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.25 }}
    >
      {/* Streak */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Streak
          </h3>
          <span className="text-xl">🔥</span>
        </div>
        <p
          className="text-5xl font-black leading-none mb-1"
          style={{ color: 'var(--accent)', fontFamily: 'Orbitron, sans-serif' }}
        >
          21
        </p>
        <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
          consecutive days · personal best
        </p>

        {/* Heat map */}
        <div className="flex flex-col gap-1">
          {heatmapWeeks.map((week, wi) => (
            <div key={wi} className="flex gap-1">
              {week.map((day, di) => (
                <div
                  key={di}
                  className="flex-1 aspect-square rounded-sm"
                  style={{
                    background: day ? 'rgba(255,126,54,0.55)' : 'var(--tint-2)',
                    border: `1px solid ${day ? 'rgba(255,126,54,0.3)' : 'var(--tint-2)'}`,
                  }}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* XP bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div>
            <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
              Level 12
            </p>
            <p
              className="text-xs mt-0.5"
              style={{
                color: 'var(--muted-foreground)',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              4,820 / 7,000 XP
            </p>
          </div>
          <span
            className="text-xs px-2.5 py-1 rounded-full font-bold"
            style={{
              background: 'rgba(255,126,54,0.12)',
              color: 'var(--accent)',
              fontFamily: 'Orbitron, sans-serif',
            }}
          >
            ⚡ LVL 12
          </span>
        </div>

        <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
          <motion.div
            className="h-full rounded-full relative overflow-hidden"
            style={{
              background: 'linear-gradient(90deg, var(--accent), #ffad7a)',
            }}
            initial={{ width: 0 }}
            animate={{ width: '68%' }}
            transition={{ duration: 1.5, ease: [0.16, 1, 0.3, 1], delay: 0.6 }}
          >
            <div
              className="absolute inset-0"
              style={{
                background:
                  'linear-gradient(90deg, transparent 0%, var(--tint-7) 50%, transparent 100%)',
                backgroundSize: '200% 100%',
                animation: 'shimmer-line 2.5s linear infinite',
              }}
            />
          </motion.div>
        </div>

        <div className="flex justify-between mt-1.5">
          <span
            className="text-xs"
            style={{
              color: 'var(--accent)',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            +1,240 XP today
          </span>
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            2,180 to LVL 13
          </span>
        </div>
      </div>

      {/* Next badge */}
      <div
        className="p-3 rounded-xl"
        style={{
          background: 'rgba(255,126,54,0.06)',
          border: '1px solid rgba(255,126,54,0.14)',
        }}
      >
        <p className="text-xs font-semibold mb-0.5" style={{ color: 'var(--accent)' }}>
          🏅 Next: "Polymath" badge
        </p>
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          Study 1 more subject this week
        </p>
      </div>
    </motion.div>
  )
}

/* ─── Activity Feed ─── */

const activities = [
  {
    time: 'Just now',
    icon: '🤖',
    text: 'AI analysed your Physics notes — 3 weak concepts flagged',
    type: 'ai',
  },
  {
    time: '2h ago',
    icon: '✅',
    text: "Completed 'Cell Division' quiz — 84/100 (new personal best)",
    type: 'quiz',
  },
  {
    time: '5h ago',
    icon: '📄',
    text: 'Uploaded Thermodynamics Ch. 12 — 32 flashcards generated',
    type: 'upload',
  },
  {
    time: 'Yesterday',
    icon: '🐦',
    text: "Earned 'Early Bird' badge — 3 sessions before 8am",
    type: 'badge',
  },
  {
    time: 'Yesterday',
    icon: '🔥',
    text: '3h 22m deep work session — Calculus chapter review',
    type: 'focus',
  },
]

const typeColors: Record<string, string> = {
  ai: 'var(--primary)',
  quiz: '#22c55e',
  upload: '#a855f7',
  badge: 'var(--accent)',
  focus: '#f59e0b',
}

export function ActivityFeed() {
  return (
    <motion.div
      className="glass-card p-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
    >
      <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
        Recent Activity
      </h3>
      <div className="flex gap-4 overflow-x-auto pb-1 scrollbar-thin">
        {activities.map((act, i) => (
          <motion.div
            key={i}
            className="flex-shrink-0 rounded-xl p-4"
            style={{
              background: 'var(--tint-1)',
              border: '1px solid var(--tint-3)',
              minWidth: 220,
              borderLeft: `2px solid ${typeColors[act.type]}`,
            }}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 + i * 0.08, duration: 0.4 }}
          >
            <div className="flex items-start gap-2.5">
              <span className="text-base flex-shrink-0">{act.icon}</span>
              <div>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--foreground)' }}>
                  {act.text}
                </p>
                <p
                  className="text-xs mt-1.5"
                  style={{
                    color: 'var(--muted-foreground)',
                    fontFamily: 'JetBrains Mono, monospace',
                  }}
                >
                  {act.time}
                </p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

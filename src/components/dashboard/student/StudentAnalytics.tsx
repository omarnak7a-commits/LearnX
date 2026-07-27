import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip, CartesianGrid } from 'recharts'
import StatCard from '../shared/StatCard'

const weekly = [
  { day: 'Mon', hours: 2.4 },
  { day: 'Tue', hours: 3.1 },
  { day: 'Wed', hours: 1.8 },
  { day: 'Thu', hours: 4.0 },
  { day: 'Fri', hours: 3.4 },
  { day: 'Sat', hours: 4.6 },
  { day: 'Sun', hours: 3.9 },
]

function ChartTooltip({
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
    <div className="surface-popover px-3 py-2 rounded-lg text-xs">
      <p style={{ color: 'var(--muted-foreground)' }}>{label}</p>
      <p className="font-bold" style={{ color: 'var(--primary)' }}>
        {payload[0]?.value}h studied
      </p>
    </div>
  )
}

/** Analytics: study hours, focus score, quiz accuracy, streak, XP, weekly/monthly trend. */
export default function StudentAnalytics() {
  return (
    <motion.div
      className="glass-card p-6 h-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          Analytics
        </h3>
        <span
          className="text-xs px-2.5 py-1 rounded-full"
          style={{
            background: 'rgba(45,212,191,0.1)',
            color: 'var(--primary)',
          }}
        >
          This week
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard
          icon="⏱️"
          label="Study hours"
          value={23.2}
          decimals={1}
          suffix="h"
          delta="+3.2h"
          color="#2DD4BF"
          delay={0}
        />
        <StatCard
          icon="🎯"
          label="Focus score"
          value={94}
          suffix=""
          delta="+12"
          color="#38bdf8"
          delay={0.05}
        />
        <StatCard
          icon="✅"
          label="Quiz accuracy"
          value={87}
          suffix="%"
          delta="+4%"
          color="#22c55e"
          delay={0.1}
        />
        <StatCard
          icon="🔥"
          label="Learning streak"
          value={21}
          suffix=" days"
          delta="best"
          color="#FF7E36"
          delay={0.15}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <p className="text-xs font-semibold mb-3" style={{ color: 'var(--muted-foreground)' }}>
            Weekly study hours
          </p>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={weekly} margin={{ left: -30 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="var(--chart-grid)" vertical={false} />
              <XAxis
                dataKey="day"
                tick={{ fill: 'var(--chart-tick)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--tint-2)' }} />
              <Bar dataKey="hours" radius={[6, 6, 0, 0]} fill="var(--primary)" maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col gap-3 justify-center">
          <div
            className="p-3.5 rounded-xl"
            style={{
              background: 'rgba(255,126,54,0.08)',
              border: '1px solid rgba(255,126,54,0.16)',
            }}
          >
            <p className="text-xs font-semibold" style={{ color: 'var(--accent)' }}>
              Monthly progress
            </p>
            <div className="flex items-baseline gap-1 mt-1">
              <p
                className="text-2xl font-black"
                style={{
                  fontFamily: 'Orbitron, sans-serif',
                  color: 'var(--accent)',
                }}
              >
                +18%
              </p>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                vs last month
              </span>
            </div>
          </div>
          <div
            className="p-3.5 rounded-xl"
            style={{
              background: 'rgba(45,212,191,0.06)',
              border: '1px solid rgba(45,212,191,0.14)',
            }}
          >
            <p className="text-xs font-semibold" style={{ color: 'var(--primary)' }}>
              XP earned this week
            </p>
            <div className="flex items-baseline gap-1 mt-1">
              <p
                className="text-2xl font-black"
                style={{
                  fontFamily: 'Orbitron, sans-serif',
                  color: 'var(--primary)',
                }}
              >
                6,420
              </p>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                XP
              </span>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

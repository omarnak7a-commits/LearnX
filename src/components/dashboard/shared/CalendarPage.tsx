import { motion } from 'framer-motion'
import MiniCalendar from './MiniCalendar'
import Badge from '../../ui/Badge'
import type { Role } from '../Sidebar'

interface CalendarPageProps {
  role: Role
}

const studentEvents = [
  { day: 27, label: 'Physics Lab Report due', color: '#2DD4BF' },
  { day: 27, label: 'AI Tutor session 6pm', color: '#a855f7' },
  { day: 30, label: 'Problem Set 6 due', color: '#f59e0b' },
  { day: 8, label: 'Midterm Exam — Mechanics', color: '#FF7E36' },
]

const doctorEvents = [
  { day: 27, label: 'Office hours 2–4pm', color: '#2DD4BF' },
  { day: 29, label: 'CS201 Pop Quiz', color: '#f59e0b' },
  { day: 30, label: 'Department meeting', color: '#a855f7' },
  { day: 8, label: 'CS201 Midterm proctoring', color: '#FF7E36' },
]

const upcoming = {
  student: [
    {
      title: 'Physics Lab Report',
      time: 'Tomorrow, 11:59pm',
      color: '#2DD4BF',
    },
    { title: 'AI Tutor Session', time: 'Today, 6:00pm', color: '#a855f7' },
    { title: 'Problem Set 6', time: 'Jul 30, 11:59pm', color: '#f59e0b' },
  ],
  doctor: [
    { title: 'Office hours', time: 'Today, 2:00pm', color: '#2DD4BF' },
    { title: 'CS201 Pop Quiz', time: 'Jul 29, 9:00am', color: '#f59e0b' },
    { title: 'Department meeting', time: 'Jul 30, 3:00pm', color: '#a855f7' },
  ],
}

export default function CalendarPage({ role }: CalendarPageProps) {
  const events = role === 'doctor' ? doctorEvents : studentEvents
  const list = role === 'doctor' ? upcoming.doctor : upcoming.student

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <MiniCalendar month="July" year={2026} today={27} events={events} />
      </motion.div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Upcoming
          </h3>
          <Badge tone="primary" size="xs">
            {list.length}
          </Badge>
        </div>
        <div className="space-y-2.5">
          {list.map((e, i) => (
            <motion.div
              key={e.title}
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.08 * i }}
            >
              <span
                className="w-1.5 h-8 rounded-full flex-shrink-0"
                style={{ background: e.color }}
              />
              <div className="min-w-0">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {e.title}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {e.time}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

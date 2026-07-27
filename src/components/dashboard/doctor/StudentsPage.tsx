import { motion } from 'framer-motion'
import DataTable, { type Column } from '../shared/DataTable'
import Badge from '../../ui/Badge'
import ProgressRing from '../../ui/ProgressRing'

interface Student {
  id: number
  name: string
  course: string
  grade: number
  engagement: number
  attendance: number
  status: 'excellent' | 'good' | 'at-risk'
}

const students: Student[] = [
  {
    id: 1,
    name: 'Amelia Torres',
    course: 'CS201',
    grade: 97,
    engagement: 94,
    attendance: 98,
    status: 'excellent',
  },
  {
    id: 2,
    name: 'Ravi Malhotra',
    course: 'CS310',
    grade: 94,
    engagement: 89,
    attendance: 95,
    status: 'excellent',
  },
  {
    id: 3,
    name: 'Lucia Fernandez',
    course: 'MATH210',
    grade: 91,
    engagement: 85,
    attendance: 92,
    status: 'good',
  },
  {
    id: 4,
    name: 'Noah Kim',
    course: 'CS420',
    grade: 89,
    engagement: 80,
    attendance: 88,
    status: 'good',
  },
  {
    id: 5,
    name: 'Jordan Blake',
    course: 'CS201',
    grade: 58,
    engagement: 22,
    attendance: 61,
    status: 'at-risk',
  },
  {
    id: 6,
    name: 'Priya Nair',
    course: 'MATH210',
    grade: 64,
    engagement: 41,
    attendance: 74,
    status: 'at-risk',
  },
  {
    id: 7,
    name: "Sam O'Connor",
    course: 'CS310',
    grade: 68,
    engagement: 48,
    attendance: 70,
    status: 'at-risk',
  },
  {
    id: 8,
    name: 'Emeka Obi',
    course: 'CS420',
    grade: 85,
    engagement: 76,
    attendance: 91,
    status: 'good',
  },
]

const statusTone: Record<Student['status'], 'success' | 'warning' | 'danger'> = {
  excellent: 'success',
  good: 'warning',
  'at-risk': 'danger',
}

const columns: Column<Student>[] = [
  {
    key: 'name',
    header: 'Student',
    render: (s) => (
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
            color: 'var(--primary-foreground)',
          }}
        >
          {s.name
            .split(' ')
            .map((n) => n[0])
            .join('')}
        </div>
        <span className="font-medium">{s.name}</span>
      </div>
    ),
  },
  {
    key: 'course',
    header: 'Course',
    render: (s) => <span style={{ color: 'var(--muted-foreground)' }}>{s.course}</span>,
    hideOnMobile: true,
  },
  {
    key: 'grade',
    header: 'Grade',
    render: (s) => <span className="font-semibold">{s.grade}%</span>,
  },
  {
    key: 'engagement',
    header: 'Engagement',
    render: (s) => (
      <div className="flex items-center gap-2 w-28">
        <div
          className="flex-1 h-1.5 rounded-full overflow-hidden"
          style={{ background: 'var(--tint-3)' }}
        >
          <div
            className="h-full rounded-full"
            style={{ width: `${s.engagement}%`, background: 'var(--primary)' }}
          />
        </div>
        <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          {s.engagement}%
        </span>
      </div>
    ),
    hideOnMobile: true,
  },
  {
    key: 'attendance',
    header: 'Attendance',
    render: (s) => <span style={{ color: 'var(--muted-foreground)' }}>{s.attendance}%</span>,
    hideOnMobile: true,
  },
  {
    key: 'status',
    header: 'Status',
    render: (s) => (
      <Badge tone={statusTone[s.status]} size="xs">
        {s.status}
      </Badge>
    ),
  },
]

export default function StudentsPage() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          {
            label: 'Excellent',
            value: students.filter((s) => s.status === 'excellent').length,
            color: 'var(--success)',
          },
          {
            label: 'Good standing',
            value: students.filter((s) => s.status === 'good').length,
            color: 'var(--primary)',
          },
          {
            label: 'At-risk',
            value: students.filter((s) => s.status === 'at-risk').length,
            color: 'var(--danger)',
          },
          {
            label: 'Avg. grade',
            value: Math.round(students.reduce((a, s) => a + s.grade, 0) / students.length),
            suffix: '%',
            color: 'var(--accent)',
          },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            className="glass-card p-4"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <p
              className="text-2xl font-black"
              style={{ fontFamily: 'Orbitron, sans-serif', color: s.color }}
            >
              {s.value}
              {s.suffix ?? ''}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
              {s.label}
            </p>
          </motion.div>
        ))}
      </div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Student Roster
          </h3>
          <input
            placeholder="Search students..."
            className="input-field px-3.5 py-2 rounded-lg text-xs w-48"
          />
        </div>
        <DataTable columns={columns} rows={students} rowKey={(s) => s.id} />
      </motion.div>

      <motion.div
        className="glass-card p-6 flex items-center gap-6 flex-wrap"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <ProgressRing pct={81} color="var(--primary)" size={72} label="avg score" />
        <div>
          <p className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            Class-wide average performance
          </p>
          <p className="text-xs mt-1 max-w-md" style={{ color: 'var(--muted-foreground)' }}>
            Performance is up 3% from last month. Jordan Blake, Priya Nair, and Sam O'Connor need
            outreach this week — see AI insights in Analytics.
          </p>
        </div>
      </motion.div>
    </div>
  )
}

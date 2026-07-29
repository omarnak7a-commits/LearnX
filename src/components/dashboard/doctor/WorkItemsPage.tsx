import { motion } from 'framer-motion'
import DataTable, { type Column } from '../shared/DataTable'
import Badge from '../../ui/Badge'

interface WorkItem {
  id: number
  title: string
  course: string
  due: string
  submissions: string
  status: 'draft' | 'published' | 'grading' | 'closed'
}

interface WorkItemsPageProps {
  kind: 'assignments' | 'exams'
}

const assignmentSeed: WorkItem[] = [
  {
    id: 1,
    title: 'Lab Report — Sorting Algorithms',
    course: 'CS201',
    due: 'Jul 30',
    submissions: '112 / 148',
    status: 'grading',
  },
  {
    id: 2,
    title: 'Problem Set 5',
    course: 'MATH210',
    due: 'Aug 2',
    submissions: '40 / 96',
    status: 'published',
  },
  {
    id: 3,
    title: 'ER Diagram Design',
    course: 'CS310',
    due: 'Aug 4',
    submissions: '0 / 112',
    status: 'draft',
  },
  {
    id: 4,
    title: 'Neural Net Mini-Project',
    course: 'CS420',
    due: 'Jul 18',
    submissions: '56 / 56',
    status: 'closed',
  },
]

const examSeed: WorkItem[] = [
  {
    id: 1,
    title: 'Midterm Exam',
    course: 'CS201',
    due: 'Aug 8',
    submissions: 'Scheduled',
    status: 'published',
  },
  {
    id: 2,
    title: 'Final Exam Draft',
    course: 'CS310',
    due: 'TBD',
    submissions: 'AI-generated draft',
    status: 'draft',
  },
  {
    id: 3,
    title: 'Pop Quiz — Recursion',
    course: 'CS201',
    due: 'Jul 29',
    submissions: 'Scheduled',
    status: 'published',
  },
]

const statusTone: Record<WorkItem['status'], 'primary' | 'warning' | 'success' | 'neutral'> = {
  draft: 'neutral',
  published: 'primary',
  grading: 'warning',
  closed: 'success',
}

export default function WorkItemsPage({ kind }: WorkItemsPageProps) {
  const rows = kind === 'assignments' ? assignmentSeed : examSeed
  const label = kind === 'assignments' ? 'Assignment' : 'Exam'

  const columns: Column<WorkItem>[] = [
    {
      key: 'title',
      header: label,
      render: (r) => <span className="font-medium">{r.title}</span>,
    },
    {
      key: 'course',
      header: 'Course',
      render: (r) => <span style={{ color: 'var(--muted-foreground)' }}>{r.course}</span>,
      hideOnMobile: true,
    },
    {
      key: 'due',
      header: 'Due',
      render: (r) => <span style={{ color: 'var(--muted-foreground)' }}>{r.due}</span>,
    },
    {
      key: 'submissions',
      header: kind === 'assignments' ? 'Submissions' : 'Details',
      render: (r) => <span style={{ color: 'var(--muted-foreground)' }}>{r.submissions}</span>,
      hideOnMobile: true,
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <Badge tone={statusTone[r.status]} size="xs">
          {r.status}
        </Badge>
      ),
    },
  ]

  return (
    <div className="space-y-5">
      <motion.div
        className="glass-card p-6 flex flex-col sm:flex-row items-center justify-between gap-4"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            AI-assisted {label.toLowerCase()} builder
          </h3>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            Describe the topic and difficulty — the AI Teaching Assistant drafts a full{' '}
            {label.toLowerCase()} from your course materials.
          </p>
        </div>
        <button
          className="px-5 py-2.5 rounded-full text-sm font-semibold flex-shrink-0"
          style={{
            background: 'var(--primary)',
            color: 'var(--primary-foreground)',
          }}
        >
          ✨ Generate {label}
        </button>
      </motion.div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            All {label.toLowerCase()}s
          </h3>
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {rows.length} total
          </span>
        </div>
        <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />
      </motion.div>
    </div>
  )
}

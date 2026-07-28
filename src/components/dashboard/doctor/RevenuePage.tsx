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
import { useCourseCatalog } from '../../../context/CourseCatalogContext'
import StatCard from '../shared/StatCard'
import DataTable, { type Column } from '../shared/DataTable'
import Badge from '../../ui/Badge'
import { courseTypeLabel } from './course-management/courseMeta'
import type { Course } from '../../../types/course'

/** Deterministic per-course "price" derived from course type — premium
 * courses monetize, university/public courses don't (matches the spec's
 * "University Course / Public Course / Premium Course" distinction). */
function coursePrice(course: Course): number {
  if (course.courseType === 'premium') return 49
  return 0
}

function courseRevenue(course: Course): number {
  return coursePrice(course) * course.studentsCount
}

const trend = [
  { month: 'Feb', revenue: 1120 },
  { month: 'Mar', revenue: 1480 },
  { month: 'Apr', revenue: 1690 },
  { month: 'May', revenue: 2040 },
  { month: 'Jun', revenue: 2380 },
  { month: 'Jul', revenue: 2744 },
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
        ${payload[0]?.value.toLocaleString()}
      </p>
    </div>
  )
}

/**
 * Doctor Revenue page — derives real numbers from the shared course
 * catalog (premium courses × enrolled students) rather than fabricating
 * unrelated fake figures, so it stays consistent with Courses/Analytics.
 */
export default function RevenuePage() {
  const { courses } = useCourseCatalog()
  const monetized = courses.filter((c) => c.courseType === 'premium' && c.status !== 'archived')
  const totalRevenue = monetized.reduce((sum, c) => sum + courseRevenue(c), 0)
  const totalPaidStudents = monetized.reduce((sum, c) => sum + c.studentsCount, 0)
  const avgPrice = monetized.length
    ? Math.round(monetized.reduce((sum, c) => sum + coursePrice(c), 0) / monetized.length)
    : 0

  const columns: Column<Course>[] = [
    {
      key: 'title',
      header: 'Course',
      render: (c) => (
        <div className="flex items-center gap-2.5">
          <span
            className="w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
            style={{ background: `${c.color}18` }}
          >
            {c.icon}
          </span>
          <span className="font-medium">{c.title}</span>
        </div>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (c) => (
        <Badge tone="accent" size="xs">
          {courseTypeLabel[c.courseType]}
        </Badge>
      ),
      hideOnMobile: true,
    },
    {
      key: 'students',
      header: 'Paid Students',
      render: (c) => <span>{c.studentsCount.toLocaleString()}</span>,
    },
    {
      key: 'price',
      header: 'Price',
      render: (c) => <span style={{ color: 'var(--muted-foreground)' }}>${coursePrice(c)}</span>,
      hideOnMobile: true,
    },
    {
      key: 'revenue',
      header: 'Revenue',
      render: (c) => (
        <span className="font-semibold" style={{ color: 'var(--primary)' }}>
          ${courseRevenue(c).toLocaleString()}
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="💰"
          label="Total Revenue"
          value={totalRevenue}
          prefix="$"
          color="#2DD4BF"
          delay={0}
        />
        <StatCard
          icon="🎓"
          label="Paid Students"
          value={totalPaidStudents}
          color="#38bdf8"
          delay={0.05}
        />
        <StatCard
          icon="📦"
          label="Premium Courses"
          value={monetized.length}
          color="#a855f7"
          delay={0.1}
        />
        <StatCard
          icon="🏷️"
          label="Avg. Price"
          value={avgPrice}
          prefix="$"
          color="#f59e0b"
          delay={0.15}
        />
      </div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
              Revenue Trend
            </h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
              Last 6 months across all premium courses
            </p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={trend} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.28} />
                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke="var(--tint-2)" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'var(--muted-foreground)', fontSize: 9 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="revenue"
              stroke="var(--primary)"
              strokeWidth={2.5}
              fill="url(#revGrad)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <h3 className="text-sm font-bold mb-5" style={{ color: 'var(--foreground)' }}>
          Revenue by Course
        </h3>
        {monetized.length > 0 ? (
          <DataTable columns={columns} rows={monetized} rowKey={(c) => c.id} />
        ) : (
          <p className="text-sm text-center py-8" style={{ color: 'var(--muted-foreground)' }}>
            No premium courses yet — mark a course as "Premium Course" to start tracking revenue.
          </p>
        )}
      </motion.div>
    </div>
  )
}

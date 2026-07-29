import { motion } from 'framer-motion'

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => React.ReactNode
  className?: string
  hideOnMobile?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
}

/** Generic, theme-aware data table used across Doctor roster/assignment/exam views. */
export default function DataTable<T>({ columns, rows, rowKey }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className="w-full text-left border-collapse min-w-[560px]">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`text-xs font-semibold pb-3 pr-4 whitespace-nowrap ${
                  col.hideOnMobile ? 'hidden sm:table-cell' : ''
                } ${col.className ?? ''}`}
                style={{ color: 'var(--muted-foreground)' }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <motion.tr
              key={rowKey(row)}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.04, 0.4) }}
              className="transition-colors"
              style={{ borderBottom: '1px solid var(--border-subtle)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`py-3 pr-4 text-sm ${col.hideOnMobile ? 'hidden sm:table-cell' : ''}`}
                  style={{ color: 'var(--foreground)' }}
                >
                  {col.render(row)}
                </td>
              ))}
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

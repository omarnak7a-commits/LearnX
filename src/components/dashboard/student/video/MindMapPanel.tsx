import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { MindMapNode } from '../../../../types/video'

interface MindMapPanelProps {
  root: MindMapNode
}

const COLORS = ['#2DD4BF', '#a855f7', '#f59e0b', '#38bdf8', '#FF7E36', '#22c55e']

function Node({ node, depth, colorIndex }: { node: MindMapNode; depth: number; colorIndex: number }) {
  const [open, setOpen] = useState(depth < 1)
  const hasChildren = node.children.length > 0
  const color = COLORS[colorIndex % COLORS.length]

  return (
    <div className="relative">
      <motion.div
        className="flex items-center gap-2"
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
      >
        {hasChildren && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-xs"
            style={{ background: `${color}20`, color }}
          >
            <motion.span animate={{ rotate: open ? 90 : 0 }}>›</motion.span>
          </button>
        )}
        {!hasChildren && (
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
        )}
        <span
          className="px-3 py-1.5 rounded-lg text-sm font-medium"
          style={{
            background: depth === 0 ? `${color}20` : 'var(--tint-1)',
            color: depth === 0 ? color : 'var(--foreground)',
            fontWeight: depth === 0 ? 700 : 500,
            border: depth === 0 ? `1px solid ${color}40` : '1px solid var(--border-subtle)',
          }}
        >
          {node.label}
        </span>
      </motion.div>

      <AnimatePresence>
        {hasChildren && open && (
          <motion.div
            className="ml-2.5 pl-4 mt-1.5 space-y-1.5 border-l"
            style={{ borderColor: `${color}30` }}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            {node.children.map((child, i) => (
              <Node key={child.id} node={child} depth={depth + 1} colorIndex={colorIndex + i + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function MindMapPanel({ root }: MindMapPanelProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          Click any branch to expand or collapse it.
        </p>
        <div className="flex gap-1.5">
          <button className="text-xs px-2.5 py-1 rounded-lg input-field">Export</button>
          <button className="text-xs px-2.5 py-1 rounded-lg input-field">Print</button>
        </div>
      </div>
      <div className="p-2">
        <Node node={root} depth={0} colorIndex={0} />
      </div>
    </div>
  )
}

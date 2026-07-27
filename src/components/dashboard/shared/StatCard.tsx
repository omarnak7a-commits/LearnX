import { useEffect, useRef, useState } from 'react'
import { motion, animate } from 'framer-motion'

interface StatCardProps {
  icon: string
  label: string
  value: number
  suffix?: string
  decimals?: number
  delta?: string
  deltaTone?: 'up' | 'down' | 'neutral'
  color?: string
  delay?: number
  sublabel?: string
}

/** Animated KPI tile used across both Student and Doctor dashboards. */
export default function StatCard({
  icon,
  label,
  value,
  suffix = '',
  decimals = 0,
  delta,
  deltaTone = 'up',
  color = 'var(--primary)',
  delay = 0,
  sublabel,
}: StatCardProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) setInView(true)
      },
      { threshold: 0.4 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    if (!inView || !ref.current) return
    const controls = animate(0, value, {
      duration: 1.6,
      delay: 0.15 + delay,
      ease: [0.16, 1, 0.3, 1],
      onUpdate(v) {
        if (ref.current) {
          ref.current.textContent =
            decimals > 0 ? v.toFixed(decimals) : Math.round(v).toLocaleString()
        }
      },
    })
    return () => controls.stop()
  }, [inView, value, decimals, delay])

  return (
    <motion.div
      className="glass-card p-5 h-full relative overflow-hidden group"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -3 }}
    >
      <div
        className="absolute top-0 inset-x-0 h-0.5 opacity-70"
        style={{
          background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
        }}
      />
      <div className="flex items-start justify-between mb-3">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center text-base"
          style={{ background: `${color}18` }}
        >
          {icon}
        </div>
        {delta && (
          <span
            className="text-xs font-semibold px-1.5 py-0.5 rounded-md"
            style={{
              color:
                deltaTone === 'up'
                  ? 'var(--success)'
                  : deltaTone === 'down'
                    ? 'var(--danger)'
                    : 'var(--muted-foreground)',
              background:
                deltaTone === 'up'
                  ? 'var(--success-soft)'
                  : deltaTone === 'down'
                    ? 'var(--danger-soft)'
                    : 'var(--muted)',
            }}
          >
            {delta}
          </span>
        )}
      </div>
      <p
        className="text-2xl font-black leading-none"
        style={{
          fontFamily: 'Orbitron, sans-serif',
          color: 'var(--foreground)',
        }}
      >
        <span ref={ref}>0</span>
        {suffix}
      </p>
      <p className="text-xs mt-1.5 font-medium" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
      {sublabel && (
        <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)', opacity: 0.7 }}>
          {sublabel}
        </p>
      )}
    </motion.div>
  )
}

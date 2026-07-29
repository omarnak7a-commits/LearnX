import { useCountUp } from '@/hooks/useCountUp'
import { motion } from 'framer-motion'

const stats = [
  {
    label: 'students worldwide',
    value: 247000,
    prefix: '',
    suffix: '',
    decimals: 0,
    note: 'across 60+ countries',
  },
  {
    label: 'average grade improvement',
    value: 94,
    prefix: '',
    suffix: '%',
    decimals: 0,
    note: 'in first 30 days',
  },
  {
    label: 'hours saved per week',
    value: 4.2,
    prefix: '',
    suffix: 'h',
    decimals: 1,
    note: 'vs traditional studying',
  },
]

export default function NumbersSection() {
  return (
    <section
      className="py-28 px-8 relative overflow-hidden"
      style={{ background: 'var(--section-dark)' }}
    >
      {/* Very subtle top border */}
      <div
        className="absolute top-0 left-16 right-16 h-px"
        style={{ background: 'var(--border-subtle)' }}
      />

      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              className="relative py-10 px-8"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.65, delay: i * 0.14, ease: [0.16, 1, 0.3, 1] }}
            >
              {/* Right separator (not on last) */}
              {i < stats.length - 1 && (
                <div
                  className="hidden md:block absolute top-8 bottom-8 right-0 w-px"
                  style={{ background: 'var(--border-subtle)' }}
                />
              )}

              {/* Number */}
              <div
                className="flex items-baseline gap-1 mb-3 flex-wrap"
                style={{ fontFamily: 'Orbitron, sans-serif' }}
              >
                {stat.prefix && (
                  <span className="text-3xl font-semibold" style={{ color: 'var(--primary)' }}>
                    {stat.prefix}
                  </span>
                )}
                <NumberValue stat={stat} />
                {stat.suffix && (
                  <span
                    className="font-bold"
                    style={{ fontSize: 'clamp(1.15rem, 3vw, 2.15rem)', color: 'var(--primary)' }}
                  >
                    {stat.suffix}
                  </span>
                )}
              </div>

              <p className="text-base font-medium mb-1" style={{ color: 'var(--foreground)' }}>
                {stat.label}
              </p>
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {stat.note}
              </p>
            </motion.div>
          ))}
        </div>
      </div>

      <div
        className="absolute bottom-0 left-16 right-16 h-px"
        style={{ background: 'var(--border-subtle)' }}
      />
    </section>
  )
}

function NumberValue({ stat }: { stat: (typeof stats)[0] }) {
  const ref = useCountUp<HTMLSpanElement>(stat.value, {
    duration: 2.4,
    delay: 0.1,
    decimals: stat.decimals,
  })

  return (
    <span
      ref={ref}
      style={{
        fontSize: 'clamp(1.75rem, 4vw, 3.25rem)',
        fontWeight: 900,
        color: 'var(--primary)',
        lineHeight: 1,
      }}
    >
      0
    </span>
  )
}

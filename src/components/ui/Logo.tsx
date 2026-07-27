import { motion } from 'framer-motion'
import LogoMark from './LogoMark'

type LogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

const SYMBOL_SIZE: Record<LogoSize, number> = {
  xs: 20,
  sm: 24,
  md: 30,
  lg: 40,
  xl: 64,
}

const WORDMARK_SIZE: Record<LogoSize, string> = {
  xs: '0.9rem',
  sm: '1rem',
  md: '1.125rem',
  lg: '1.5rem',
  xl: '2.25rem',
}

const GAP: Record<LogoSize, number> = {
  xs: 6,
  sm: 8,
  md: 10,
  lg: 12,
  xl: 16,
}

interface LogoProps {
  /** 'full' = symbol + wordmark (marketing pages). 'symbol' = mark only (dashboards / compact nav). */
  variant?: 'full' | 'symbol'
  size?: LogoSize
  animated?: boolean
  /** Show the "Less Stress | More Success" tagline beneath the wordmark. */
  withTagline?: boolean
  className?: string
  onClick?: () => void
  as?: 'div' | 'button'
  'aria-label'?: string
}

/**
 * Canonical LearnX logo lockup. Always theme-aware (ink follows
 * `--logo-ink`, spark diamond stays brand teal) so it never needs a manual
 * dark/light color prop at the call site.
 */
export default function Logo({
  variant = 'full',
  size = 'md',
  animated = false,
  withTagline = false,
  className = '',
  onClick,
  as = 'div',
  'aria-label': ariaLabel,
}: LogoProps) {
  const symbolSize = SYMBOL_SIZE[size]
  const gap = GAP[size]

  const content = (
    <div className="flex items-center" style={{ gap }}>
      <LogoMark size={symbolSize} animated={animated} color="var(--logo-ink)" />
      {variant === 'full' && (
        <div className="flex flex-col justify-center leading-none">
          <span
            className="font-bold whitespace-nowrap"
            style={{
              fontFamily: 'Orbitron, sans-serif',
              fontSize: WORDMARK_SIZE[size],
              color: 'var(--foreground)',
              letterSpacing: '0.06em',
              lineHeight: 1,
            }}
          >
            LearnX
          </span>
          {withTagline && (
            <span
              className="whitespace-nowrap mt-1.5"
              style={{
                fontSize: '0.625rem',
                color: 'var(--muted-foreground)',
                letterSpacing: '0.18em',
                textTransform: 'uppercase',
                fontFamily: 'Inter, sans-serif',
              }}
            >
              Less Stress · More Success
            </span>
          )}
        </div>
      )}
    </div>
  )

  const commonProps = {
    className: `inline-flex items-center flex-shrink-0 ${onClick ? 'group' : ''} ${className}`,
    onClick,
    'aria-label': ariaLabel ?? 'LearnX',
  }

  if (as === 'button') {
    return (
      <motion.button
        {...commonProps}
        whileHover={onClick ? { scale: 1.03 } : undefined}
        whileTap={onClick ? { scale: 0.97 } : undefined}
        transition={{ duration: 0.15 }}
      >
        {content}
      </motion.button>
    )
  }

  return <div {...commonProps}>{content}</div>
}

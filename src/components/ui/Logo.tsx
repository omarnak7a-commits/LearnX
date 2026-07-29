import { motion } from 'framer-motion'
import logoFullDarkInk from '../../assets/brand/logo-full-dark-ink.png'
import logoFullLightInk from '../../assets/brand/logo-full-light-ink.png'
import logoSymbolDarkInk from '../../assets/brand/logo-symbol-dark-ink.png'
import logoSymbolLightInk from '../../assets/brand/logo-symbol-light-ink.png'

type LogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

/** Symbol height in px per size step — width is derived from the source aspect ratio. */
const SYMBOL_HEIGHT: Record<LogoSize, number> = {
  xs: 22,
  sm: 26,
  md: 32,
  lg: 44,
  xl: 72,
}

/** Full wordmark height in px per size step. */
const FULL_HEIGHT: Record<LogoSize, number> = {
  xs: 20,
  sm: 24,
  md: 30,
  lg: 40,
  xl: 64,
}

interface LogoProps {
  /** 'full' = symbol + wordmark (marketing pages). 'symbol' = mark only (dashboards / compact nav). */
  variant?: 'full' | 'symbol'
  size?: LogoSize
  className?: string
  onClick?: () => void
  as?: 'div' | 'button'
  'aria-label'?: string
}

/**
 * Canonical LearnX logo lockup, rendered from the official brand asset
 * (src/imports/logo1.png light-mode artwork / logo2.png dark-mode artwork —
 * cropped and trimmed once into `src/assets/brand/`, never re-drawn).
 *
 * Automatically swaps the correct light/dark-ink variant via CSS using the
 * same `.light` class convention the rest of the design system already
 * uses on `<html>` — no theme prop needs to be threaded through call sites.
 */
export default function Logo({
  variant = 'full',
  size = 'md',
  className = '',
  onClick,
  as = 'div',
  'aria-label': ariaLabel,
}: LogoProps) {
  const height = variant === 'full' ? FULL_HEIGHT[size] : SYMBOL_HEIGHT[size]
  const darkSrc = variant === 'full' ? logoFullDarkInk : logoSymbolDarkInk
  const lightSrc = variant === 'full' ? logoFullLightInk : logoSymbolLightInk

  const content = (
    <>
      {/* Dark-ink artwork — shown on light backgrounds (default / light mode) */}
      <img
        src={darkSrc}
        alt="LearnX"
        className="logo-asset logo-asset-dark-ink"
        style={{ height, width: 'auto' }}
        draggable={false}
      />
      {/* Light-ink artwork — shown on dark backgrounds (dark mode) */}
      <img
        src={lightSrc}
        alt=""
        aria-hidden="true"
        className="logo-asset logo-asset-light-ink"
        style={{ height, width: 'auto' }}
        draggable={false}
      />
    </>
  )


  const commonProps = {
    className: `relative inline-flex items-center flex-shrink-0 ${onClick ? 'group' : ''} ${className}`,
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

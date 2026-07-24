import { motion } from 'framer-motion'

interface LogoMarkProps {
  size?: number
  animated?: boolean
  color?: string
  className?: string
}

export default function LogoMark({ size = 40, animated = false, color = '#2DD4BF', className = '' }: LogoMarkProps) {
  const w = size * 0.7
  const h = size

  const pathVariants = {
    hidden: { pathLength: 0, opacity: 0 },
    visible: (i: number) => ({
      pathLength: 1,
      opacity: 1,
      transition: { duration: 0.6, delay: i * 0.18, ease: 'easeOut' },
    }),
  }

  const diamondVariants = {
    hidden: { scale: 0, opacity: 0 },
    visible: {
      scale: 1,
      opacity: 1,
      transition: { duration: 0.4, delay: 0.85, ease: [0.34, 1.56, 0.64, 1] },
    },
  }

  const Tag = animated ? motion.svg : 'svg'
  const PathTag = animated ? motion.path : 'path'
  const RectTag = animated ? motion.rect : 'rect'

  return (
    <Tag
      width={w}
      height={h}
      viewBox="0 0 56 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      initial={animated ? 'hidden' : undefined}
      animate={animated ? 'visible' : undefined}
    >
      {/* Outer chevron – top stroke */}
      <PathTag
        d="M6 6 L28 36"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="square"
        custom={0}
        variants={animated ? pathVariants : undefined}
      />
      {/* Outer chevron – bottom stroke */}
      <PathTag
        d="M6 66 L28 36"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="square"
        custom={1}
        variants={animated ? pathVariants : undefined}
      />
      {/* Inner chevron – top stroke */}
      <PathTag
        d="M26 6 L50 36"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="square"
        custom={2}
        variants={animated ? pathVariants : undefined}
      />
      {/* Inner chevron – bottom stroke */}
      <PathTag
        d="M26 66 L50 36"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="square"
        custom={3}
        variants={animated ? pathVariants : undefined}
      />
      {/* Central diamond */}
      <RectTag
        x="20"
        y="30"
        width="11"
        height="11"
        fill="#2DD4BF"
        transform="rotate(45 25.5 35.5)"
        variants={animated ? diamondVariants : undefined}
        style={{ transformOrigin: '25.5px 35.5px' }}
      />
    </Tag>
  )
}

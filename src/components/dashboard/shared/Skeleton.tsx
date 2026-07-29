interface SkeletonProps {
  className?: string
  height?: number | string
  width?: number | string
  rounded?: string
}

/** Shimmering loading placeholder — theme-aware. */
export default function Skeleton({
  className = '',
  height = 16,
  width = '100%',
  rounded = '8px',
}: SkeletonProps) {
  return (
    <div className={`skeleton ${className}`} style={{ height, width, borderRadius: rounded }} />
  )
}

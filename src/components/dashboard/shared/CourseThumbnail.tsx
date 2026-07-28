interface CourseThumbnailProps {
  icon: string
  color: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeMap = {
  sm: { box: 'w-12 h-12', text: 'text-xl' },
  md: { box: 'w-full aspect-video', text: 'text-4xl' },
  lg: { box: 'w-full aspect-[21/9]', text: 'text-5xl' },
}

/**
 * Reusable course "thumbnail" — a branded gradient tile built from the
 * course's icon + accent color. Every course card, builder header, and
 * detail page uses this so the experience never shows a broken/missing
 * image while still feeling like a real thumbnail slot.
 */
export default function CourseThumbnail({
  icon,
  color,
  className = '',
  size = 'md',
}: CourseThumbnailProps) {
  const s = sizeMap[size]
  return (
    <div
      className={`relative rounded-xl overflow-hidden flex items-center justify-center flex-shrink-0 ${s.box} ${className}`}
      style={{ background: `linear-gradient(135deg, ${color}26, ${color}0d)` }}
    >
      <div
        className="absolute inset-0 opacity-40"
        style={{
          backgroundImage: `radial-gradient(circle at 30% 20%, ${color}55 0%, transparent 55%)`,
        }}
      />
      <span className={`relative ${s.text}`}>{icon}</span>
    </div>
  )
}

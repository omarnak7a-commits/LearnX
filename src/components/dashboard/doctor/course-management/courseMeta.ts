import type { CourseStatus, CourseType } from '../../../../types/course'
import type { BadgeToneMap } from './types'

export const statusTone: BadgeToneMap<CourseStatus> = {
  draft: 'neutral',
  'pending-review': 'warning',
  published: 'success',
  archived: 'info',
}

export const statusLabel: Record<CourseStatus, string> = {
  draft: 'Draft',
  'pending-review': 'Pending Review',
  published: 'Published',
  archived: 'Archived',
}

export const courseTypeTone: BadgeToneMap<CourseType> = {
  university: 'primary',
  public: 'neutral',
  premium: 'accent',
}

export const courseTypeLabel: Record<CourseType, string> = {
  university: 'University Course',
  public: 'Public Course',
  premium: 'Premium Course',
}

/** Exchange rate the Reward Store / Create/Edit Course flows use to
 *  suggest an XP price from a doctor's USD price — matches the spec's
 *  examples exactly ($30 → 12,000 XP, $50 → 20,000 XP = 400 XP/dollar). */
export const XP_PER_USD = 400

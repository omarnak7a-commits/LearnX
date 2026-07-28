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

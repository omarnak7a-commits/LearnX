import type { BadgeId } from '../types/profile'

export interface BadgeDefinition {
  id: BadgeId
  icon: string
  label: string
  description: string
}

/**
 * Every badge referenced by the spec's "PROFILE BADGES" section, resolved
 * against a stable id everywhere (profile records, leaderboard entries,
 * badge showcase grids) instead of re-typing labels/icons per component.
 */
export const BADGE_DEFINITIONS: BadgeDefinition[] = [
  {
    id: 'top-10-student',
    icon: '🏆',
    label: 'Top 10 Student',
    description: 'Ranked in the top 10 on the all-time leaderboard.',
  },
  {
    id: 'top-engineering-student',
    icon: '⚙️',
    label: 'Top Engineering Student',
    description: "Highest XP among your faculty's engineering students.",
  },
  {
    id: 'perfect-quiz',
    icon: '💯',
    label: 'Perfect Quiz',
    description: 'Scored 100% on a quiz.',
  },
  {
    id: '30-day-streak',
    icon: '🔥',
    label: '30-Day Streak',
    description: 'Studied 30 days in a row.',
  },
  {
    id: 'ai-explorer',
    icon: '🤖',
    label: 'AI Explorer',
    description: 'Used every AI Study Hub feature at least once.',
  },
  {
    id: 'fast-learner',
    icon: '⚡',
    label: 'Fast Learner',
    description: 'Completed a course faster than 90% of students.',
  },
  {
    id: 'course-master',
    icon: '🎓',
    label: 'Course Master',
    description: 'Completed 10 or more courses.',
  },
  {
    id: 'weekly-champion',
    icon: '👑',
    label: 'Weekly Champion',
    description: '#1 on the weekly leaderboard.',
  },
  {
    id: 'monthly-champion',
    icon: '🥇',
    label: 'Monthly Champion',
    description: '#1 on the monthly leaderboard.',
  },
]

const BADGE_MAP: Record<BadgeId, BadgeDefinition> = BADGE_DEFINITIONS.reduce(
  (acc, def) => {
    acc[def.id] = def
    return acc
  },
  {} as Record<BadgeId, BadgeDefinition>
)

export function getBadgeDefinition(id: BadgeId): BadgeDefinition {
  return BADGE_MAP[id]
}

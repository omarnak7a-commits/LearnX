/**
 * Shared types for the Global XP System, Gamification page, and Reward
 * Store — the spec's Feature 2/3/4/5/6/7. This is the *centralized* XP
 * ledger the spec asks for ("Create one centralized XP system. XP should
 * be stored globally.") — a real, append-only transaction log persisted
 * via `src/lib/xp/storage.ts` (localStorage), read by `useXp()`
 * (`src/context/XpContext.tsx`), and written to by every feature that
 * awards XP (lessons, quizzes, study sessions, uploads, flashcards,
 * assignments, certificates, streaks).
 *
 * Design note: unlike `src/hooks/useProfileStats.ts` (which *derives* an
 * academic-identity XP number from course/file activity so it can never
 * double-count), this ledger is the deliberate exception — the spec
 * explicitly asks for XP to be "awarded" by discrete actions with fixed
 * amounts, which requires a real transaction log (so History/Weekly/
 * Monthly/Lifetime XP and "was this specific action already rewarded"
 * checks are all real and auditable, not recomputed guesses). Both
 * systems intentionally coexist: `useProfileStats` still drives the
 * Profile/Rankings leaderboard's academic-identity XP, while `useXp`
 * drives the reward economy (Gamification, Reward Store, unlocks).
 */

export type XpSourceId =
  | 'lesson-complete'
  | 'course-complete'
  | 'quiz-complete'
  | 'quiz-high-score'
  | 'study-30-min'
  | 'daily-streak'
  | 'upload-notes'
  | 'generate-flashcards'
  | 'study-session-complete'
  | 'assignment-complete'
  | 'certificate-earned'
  | 'daily-challenge'
  | 'daily-challenge-bonus'
  | 'weekly-challenge'
  | 'reward-redeemed'

export interface XpSourceDefinition {
  id: XpSourceId
  label: string
  amount: number
  icon: string
}

/** Every award rule from the spec's "FEATURE 2 — Global XP System"
 *  section, resolved against a stable id everywhere XP is granted. */
export const XP_SOURCES: Record<XpSourceId, XpSourceDefinition> = {
  'lesson-complete': { id: 'lesson-complete', label: 'Complete Lesson', amount: 50, icon: '🎬' },
  'course-complete': { id: 'course-complete', label: 'Finish Course', amount: 500, icon: '🎓' },
  'quiz-complete': { id: 'quiz-complete', label: 'Complete Quiz', amount: 100, icon: '❓' },
  'quiz-high-score': { id: 'quiz-high-score', label: 'Score above 90%', amount: 150, icon: '🌟' },
  'study-30-min': { id: 'study-30-min', label: 'Study 30 Minutes', amount: 40, icon: '⏱️' },
  'daily-streak': { id: 'daily-streak', label: 'Maintain Daily Streak', amount: 30, icon: '🔥' },
  'upload-notes': { id: 'upload-notes', label: 'Upload Notes', amount: 20, icon: '📝' },
  'generate-flashcards': {
    id: 'generate-flashcards',
    label: 'Generate Flashcards',
    amount: 25,
    icon: '🗂️',
  },
  'study-session-complete': {
    id: 'study-session-complete',
    label: 'Complete Study Session',
    amount: 50,
    icon: '📖',
  },
  'assignment-complete': {
    id: 'assignment-complete',
    label: 'Finish Assignment',
    amount: 80,
    icon: '📋',
  },
  'certificate-earned': {
    id: 'certificate-earned',
    label: 'Earn Certificate',
    amount: 300,
    icon: '📜',
  },
  'daily-challenge': { id: 'daily-challenge', label: 'Daily Challenge', amount: 0, icon: '🎯' },
  'daily-challenge-bonus': {
    id: 'daily-challenge-bonus',
    label: 'All Daily Challenges Bonus',
    amount: 100,
    icon: '🏅',
  },
  'weekly-challenge': { id: 'weekly-challenge', label: 'Weekly Challenge', amount: 0, icon: '🏆' },
  'reward-redeemed': { id: 'reward-redeemed', label: 'Reward Redeemed', amount: 0, icon: '🛍️' },
}

/** A single ledger entry — every XP gain (positive amount) or spend
 *  (negative amount, e.g. redeeming a reward) is one immutable row. */
export interface XpTransaction {
  id: string
  source: XpSourceId
  amount: number
  label: string
  /** Free-form context, e.g. a course/file title, shown in XP History. */
  detail: string | null
  /** De-duplication key so the same concrete action (e.g. "lesson X of
   *  course Y complete") can never be credited twice. Null for
   *  intentionally-repeatable actions (study time, streak ticks). */
  dedupeKey: string | null
  timestamp: number
}

export type BadgeRewardId = string

export type ChallengeCadence = 'daily' | 'weekly'

export type ChallengeMetric =
  | 'study-minutes'
  | 'quiz-complete'
  | 'lesson-complete'
  | 'flashcards-generated'
  | 'pdf-read'
  | 'lecture-watched'
  | 'notes-uploaded'
  | 'assignment-complete'
  | 'course-complete'
  | 'streak-days'
  | 'quiz-high-score'
  | 'xp-earned'

export interface ChallengeDefinition {
  id: string
  cadence: ChallengeCadence
  metric: ChallengeMetric
  label: string
  icon: string
  target: number
  xpReward: number
  /** Weekly-only bonus rewards beyond XP (spec Feature 6). */
  bonusBadgeId?: BadgeRewardId
  bonusCouponPercent?: number
}

export interface ChallengeProgress {
  id: string
  /** The rotating period key this progress belongs to — an ISO date for
   *  daily challenges, an ISO week-start date for weekly ones — so
   *  progress never bleeds across rotations. */
  periodKey: string
  definitionId: string
  current: number
  completed: boolean
  completedAt: number | null
  rewardClaimed: boolean
}

export type RewardCategory =
  | 'premium-course'
  | 'course-discount'
  | 'course-coupon'
  | 'certificate'
  | 'profile-theme'
  | 'animated-frame'
  | 'exclusive-badge'
  | 'seasonal'
  | 'premium-icon'
  | 'ai-credits'

export interface RewardItem {
  id: string
  category: RewardCategory
  name: string
  description: string
  icon: string
  xpCost: number
  /** Only set for `premium-course` rewards — the real course this
   *  unlocks, resolved against the shared course catalog. */
  courseId?: string
  /** Only set for `course-discount`/`course-coupon` rewards. */
  discountPercent?: number
  seasonal?: boolean
}

export type RewardTransactionStatus = 'success' | 'insufficient-xp'

export interface RewardRedemption {
  id: string
  rewardId: string
  rewardName: string
  category: RewardCategory
  xpSpent: number
  courseId: string | null
  status: RewardTransactionStatus
  timestamp: number
}

/** Every level-unlock milestone from the spec's "FEATURE 7 — Level
 *  Unlocks" section. */
export interface LevelUnlock {
  level: number
  label: string
  icon: string
  category: RewardCategory
}

export const LEVEL_UNLOCKS: LevelUnlock[] = [
  { level: 5, label: 'Aurora Profile Theme', icon: '🎨', category: 'profile-theme' },
  { level: 10, label: 'Premium Badge', icon: '🥇', category: 'exclusive-badge' },
  { level: 15, label: '10% Course Discount', icon: '🏷️', category: 'course-discount' },
  { level: 20, label: 'Free Premium Course', icon: '🎁', category: 'premium-course' },
  { level: 25, label: 'Animated Avatar Frame', icon: '🌀', category: 'animated-frame' },
  { level: 30, label: 'Exclusive AI Theme', icon: '🤖', category: 'profile-theme' },
]

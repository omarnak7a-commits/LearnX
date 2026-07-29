import type { RewardCategory, RewardItem } from '../types/gamification'

/**
 * Static reward catalog for every category the spec's "FEATURE 4 —
 * Reward Store" section lists. Premium-course rewards are intentionally
 * NOT hardcoded here — they're generated dynamically from the live
 * course catalog (`buildPremiumCourseRewards()` in
 * `src/context/RewardStoreContext.tsx`) so a doctor toggling
 * `allowXpRedemption`/`xpPrice` on a real course immediately reflects in
 * the store, matching the spec's "Teachers can choose whether a paid
 * course supports XP redemption."
 */
export const REWARD_CATALOG: RewardItem[] = [
  // Course Discounts
  {
    id: 'discount-10',
    category: 'course-discount',
    name: '10% Off Any Premium Course',
    description: 'Apply a 10% discount coupon to your next premium course purchase.',
    icon: '🏷️',
    xpCost: 2000,
    discountPercent: 10,
  },
  {
    id: 'discount-25',
    category: 'course-discount',
    name: '25% Off Any Premium Course',
    description: 'Apply a 25% discount coupon to your next premium course purchase.',
    icon: '🏷️',
    xpCost: 4500,
    discountPercent: 25,
  },
  // Course Coupons
  {
    id: 'coupon-free-month',
    category: 'course-coupon',
    name: 'Skip-the-Line Coupon',
    description: 'Redeemable for priority AI grading turnaround on your next assignment.',
    icon: '🎟️',
    xpCost: 1200,
  },
  // Certificates
  {
    id: 'certificate-completion',
    category: 'certificate',
    name: 'Verified Completion Certificate',
    description: 'A shareable, verified LearnX certificate for any completed course.',
    icon: '📜',
    xpCost: 1500,
  },
  // Profile Themes
  {
    id: 'theme-aurora',
    category: 'profile-theme',
    name: 'Aurora Profile Theme',
    description: 'A teal-to-violet gradient theme for your profile card.',
    icon: '🎨',
    xpCost: 1000,
  },
  {
    id: 'theme-midnight',
    category: 'profile-theme',
    name: 'Midnight Gold Theme',
    description: 'A deep-navy and gold profile theme for top performers.',
    icon: '🌌',
    xpCost: 3000,
  },
  // Animated Frames
  {
    id: 'frame-flame',
    category: 'animated-frame',
    name: 'Animated Flame Frame',
    description: 'A flickering flame border around your avatar everywhere it appears.',
    icon: '🔥',
    xpCost: 1800,
  },
  {
    id: 'frame-orbit',
    category: 'animated-frame',
    name: 'Orbit Ring Frame',
    description: 'A slow-rotating ring of stars around your avatar.',
    icon: '🪐',
    xpCost: 2200,
  },
  // Exclusive Badges
  {
    id: 'badge-scholar',
    category: 'exclusive-badge',
    name: 'Scholar Badge',
    description: 'A rare badge available only through the Reward Store.',
    icon: '🦉',
    xpCost: 2500,
  },
  // Seasonal Rewards
  {
    id: 'seasonal-winter',
    category: 'seasonal',
    name: 'Winter Solstice Frame',
    description: 'Limited-time seasonal avatar frame.',
    icon: '❄️',
    xpCost: 1600,
    seasonal: true,
  },
  // Premium Icons
  {
    id: 'icon-pack-neon',
    category: 'premium-icon',
    name: 'Neon Icon Pack',
    description: 'Unlock a set of premium neon sidebar/dashboard icons.',
    icon: '💠',
    xpCost: 900,
  },
  // Future AI Credits
  {
    id: 'ai-credits-50',
    category: 'ai-credits',
    name: '50 Future AI Credits',
    description: 'Reserved credits for upcoming premium AI features.',
    icon: '🤖',
    xpCost: 800,
  },
]

export const CATEGORY_META: Record<RewardCategory, { label: string; icon: string }> = {
  'premium-course': { label: 'Premium Courses', icon: '🎓' },
  'course-discount': { label: 'Course Discounts', icon: '🏷️' },
  'course-coupon': { label: 'Course Coupons', icon: '🎟️' },
  certificate: { label: 'Certificates', icon: '📜' },
  'profile-theme': { label: 'Profile Themes', icon: '🎨' },
  'animated-frame': { label: 'Animated Frames', icon: '🌀' },
  'exclusive-badge': { label: 'Exclusive Badges', icon: '🦉' },
  seasonal: { label: 'Seasonal Rewards', icon: '❄️' },
  'premium-icon': { label: 'Premium Icons', icon: '💠' },
  'ai-credits': { label: 'Future AI Credits', icon: '🤖' },
}

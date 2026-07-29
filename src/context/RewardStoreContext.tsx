import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { RewardItem, RewardRedemption } from '../types/gamification'
import { REWARD_CATALOG } from '../data/rewardCatalog'
import { useXp } from './XpContext'
import { useCourseCatalog } from './CourseCatalogContext'
import {
  loadRedemptions,
  saveRedemptions,
  loadCoupons,
  saveCoupons,
  type ActiveCoupon,
} from '../lib/xp/rewardStorage'

export type RedeemOutcome =
  { status: 'success'; redemption: RewardRedemption } | { status: 'insufficient-xp' }

interface RewardStoreContextValue {
  loading: boolean
  /** Full store catalog — static rewards plus one dynamically-generated
   *  reward per XP-redeemable premium course in the live catalog. */
  rewards: RewardItem[]
  redemptions: RewardRedemption[]
  coupons: ActiveCoupon[]
  /**
   * Redemption Logic per the spec: checks available XP, and if enough
   * exists, deducts XP, unlocks the course/reward instantly, and updates
   * Reward History + (for premium courses) Purchased Courses. Returns a
   * discriminated result so the calling UI can show the exact success/
   * failure state (and success animation) without re-deriving it.
   */
  redeem: (rewardId: string) => RedeemOutcome
  useCoupon: (couponId: string) => void
}

const RewardStoreContext = createContext<RewardStoreContextValue | null>(null)

let redemptionCounter = 0

export function RewardStoreProvider({ children }: { children: ReactNode }) {
  const [redemptions, setRedemptions] = useState<RewardRedemption[]>([])
  const [coupons, setCoupons] = useState<ActiveCoupon[]>([])
  const [loading, setLoading] = useState(true)
  const { totalXp, spend } = useXp()
  const { courses, markPurchasedViaReward } = useCourseCatalog()

  useEffect(() => {
    setRedemptions(loadRedemptions())
    setCoupons(loadCoupons())
    setLoading(false)
  }, [])

  const premiumCourseRewards = useMemo<RewardItem[]>(
    () =>
      courses
        .filter(
          (c) =>
            c.courseType === 'premium' &&
            c.status === 'published' &&
            c.allowXpRedemption &&
            c.xpPrice !== null &&
            !c.enrolled
        )
        .map((c) => ({
          id: `premium-course-${c.id}`,
          category: 'premium-course' as const,
          name: c.title,
          description: `Unlock "${c.title}" by ${c.doctorName} — ${c.priceUsd !== null ? `$${c.priceUsd} OR ` : ''}${c.xpPrice!.toLocaleString()} XP.`,
          icon: c.icon,
          xpCost: c.xpPrice!,
          courseId: c.id,
        })),
    [courses]
  )

  const rewards = useMemo(
    () => [...premiumCourseRewards, ...REWARD_CATALOG],
    [premiumCourseRewards]
  )

  const redeem = useCallback(
    (rewardId: string): RedeemOutcome => {
      const reward = rewards.find((r) => r.id === rewardId)
      if (!reward) return { status: 'insufficient-xp' }
      if (totalXp < reward.xpCost) return { status: 'insufficient-xp' }

      const success = spend(reward.xpCost, reward.name, reward.courseId ?? null)
      if (!success) return { status: 'insufficient-xp' }

      // Unlock instantly.
      if (reward.category === 'premium-course' && reward.courseId) {
        markPurchasedViaReward(reward.courseId)
      }
      if (reward.category === 'course-discount' && reward.discountPercent) {
        redemptionCounter += 1
        const coupon: ActiveCoupon = {
          id: `coupon-${Date.now()}-${redemptionCounter}`,
          discountPercent: reward.discountPercent,
          redeemedAt: Date.now(),
          used: false,
        }
        setCoupons((prev) => {
          const next = [...prev, coupon]
          saveCoupons(next)
          return next
        })
      }

      redemptionCounter += 1
      const redemption: RewardRedemption = {
        id: `redemption-${Date.now()}-${redemptionCounter}`,
        rewardId: reward.id,
        rewardName: reward.name,
        category: reward.category,
        xpSpent: reward.xpCost,
        courseId: reward.courseId ?? null,
        status: 'success',
        timestamp: Date.now(),
      }
      setRedemptions((prev) => {
        const next = [redemption, ...prev]
        saveRedemptions(next)
        return next
      })

      return { status: 'success', redemption }
    },
    [rewards, totalXp, spend, markPurchasedViaReward]
  )

  const useCoupon = useCallback((couponId: string) => {
    setCoupons((prev) => {
      const next = prev.map((c) => (c.id === couponId ? { ...c, used: true } : c))
      saveCoupons(next)
      return next
    })
  }, [])

  const value = useMemo<RewardStoreContextValue>(
    () => ({ loading, rewards, redemptions, coupons, redeem, useCoupon }),
    [loading, rewards, redemptions, coupons, redeem, useCoupon]
  )

  return <RewardStoreContext.Provider value={value}>{children}</RewardStoreContext.Provider>
}

export function useRewardStore() {
  const ctx = useContext(RewardStoreContext)
  if (!ctx) throw new Error('useRewardStore must be used within a RewardStoreProvider')
  return ctx
}

import type { RewardRedemption } from '../../types/gamification'

const STORAGE_KEY = 'learnx-reward-history-v1'

export function loadRedemptions(): RewardRedemption[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveRedemptions(redemptions: RewardRedemption[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(redemptions))
  } catch {
    // ignore
  }
}

/** Active (unspent) coupons — id + discount percent — a student has
 *  redeemed. Kept separate from the raw redemption log so "apply my
 *  coupon at checkout" can consume one without rewriting history. */
export interface ActiveCoupon {
  id: string
  discountPercent: number
  redeemedAt: number
  used: boolean
}

const COUPONS_KEY = 'learnx-active-coupons-v1'

export function loadCoupons(): ActiveCoupon[] {
  try {
    const raw = localStorage.getItem(COUPONS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveCoupons(coupons: ActiveCoupon[]): void {
  try {
    localStorage.setItem(COUPONS_KEY, JSON.stringify(coupons))
  } catch {
    // ignore
  }
}

import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useXp } from '../../../context/XpContext'
import { useRewardStore } from '../../../context/RewardStoreContext'
import { CATEGORY_META } from '../../../data/rewardCatalog'
import type { RewardCategory, RewardItem } from '../../../types/gamification'
import Badge from '../../ui/Badge'

const CATEGORY_ORDER: RewardCategory[] = [
  'premium-course',
  'course-discount',
  'course-coupon',
  'certificate',
  'profile-theme',
  'animated-frame',
  'exclusive-badge',
  'seasonal',
  'premium-icon',
  'ai-credits',
]

function RewardCard({
  reward,
  canAfford,
  onRedeem,
}: {
  reward: RewardItem
  canAfford: boolean
  onRedeem: () => void
}) {
  return (
    <motion.div
      className="rounded-xl p-4 flex flex-col"
      style={{ background: 'var(--tint-1)', border: '1px solid var(--border-subtle)' }}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3, borderColor: 'rgba(45,212,191,0.35)' }}
    >
      <div className="flex items-start gap-3 mb-3">
        <span
          className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
          style={{ background: 'rgba(45,212,191,0.12)' }}
        >
          {reward.icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold truncate" style={{ color: 'var(--foreground)' }}>
            {reward.name}
          </p>
          {reward.seasonal && (
            <Badge tone="info" size="xs">
              Seasonal
            </Badge>
          )}
        </div>
      </div>
      <p
        className="text-xs leading-relaxed mb-4 flex-1"
        style={{ color: 'var(--muted-foreground)' }}
      >
        {reward.description}
      </p>
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-xs font-bold px-2.5 py-1 rounded-full"
          style={{ background: 'rgba(255,126,54,0.12)', color: 'var(--accent)' }}
        >
          {reward.xpCost.toLocaleString()} XP
        </span>
        <button
          onClick={onRedeem}
          disabled={!canAfford}
          className="text-xs font-semibold px-4 py-2 rounded-full transition-opacity"
          style={{
            background: canAfford ? 'var(--primary)' : 'var(--tint-3)',
            color: canAfford ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
            opacity: canAfford ? 1 : 0.7,
            cursor: canAfford ? 'pointer' : 'not-allowed',
          }}
        >
          {canAfford ? 'Redeem' : 'Not enough XP'}
        </button>
      </div>
    </motion.div>
  )
}

/**
 * Complete Reward Store per the spec's "FEATURE 4 — Reward Store" and
 * "REDEMPTION LOGIC" sections. Every category listed in the spec is
 * represented; Premium Course rewards are generated live from the real
 * course catalog (only courses a doctor has explicitly opted into XP
 * redemption for appear here — see `RewardStoreContext`). Redeeming
 * performs the exact sequence the spec describes: check XP, deduct XP,
 * unlock instantly, show a success animation, and update Reward
 * History/XP History/Purchased Courses/Dashboard (all live via context,
 * no page refresh needed).
 */
export default function RewardStorePage() {
  const { totalXp } = useXp()
  const { rewards, redeem } = useRewardStore()
  const [activeCategory, setActiveCategory] = useState<RewardCategory | 'all'>('all')
  const [successReward, setSuccessReward] = useState<RewardItem | null>(null)
  const [insufficientId, setInsufficientId] = useState<string | null>(null)

  const grouped = useMemo(() => {
    const map = new Map<RewardCategory, RewardItem[]>()
    for (const r of rewards) {
      const list = map.get(r.category) ?? []
      list.push(r)
      map.set(r.category, list)
    }
    return map
  }, [rewards])

  const visibleCategories = activeCategory === 'all' ? CATEGORY_ORDER : [activeCategory]

  function handleRedeem(reward: RewardItem) {
    const outcome = redeem(reward.id)
    if (outcome.status === 'success') {
      setSuccessReward(reward)
      setInsufficientId(null)
      setTimeout(() => setSuccessReward(null), 2600)
    } else {
      setInsufficientId(reward.id)
      setTimeout(() => setInsufficientId((id) => (id === reward.id ? null : id)), 1800)
    }
  }

  return (
    <div className="space-y-5">
      <motion.div
        className="glass-card p-6 flex items-center justify-between flex-wrap gap-4"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div>
          <h2
            className="text-lg font-bold"
            style={{ color: 'var(--foreground)', fontFamily: 'Orbitron, sans-serif' }}
          >
            🎁 Reward Store
          </h2>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            Spend your earned XP on real rewards — premium courses, discounts, and exclusive extras.
          </p>
        </div>
        <div
          className="flex items-center gap-2 px-4 py-2.5 rounded-full"
          style={{ background: 'rgba(255,126,54,0.12)', border: '1px solid rgba(255,126,54,0.25)' }}
        >
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Your balance
          </span>
          <span
            className="text-sm font-black"
            style={{ color: 'var(--accent)', fontFamily: 'Orbitron, sans-serif' }}
          >
            {totalXp.toLocaleString()} XP
          </span>
        </div>
      </motion.div>

      <motion.div
        className="flex flex-wrap gap-2"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <button
          onClick={() => setActiveCategory('all')}
          className="px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors"
          style={{
            background: activeCategory === 'all' ? 'var(--primary)' : 'var(--tint-1)',
            color:
              activeCategory === 'all' ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
          }}
        >
          All Rewards
        </button>
        {CATEGORY_ORDER.filter((c) => (grouped.get(c)?.length ?? 0) > 0).map((cat) => {
          const meta = CATEGORY_META[cat]
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
              style={{
                background: activeCategory === cat ? 'var(--primary)' : 'var(--tint-1)',
                color:
                  activeCategory === cat ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
              }}
            >
              <span>{meta.icon}</span>
              {meta.label}
            </button>
          )
        })}
      </motion.div>

      {visibleCategories.map((cat) => {
        const items = grouped.get(cat) ?? []
        if (items.length === 0) return null
        const meta = CATEGORY_META[cat]
        return (
          <motion.div
            key={cat}
            className="glass-card p-6"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
              {meta.icon} {meta.label}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((reward) => (
                <div key={reward.id} className="relative">
                  <RewardCard
                    reward={reward}
                    canAfford={totalXp >= reward.xpCost}
                    onRedeem={() => handleRedeem(reward)}
                  />
                  <AnimatePresence>
                    {insufficientId === reward.id && (
                      <motion.div
                        className="absolute inset-x-0 -bottom-2 text-center"
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                      >
                        <span
                          className="text-xs font-semibold px-2.5 py-1 rounded-full"
                          style={{ background: 'var(--danger-soft)', color: 'var(--danger)' }}
                        >
                          Not enough XP yet
                        </span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>
          </motion.div>
        )
      })}

      {/* Success animation overlay */}
      <AnimatePresence>
        {successReward && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center px-4 pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="surface-popover rounded-2xl p-8 text-center pointer-events-auto"
              initial={{ opacity: 0, scale: 0.7, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ type: 'spring', stiffness: 300, damping: 22 }}
            >
              <motion.div
                className="text-5xl mb-3"
                initial={{ scale: 0 }}
                animate={{ scale: [0, 1.3, 1] }}
                transition={{ duration: 0.5 }}
              >
                {successReward.icon}
              </motion.div>
              <p className="text-base font-bold mb-1" style={{ color: 'var(--foreground)' }}>
                Reward Unlocked!
              </p>
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {successReward.name}
              </p>
              <p className="text-xs mt-2" style={{ color: 'var(--primary)' }}>
                -{successReward.xpCost.toLocaleString()} XP
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

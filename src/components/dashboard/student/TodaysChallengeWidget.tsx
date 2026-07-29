import { motion, AnimatePresence } from 'framer-motion'
import { useChallenges } from '../../../context/ChallengesContext'
import { useRewardStore } from '../../../context/RewardStoreContext'
import { useXp } from '../../../context/XpContext'
import { LEVEL_UNLOCKS } from '../../../types/gamification'

/**
 * "FEATURE 8 — Dashboard Integration" widget: Today's Challenge,
 * Upcoming Reward (next level unlock), Reward Store shortcut, and Recent
 * Reward — every value sourced live from `useChallenges()`/
 * `useRewardStore()`/`useXp()` so it updates in real time exactly like
 * the rest of the gamification system, with no separate copy of any of
 * this data.
 */
export default function TodaysChallengeWidget({
  onOpenRewardStore,
}: {
  onOpenRewardStore: () => void
}) {
  const { dailyChallenges } = useChallenges()
  const { redemptions } = useRewardStore()
  const { level, totalXp } = useXp()

  const activeChallenge = dailyChallenges.find((c) => !c.completed) ?? dailyChallenges[0]
  const nextUnlock = LEVEL_UNLOCKS.find((u) => u.level > level.level)
  const recentReward = redemptions[0]

  const pct =
    activeChallenge && activeChallenge.target > 0
      ? Math.min(100, Math.round((activeChallenge.current / activeChallenge.target) * 100))
      : 0

  return (
    <motion.div
      className="glass-card p-5 h-full flex flex-col gap-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
          🎮 Progression
        </h3>
        <button
          onClick={onOpenRewardStore}
          className="text-xs font-semibold px-3 py-1.5 rounded-full flex-shrink-0"
          style={{ background: 'rgba(45,212,191,0.1)', color: 'var(--primary)' }}
        >
          Reward Store →
        </button>
      </div>

      {activeChallenge && (
        <div>
          <p className="text-xs mb-1.5" style={{ color: 'var(--muted-foreground)' }}>
            Today's Challenge
          </p>
          <div
            className="p-3 rounded-xl"
            style={{
              background: activeChallenge.completed ? 'rgba(34,197,94,0.08)' : 'var(--tint-1)',
              border: `1px solid ${activeChallenge.completed ? 'rgba(34,197,94,0.25)' : 'var(--border-subtle)'}`,
            }}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span
                className="text-xs font-semibold flex items-center gap-1.5"
                style={{ color: 'var(--foreground)' }}
              >
                <span>{activeChallenge.completed ? '✅' : activeChallenge.icon}</span>
                {activeChallenge.label}
              </span>
              <span className="text-xs font-bold" style={{ color: 'var(--accent)' }}>
                +{activeChallenge.xpReward} XP
              </span>
            </div>
            <div
              className="h-1.5 rounded-full overflow-hidden"
              style={{ background: 'var(--tint-2)' }}
            >
              <motion.div
                className="h-full rounded-full"
                style={{
                  background: activeChallenge.completed ? 'var(--success)' : 'var(--primary)',
                }}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>
          </div>
        </div>
      )}

      {nextUnlock && (
        <div>
          <p className="text-xs mb-1.5" style={{ color: 'var(--muted-foreground)' }}>
            Upcoming Reward
          </p>
          <div
            className="flex items-center gap-3 p-3 rounded-xl"
            style={{ background: 'var(--tint-1)' }}
          >
            <span className="text-xl flex-shrink-0">{nextUnlock.icon}</span>
            <div className="min-w-0">
              <p className="text-xs font-semibold truncate" style={{ color: 'var(--foreground)' }}>
                {nextUnlock.label}
              </p>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                Unlocks at Level {nextUnlock.level}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="mt-auto">
        <p className="text-xs mb-1.5" style={{ color: 'var(--muted-foreground)' }}>
          Recent Reward
        </p>
        <AnimatePresence mode="wait">
          {recentReward ? (
            <motion.div
              key={recentReward.id}
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{ background: 'var(--tint-1)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="min-w-0 flex-1">
                <p
                  className="text-xs font-semibold truncate"
                  style={{ color: 'var(--foreground)' }}
                >
                  {recentReward.rewardName}
                </p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  -{recentReward.xpSpent.toLocaleString()} XP
                </p>
              </div>
            </motion.div>
          ) : (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              No rewards redeemed yet — you have {totalXp.toLocaleString()} XP to spend.
            </p>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

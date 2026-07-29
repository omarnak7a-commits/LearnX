import { motion } from 'framer-motion'
import { useProfile } from '../../../context/ProfileContext'
import { useXp } from '../../../context/XpContext'
import { useChallenges } from '../../../context/ChallengesContext'
import { useRewardStore } from '../../../context/RewardStoreContext'
import { useProfileStats } from '../../../hooks/useProfileStats'
import { getBadgeDefinition } from '../../../data/badges'
import { XP_SOURCES, LEVEL_UNLOCKS } from '../../../types/gamification'
import ProgressRing from '../../ui/ProgressRing'
import Badge from '../../ui/Badge'

const MONTHLY_XP_GOAL = 5000

function SectionCard({
  title,
  icon,
  children,
  delay = 0,
  className = '',
}: {
  title: string
  icon: string
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  return (
    <motion.div
      className={`glass-card p-6 h-full ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
    >
      <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
        {icon} {title}
      </h3>
      {children}
    </motion.div>
  )
}

function ChallengeRow({
  icon,
  label,
  current,
  target,
  xpReward,
  completed,
}: {
  icon: string
  label: string
  current: number
  target: number
  xpReward: number
  completed: boolean
}) {
  const pct = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0
  return (
    <div
      className="p-3.5 rounded-xl"
      style={{
        background: completed ? 'rgba(34,197,94,0.08)' : 'var(--tint-1)',
        border: `1px solid ${completed ? 'rgba(34,197,94,0.25)' : 'var(--border-subtle)'}`,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-xs font-semibold flex items-center gap-1.5"
          style={{ color: 'var(--foreground)' }}
        >
          <span>{completed ? '✅' : icon}</span>
          {label}
        </span>
        <span
          className="text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0"
          style={{
            background: completed ? 'var(--success-soft)' : 'rgba(255,126,54,0.1)',
            color: completed ? 'var(--success)' : 'var(--accent)',
          }}
        >
          +{xpReward} XP
        </span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-2)' }}>
        <motion.div
          className="h-full rounded-full"
          style={{ background: completed ? 'var(--success)' : 'var(--primary)' }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <p className="text-xs mt-1.5" style={{ color: 'var(--muted-foreground)' }}>
        {Math.round(current)} / {target}
      </p>
    </div>
  )
}

/**
 * Complete progression system per the spec's "FEATURE 3 — Gamification
 * Improvements" section — every panel reads from the real Global XP
 * ledger (`useXp`), real rotating Daily/Weekly Challenges
 * (`useChallenges`), real Reward History (`useRewardStore`), and the
 * same Profile/Rankings stats (`useProfileStats`) shown everywhere else,
 * so this page can never disagree with the numbers a student sees on
 * their Profile, the Dashboard widget, or the Leaderboard.
 */
export default function GamificationPage() {
  const { profile } = useProfile()
  const { totalXp, weeklyXp, monthlyXp, level, ledger } = useXp()
  const { dailyChallenges, weeklyChallenges, allDailyCompleted } = useChallenges()
  const { redemptions } = useRewardStore()
  const stats = useProfileStats()

  const recentLedger = [...ledger].sort((a, b) => b.timestamp - a.timestamp).slice(0, 8)
  const recentRedemptions = redemptions.slice(0, 5)
  const nextUnlock = LEVEL_UNLOCKS.find((u) => u.level > level.level)
  const monthlyGoalPct = Math.min(100, Math.round((monthlyXp / MONTHLY_XP_GOAL) * 100))

  return (
    <div className="space-y-5">
      {/* Hero: Level + XP + Progress Ring */}
      <motion.div
        className="glass-card p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <ProgressRing
            pct={level.progressPct}
            valueLabel={`L${level.level}`}
            size={110}
            color="var(--accent)"
          />
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 w-full">
            <div>
              <p
                className="text-2xl font-black"
                style={{ color: 'var(--primary)', fontFamily: 'Orbitron, sans-serif' }}
              >
                {totalXp.toLocaleString()}
              </p>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                Total XP
              </p>
            </div>
            <div>
              <p
                className="text-2xl font-black"
                style={{ color: 'var(--foreground)', fontFamily: 'Orbitron, sans-serif' }}
              >
                {weeklyXp.toLocaleString()}
              </p>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                This Week
              </p>
            </div>
            <div>
              <p
                className="text-2xl font-black"
                style={{ color: 'var(--foreground)', fontFamily: 'Orbitron, sans-serif' }}
              >
                {monthlyXp.toLocaleString()}
              </p>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                This Month
              </p>
            </div>
            <div>
              <p
                className="text-2xl font-black"
                style={{ color: 'var(--foreground)', fontFamily: 'Orbitron, sans-serif' }}
              >
                #{stats.allTimeRank}
              </p>
              <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                Leaderboard Position
              </p>
            </div>
          </div>
        </div>
        <div className="mt-5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
              Level {level.level} → {level.level + 1}
            </span>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {level.xpIntoLevel} / {level.xpForNextLevel} XP
            </span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--tint-2)' }}>
            <motion.div
              className="h-full rounded-full"
              style={{ background: 'linear-gradient(90deg, var(--accent), #ffad7a)' }}
              initial={{ width: 0 }}
              animate={{ width: `${level.progressPct}%` }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        </div>
      </motion.div>

      {/* Streaks */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <SectionCard title="Current Streak" icon="🔥" delay={0.05}>
          <p
            className="text-4xl font-black"
            style={{ color: 'var(--accent)', fontFamily: 'Orbitron, sans-serif' }}
          >
            {profile?.streakDays ?? 0}
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            consecutive days
          </p>
        </SectionCard>
        <SectionCard title="Longest Streak" icon="🏔️" delay={0.08}>
          <p
            className="text-4xl font-black"
            style={{ color: 'var(--primary)', fontFamily: 'Orbitron, sans-serif' }}
          >
            {profile?.longestStreakDays ?? 0}
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
            personal best
          </p>
        </SectionCard>
      </div>

      {/* Daily + Weekly Challenges */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <SectionCard title="Daily Challenges" icon="🎯" delay={0.1}>
          <div className="space-y-2.5">
            {dailyChallenges.map((c) => (
              <ChallengeRow
                key={c.id}
                icon={c.icon}
                label={c.label}
                current={c.current}
                target={c.target}
                xpReward={c.xpReward}
                completed={c.completed}
              />
            ))}
          </div>
          {allDailyCompleted && (
            <div
              className="mt-3 p-3 rounded-xl text-center"
              style={{
                background: 'rgba(255,126,54,0.1)',
                border: '1px solid rgba(255,126,54,0.25)',
              }}
            >
              <p className="text-xs font-bold" style={{ color: 'var(--accent)' }}>
                🏅 All daily challenges complete — bonus{' '}
                {XP_SOURCES['daily-challenge-bonus'].amount} XP awarded!
              </p>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Weekly Challenges" icon="🏆" delay={0.12}>
          <div className="space-y-2.5">
            {weeklyChallenges.map((c) => (
              <ChallengeRow
                key={c.id}
                icon={c.icon}
                label={c.label}
                current={c.current}
                target={c.target}
                xpReward={c.xpReward}
                completed={c.completed}
              />
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Monthly Goal */}
      <SectionCard title="Monthly Goal" icon="📅" delay={0.14}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
            Earn {MONTHLY_XP_GOAL.toLocaleString()} XP this month
          </span>
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {monthlyXp.toLocaleString()} / {MONTHLY_XP_GOAL.toLocaleString()}
          </span>
        </div>
        <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-2)' }}>
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg, #2DD4BF, var(--secondary))' }}
            initial={{ width: 0 }}
            animate={{ width: `${monthlyGoalPct}%` }}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
      </SectionCard>

      {/* Achievements / Badges */}
      <SectionCard title={`Badges & Achievements (${stats.badges.length})`} icon="🏅" delay={0.16}>
        {stats.badges.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            Keep studying to earn your first badge.
          </p>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {stats.badges.map((badgeId, i) => {
              const def = getBadgeDefinition(badgeId)
              return (
                <motion.div
                  key={badgeId}
                  className="flex flex-col items-center gap-2 p-3.5 rounded-xl text-center"
                  style={{
                    background: 'rgba(255,126,54,0.08)',
                    border: '1px solid rgba(255,126,54,0.2)',
                  }}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.05 * i, type: 'spring', stiffness: 260, damping: 20 }}
                  title={def.description}
                >
                  <span className="text-2xl">{def.icon}</span>
                  <span
                    className="text-xs font-medium leading-tight"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {def.label}
                  </span>
                </motion.div>
              )
            })}
          </div>
        )}
      </SectionCard>

      {/* Level Unlocks */}
      <SectionCard title="Level Unlocks" icon="🔓" delay={0.18}>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {LEVEL_UNLOCKS.map((unlock) => {
            const isUnlocked = unlock.level <= level.level
            return (
              <div
                key={unlock.level}
                className="flex flex-col items-center gap-1.5 p-3 rounded-xl text-center"
                style={{
                  background: isUnlocked ? 'rgba(45,212,191,0.08)' : 'var(--tint-1)',
                  border: `1px solid ${isUnlocked ? 'rgba(45,212,191,0.25)' : 'var(--border-subtle)'}`,
                  opacity: isUnlocked ? 1 : 0.5,
                }}
              >
                <span className="text-xl">{unlock.icon}</span>
                <span
                  className="text-xs font-bold"
                  style={{ color: isUnlocked ? 'var(--primary)' : 'var(--muted-foreground)' }}
                >
                  Level {unlock.level}
                </span>
                <span
                  className="text-xs leading-tight"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  {unlock.label}
                </span>
              </div>
            )
          })}
        </div>
        {nextUnlock && (
          <p className="text-xs mt-3" style={{ color: 'var(--muted-foreground)' }}>
            Next unlock: <strong style={{ color: 'var(--foreground)' }}>{nextUnlock.label}</strong>{' '}
            at Level {nextUnlock.level} (
            {level.xpToNextLevel > 0 ? `${level.xpToNextLevel} XP to next level` : 'almost there!'})
          </p>
        )}
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent Rewards */}
        <SectionCard title="Recent Rewards" icon="🛍️" delay={0.2}>
          {recentRedemptions.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              No rewards redeemed yet — visit the Reward Store to spend your XP.
            </p>
          ) : (
            <div className="space-y-2.5">
              {recentRedemptions.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-3 p-3 rounded-xl"
                  style={{ background: 'var(--tint-1)' }}
                >
                  <div className="min-w-0 flex-1">
                    <p
                      className="text-xs font-semibold truncate"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {r.rewardName}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      {new Date(r.timestamp).toLocaleDateString()}
                    </p>
                  </div>
                  <Badge tone="accent" size="xs" mono>
                    -{r.xpSpent.toLocaleString()} XP
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        {/* XP History / Recent Activity */}
        <SectionCard title="XP History" icon="📈" delay={0.22}>
          {recentLedger.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              No XP earned yet — complete a lesson, quiz, or study session to get started.
            </p>
          ) : (
            <div className="space-y-2.5">
              {recentLedger.map((tx) => (
                <div
                  key={tx.id}
                  className="flex items-center gap-3 p-3 rounded-xl"
                  style={{ background: 'var(--tint-1)' }}
                >
                  <span className="text-base flex-shrink-0">
                    {XP_SOURCES[tx.source]?.icon ?? '⚡'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p
                      className="text-xs font-semibold truncate"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {tx.label}
                      {tx.detail ? ` — ${tx.detail}` : ''}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      {new Date(tx.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <span
                    className="text-xs font-bold flex-shrink-0"
                    style={{ color: tx.amount >= 0 ? 'var(--success)' : 'var(--danger)' }}
                  >
                    {tx.amount >= 0 ? '+' : ''}
                    {tx.amount.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}

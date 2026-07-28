import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStudyPlan } from '../../../../hooks/useStudyPlan'
import { plannerInputs, weakTopics, upcomingExams, recommendations, studyTips } from '../../../../data/plannerMock'
import DailyTimeline from './DailyTimeline'
import WeeklyCalendar from './WeeklyCalendar'
import MonthlyCalendar from './MonthlyCalendar'
import ExamCountdown from './ExamCountdown'
import RecommendationsPanel from './RecommendationsPanel'
import CalendarSyncCard from './CalendarSyncCard'
import Tabs from '../../shared/Tabs'
import Badge from '../../../ui/Badge'
import ProgressRing from '../../../ui/ProgressRing'
import type { PlanTrigger } from '../../../../hooks/useStudyPlan'

const triggerButtons: Array<{ id: PlanTrigger; label: string }> = [
  { id: 'quiz-completed', label: 'Simulate: Quiz completed' },
  { id: 'exam-added', label: 'Simulate: New exam added' },
  { id: 'performance-declined', label: 'Simulate: Performance dip' },
]

export default function StudyPlannerPage() {
  const { tasks, toggleTask, regenerate, regenerating, todayTasks, completionPct, remainingMinutes, history } =
    useStudyPlan()
  const [view, setView] = useState<'Daily' | 'Weekly' | 'Monthly'>('Daily')
  const [selectedDay, setSelectedDay] = useState(0)

  const visibleTasks = view === 'Daily' ? tasks.filter((t) => t.day === selectedDay) : tasks

  return (
    <div className="space-y-5">
      {/* Hero */}
      <motion.div className="glass-card p-6 relative overflow-hidden" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <div
          className="absolute -top-16 -left-16 w-56 h-56 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(45,212,191,0.1) 0%, transparent 70%)' }}
        />
        <div className="relative flex items-center justify-between flex-wrap gap-4">
          <div>
            <p
              className="text-xs tracking-[0.2em] uppercase font-semibold mb-2"
              style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}
            >
              AI Study Plan Generator
            </p>
            <h2 className="text-2xl font-black leading-tight" style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}>
              A plan that <span className="text-gradient">rebuilds itself</span>
            </h2>
            <p className="text-sm mt-2 max-w-lg" style={{ color: 'var(--muted-foreground)' }}>
              Built from your exams, quiz scores, lecture progress, and available hours — and
              automatically regenerated whenever anything changes.
            </p>
          </div>
          <ProgressRing pct={completionPct} color="var(--primary)" size={92} label="today" />
        </div>
      </motion.div>

      {/* Regeneration demo controls */}
      <motion.div className="glass-card p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
              Adaptive Planning
            </h3>
            <AnimatePresence>
              {regenerating && (
                <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Badge tone="primary" size="xs" pulse>
                    Regenerating…
                  </Badge>
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {triggerButtons.map((b) => (
              <button
                key={b.id}
                onClick={() => regenerate(b.id)}
                disabled={regenerating}
                className="text-xs px-2.5 py-1.5 rounded-lg input-field disabled:opacity-40"
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs mb-3" style={{ color: 'var(--muted-foreground)' }}>
          No manual editing needed — the plan reprioritizes itself whenever a new signal comes in.
        </p>
        {history.length > 0 && (
          <div className="space-y-1.5">
            {history.map((h, i) => (
              <motion.p
                key={h.at + i}
                className="text-xs flex items-center gap-1.5"
                style={{ color: 'var(--muted-foreground)' }}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
              >
                <span style={{ color: 'var(--primary)' }}>●</span> {h.message}
              </motion.p>
            ))}
          </div>
        )}
      </motion.div>

      {/* Today's snapshot */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Today's tasks", value: `${todayTasks.filter((t) => t.done).length}/${todayTasks.length}`, color: 'var(--primary)' },
          { label: 'Remaining time', value: `${Math.round(remainingMinutes / 60)}h ${remainingMinutes % 60}m`, color: 'var(--accent)' },
          { label: 'Focus score', value: plannerInputs.focusScore, color: '#38bdf8' },
          { label: 'Learning streak', value: `${plannerInputs.currentStreak}d`, color: 'var(--warning)' },
        ].map((s, i) => (
          <motion.div key={s.label} className="glass-card p-4" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <p className="text-2xl font-black" style={{ fontFamily: 'Orbitron, sans-serif', color: s.color }}>
              {s.value}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
              {s.label}
            </p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-5 items-start">
        <div className="space-y-5">
          {/* Calendar views */}
          <motion.div className="glass-card p-6" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
              <Tabs tabs={['Daily', 'Weekly', 'Monthly']} active={view} onChange={(v) => setView(v as typeof view)} />
              {view === 'Weekly' && (
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  Click a day to preview its plan below
                </p>
              )}
            </div>

            {view === 'Daily' && (
              <>
                <div className="flex items-center gap-1.5 mb-4 overflow-x-auto scrollbar-thin pb-1">
                  {['Today', 'Tomorrow', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((label, day) => (
                    <button
                      key={label}
                      onClick={() => setSelectedDay(day)}
                      className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                      style={{
                        background: selectedDay === day ? 'var(--primary)' : 'var(--tint-2)',
                        color: selectedDay === day ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <DailyTimeline tasks={visibleTasks} onToggle={toggleTask} />
              </>
            )}

            {view === 'Weekly' && (
              <WeeklyCalendar tasks={tasks} selectedDay={selectedDay} onSelectDay={setSelectedDay} />
            )}

            {view === 'Monthly' && <MonthlyCalendar tasks={tasks} />}
          </motion.div>

          {/* Recommendations */}
          <motion.div className="glass-card p-6" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
              ✨ Smart Recommendations
            </h3>
            <RecommendationsPanel recommendations={recommendations} />
          </motion.div>

          {/* Study tips */}
          <motion.div className="glass-card p-6" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
            <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
              💡 Study Tips
            </h3>
            <div className="space-y-2.5">
              {studyTips.map((tip, i) => (
                <div key={i} className="flex items-start gap-2.5 text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
                  <span className="w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0" style={{ background: 'var(--primary)' }} />
                  {tip}
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        <div className="space-y-5">
          {/* Exam countdown */}
          <motion.div className="glass-card p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
              🧾 Exam Countdown
            </h3>
            <ExamCountdown exams={upcomingExams} />
          </motion.div>

          {/* Weak topics */}
          <motion.div className="glass-card p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--foreground)' }}>
              🧩 Weak Topics
            </h3>
            <div className="space-y-3">
              {weakTopics.map((w) => (
                <div key={w.topic}>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>
                      {w.topic}
                    </p>
                    <span className="text-xs" style={{ color: 'var(--warning)' }}>
                      {w.masteryPct}% {w.trend === 'up' ? '↑' : w.trend === 'down' ? '↓' : '—'}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--tint-3)' }}>
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: 'var(--warning)' }}
                      initial={{ width: 0 }}
                      animate={{ width: `${w.masteryPct}%` }}
                      transition={{ duration: 1 }}
                    />
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                    {w.subject}
                  </p>
                </div>
              ))}
            </div>
          </motion.div>

          <CalendarSyncCard />
        </div>
      </div>
    </div>
  )
}

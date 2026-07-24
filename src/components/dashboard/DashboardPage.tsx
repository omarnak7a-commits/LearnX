import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { GreetingWidget, FocusChart, StudyPlanCards, StreaksXP, ActivityFeed } from './DashboardWidgets'
import AIAssistant from './AIAssistant'

interface DashboardPageProps {
  onBack: () => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

export default function DashboardPage({ onBack, theme, onToggleTheme }: DashboardPageProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [activeItem, setActiveItem] = useState('dashboard')

  return (
    <div className="flex" style={{ minHeight: '100vh', background: 'var(--background)' }}>
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(v => !v)}
        activeItem={activeItem}
        onNavigate={setActiveItem}
        onBack={onBack}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar theme={theme} onToggleTheme={onToggleTheme} />

        <main className="flex-1 overflow-y-auto scrollbar-thin" style={{ background: 'var(--section-dark)' }}>
          <AnimatePresence mode="wait">
            {activeItem === 'dashboard' ? (
              <motion.div
                key="dash"
                className="p-6"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {/* Page title */}
                <div className="mb-6">
                  <h1
                    className="text-xl font-bold"
                    style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)', letterSpacing: '-0.01em' }}
                  >
                    Dashboard
                  </h1>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)', fontFamily: 'JetBrains Mono, monospace' }}>
                    Monday, 21 July 2026 · Exam in 12 days
                  </p>
                </div>

                {/* Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                  {/* Row 1 */}
                  <div className="lg:col-span-3">
                    <GreetingWidget />
                  </div>
                  <div className="lg:col-span-9">
                    <FocusChart />
                  </div>

                  {/* Row 2 */}
                  <div className="lg:col-span-8">
                    <StudyPlanCards />
                  </div>
                  <div className="lg:col-span-4">
                    <StreaksXP />
                  </div>

                  {/* Row 3 */}
                  <div className="lg:col-span-12">
                    <ActivityFeed />
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key={activeItem}
                className="flex flex-col items-center justify-center min-h-[60vh] p-6"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.35 }}
              >
                <div className="glass-card p-12 text-center max-w-sm">
                  <span className="text-5xl mb-5 block">
                    {activeItem === 'files' ? '📂' : activeItem === 'tutor' ? '🤖' : activeItem === 'planner' ? '📅' : activeItem === 'quizzes' ? '❓' : activeItem === 'gamification' ? '🏆' : activeItem === 'analytics' ? '📊' : '⚙️'}
                  </span>
                  <h2
                    className="text-lg font-bold mb-2"
                    style={{ fontFamily: 'Orbitron, sans-serif', color: 'var(--foreground)' }}
                  >
                    {activeItem.charAt(0).toUpperCase() + activeItem.slice(1)}
                  </h2>
                  <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                    Coming in the next release. The dashboard above gives you a preview of what's possible.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>

      <AIAssistant />
    </div>
  )
}

import { motion } from 'framer-motion'
import { GreetingWidget, FocusChart, StudyPlanCards, StreaksXP } from '../DashboardWidgets'
import QuickActions from './QuickActions'
import MyCourses from './MyCourses'
import UpcomingWork from './UpcomingWork'
import CalendarNotifications from './CalendarNotifications'
import AcademicIdentityWidget from './AcademicIdentityWidget'

/** Simplified Student Dashboard overview — focused, study-first sections only. */
export default function StudentDashboardHome() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      {/* Welcome + today's plan + academic identity (University/Faculty/
          Department/Rank/XP/Level — the spec's "DASHBOARD INTEGRATION"
          widget) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-3">
          <GreetingWidget />
        </div>
        <div className="lg:col-span-6">
          <FocusChart />
        </div>
        <div className="lg:col-span-3">
          <AcademicIdentityWidget />
        </div>
      </div>

      {/* Quick actions */}
      <QuickActions />

      {/* Study plan + streaks/xp */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8">
          <StudyPlanCards />
        </div>
        <div className="lg:col-span-4">
          <StreaksXP />
        </div>
      </div>

      {/* My courses */}
      <MyCourses />

      {/* Upcoming assignments + exams */}
      <UpcomingWork />

      {/* Calendar + notifications */}
      <CalendarNotifications />
    </motion.div>
  )
}

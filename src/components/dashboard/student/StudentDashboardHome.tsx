import { motion } from 'framer-motion'
import {
  GreetingWidget,
  FocusChart,
  StudyPlanCards,
  StreaksXP,
  ActivityFeed,
} from '../DashboardWidgets'
import QuickActions from './QuickActions'
import MyCourses from './MyCourses'
import StudentAnalytics from './StudentAnalytics'
import AIRecommendations from './AIRecommendations'
import UpcomingWork from './UpcomingWork'
import RecentActivityPanels from './RecentActivityPanels'
import CertificatesAchievements from './CertificatesAchievements'
import GoalsPanel from './GoalsPanel'
import CalendarNotifications from './CalendarNotifications'

/** Full Student Dashboard overview — composes every required section. */
export default function StudentDashboardHome() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      {/* Welcome + today's plan */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-3">
          <GreetingWidget />
        </div>
        <div className="lg:col-span-9">
          <FocusChart />
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

      {/* Analytics */}
      <StudentAnalytics />

      {/* AI recommendations */}
      <AIRecommendations />

      {/* Recent uploads + AI conversations */}
      <RecentActivityPanels />

      {/* Goals */}
      <GoalsPanel />

      {/* Certificates + achievements */}
      <CertificatesAchievements />

      {/* Recent activity feed */}
      <ActivityFeed />
    </motion.div>
  )
}

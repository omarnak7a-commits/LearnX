import { motion } from 'framer-motion'
import DoctorOverview from './DoctorOverview'
import StudentAnalyticsPanel from './StudentAnalyticsPanel'
import CourseManagement from './CourseManagement'
import AITeachingAssistant from './AITeachingAssistant'

/** Full Doctor Dashboard overview — mirrors the Student dashboard's design language. */
export default function DoctorDashboardHome() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <DoctorOverview />
      <CourseManagement />
      <StudentAnalyticsPanel />
      <AITeachingAssistant />
    </motion.div>
  )
}

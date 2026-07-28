import { motion } from 'framer-motion'
import DoctorOverview from './DoctorOverview'
import StudentAnalyticsPanel from './StudentAnalyticsPanel'
import CourseOverviewWidget from './CourseOverviewWidget'
import AITeachingAssistant from './AITeachingAssistant'

interface DoctorDashboardHomeProps {
  onNavigate?: (item: string) => void
  onOpenCourse?: (courseId: string) => void
}

/** Full Doctor Dashboard overview — mirrors the Student dashboard's design language. */
export default function DoctorDashboardHome({
  onNavigate,
  onOpenCourse,
}: DoctorDashboardHomeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <DoctorOverview />
      <CourseOverviewWidget
        onManageCourses={() => onNavigate?.('courses')}
        onOpenCourse={onOpenCourse}
      />
      <StudentAnalyticsPanel />
      <AITeachingAssistant />
    </motion.div>
  )
}

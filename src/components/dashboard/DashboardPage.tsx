import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar, { type Role } from './Sidebar'
import TopBar from './TopBar'
import AIAssistant from './AIAssistant'
import { CourseCatalogProvider } from '../../context/CourseCatalogContext'

import StudentDashboardHome from './student/StudentDashboardHome'
import AITutorPage from './student/AITutorPage'
import QuizzesPage from './student/QuizzesPage'
import MyFilesPage from './student/MyFilesPage'
import CertificatesAchievements from './student/CertificatesAchievements'
import VideoIntelligencePage from './student/video/VideoIntelligencePage'
import StudyPlannerPage from './student/planner/StudyPlannerPage'
import StudentCoursesPage from './student/StudentCoursesPage'

import DoctorDashboardHome from './doctor/DoctorDashboardHome'
import DoctorCoursesPage from './doctor/DoctorCoursesPage'
import CourseBuilderPage from './doctor/CourseBuilderPage'
import RevenuePage from './doctor/RevenuePage'
import MaterialsPage from './doctor/MaterialsPage'
import StudentsPage from './doctor/StudentsPage'
import WorkItemsPage from './doctor/WorkItemsPage'
import StudentAnalyticsPanel from './doctor/StudentAnalyticsPanel'
import AITeachingAssistant from './doctor/AITeachingAssistant'

import CalendarPage from './shared/CalendarPage'
import MessagesPage from './shared/MessagesPage'
import AnnouncementsPage from './shared/AnnouncementsPage'
import SettingsPage from './shared/SettingsPage'
import EmptyState from './shared/EmptyState'

interface DashboardPageProps {
  onBack: () => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

const studentTitles: Record<string, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'Dashboard',
    subtitle: 'Monday, 27 July 2026 · Exam in 12 days',
  },
  courses: {
    title: 'My Courses',
    subtitle: 'Every course your instructors have published — pick up where you left off',
  },
  files: {
    title: 'My Files',
    subtitle: 'Every document, lecture, and note in one place',
  },
  video: {
    title: 'AI Video Intelligence',
    subtitle: 'Watch Less. Learn More.',
  },
  tutor: { title: 'AI Workspace', subtitle: 'Your adaptive study companion' },
  planner: {
    title: 'Study Planner',
    subtitle: 'A study plan that rebuilds itself around you',
  },
  calendar: { title: 'Calendar', subtitle: 'Your schedule at a glance' },
  quizzes: {
    title: 'Quizzes',
    subtitle: 'AI-generated practice from your materials',
  },
  gamification: {
    title: 'Achievements',
    subtitle: 'Certificates, achievements, and progress',
  },
  analytics: {
    title: 'Analytics',
    subtitle: 'Your learning trends at a glance',
  },
  settings: {
    title: 'Settings',
    subtitle: 'Manage your account and preferences',
  },
}

const doctorTitles: Record<string, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'Dashboard',
    subtitle: 'Monday, 27 July 2026 · Exam in 12 days',
  },
  courses: {
    title: 'Courses',
    subtitle: 'Create, publish, and manage every course you teach',
  },
  'course-builder': {
    title: 'Course Builder',
    subtitle: 'Structure modules, lessons, and resources with drag-and-drop',
  },
  materials: {
    title: 'Materials',
    subtitle: 'Upload and organize lecture content',
  },
  students: {
    title: 'Students',
    subtitle: 'Roster, performance, and engagement',
  },
  assignments: {
    title: 'Assignments',
    subtitle: 'Create and track student assignments',
  },
  exams: {
    title: 'Exams',
    subtitle: 'Build and schedule exams with AI assistance',
  },
  analytics: {
    title: 'Analytics',
    subtitle: 'Student performance across every course',
  },
  revenue: {
    title: 'Revenue',
    subtitle: 'Earnings from your premium courses',
  },
  messages: { title: 'Messages', subtitle: 'Conversations with your students' },
  calendar: { title: 'Calendar', subtitle: 'Your schedule at a glance' },
  announcements: {
    title: 'Announcements',
    subtitle: 'Broadcast updates to your classes',
  },
  ai: {
    title: 'AI Teaching Assistant',
    subtitle: 'Generate, summarize, and analyze — instantly',
  },
  settings: {
    title: 'Settings',
    subtitle: 'Manage your account and preferences',
  },
}

export default function DashboardPage({ onBack, theme, onToggleTheme }: DashboardPageProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [role, setRole] = useState<Role>('student')
  const [activeItem, setActiveItem] = useState('dashboard')
  const [pendingCourseId, setPendingCourseId] = useState<string | null>(null)

  function handleRoleChange(next: Role) {
    setRole(next)
    setActiveItem('dashboard')
  }

  function navigateToCourse(courseId: string) {
    setPendingCourseId(courseId)
    setActiveItem('courses')
  }

  function handleSidebarNavigate(item: string) {
    setPendingCourseId(null)
    setActiveItem(item)
  }

  const meta = (role === 'student' ? studentTitles[activeItem] : doctorTitles[activeItem]) ?? {
    title: activeItem,
    subtitle: '',
  }

  function renderContent() {
    if (role === 'student') {
      switch (activeItem) {
        case 'dashboard':
          return <StudentDashboardHome />
        case 'courses':
          return <StudentCoursesPage />
        case 'files':
          return <MyFilesPage />
        case 'video':
          return <VideoIntelligencePage />
        case 'tutor':
          return <AITutorPage />
        case 'planner':
          return <StudyPlannerPage />
        case 'calendar':
          return <CalendarPage role={role} />
        case 'quizzes':
          return <QuizzesPage />
        case 'gamification':
          return <CertificatesAchievements />
        case 'analytics':
          return <StudentDashboardHome />
        case 'settings':
          return <SettingsPage role={role} theme={theme} onToggleTheme={onToggleTheme} />
        default:
          return (
            <EmptyState icon="🚧" title="Coming soon" body="This section is still being built." />
          )
      }
    }
    switch (activeItem) {
      case 'dashboard':
        return <DoctorDashboardHome onNavigate={setActiveItem} onOpenCourse={navigateToCourse} />
      case 'courses':
        return <DoctorCoursesPage initialCourseId={pendingCourseId} />
      case 'course-builder':
        return <CourseBuilderPage />
      case 'materials':
        return <MaterialsPage />
      case 'students':
        return <StudentsPage />
      case 'assignments':
        return <WorkItemsPage kind="assignments" />
      case 'exams':
        return <WorkItemsPage kind="exams" />
      case 'analytics':
        return <StudentAnalyticsPanel />
      case 'revenue':
        return <RevenuePage />
      case 'messages':
        return <MessagesPage />
      case 'calendar':
        return <CalendarPage role={role} />
      case 'announcements':
        return <AnnouncementsPage />
      case 'ai':
        return <AITeachingAssistant />
      case 'settings':
        return <SettingsPage role={role} theme={theme} onToggleTheme={onToggleTheme} />
      default:
        return (
          <EmptyState icon="🚧" title="Coming soon" body="This section is still being built." />
        )
    }
  }

  return (
    <CourseCatalogProvider>
      <div className="flex" style={{ minHeight: '100vh', background: 'var(--background)' }}>
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((v) => !v)}
          activeItem={activeItem}
          onNavigate={handleSidebarNavigate}
          onBack={onBack}
          role={role}
          onRoleChange={handleRoleChange}
          mobileOpen={mobileNavOpen}
          onCloseMobile={() => setMobileNavOpen(false)}
        />

        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <TopBar
            theme={theme}
            onToggleTheme={onToggleTheme}
            role={role}
            onOpenMobileNav={() => setMobileNavOpen(true)}
          />

          <main
            className="flex-1 overflow-y-auto scrollbar-thin"
            style={{ background: 'var(--section-dark)' }}
          >
            <AnimatePresence mode="wait">
              <motion.div
                key={`${role}-${activeItem}`}
                className="p-4 sm:p-6"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              >
                {/* Page title */}
                <div className="mb-6">
                  <h1
                    className="text-xl font-bold"
                    style={{
                      fontFamily: 'Orbitron, sans-serif',
                      color: 'var(--foreground)',
                      letterSpacing: '-0.01em',
                    }}
                  >
                    {meta.title}
                  </h1>
                  <p
                    className="text-xs mt-0.5"
                    style={{
                      color: 'var(--muted-foreground)',
                      fontFamily: 'JetBrains Mono, monospace',
                    }}
                  >
                    {meta.subtitle}
                  </p>
                </div>

                {renderContent()}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>

        <AIAssistant role={role} />
      </div>
    </CourseCatalogProvider>
  )
}

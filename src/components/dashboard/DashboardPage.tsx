import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar, { type Role } from './Sidebar'
import TopBar from './TopBar'
import AIAssistant from './AIAssistant'
import ErrorBoundary from './shared/ErrorBoundary'
import { CourseCatalogProvider } from '../../context/CourseCatalogContext'
import { FileVaultProvider } from '../../context/FileVaultContext'
import { CalendarProvider } from '../../context/CalendarContext'
import { NotificationsProvider } from '../../context/NotificationsContext'
import { XpProvider, useXp } from '../../context/XpContext'
import { ChallengesProvider } from '../../context/ChallengesContext'
import { RewardStoreProvider } from '../../context/RewardStoreContext'
import { useProfile } from '../../context/ProfileContext'
import { useAuth } from '../../context/AuthContext'
import { todayIso } from '../../lib/profile/xp'

import StudentDashboardHome from './student/StudentDashboardHome'
import AITutorPage from './student/AITutorPage'
import MyFilesPage from './student/MyFilesPage'
import GamificationPage from './student/GamificationPage'
import RewardStorePage from './student/RewardStorePage'
import VideoIntelligencePage from './student/video/VideoIntelligencePage'
import StudentCoursesPage from './student/StudentCoursesPage'
import ProfilePage from './student/ProfilePage'
import RankingsPage from './student/RankingsPage'

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
  onLogout: () => void
}

function DailyStreakXpAwarder() {
  const { profile } = useProfile()
  const { award } = useXp()

  useEffect(() => {
    if (!profile?.lastStudyDate) return
    if (profile.lastStudyDate !== todayIso()) return
    award('daily-streak', { dedupeKey: `streak-${profile.lastStudyDate}` })
  }, [profile?.lastStudyDate, award])

  return null
}

const studentTitles: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: 'Dashboard', subtitle: 'Welcome to your personalized student workspace' },
  courses: { title: 'My Courses', subtitle: 'Every course your instructors have published — pick up where you left off' },
  files: { title: 'My Files', subtitle: 'Your AI-powered study hub — upload, learn, and plan in one place' },
  video: { title: 'AI Video Intelligence', subtitle: 'Watch Less. Learn More.' },
  tutor: { title: 'AI Workspace', subtitle: 'Your adaptive study companion' },
  rankings: { title: 'Rankings', subtitle: 'See how you stack up against your university, faculty, and friends' },
  profile: { title: 'My Profile', subtitle: 'Your academic identity, stats, and achievements' },
  calendar: { title: 'Calendar', subtitle: 'Your schedule at a glance' },
  gamification: { title: 'Achievements', subtitle: 'Certificates, achievements, and progress' },
  rewards: { title: 'Reward Store', subtitle: 'Spend your earned XP on courses, discounts, and exclusive extras' },
  analytics: { title: 'Analytics', subtitle: 'Your learning trends at a glance' },
  settings: { title: 'Settings', subtitle: 'Manage your account and preferences' },
}

const doctorTitles: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: 'Doctor Dashboard', subtitle: 'Overview of courses, active student rosters, and teaching metrics' },
  courses: { title: 'Courses', subtitle: 'Create, publish, and manage every course you teach' },
  'course-builder': { title: 'Course Builder', subtitle: 'Structure modules, lessons, and resources with drag-and-drop' },
  materials: { title: 'Materials', subtitle: 'Upload and organize lecture content' },
  students: { title: 'Students', subtitle: 'Roster, performance, and engagement across all classes' },
  assignments: { title: 'Assignments', subtitle: 'Create and track student assignments' },
  exams: { title: 'Exams', subtitle: 'Build and schedule exams with AI assistance' },
  analytics: { title: 'Analytics', subtitle: 'Student performance and lecture completion insights' },
  revenue: { title: 'Revenue', subtitle: 'Course earnings and enrollment analytics' },
  messages: { title: 'Messages', subtitle: 'Conversations with your students' },
  calendar: { title: 'Calendar', subtitle: 'Your schedule and office hours' },
  announcements: { title: 'Announcements', subtitle: 'Broadcast updates to your classes' },
  ai: { title: 'AI Teaching Assistant', subtitle: 'Generate syllabus, quizzes, and summaries — instantly' },
  settings: { title: 'Settings', subtitle: 'Manage your account and preferences' },
}

export default function DashboardPage({
  onBack,
  theme,
  onToggleTheme,
  onLogout,
}: DashboardPageProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const { user } = useAuth()
  
  const pathRole =
    typeof window !== 'undefined' && window.location.pathname.startsWith('/doctor')
      ? 'doctor'
      : typeof window !== 'undefined' && window.location.pathname.startsWith('/student')
        ? 'student'
        : null

  const role: Role = (user?.role as Role) || pathRole || 'student'
  const [activeItem, setActiveItem] = useState('dashboard')
  const [pendingCourseId, setPendingCourseId] = useState<string | null>(null)

  function navigateToCourse(courseId: string) {
    setPendingCourseId(courseId)
    setActiveItem('courses')
  }

  function handleSidebarNavigate(item: string) {
    setPendingCourseId(null)
    setActiveItem(item)
  }

  const meta = (role === 'doctor' ? doctorTitles[activeItem] : studentTitles[activeItem]) ?? {
    title: activeItem,
    subtitle: '',
  }

  function renderContent() {
    if (role === 'doctor') {
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
            <EmptyState icon="👨‍🏫" title="Doctor Workspace" body="This section is active for your account." />
          )
      }
    }

    // Student View
    switch (activeItem) {
      case 'dashboard':
        return <StudentDashboardHome onNavigate={handleSidebarNavigate} />
      case 'courses':
        return <StudentCoursesPage />
      case 'files':
        return <MyFilesPage />
      case 'video':
        return <VideoIntelligencePage />
      case 'tutor':
        return <AITutorPage />
      case 'rankings':
        return <RankingsPage />
      case 'profile':
        return <ProfilePage />
      case 'calendar':
        return <CalendarPage role={role} />
      case 'gamification':
        return <GamificationPage />
      case 'rewards':
        return <RewardStorePage />
      case 'analytics':
        return <StudentDashboardHome onNavigate={handleSidebarNavigate} />
      case 'settings':
        return <SettingsPage role={role} theme={theme} onToggleTheme={onToggleTheme} />
      default:
        return (
          <EmptyState icon="🎓" title="Student Workspace" body="This section is active for your account." />
        )
    }
  }

  return (
    <CourseCatalogProvider>
      <FileVaultProvider>
        <CalendarProvider>
          <NotificationsProvider>
            <XpProvider>
              <ChallengesProvider>
                <RewardStoreProvider>
                  <DailyStreakXpAwarder />
                  <div
                    className="flex"
                    style={{ minHeight: '100vh', background: 'var(--background)' }}
                  >
                    <Sidebar
                      collapsed={collapsed}
                      onToggle={() => setCollapsed((v) => !v)}
                      activeItem={activeItem}
                      onNavigate={handleSidebarNavigate}
                      onBack={onBack}
                      role={role}
                      mobileOpen={mobileNavOpen}
                      onCloseMobile={() => setMobileNavOpen(false)}
                    />

                    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                      <TopBar
                        theme={theme}
                        onToggleTheme={onToggleTheme}
                        role={role}
                        onOpenMobileNav={() => setMobileNavOpen(true)}
                        onNavigate={handleSidebarNavigate}
                        onLogout={onLogout}
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

                            <ErrorBoundary key={`${role}-${activeItem}`} boundaryName={meta.title}>
                              {renderContent()}
                            </ErrorBoundary>
                          </motion.div>
                        </AnimatePresence>
                      </main>
                    </div>

                    <AIAssistant role={role} />
                  </div>
                </RewardStoreProvider>
              </ChallengesProvider>
            </XpProvider>
          </NotificationsProvider>
        </CalendarProvider>
      </FileVaultProvider>
    </CourseCatalogProvider>
  )
}

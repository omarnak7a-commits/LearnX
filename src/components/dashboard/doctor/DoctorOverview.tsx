import { useMemo } from 'react'
import StatCard from '../shared/StatCard'
import { useCourseCatalog } from '../../../context/CourseCatalogContext'

export default function DoctorOverview() {
  const { courses, loading } = useCourseCatalog()

  const stats = useMemo(() => {
    const ownCourses = courses
    const totalStudentsCount = ownCourses.reduce((sum, c) => sum + c.studentsCount, 0)
    const publishedCount = ownCourses.filter((c) => c.status === 'published').length
    const draftCount = ownCourses.filter(
      (c) => c.status === 'draft' || c.status === 'pending-review'
    ).length
    return {
      totalStudentsCount,
      publishedCount,
      draftCount,
      courseCount: ownCourses.length,
    }
  }, [courses])

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <StatCard
        icon="👥"
        label="Total Enrollments"
        value={loading ? 0 : stats.totalStudentsCount}
        sublabel="across all your courses"
        color="#2DD4BF"
        delay={0}
      />
      <StatCard
        icon="📚"
        label="Courses"
        value={loading ? 0 : stats.courseCount}
        sublabel={`${stats.publishedCount} published · ${stats.draftCount} in progress`}
        color="#a855f7"
        delay={0.1}
      />
    </div>
  )
}

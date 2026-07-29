import StatCard from '../shared/StatCard'

/** Top-line Doctor overview: total students, active students, courses, materials, avg performance, completion rate. */
export default function DoctorOverview() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      <StatCard
        icon="👥"
        label="Total Students"
        value={412}
        delta="+18"
        color="#2DD4BF"
        delay={0}
      />
      <StatCard
        icon="🟢"
        label="Active Students"
        value={356}
        delta="86%"
        color="#22c55e"
        delay={0.05}
      />
      <StatCard
        icon="📚"
        label="Courses"
        value={4}
        sublabel="2 in progress"
        color="#a855f7"
        delay={0.1}
      />
      <StatCard
        icon="🗂️"
        label="Materials"
        value={128}
        delta="+9 wk"
        color="#38bdf8"
        delay={0.15}
      />
      <StatCard
        icon="🎯"
        label="Avg. Performance"
        value={81}
        suffix="%"
        delta="+3%"
        color="#f59e0b"
        delay={0.2}
      />
      <StatCard
        icon="✅"
        label="Completion Rate"
        value={74}
        suffix="%"
        delta="+6%"
        color="#FF7E36"
        delay={0.25}
      />
    </div>
  )
}

import Navbar from './Navbar'
import HeroSection from './HeroSection'
import StatementSection from './StatementSection'
import FeaturesGrid from './FeaturesGrid'
import DashboardPreviewSection from './DashboardPreviewSection'
import NumbersSection from './NumbersSection'
import AudienceShowcase from './AudienceShowcase'
import Footer from './Footer'

interface LandingPageProps {
  onEnter: () => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

export default function LandingPage({ onEnter, theme, onToggleTheme }: LandingPageProps) {
  return (
    <div style={{ background: 'var(--background)', color: 'var(--foreground)', minHeight: '100vh' }}>
      <Navbar onEnter={onEnter} theme={theme} onToggleTheme={onToggleTheme} />
      <HeroSection onEnter={onEnter} />
      <StatementSection />
      <FeaturesGrid />
      <DashboardPreviewSection onEnter={onEnter} />
      <NumbersSection />
      <AudienceShowcase />
      <Footer />
    </div>
  )
}

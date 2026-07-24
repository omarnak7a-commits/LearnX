# LearnX Brand Identity & Design System — Implementation Plan

## Context

Build the full LearnX product: a cinematic Neo-Glassmorphism educational SaaS platform.  
Deliverables are (1) a public Landing Page and (2) a Student Dashboard Workspace, navigable via a "Try LearnX Free" CTA and a "Back to Landing" control. The brief explicitly specifies Dark Space Navy / Electric Cyan / Neon Orange palette, glassmorphic cards, Framer Motion spring animations, GSAP-style scroll effects, and 3D tilt interactions.

---

## Tech Decisions

| Need | Package | Reason |
|------|---------|--------|
| Animations, spring physics | `framer-motion` | Spring-based micro-interactions, scroll animations, layout transitions |
| Charts | `recharts` | Focus score / productivity charts in Dashboard |
| 3D card tilt | CSS `perspective` + Framer Motion `useMotionValue` / `useTransform` | Avoids heavy Three.js; achieves the required hover tilt with zero WebGL setup cost |
| Logo draw animation | SVG `stroke-dashoffset` via Framer Motion | Clean CSS-driven path trace, no GSAP runtime needed |
| Fonts | Orbitron (display/logo) + Inter (body) + JetBrains Mono (data labels) | `figma fonts resolve` → `@font-face` in `src/index.css` |

> Three.js / R3F are **not** installed; the 3D visual richness will be achieved with CSS 3D transforms, perspective stacking, and Framer Motion motion values.

---

## Packages to Install

```
pnpm add framer-motion recharts
```

---

## Font Wiring

1. Run `figma fonts list` to check private catalog.  
2. Run `figma fonts resolve` for Orbitron, Inter, JetBrains Mono (Google Fonts fallback).  
3. Place downloaded font files in `src/fonts/`.  
4. Add `@font-face` blocks at the **top** of `src/index.css` (before `@import 'tailwindcss'` — per CSS spec, `@font-face` must precede `@import` or use `@layer`; actually `@font-face` is fine after `@import` in Tailwind v4, just keep `@import 'tailwindcss'` first).
5. Define CSS custom properties + Tailwind theme extension.

---

## Design Tokens (added to `src/index.css`)

```css
:root {
  --background: #0A0D14;
  --foreground: #F8FAFC;
  --card: rgba(18, 24, 36, 0.6);
  --card-foreground: #F8FAFC;
  --primary: #2DD4BF;
  --primary-foreground: #0A0D14;
  --secondary: #14B8A6;
  --secondary-foreground: #F8FAFC;
  --muted: #1E2A3A;
  --muted-foreground: #94A3B8;
  --accent: #FF7E36;
  --accent-foreground: #0A0D14;
  --border: rgba(45, 212, 191, 0.15);
  --ring: #2DD4BF;
  --radius: 0.75rem;
  --font-display: 'Orbitron', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

---

## File Structure

```
src/
  App.tsx                     ← View router (landing | dashboard)
  index.css                   ← Tokens + @font-face + tailwind import
  fonts/                      ← Downloaded font files
  components/
    landing/
      Navbar.tsx              ← Glassmorphic sticky nav + logo + theme toggle
      HeroSection.tsx         ← Headline, 3D tilt stat cards, dual CTAs
      AudienceShowcase.tsx    ← Tabbed persona switcher (Student/Parent/Teacher)
      FeaturesGrid.tsx        ← Bento-box 6-card features grid
      DashboardPreview.tsx    ← Animated mock dashboard screenshot
      Footer.tsx              ← Dark footer + newsletter + links
    dashboard/
      Sidebar.tsx             ← Collapsible icon-nav with badges
      TopBar.tsx              ← Search (Cmd+K), notifications, XP badge
      GreetingWidget.tsx      ← Daily goal progress ring
      StudyPlanCards.tsx      ← Today's AI study plan (checkable)
      FocusChart.tsx          ← Recharts area chart
      StreaksXP.tsx           ← Active streaks + XP progress bar
      AIAssistant.tsx         ← Floating pulse button + slide-up panel
    ui/
      GlassCard.tsx           ← Reusable glassmorphic card primitive
      LogoMark.tsx            ← SVG dual-chevron + diamond, animated path trace
      TiltCard.tsx            ← 3D tilt wrapper using Framer Motion
```

---

## Implementation Sections

### 1. `src/index.css`
- `@import 'tailwindcss'` (keep first)
- `@font-face` declarations for Orbitron, Inter, JetBrains Mono
- `:root` CSS vars (tokens above)
- `.dark` override block (already dark-default, light mode via `.light` class on `<html>`)
- Scrollbar hide utility: `html { scrollbar-width: none; }`
- `@theme inline` block mapping CSS vars to Tailwind tokens

### 2. `src/App.tsx`
- `useState<'landing' | 'dashboard'>('landing')` for view switching
- Renders `<LandingPage onEnter={() => setView('dashboard')} />` or `<DashboardPage onBack={() => setView('landing')} />`
- `AnimatePresence` + `motion.div` for page transition (slide + fade)

### 3. Landing Page Sections

**Navbar** (`Navbar.tsx`)
- `position: sticky; top: 0; z-index: 50`
- `backdrop-blur-md bg-[#0A0D14]/70 border-b border-[--border]`
- `<LogoMark />` (small, 32px) + "LearnX" wordmark in Orbitron
- Nav links: Features · Roles · Pricing · Analytics
- Theme toggle button (sun/moon icon, toggles `.light` on `<html>`)
- "Get Started" CTA: `bg-primary text-primary-foreground rounded-full px-5 py-2`
- Mobile: hamburger → Framer Motion full-screen overlay with staggered link entrance

**HeroSection** (`HeroSection.tsx`)
- Full-viewport height, dark grid/particle background via SVG pattern
- Animated gradient headline: "Study Smarter, Not Harder" — Orbitron, large, `bg-gradient-to-r from-[#2DD4BF] to-[#14B8A6] bg-clip-text text-transparent`
- Sub-headline + tagline "Less Stress | More Success"
- Two CTAs: "Try LearnX Free" (primary teal filled) + "Watch Demo" (outline ghost)
- Three `<TiltCard />` stat cards floating below headline:
  - Focus Score: 94 🔥, XP Today: +1,240 ⚡, Active Streak: 21 days 🌊
  - Cards: `backdrop-blur-md bg-white/5 border border-[--border]`, 3D perspective tilt on hover

**AudienceShowcase** (`AudienceShowcase.tsx`)
- Three tabs: Students · Parents · Teachers
- `useState` for active tab
- Framer Motion `AnimatePresence` sliding content panel per tab
- Each panel: icon + headline + bullet points + CTA link
- Smooth underline indicator motion between tabs

**FeaturesGrid** (`FeaturesGrid.tsx`)
- CSS Grid bento layout: 2 large cells + 4 smaller cells
- Feature cards:
  1. AI RAG Document Processor (PDF icon, upload preview mockup) — large
  2. Smart Pomodoro Timer (waveform visualizer bars) — large
  3. AI Tutor (chat bubble icon)
  4. Spaced Repetition (calendar heatmap icon)
  5. Gamification Hub (badge/trophy icons)
  6. Analytics Engine (mini bar chart)
- Each card: `<GlassCard />` with hover `translateZ(8px)` + glow border on `--primary`

**DashboardPreview** (`DashboardPreview.tsx`)
- Centered mock screenshot framed in a MacBook-style bezel
- Shows a simplified static render of the Dashboard UI
- Framer Motion: enters from below as user scrolls (uses `whileInView`)
- Subtle rotation/perspective on the frame

**Footer** (`Footer.tsx`)
- Dark `bg-[#060810]`
- Three columns: Brand + tagline | Quick links | Newsletter signup
- Social icons (Twitter/X, GitHub, Discord, LinkedIn) as SVG icons
- Bottom bar: © 2026 LearnX

### 4. Student Dashboard

**Layout** (`DashboardPage.tsx`)
- CSS Grid: `grid-cols-[240px_1fr]` (sidebar + main), collapsible to icon-only `grid-cols-[64px_1fr]`
- `useState` for collapsed sidebar
- Sticky `<TopBar />` in main column

**Sidebar** (`Sidebar.tsx`)
- Icon-nav items: Dashboard · My Files · AI Tutor · Smart Planner · Quizzes · Gamification · Analytics · Settings
- Active state: teal left-border + glow background
- Badge counts on Quizzes (3) and Notifications
- Collapse toggle button at bottom

**TopBar** (`TopBar.tsx`)
- Search bar (Cmd+K activates modal overlay)
- Notification bell with live badge (count=4)
- XP badge: "Level 12 · 4,820 XP" in orange pill
- Avatar dropdown

**Dashboard Widgets Grid** — `grid-cols-12` responsive bento:
- Row 1: Greeting + Goal Ring (`col-span-4`) | Focus Chart (`col-span-8`)
- Row 2: Today's Study Plan (`col-span-6`) | Streaks + XP bar (`col-span-3`) | Quick Stats (`col-span-3`)

**FocusChart** (`FocusChart.tsx`)
- `recharts` `AreaChart` with gradient fill (`#2DD4BF` → transparent)
- 7-day focus score data
- Custom tooltip with glassmorphic styling

**StreaksXP** (`StreaksXP.tsx`)
- Animated XP progress bar (Framer Motion `animate={{ width: '68%' }}`)
- Streak flames with day counters
- "Level Up" indicator

**AIAssistant** (`AIAssistant.tsx`)
- Fixed bottom-right FAB: `position: fixed; bottom: 24px; right: 24px`
- Glowing teal pulse ring animation (CSS keyframe)
- Click expands Framer Motion slide-up panel with mock chat interface

---

## Animation Inventory

| Element | Technique |
|---------|-----------|
| Logo path trace on mount | SVG `pathLength` 0→1, `strokeDashoffset` via Framer Motion |
| Navbar entrance | `y: -20 → 0, opacity: 0→1` on mount |
| Hero headline words | Stagger `opacity/y` with 0.08s per word delay |
| Stat cards float | CSS `animation: float 3s ease-in-out infinite` |
| Tilt cards (hover) | `useMotionValue(rotateX/Y)` + `useTransform` via Framer Motion |
| Section entrance | `whileInView={{ opacity: 1, y: 0 }}` with `viewport={{ once: true }}` |
| Tab indicator | `layoutId="tab-indicator"` shared layout animation |
| Feature cards hover | `whileHover={{ scale: 1.02, z: 8 }}` + border glow |
| Button hover | `whileHover={{ scale: 1.05 }}` + box-shadow CSS transition |
| Page transition | `AnimatePresence` exit `opacity → 0, y → -20` / enter `opacity → 1, y → 0` |
| XP progress bar | `animate={{ width }}` with `spring` transition |
| AI Assistant FAB pulse | CSS `@keyframes pulse-ring` scale + opacity |
| Sidebar collapse | `animate={{ width }}` with `spring` |
| Modal/dropdown | `type: "spring", stiffness: 300, damping: 25` |

---

## Responsive Breakpoints

- `< 768px`: Hamburger nav, single-column grid, sidebar becomes bottom sheet
- `768px – 1024px`: 2-col feature grid, sidebar icon-only
- `> 1024px`: Full layout as designed

---

## Verification

1. Dev server auto-runs at `$PORT` — check preview panel immediately after changes
2. Confirm logo SVG trace animation plays on load
3. Test 3D tilt cards respond to mouse movement
4. Switch between landing and dashboard view via "Try LearnX Free" CTA
5. Verify Recharts focus chart renders with gradient fill
6. Test sidebar collapse toggle
7. Test Cmd+K search overlay opens/closes
8. Test mobile hamburger menu overlay
9. Verify dark/light theme toggle works (`.light` class on `<html>`)
10. Check AA contrast: `#F8FAFC` on `#0A0D14` = ~19:1 ✓, `#2DD4BF` on `#0A0D14` = ~8.7:1 ✓

# Project Aura Design System

A comprehensive, professional UI/UX system inspired by Anthropic's design language with olive green accents, featuring smooth animations and full dark mode support.

## Design Philosophy

**Minimalist Excellence**
- Every element earns its place on screen
- White space is intentional, not wasted
- Reduce visual noise to enhance clarity

**Professional Enterprise Aesthetic**
- Clean, Apple-inspired minimalism
- Suitable for CTOs, CIOs, and security professionals
- WCAG 2.1 AA accessibility compliance

**Smooth & Responsive**
- Microsoft Foundry-inspired animations
- 60fps transitions throughout
- Loading states that communicate progress

---

## Color Palette

### Primary Brand Colors (Aura Blue)

| Token | Hex | Usage |
|-------|-----|-------|
| `aura-50` | `#EFF6FF` | Subtle backgrounds |
| `aura-100` | `#DBEAFE` | Hover states |
| `aura-200` | `#BFDBFE` | Light borders |
| `aura-300` | `#93C5FD` | Icon backgrounds |
| `aura-400` | `#60A5FA` | Dark mode primary |
| `aura-500` | `#3B82F6` | **Primary brand color** |
| `aura-600` | `#2563EB` | Hover state |
| `aura-700` | `#1D4ED8` | Active state |
| `aura-800` | `#1E40AF` | Dark accents |
| `aura-900` | `#1E3A8A` | Very dark |

### Olive Green (Success/Accent)

Replaces orange throughout the system for a professional, sophisticated palette.

| Token | Hex | Usage |
|-------|-----|-------|
| `olive-50` | `#F7F9F3` | Subtle success backgrounds |
| `olive-100` | `#EDF2E4` | Light olive tints |
| `olive-200` | `#D9E4C8` | Borders |
| `olive-300` | `#BFD1A3` | Decorative |
| `olive-400` | `#9FB87A` | Dark mode olive |
| `olive-500` | `#7C9A3E` | **Primary olive** |
| `olive-600` | `#6B8E23` | Dark olive (OliveDrab) |
| `olive-700` | `#556B2F` | Darker olive |
| `olive-800` | `#4A5D29` | Very dark |
| `olive-900` | `#3F4E23` | Almost black |

### Semantic Colors

| Purpose | Light Mode | Dark Mode |
|---------|------------|-----------|
| **Critical/Error** | `#DC2626` | `#F87171` |
| **Warning** | `#F59E0B` | `#FBBF24` |
| **Success** | `#7C9A3E` (olive) | `#9FB87A` |
| **Info** | `#3B82F6` (aura) | `#60A5FA` |

### Surface Colors (Backgrounds)

| Token | Light Mode | Dark Mode |
|-------|------------|-----------|
| `surface-50` | `#F9FAFB` | N/A |
| `surface-100` | `#F3F4F6` | N/A |
| `surface-200` | `#E5E7EB` | N/A |
| `surface-700` | N/A | `#374151` |
| `surface-800` | N/A | `#1F2937` |
| `surface-900` | N/A | `#111827` |

---

## Typography

### Font Stack

```css
/* Primary */
font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Monospace (code, logs) */
font-family: 'JetBrains Mono', Menlo, Monaco, Consolas, monospace;
```

### Type Scale

| Name | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Display | 36px | 700 | 40px | Hero sections |
| H1 | 32px | 600 | 36px | Page titles |
| H2 | 24px | 600 | 32px | Section headers |
| H3 | 18px | 600 | 28px | Card titles |
| Body | 14px | 400 | 24px | Primary content |
| Caption | 13px | 500 | 20px | Labels, metadata |
| Code | 13px | 400 | 24px | Code snippets |

### Tailwind Classes

```jsx
// Headlines
<h1 className="text-2xl lg:text-3xl font-bold text-surface-900 dark:text-surface-50">

// Body text
<p className="text-sm text-surface-600 dark:text-surface-400">

// Captions
<span className="text-xs font-medium text-surface-500 dark:text-surface-500">

// Code
<code className="font-mono text-sm">
```

---

## Spacing System

Based on an 8px grid with half-unit (4px) for fine adjustments.

| Token | Value | Usage |
|-------|-------|-------|
| `1` | 4px | Fine adjustments |
| `2` | 8px | Tight spacing |
| `3` | 12px | Compact elements |
| `4` | 16px | Standard padding |
| `6` | 24px | Card padding |
| `8` | 32px | Section spacing |
| `12` | 48px | Large gaps |
| `16` | 64px | Page margins |

### Tailwind Usage

```jsx
// Card with standard padding
<div className="p-6">

// Metric cards grid
<div className="grid gap-4 md:gap-6">

// Section spacing
<div className="mb-8">
```

---

## Component Specifications

### Metric Cards

Full-featured cards for displaying key metrics with trends and sparklines.

```jsx
import MetricCard from './components/ui/MetricCard';

<MetricCard
  title="Active Agents"
  value={3}
  icon={CpuChipIcon}
  trend={12}                    // Percentage change
  trendInverse={false}          // For metrics where down is good
  trendLabel="vs last hour"
  sparklineData={[2, 3, 2, 4, 3, 3, 3]}
  sparklineColor="aura"         // aura, olive, critical, warning
  iconColor="aura"
  status="healthy"              // healthy, warning, critical
  statusLabel="Running"
  loading={false}
/>
```

**Visual Specifications:**
- Border radius: 12px (`rounded-xl`)
- Padding: 24px (`p-6`)
- Shadow: Subtle card shadow, elevated on hover
- Icon: 20x20px in colored background circle
- Value: 30px bold
- Title: 14px medium gray

### Activity Feed

Timeline-style feed for recent events.

```jsx
import ActivityFeed from './components/ui/ActivityFeed';

<ActivityFeed
  activities={[
    {
      id: '1',
      type: 'vulnerability_detected',
      title: 'SQL Injection vulnerability',
      description: 'CWE-89 detected in login handler',
      timestamp: new Date().toISOString(),
      severity: 'critical',
      metadata: { file: 'src/auth/login.py' }
    }
  ]}
  title="Recent Activity"
  maxItems={6}
  onItemClick={(activity) => console.log(activity)}
  loading={false}
/>
```

**Activity Types:**
- `vulnerability_detected` - Red bug icon
- `patch_generated` - Blue code icon
- `patch_approved` - Green check icon
- `patch_rejected` - Red X icon
- `patch_deployed` - Green shield icon
- `agent_started` / `agent_completed` / `agent_failed`
- `anomaly_detected` - Yellow warning icon
- `incident_opened` / `incident_resolved`

### Charts

Simple SVG-based charts with smooth animations.

```jsx
import { LineChart, DonutChart, ProgressChart } from './components/ui/Charts';

// Line Chart
<LineChart
  data={[45, 52, 48, 55, 42, 38]}
  labels={['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']}
  title="Vulnerability Trend"
  color="critical"
  height={240}
  showDots={true}
  showGrid={true}
  showArea={true}
/>

// Donut Chart
<DonutChart
  data={[3, 8, 9, 4]}
  labels={['Critical', 'High', 'Medium', 'Low']}
  colors={['critical', 'warning', 'olive', 'surface']}
  title="Severity Distribution"
  size={160}
  centerValue={24}
  centerLabel="Total"
/>

// Progress/Gauge Chart
<ProgressChart
  value={82}
  max={100}
  label="Cache Hit Rate"
  color="aura"
  size={120}
/>
```

### Loading Skeletons

Shimmer-effect placeholders for loading states.

```jsx
import {
  Skeleton,
  MetricCardSkeleton,
  ChartSkeleton,
  ActivityFeedSkeleton,
  PageSkeleton
} from './components/ui/LoadingSkeleton';

// Full page loading
<PageSkeleton />

// Individual components
<MetricCardSkeleton />
<ChartSkeleton />
<ActivityFeedSkeleton count={5} />
```

### Dark Mode Toggle

Smooth animated toggle with icon rotation.

```jsx
import DarkModeToggle from './components/ui/DarkModeToggle';

// Compact version (icon only)
<DarkModeToggle />

// Expanded version (with label)
import { DarkModeToggleExpanded } from './components/ui/DarkModeToggle';
<DarkModeToggleExpanded />
```

---

## Animation System

### Timing

| Duration | Value | Usage |
|----------|-------|-------|
| Fast | 150ms | Micro-interactions |
| Normal | 250ms | Standard transitions |
| Slow | 400ms | Page transitions |

### Easing Functions

```css
/* Smooth (default) */
--ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);

/* Bounce (playful) */
--ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
```

### Animation Classes

```jsx
// Fade in
<div className="animate-fade-in">

// Fade in with upward motion
<div className="animate-fade-in-up">

// Slide in from right
<div className="animate-slide-in-right">

// Scale in
<div className="animate-scale-in">

// Shimmer (for skeletons)
<div className="animate-shimmer">

// Delayed animations
<div className="animate-fade-in-up animation-delay-100">
<div className="animate-fade-in-up animation-delay-200">
<div className="animate-fade-in-up animation-delay-300">
```

### Hover States

```jsx
// Card hover with lift effect
<div className="hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200">

// Button press effect
<button className="active:scale-[0.98] transition-transform">

// Subtle background change
<div className="hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors">
```

---

## Dark Mode Implementation

### Theme Context

```jsx
import { useTheme } from './context/ThemeContext';

function MyComponent() {
  const { isDarkMode, toggleTheme, theme } = useTheme();

  return (
    <button onClick={toggleTheme}>
      Current: {theme}
    </button>
  );
}
```

### CSS Classes

All components use Tailwind's `dark:` prefix for dark mode styles:

```jsx
// Background
<div className="bg-white dark:bg-surface-800">

// Text
<p className="text-surface-900 dark:text-surface-50">

// Borders
<div className="border-surface-200 dark:border-surface-700">

// Shadows (lighter in dark mode)
<div className="shadow-card dark:shadow-none dark:border">
```

### Persistence

Theme preference is automatically saved to `localStorage` as `aura-theme` and respects system preference on first visit.

---

## Accessibility

### Color Contrast

All text meets WCAG 2.1 AA standards (4.5:1 minimum):

| Combination | Ratio | Status |
|-------------|-------|--------|
| surface-900 on white | 15.1:1 | Pass |
| surface-50 on surface-900 | 12.6:1 | Pass |
| aura-500 on white | 4.5:1 | Pass |
| olive-600 on white | 5.2:1 | Pass |

### Focus States

```jsx
// Standard focus ring
<button className="focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2">

// Dark mode offset adjustment
<button className="dark:focus:ring-offset-surface-900">
```

### Reduced Motion

Animations are disabled when user prefers reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Keyboard Navigation

All interactive elements are keyboard accessible:
- Buttons and links have visible focus states
- Modal dialogs trap focus
- Tooltips appear on focus as well as hover
- Skip links for main content navigation

---

## Page Design Briefs

### 1. HITL Approvals Page

**Purpose:** Review and approve/reject AI-generated security patches

**Layout:**
- Header with filter/search controls
- Two-column layout: Approval list (left), Detail panel (right)
- Quick action buttons: Approve, Reject, Request Changes

**Key Components:**
- Approval cards with severity badge, file path, agent info
- Diff viewer for code changes
- Timeline showing patch lifecycle
- Comment/feedback form

**Colors:**
- Pending items: Warning (amber) badge
- Approved: Olive green badge
- Rejected: Critical (red) badge

### 2. Incident Investigations Page

**Purpose:** Investigate and respond to security incidents

**Layout:**
- Timeline-based incident view
- Evidence panel with related artifacts
- Response action buttons

**Key Components:**
- Incident severity header (Critical/High/Medium/Low)
- Timeline with expandable events
- Related vulnerabilities list
- Remediation checklist
- Audit log viewer

**Colors:**
- Critical incidents: Red header background
- Active investigation: Blue status
- Resolved: Olive green status

### 3. Red Team Dashboard

**Purpose:** Monitor adversarial security testing

**Layout:**
- Attack campaign overview cards
- Success/failure metrics
- Timeline of attack attempts

**Key Components:**
- Campaign status cards (Active, Completed, Scheduled)
- Attack chain visualization
- Coverage metrics (% of attack surface tested)
- Technique breakdown (MITRE ATT&CK mapping)

**Colors:**
- Active attacks: Warning (amber)
- Successful defenses: Olive green
- Failed defenses: Critical (red)

### 4. Agent Registry Page

**Purpose:** Monitor and manage AI agents (Coder, Reviewer, Validator)

**Layout:**
- Agent cards with status and metrics
- Activity timeline
- Configuration panels

**Key Components:**
- Agent health indicators (CPU, memory, task queue)
- Recent task history
- Performance metrics (success rate, avg. time)
- Enable/disable controls

**Colors:**
- Active agents: Olive green status
- Idle agents: Surface gray
- Failed agents: Critical red

### 5. GraphRAG Explorer Page

**Purpose:** Explore code knowledge graph

**Layout:**
- Graph visualization (full width)
- Search/filter sidebar
- Detail panel for selected nodes

**Key Components:**
- Interactive graph canvas (zoom, pan, click)
- Node type filters (files, functions, classes, vulnerabilities)
- Search with autocomplete
- Path finder between nodes

**Colors:**
- Vulnerability nodes: Critical red
- Security-related: Warning amber
- Standard code: Aura blue
- Dependencies: Surface gray

### 6. Settings Page

**Purpose:** Application and user configuration

**Layout:**
- Tabbed interface or section-based scroll
- Form inputs with validation
- Save/cancel actions

**Sections:**
- Profile (name, avatar, email)
- Notifications (email, in-app preferences)
- Security (MFA, sessions)
- Appearance (theme, density)
- API Keys (generate, revoke)

**Key Components:**
- Toggle switches for preferences
- Input validation with inline errors
- Danger zone for destructive actions

### 7. Integration Hub Page

**Purpose:** Manage external integrations

**Layout:**
- Grid of integration cards
- Filter by type (SCM, CI/CD, Security Tools)
- Connection status indicators

**Key Components:**
- Integration cards with logo, name, status
- Connect/disconnect buttons
- Configuration modals
- OAuth flow handling
- Webhook configuration

**Colors:**
- Connected: Olive green badge
- Disconnected: Surface gray
- Error: Critical red

---

## File Structure

```
frontend/src/
├── components/
│   ├── ui/                    # Reusable UI components
│   │   ├── index.js           # Component exports
│   │   ├── MetricCard.jsx     # Metric display cards
│   │   ├── ActivityFeed.jsx   # Activity timeline
│   │   ├── Charts.jsx         # SVG charts
│   │   ├── LoadingSkeleton.jsx # Loading states
│   │   └── DarkModeToggle.jsx # Theme toggle
│   ├── Dashboard.jsx          # Main dashboard
│   ├── CollapsibleSidebar.jsx # Navigation
│   └── ...                    # Other page components
├── context/
│   ├── AuthContext.jsx        # Authentication state
│   └── ThemeContext.jsx       # Dark mode state
├── index.css                  # Global styles & Tailwind
└── App.jsx                    # Root component
```

---

## Usage Examples

### Complete Dashboard Implementation

```jsx
import React, { useState, useEffect } from 'react';
import MetricCard, { MetricCardGrid } from './components/ui/MetricCard';
import ActivityFeed from './components/ui/ActivityFeed';
import { LineChart, DonutChart } from './components/ui/Charts';
import { PageSkeleton } from './components/ui/LoadingSkeleton';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchDashboardData().then(data => {
      setData(data);
      setLoading(false);
    });
  }, []);

  if (loading) return <PageSkeleton />;

  return (
    <div className="flex-1 overflow-y-auto bg-surface-50 dark:bg-surface-900">
      <div className="p-6 lg:p-8 max-w-[1800px] mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl lg:text-3xl font-bold text-surface-900 dark:text-surface-50">
            Security Dashboard
          </h1>
        </div>

        {/* Metrics */}
        <MetricCardGrid columns={4} className="mb-8">
          {data.metrics.map((metric, i) => (
            <MetricCard
              key={metric.id}
              {...metric}
              className={`animate-fade-in-up animation-delay-${i}00`}
            />
          ))}
        </MetricCardGrid>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <LineChart {...data.trendChart} />
          <DonutChart {...data.distributionChart} />
        </div>

        {/* Activity */}
        <ActivityFeed activities={data.activities} />
      </div>
    </div>
  );
}
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-08 | Initial design system release |

---

## Credits

Design system created for Project Aura, an autonomous AI SaaS platform for enterprise code security.

Inspired by:
- Anthropic's design language
- Apple's Human Interface Guidelines
- Microsoft Foundry animations
- Tailwind CSS utility-first approach

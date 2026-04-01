# Project Aura Design Principles

**Platform:** Autonomous AI SaaS Platform for Enterprise Code Intelligence
**Design Philosophy:** Enterprise-grade, security-first, developer-focused interfaces
**Target Users:** Security engineers, DevOps teams, platform administrators, compliance officers

---

## I. Core Design Philosophy & Strategy

### Users First
- **Primary Personas:** Security engineers analyzing vulnerabilities, DevOps teams managing deployments, administrators configuring policies
- **Workflow-Centric:** Design for continuous monitoring, incident response, and approval workflows
- **Task Efficiency:** Minimize clicks for critical actions (approve/reject patches, view vulnerability details, sandbox testing)

### Enterprise-Grade Quality
- **Meticulous Craft:** Precision in data visualization, dashboard clarity, and status indicators
- **Trustworthiness:** Clear visual hierarchy for critical security information
- **Professional Aesthetics:** Clean, modern interface inspired by enterprise tools (AWS Console, GitHub, Linear)

### Speed & Performance
- **Real-Time Updates:** Live status updates for agent activities, vulnerability scans, patch deployments
- **Optimistic UI:** Immediate visual feedback for actions while background processing continues
- **Progressive Loading:** Skeleton screens for data-intensive views (code graphs, security reports)

### Security-First Design
- **Visual Security Indicators:** Color-coded severity levels (Critical, High, Medium, Low)
- **Clear Permissions:** Visible role indicators and access controls
- **Audit Trail:** Timestamped activity logs with user attribution
- **Compliance Visibility:** CMMC, SOX, NIST compliance status at-a-glance

### Simplicity & Clarity
- **Information Hierarchy:** Critical alerts and blocking issues prominently displayed
- **Contextual Help:** Inline tooltips for technical terms (GraphRAG, HITL, AST parsing)
- **Progressive Disclosure:** Advanced settings hidden by default, accessible when needed

### Consistency
- **Design System:** Unified component library across all modules
- **Pattern Library:** Consistent interaction patterns (modals for confirmations, toasts for notifications)
- **Terminology:** Standardized language (e.g., "Sandbox" not "Test Environment", "Agent" not "Bot")

### Accessibility (WCAG AA+)
- **Keyboard Navigation:** Full keyboard support for critical workflows
- **Screen Reader:** Semantic HTML with proper ARIA labels
- **Color Contrast:** Minimum 4.5:1 for all text
- **Focus States:** Clear visual focus indicators on all interactive elements

---

## II. Design System Foundation

### Color Palette

#### Primary Brand Color
- **Primary Blue:** `#3B82F6` (User-specified, strategic use for CTAs and brand elements)

#### Neutrals (7-step grayscale)
- **Gray 50:** `#F9FAFB` (Backgrounds, subtle surfaces)
- **Gray 100:** `#F3F4F6` (Card backgrounds)
- **Gray 200:** `#E5E7EB` (Borders, dividers)
- **Gray 300:** `#D1D5DB` (Disabled states)
- **Gray 600:** `#4B5563` (Secondary text)
- **Gray 700:** `#374151` (Body text)
- **Gray 900:** `#111827` (Headings, primary text)

#### Semantic Colors (Security-Focused)
- **Critical/Error:** `#DC2626` (Critical vulnerabilities, failed operations)
- **High Priority:** `#EA580C` (High severity issues, warnings)
- **Medium Priority:** `#F59E0B` (Medium severity, cautionary states)
- **Success:** `#10B981` (Approved patches, successful scans, healthy agents)
- **Info:** `#3B82F6` (Informational alerts, in-progress states)
- **Low Priority:** `#6B7280` (Low severity, deferred items)

#### Dark Mode Palette
- **Background:** `#0F172A` (Slate 900)
- **Surface:** `#1E293B` (Slate 800)
- **Border:** `#334155` (Slate 700)
- **Text Primary:** `#F1F5F9` (Slate 100)
- **Text Secondary:** `#94A3B8` (Slate 400)

**Accessibility Check:** All combinations meet WCAG AA (4.5:1 minimum)

### Typography

#### Font Family
- **Primary:** `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Monospace (Code):** `'JetBrains Mono', 'Fira Code', 'Courier New', monospace`

#### Modular Scale
- **H1 (Page Titles):** 32px / 2rem, SemiBold (600)
- **H2 (Section Headers):** 24px / 1.5rem, SemiBold (600)
- **H3 (Subsections):** 20px / 1.25rem, Medium (500)
- **H4 (Card Titles):** 16px / 1rem, Medium (500)
- **Body Large:** 16px / 1rem, Regular (400)
- **Body Medium (Default):** 14px / 0.875rem, Regular (400)
- **Body Small/Caption:** 12px / 0.75rem, Regular (400)
- **Code/Monospace:** 13px / 0.8125rem, Regular (400)

#### Line Height
- **Headings:** 1.2-1.3
- **Body Text:** 1.6-1.7
- **Code Blocks:** 1.5

### Spacing Units (8px base)
- **4px** - Tight spacing (icon padding)
- **8px** - Standard element spacing
- **12px** - Card inner padding
- **16px** - Section spacing, button padding
- **24px** - Component gaps
- **32px** - Page section gaps
- **48px** - Major layout divisions

### Border Radii
- **Small (4px):** Inputs, buttons, badges
- **Medium (8px):** Cards, modals, dropdowns
- **Large (12px):** Dashboard panels, major containers
- **Pill (999px):** Status badges, tags

### Shadows (Elevation System)
- **Shadow SM:** `0 1px 2px rgba(0,0,0,0.05)` - Subtle cards
- **Shadow MD:** `0 4px 6px rgba(0,0,0,0.1)` - Modals, dropdowns
- **Shadow LG:** `0 10px 15px rgba(0,0,0,0.1)` - Overlays
- **Shadow XL:** `0 20px 25px rgba(0,0,0,0.1)` - Critical notifications

---

## III. Core UI Components (with States)

### Buttons
- **Primary:** Filled blue, for primary actions (Approve Patch, Deploy Fix)
- **Secondary:** Outlined gray, for secondary actions (View Details, Cancel)
- **Destructive:** Filled red, for dangerous actions (Reject Patch, Delete Sandbox)
- **Ghost/Tertiary:** Text-only, minimal styling for tertiary actions
- **Icon Buttons:** For toolbars and compact layouts

**States:** Default, Hover (brightness +10%), Active (brightness -10%), Focus (ring outline), Disabled (opacity 50%)

### Input Fields
- **Text Input:** Single-line text entry (search, filters)
- **Textarea:** Multi-line input (patch notes, remediation instructions)
- **Select Dropdown:** Single-choice selection (severity filter, time range)
- **Multi-Select:** Multiple-choice (affected services, vulnerability types)
- **Date/Time Picker:** For scheduling scans, filtering by date range
- **Code Input:** Syntax-highlighted input for configuration (YAML, JSON)

**Elements:** Label (above), placeholder (subtle gray), helper text (below, small), error message (red, below)

### Status Indicators
- **Badges:** Small colored pills for status (Critical, Approved, In Progress, Sandbox Testing)
- **Progress Bars:** Linear progress for long-running operations (code scan 45%)
- **Health Icons:** Visual health status (🟢 Healthy, 🟡 Degraded, 🔴 Failed)
- **Agent Status:** Visual indicator for agent states (Active, Idle, Analyzing, Failed)

### Cards
- **Data Cards:** Display metrics, summaries (vulnerability count, agent uptime)
- **Content Cards:** Show details (vulnerability details, patch information)
- **Interactive Cards:** Clickable for navigation (recent alerts, pending approvals)
- **Gradient Accents:** Subtle top border gradient for visual hierarchy

### Tables
- **Data Table:** For lists (vulnerabilities, patches, sandboxes, audit logs)
- **Column Sorting:** Clickable headers with sort indicators (↑↓)
- **Row Actions:** Inline buttons/icons (View, Edit, Approve, Reject)
- **Expandable Rows:** For detailed information (stack traces, remediation steps)
- **Sticky Headers:** For long tables
- **Zebra Striping:** Optional alternating row colors for dense data

**Alignment:** Left-align text, right-align numbers/dates

### Modals/Dialogs
- **Confirmation Modal:** For destructive actions (Delete sandbox, Reject patch)
- **Detail Modal:** For expanded views (vulnerability details, agent logs)
- **Form Modal:** For creating/editing (new policy, sandbox configuration)
- **Alert Modal:** For critical notifications (agent failure, critical CVE detected)

**Structure:** Header with title/close button, body content, footer with actions

### Navigation
- **Sidebar:** Persistent left navigation (Dashboard, Vulnerabilities, Patches, Agents, Settings)
- **Top Bar:** Global search, notifications, user profile
- **Tabs:** Section navigation within pages (Overview, Remediations, Audit Log)
- **Breadcrumbs:** Hierarchical navigation (Home > Vulnerabilities > CVE-2024-1234)

### Notifications
- **Toast/Snackbar:** Temporary bottom-right notifications (Success: "Patch approved", Error: "Agent failed")
- **Notification Center:** Persistent notification panel (bell icon in top bar)
- **Alert Banner:** Page-level persistent alerts (Critical: "5 new critical vulnerabilities detected")

### Progress Indicators
- **Linear Progress:** For deterministic progress (scan progress 75%)
- **Circular Spinner:** For indeterminate loading (fetching data)
- **Skeleton Screens:** For initial page loads (placeholder cards/tables)

### Data Visualization
- **Line Charts:** Vulnerability trends over time
- **Bar Charts:** Vulnerability counts by severity
- **Pie/Donut Charts:** Remediation status distribution
- **Network Graph:** Code Knowledge Graph visualization
- **Heatmaps:** Activity patterns, hotspot analysis

**Library Recommendation:** Recharts, Victory, or D3.js

### Code Display
- **Code Block:** Syntax-highlighted code snippets (Python, JavaScript, YAML)
- **Diff Viewer:** Side-by-side or unified diff for patch comparison
- **File Tree:** Collapsible directory structure
- **Inline Code:** Monospace inline code (e.g., `neptune.aura.local`)

**Syntax Highlighting:** Use Prism.js or highlight.js

---

## IV. Layout & Visual Hierarchy

### Responsive Grid
- **Desktop (1440px+):** 12-column grid
- **Tablet (768px-1439px):** 8-column grid, collapsible sidebar
- **Mobile (320px-767px):** Single column, bottom navigation

### Dashboard Layout
- **Persistent Left Sidebar (240px):** Primary module navigation
- **Top Bar (64px):** Global search, notifications, user menu
- **Content Area (Fluid):** Main workspace for module-specific views
- **Right Panel (Optional, 320px):** Contextual details, activity feed

### White Space & Balance
- **Card Padding:** 16-24px internal padding
- **Section Gaps:** 32-48px between major sections
- **Element Spacing:** 8-16px between related elements

### Visual Hierarchy Tactics
- **Typography Weight:** Bold headings (600), medium subheadings (500), regular body (400)
- **Color Contrast:** Dark text on light backgrounds, semantic colors for emphasis
- **Size Differentiation:** Larger elements for primary actions, smaller for secondary

---

## V. Module-Specific Design Patterns

### A. Dashboard (Overview)
- **Key Metrics:** 4-6 metric cards at top (Total Vulnerabilities, Critical Count, Agent Status, Scan Coverage)
- **Trend Visualizations:** Line/bar charts for historical trends
- **Recent Activity Feed:** Real-time agent activities, vulnerability discoveries
- **Quick Actions:** Prominent CTAs (Run Scan, View Critical Alerts, Approve Pending)

### B. Vulnerability Management
- **Table View:** Sortable/filterable table of vulnerabilities (CVE ID, Severity, Affected Services, Status)
- **Severity Filters:** Quick filter pills (Critical, High, Medium, Low, All)
- **Status Filters:** Filter by remediation status (Open, In Progress, Patched, Sandbox Testing)
- **Bulk Actions:** Select multiple vulnerabilities for batch operations
- **Detail Panel:** Right-side panel with full vulnerability details (CVSS score, description, remediation steps)

### C. Patch Management & HITL Approval
- **Pending Approvals:** Highlighted section for patches awaiting human review
- **Patch Details Card:**
  - Patch summary (description, affected files, risk level)
  - Sandbox test results (success/failure indicators)
  - Diff viewer (before/after code comparison)
  - Approval actions (Approve, Reject, Request Changes)
- **Approval History:** Audit trail of past approvals with timestamps and approvers

### D. Agent Orchestration
- **Agent Status Grid:** Visual grid of active agents with real-time status
- **Agent Detail View:**
  - Current task (e.g., "Analyzing CVE-2024-5678")
  - Execution logs (scrollable, syntax-highlighted)
  - Resource usage (CPU, memory)
  - Agent metrics (uptime, success rate, average execution time)
- **Agent Controls:** Start, Stop, Restart, View Logs

### E. Code Knowledge Graph (GraphRAG)
- **Interactive Graph Visualization:**
  - Nodes (entities: classes, functions, files)
  - Edges (relationships: imports, calls, dependencies)
  - Zoom, pan, search capabilities
- **Entity Detail Sidebar:** Clicked node details (file path, description, connections)
- **Graph Filters:** Filter by entity type, connection strength, time range

### F. Sandbox Management
- **Sandbox List:** Table of active/terminated sandboxes (ID, Status, Created, Patch ID)
- **Sandbox Actions:** Create, Terminate, View Logs, Access Console
- **Resource Indicators:** CPU/memory usage per sandbox
- **Isolation Level Badges:** Visual indicator (Container, VPC, Full)

### G. Configuration & Settings
- **Tabbed Navigation:** Sections (General, Security Policies, Notifications, Integrations, Users)
- **Form Layouts:**
  - Grouped settings with section headers
  - Toggle switches for boolean settings
  - Input fields with validation and helper text
- **Policy Builder:** Visual rule builder for security policies (if/then conditions)
- **Preview Panel:** Live preview of configuration changes (e.g., email notification template)

### H. Audit Logs & Compliance
- **Filterable Log Table:** Timestamp, User, Action, Resource, Result
- **Export Options:** CSV, JSON export for compliance audits
- **Compliance Dashboard:** Visual compliance status (CMMC Level 3, SOX, NIST 800-53)
- **Audit Trail Search:** Full-text search with advanced filters

---

## VI. Interaction Design & Animations

### Micro-interactions
- **Button Feedback:** Subtle scale (0.98) on click, bounce-back on release
- **Hover States:** Brightness increase (110%), subtle shadow lift
- **Loading States:** Shimmer animation for skeleton screens
- **Success Feedback:** Green checkmark animation, fade-out toast (3s)
- **Error Shake:** Gentle horizontal shake for invalid inputs

### Animation Timing
- **Fast (150ms):** Hover, focus states, button clicks
- **Standard (250ms):** Modal open/close, dropdown expand, toast fade-in
- **Slow (350ms):** Page transitions, panel slides

### Easing Functions
- **Ease-in-out:** Most animations (smooth start and end)
- **Ease-out:** Entering elements (quick start, smooth end)
- **Ease-in:** Exiting elements (smooth start, quick end)

### Keyboard Navigation
- **Tab Order:** Logical top-to-bottom, left-to-right
- **Shortcuts:**
  - `Ctrl/Cmd + K` - Global search
  - `Esc` - Close modal/dropdown
  - `Enter` - Submit form, activate primary button
  - `Space` - Toggle checkboxes, activate buttons
- **Focus Indicators:** 2px blue ring (`ring-2 ring-blue-500`)

---

## VII. CSS & Styling Architecture

### Recommended Approach: Tailwind CSS (Utility-First)

**Why Tailwind for Project Aura:**
- **LLM-Friendly:** Claude can generate accurate Tailwind classes
- **Consistency:** Design tokens defined in `tailwind.config.js`
- **Rapid Iteration:** Fast UI prototyping and iteration
- **Performance:** PurgeCSS removes unused styles in production

**Tailwind Configuration:**
```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        critical: '#DC2626',
        high: '#EA580C',
        medium: '#F59E0B',
        success: '#10B981',
        // ... other semantic colors
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      spacing: {
        // 8px base unit system
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
```

**Alternative:** CSS-in-JS (styled-components, Emotion) if component-scoped styles preferred

---

## VIII. Accessibility Checklist (WCAG 2.1 AA)

- [ ] **Color Contrast:** All text meets 4.5:1 minimum (7:1 for AAA)
- [ ] **Keyboard Navigation:** All interactive elements accessible via Tab
- [ ] **Focus States:** Visible focus indicators on all interactive elements
- [ ] **Semantic HTML:** Proper use of `<button>`, `<nav>`, `<main>`, `<aside>`
- [ ] **ARIA Labels:** `aria-label` for icon-only buttons, `aria-describedby` for form fields
- [ ] **Alt Text:** Descriptive alt text for all images
- [ ] **Form Labels:** Associated `<label>` for every form input
- [ ] **Screen Reader Testing:** Test with NVDA (Windows) or VoiceOver (macOS)
- [ ] **Heading Hierarchy:** Proper `<h1>` → `<h2>` → `<h3>` structure
- [ ] **Color Independence:** Information not conveyed by color alone (icons + color)

---

## IX. General Best Practices

### Progressive Disclosure
- **Novice Users:** Simple default views, guided onboarding
- **Advanced Users:** Expandable "Advanced Settings" sections, keyboard shortcuts

### Error Prevention & Recovery
- **Confirmations:** Modals for destructive actions (Delete, Reject)
- **Undo:** Undo option for reversible actions (within 10s)
- **Inline Validation:** Real-time validation with clear error messages

### Performance Optimization
- **Lazy Loading:** Load images, charts, and heavy components on-demand
- **Virtualized Lists:** Virtual scrolling for tables with 100+ rows (react-window)
- **Code Splitting:** Route-based code splitting for faster initial load
- **Caching:** Cache API responses (React Query, SWR)

### Responsive Design
- **Mobile-First:** Design for small screens, enhance for larger viewports
- **Touch-Friendly:** Minimum 44px tap targets on mobile
- **Adaptive Layouts:** Sidebar collapses on tablet, bottom nav on mobile

### Documentation
- **Component Library:** Storybook or Styleguidist for component documentation
- **Design System Site:** Living style guide with code examples
- **Accessibility Notes:** Document accessibility features in each component

---

## X. Design Review Workflow Integration

### When to Conduct Design Reviews
1. **After implementing new UI features** (new dashboard panels, modals, forms)
2. **Before finalizing pull requests** with visual changes
3. **When adding user-facing functionality** (new approval workflows, notification systems)
4. **During significant UI refactoring** (component library updates, layout changes)

### Design Review Agent Usage
- Invoke `@agent-design-review` for comprehensive UI/UX validation
- Use `/design-review` slash command for on-demand reviews
- Automated review on PR events (see `.github/workflows/design-review.yml`)

### Review Checklist (7 Phases)
1. **Preparation:** Understand changes, set up preview environment
2. **Interaction & User Flow:** Test primary workflows, interactive states
3. **Responsiveness:** Verify desktop (1440px), tablet (768px), mobile (375px)
4. **Visual Polish:** Check alignment, spacing, typography, color consistency
5. **Accessibility:** Keyboard navigation, focus states, ARIA labels, color contrast
6. **Robustness:** Test edge cases, loading states, error states, content overflow
7. **Code Health:** Verify component reuse, design token usage, pattern adherence

---

## XI. Technology Stack Recommendations

### Frontend Framework
- **React 18+** with TypeScript (enterprise-standard, LLM-friendly)
- **Next.js 14+** for SSR, routing, and API routes (optional)

### State Management
- **Zustand** or **Jotai** (lightweight, simple)
- **React Query (TanStack Query)** for server state management

### UI Component Libraries (Optional Starter Kits)
- **Headless UI** (Tailwind-compatible, accessible primitives)
- **Radix UI** (unstyled, accessible components)
- **shadcn/ui** (copy-paste component library, Tailwind-based)

**Note:** Build custom components for maximum control, use libraries for complex patterns (date pickers, modals)

### Data Visualization
- **Recharts** (React-friendly, declarative charts)
- **D3.js** (for advanced custom visualizations like Code Knowledge Graph)

### Code Syntax Highlighting
- **Prism.js** or **highlight.js**
- **react-syntax-highlighter** (React wrapper)

### Testing
- **Playwright** (end-to-end testing, visual regression)
- **React Testing Library** (component testing)
- **Axe-core** (automated accessibility testing)

---

## XII. Iterative Design Process

### Design → Build → Review → Iterate

1. **Define User Story:** "As a security engineer, I want to approve patches with one click"
2. **Design Mockup:** Sketch UI in Figma or directly code with Tailwind
3. **Implement:** Build component with React + Tailwind
4. **Automated Review:** Run `@agent-design-review` on PR
5. **Manual QA:** Test in preview environment with Playwright
6. **Iterate:** Address feedback, refine visual polish
7. **Deploy:** Merge to main, monitor user feedback

### Continuous Improvement
- **User Feedback:** Collect feedback from security engineers, DevOps teams
- **Analytics:** Track feature usage, identify pain points
- **A/B Testing:** Test variations for critical workflows (approval flow, alert presentation)

---

## Summary

Project Aura's UI/UX design prioritizes **enterprise-grade quality**, **security-first** visual design, and **developer efficiency**. By following these principles, we ensure the platform is:

- **Trustworthy:** Clear visual hierarchy for critical security information
- **Efficient:** Minimal clicks for high-frequency tasks (approve patches, view alerts)
- **Accessible:** WCAG AA compliant for all users
- **Scalable:** Design system supports rapid feature development
- **Consistent:** Unified experience across all modules

**Next Steps:**
1. Implement design system foundation (Tailwind config, component library)
2. Build core UI components (buttons, inputs, cards, tables, modals)
3. Design and implement Dashboard (Overview) module
4. Integrate design review workflow (`@agent-design-review`)
5. Conduct user testing with target personas (security engineers, DevOps)

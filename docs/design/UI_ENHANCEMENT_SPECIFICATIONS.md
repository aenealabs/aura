# Project Aura UI Enhancement Specifications

**Document Version:** 1.0
**Date:** 2026-01-27
**Author:** UI/UX Design Team

This document provides comprehensive UI/UX specifications for three priority ADRs requiring frontend implementation. These designs align with Project Aura's established design system, component patterns, and Apple-inspired aesthetic philosophy.

---

## Table of Contents

1. [Design System Reference](#design-system-reference)
2. [ADR-069: Guardrail Configuration UI](#adr-069-guardrail-configuration-ui)
3. [ADR-068: Explainability Dashboard](#adr-068-explainability-dashboard)
4. [ADR-071: Capability Graph Completion](#adr-071-capability-graph-completion)
5. [Shared Components](#shared-components)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Design System Reference

### Color Palette (Quick Reference)

| Token | Value | Usage |
|-------|-------|-------|
| `aura` (Primary) | `#3B82F6` | CTAs, brand elements, info states |
| `critical` | `#DC2626` | Critical severity, errors, destructive actions |
| `warning` | `#F59E0B` | Medium priority, caution states |
| `high` | `#EA580C` | High priority warnings |
| `olive` (Success) | `#10B981` | Success states, healthy indicators |
| `surface-50` | `#F9FAFB` | Light backgrounds |
| `surface-800` | `#1E293B` | Dark mode surfaces |
| `surface-900` | `#0F172A` | Dark mode backgrounds |

### Typography Scale

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| H1 | 32px (2rem) | 600 | Page titles |
| H2 | 24px (1.5rem) | 600 | Section headers |
| H3 | 20px (1.25rem) | 500 | Card titles |
| Body | 14px (0.875rem) | 400 | Default text |
| Caption | 12px (0.75rem) | 400 | Labels, metadata |
| Code | 13px | 400 | Monospace content |

### Spacing Scale (8px base)

`4px | 8px | 12px | 16px | 24px | 32px | 48px`

### Component Patterns (Established)

Based on analysis of existing components (`DashboardEditor.jsx`, `WidgetLibrary.jsx`, `AlignmentDashboard.jsx`, `SecurityAlertSettings.jsx`, `CapabilityGraph.jsx`):

- **Cards:** `bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]`
- **Buttons Primary:** `px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors`
- **Buttons Secondary:** `px-4 py-2 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors`
- **Input Fields:** `px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500`
- **Section Headers:** `text-lg font-semibold text-surface-900 dark:text-surface-100`

---

## ADR-069: Guardrail Configuration UI

### Overview

The Guardrail Configuration UI enables users to configure their AI safety settings through a tiered exposure model. The design prioritizes progressive disclosure, framing choices around business outcomes rather than technical security mechanisms.

### Components Required

1. **GuardrailSettings.jsx** - Main settings page container
2. **SecurityProfileSelector.jsx** - Primary preset selection
3. **AdvancedGuardrailSettings.jsx** - Expandable advanced options
4. **GuardrailActivityDashboard.jsx** - Read-only metrics dashboard
5. **ComplianceProfileBadge.jsx** - Locked settings indicator
6. **ImpactPreviewModal.jsx** - Change impact preview
7. **GuardrailAuditLog.jsx** - Configuration change history

---

### 1. SecurityProfileSelector Component

**Purpose:** Allow users to select their security posture through intuitive presets.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Security Profile                                                     [?] Help  |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  Choose how Aura balances speed and safety for your organization:               |
|                                                                                  |
|  +------------------------+  +------------------------+                          |
|  |  [ ] Conservative      |  |  [x] Balanced          |                          |
|  |                        |  |                        |                          |
|  |  Maximum oversight     |  |  Recommended balance   |                          |
|  |  for high-risk envs    |  |  of speed and safety   |                          |
|  |                        |  |                        |                          |
|  |  - Review all actions  |  |  - Auto-approve safe   |                          |
|  |  - Detailed logging    |  |  - Review risky ops    |                          |
|  |  - ~15 prompts/day     |  |  - ~5 prompts/day      |                          |
|  +------------------------+  +------------------------+                          |
|                                                                                  |
|  +------------------------+  +------------------------+                          |
|  |  [ ] Efficient         |  |  [ ] Aggressive        |                          |
|  |                        |  |                        |                          |
|  |  Minimal interruptions |  |  Maximum autonomy      |                          |
|  |  for trusted teams     |  |  for experienced users |                          |
|  |                        |  |                        |                          |
|  |  - Review critical     |  |  - Critical only       |                          |
|  |  - Standard logging    |  |  - Minimal prompts     |                          |
|  |  - ~2 prompts/day      |  |  - ~0-1 prompts/day    |                          |
|  +------------------------+  +------------------------+                          |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Tailwind Implementation:**

```jsx
// SecurityProfileSelector.jsx
const profiles = [
  {
    id: 'conservative',
    name: 'Conservative',
    tagline: 'Maximum oversight for high-risk environments',
    features: ['Review all actions', 'Detailed logging', '~15 prompts/day'],
    iconColor: 'olive',
    recommended: false,
  },
  {
    id: 'balanced',
    name: 'Balanced',
    tagline: 'Recommended balance of speed and safety',
    features: ['Auto-approve safe ops', 'Review risky ops', '~5 prompts/day'],
    iconColor: 'aura',
    recommended: true,
  },
  {
    id: 'efficient',
    name: 'Efficient',
    tagline: 'Minimal interruptions for trusted teams',
    features: ['Review critical only', 'Standard logging', '~2 prompts/day'],
    iconColor: 'warning',
    recommended: false,
  },
  {
    id: 'aggressive',
    name: 'Aggressive',
    tagline: 'Maximum autonomy for experienced users',
    features: ['Critical only', 'Minimal prompts', '~0-1 prompts/day'],
    iconColor: 'critical',
    recommended: false,
  },
];
```

**Card Styling (Selected vs Unselected):**

```css
/* Unselected */
.profile-card {
  @apply border border-surface-200 dark:border-surface-700
         bg-white dark:bg-surface-800 rounded-xl p-4
         cursor-pointer transition-all duration-200
         hover:border-aura-300 dark:hover:border-aura-700
         hover:shadow-md;
}

/* Selected */
.profile-card.selected {
  @apply border-2 border-aura-500
         ring-2 ring-aura-500/20
         bg-aura-50 dark:bg-aura-900/20;
}
```

**Interaction States:**
- Hover: Subtle border color change, slight shadow lift
- Selected: Blue border, blue tint background, checkmark icon
- Disabled (compliance locked): Gray overlay, lock icon, tooltip explaining restriction

---

### 2. AdvancedGuardrailSettings Component

**Purpose:** Progressive disclosure of granular settings for power users.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  > Advanced Settings                                                            |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  HITL Escalation Sensitivity                                                     |
|  +------------------------------------------------------------------------+     |
|  |  Low        [======|==================] High                           |     |
|  |                    ^                                                   |     |
|  |                 Medium                                                 |     |
|  +------------------------------------------------------------------------+     |
|  Fewer interruptions <<<                        >>> More human oversight        |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Context Trust Requirements                                                      |
|  +------------------------------------------------------------------------+     |
|  |  ○ All Sources    ○ Low+    ● Medium+    ○ High Only                   |     |
|  +------------------------------------------------------------------------+     |
|  Accept context from sources with Medium trust or higher                        |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Explanation Verbosity                                                           |
|  +------------------------------------------------------------------------+     |
|  |  Minimal  |  Standard  |  Detailed  |  Debug                           |     |
|  |    [ ]    |    [x]     |    [ ]     |   [ ]                            |     |
|  +------------------------------------------------------------------------+     |
|  Standard: Reasoning steps + alternatives for significant decisions             |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Quarantine Review Delegation                                                    |
|  +------------------------------------------------------------------------+     |
|  |  Who reviews quarantined content?                                      |     |
|  |  +--------------------------------------------------+                  |     |
|  |  |  Team Lead                                    v  |                  |     |
|  |  +--------------------------------------------------+                  |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Segmented Control Pattern:**

```jsx
// SegmentedControl component for discrete options
<div className="inline-flex rounded-lg bg-surface-100 dark:bg-surface-700 p-1">
  {options.map((option) => (
    <button
      key={option.value}
      onClick={() => onChange(option.value)}
      className={`
        px-4 py-2 text-sm font-medium rounded-md transition-all
        ${selected === option.value
          ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-surface-100 shadow-sm'
          : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
        }
      `}
    >
      {option.label}
    </button>
  ))}
</div>
```

**Slider Component:**

```jsx
// Custom slider with labeled stops
<div className="space-y-2">
  <div className="flex justify-between text-xs text-surface-500">
    <span>Low</span>
    <span>Medium</span>
    <span>High</span>
    <span>Critical-Only</span>
  </div>
  <input
    type="range"
    min={0}
    max={3}
    value={value}
    onChange={(e) => onChange(Number(e.target.value))}
    className="w-full h-2 bg-surface-200 dark:bg-surface-700 rounded-lg
               appearance-none cursor-pointer accent-aura-600"
  />
  <p className="text-sm text-surface-600 dark:text-surface-400">
    {descriptions[value]}
  </p>
</div>
```

---

### 3. ImpactPreviewModal Component

**Purpose:** Show projected impact before applying configuration changes.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|                          Review Changes                              [X]       |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  You're changing: HITL Threshold Medium -> High                                 |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Projected Impact (based on last 30 days)                             |     |
|  |                                                                        |     |
|  |  Metric                    Before      After       Change              |     |
|  |  -----------------------------------------------------------------    |     |
|  |  Daily HITL prompts        12          4           -67%  [down]       |     |
|  |  Auto-approved ops         847         891         +5%   [up]         |     |
|  |  Quarantined items         3           8           +167% [up]         |     |
|  |  Avg decision latency      2.3s        1.1s        -52%  [down]       |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  /!\ Warning                                                           |     |
|  |                                                                        |     |
|  |  Higher threshold means fewer interruptions but more items will be    |     |
|  |  quarantined for batch review. Consider your team's capacity.         |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|                         [ Cancel ]        [ Apply Changes ]                     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Metric Change Indicator:**

```jsx
function ChangeIndicator({ before, after, inverted = false }) {
  const change = ((after - before) / before) * 100;
  const isPositive = change > 0;
  const isGood = inverted ? !isPositive : isPositive;

  return (
    <div className={`flex items-center gap-1 ${
      isGood ? 'text-olive-600 dark:text-olive-400' : 'text-critical-600 dark:text-critical-400'
    }`}>
      {isPositive ? (
        <ArrowTrendingUpIcon className="w-4 h-4" />
      ) : (
        <ArrowTrendingDownIcon className="w-4 h-4" />
      )}
      <span className="font-medium">
        {isPositive ? '+' : ''}{change.toFixed(0)}%
      </span>
    </div>
  );
}
```

---

### 4. GuardrailActivityDashboard Component

**Purpose:** Read-only visibility into guardrail operations.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Guardrail Activity                                          Last 7 Days  [v]  |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  +------------------------+  +------------------------+  +------------------------+
|  |  Threat Detection      |  |  Context Trust         |  |  Agent Operations      |
|  |                        |  |                        |  |                        |
|  |  [Shield Icon]         |  |  [Lock Icon]           |  |  [Server Icon]         |
|  |                        |  |                        |  |                        |
|  |  23 Blocked            |  |  4,139 Verified        |  |  9,726 Total           |
|  |  ----------------      |  |  ----------------      |  |  ----------------      |
|  |  Prompt injection: 18  |  |  HIGH:    2,847        |  |  SAFE:      8,234      |
|  |  Jailbreak: 3          |  |  MEDIUM:  1,203        |  |  MONITORING: 1,456     |
|  |  Data exfil: 2         |  |  LOW:        89        |  |  DANGEROUS:     34     |
|  |                        |  |  Quarantined: 12       |  |  CRITICAL:       2     |
|  +------------------------+  +------------------------+  +------------------------+
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Explanations Generated                                                |     |
|  |                                                                        |     |
|  |  [===========================================-------]  87%            |     |
|  |  Average Confidence                                                    |     |
|  |                                                                        |     |
|  |  Alternatives Disclosed: 94%    Consistency: 99.2%                    |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Metric Card Pattern:**

```jsx
function GuardrailMetricCard({ title, icon: Icon, value, breakdown, iconColor }) {
  const colorMap = {
    aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
  };

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200/50
                    dark:border-surface-700/30 p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${colorMap[iconColor]}`}>
          <Icon className="w-5 h-5" />
        </div>
        <h4 className="font-medium text-surface-900 dark:text-surface-100">{title}</h4>
      </div>

      <p className="text-2xl font-bold text-surface-900 dark:text-surface-100 mb-3">
        {value}
      </p>

      <div className="space-y-1">
        {breakdown.map((item) => (
          <div key={item.label} className="flex justify-between text-sm">
            <span className="text-surface-500 dark:text-surface-400">{item.label}</span>
            <span className="font-medium text-surface-700 dark:text-surface-300">
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

### 5. ComplianceProfileBadge Component

**Purpose:** Indicate when settings are locked by compliance requirements.

**Visual Specification:**

```jsx
function ComplianceProfileBadge({ profile, lockedSettings }) {
  const profileConfig = {
    cmmc_l2: { label: 'CMMC Level 2', color: 'olive' },
    soc2: { label: 'SOC 2', color: 'aura' },
    fedramp_high: { label: 'FedRAMP High', color: 'critical' },
  };

  const config = profileConfig[profile];

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg
                    bg-surface-50 dark:bg-surface-700/50
                    border border-surface-200 dark:border-surface-600">
      <LockClosedIcon className="w-4 h-4 text-surface-500" />
      <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
        {config.label} Active
      </span>
      <Tooltip content={`${lockedSettings.length} settings are locked by compliance requirements`}>
        <InformationCircleIcon className="w-4 h-4 text-surface-400" />
      </Tooltip>
    </div>
  );
}
```

**Locked Setting Indicator:**

```jsx
function LockedSettingIndicator({ setting, complianceProfile }) {
  return (
    <div className="relative">
      <div className="opacity-50 pointer-events-none">
        {/* Original setting control */}
      </div>
      <div className="absolute inset-0 flex items-center justify-center
                      bg-surface-100/80 dark:bg-surface-800/80 rounded-lg">
        <div className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400">
          <LockClosedIcon className="w-4 h-4" />
          <span>Locked by {complianceProfile}</span>
        </div>
      </div>
    </div>
  );
}
```

---

## ADR-068: Explainability Dashboard

### Overview

The Explainability Dashboard provides human-readable visibility into AI decision-making processes. It enables users to explore reasoning chains, view alternatives considered, understand confidence levels, and identify any contradictions.

### Components Required

1. **ExplainabilityDashboard.jsx** - Main dashboard container
2. **DecisionExplorer.jsx** - Search and filter decisions
3. **ReasoningViewer.jsx** - Step-by-step reasoning display
4. **AlternativesComparison.jsx** - Side-by-side alternative comparison
5. **ConfidenceVisualization.jsx** - Confidence intervals and calibration
6. **ContradictionAlerts.jsx** - Contradiction detection alerts
7. **InterAgentTrustGraph.jsx** - Agent trust relationships

---

### 1. DecisionExplorer Component

**Purpose:** Search, filter, and browse AI decisions with full audit trail.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Decision Explorer                                          [Export]  [Filter]  |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Search decisions...                                          [Search]  |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Filters:  [Agent: All v]  [Severity: All v]  [Time: Last 24h v]  [Clear]       |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Decision                      Agent       Confidence   Time            |     |
|  +------------------------------------------------------------------------+     |
|  |  [>] Apply security patch      Coder       87%          2m ago          |     |
|  |      to CVE-2024-1234          Agent                    [View]          |     |
|  |      SIGNIFICANT                                                        |     |
|  +------------------------------------------------------------------------+     |
|  |  [>] Reject code change        Reviewer    92%          15m ago         |     |
|  |      for input validation      Agent                    [View]          |     |
|  |      NORMAL                                                             |     |
|  +------------------------------------------------------------------------+     |
|  |  [!] Approve credentials       Validator   71%          1h ago          |     |
|  |      access request            Agent                    [View]          |     |
|  |      CRITICAL   [Contradiction Detected]                                |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Showing 1-20 of 847 decisions                        [< Prev] [1] [2] [Next >] |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Decision Row Component:**

```jsx
function DecisionRow({ decision, onSelect, isExpanded }) {
  const severityColors = {
    trivial: 'bg-surface-100 text-surface-600',
    normal: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    significant: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
  };

  return (
    <div className={`
      border-b border-surface-200 dark:border-surface-700
      hover:bg-surface-50 dark:hover:bg-surface-800/50
      transition-colors cursor-pointer
      ${decision.hasContradiction ? 'bg-critical-50 dark:bg-critical-900/10' : ''}
    `}>
      <div className="flex items-center gap-4 px-4 py-3" onClick={() => onSelect(decision)}>
        <button className="p-1">
          {isExpanded ? (
            <ChevronDownIcon className="w-5 h-5 text-surface-400" />
          ) : (
            <ChevronRightIcon className="w-5 h-5 text-surface-400" />
          )}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-surface-900 dark:text-surface-100 truncate">
              {decision.summary}
            </p>
            {decision.hasContradiction && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full
                             bg-critical-100 dark:bg-critical-900/30
                             text-critical-700 dark:text-critical-400 text-xs">
                <ExclamationTriangleIcon className="w-3 h-3" />
                Contradiction
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColors[decision.severity]}`}>
              {decision.severity.toUpperCase()}
            </span>
          </div>
        </div>

        <div className="text-sm text-surface-500 dark:text-surface-400">
          {decision.agentName}
        </div>

        <ConfidenceBadge value={decision.confidence} />

        <div className="text-sm text-surface-500 dark:text-surface-400 w-24 text-right">
          {formatRelativeTime(decision.timestamp)}
        </div>

        <button className="px-3 py-1 text-sm text-aura-600 dark:text-aura-400
                          hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded">
          View
        </button>
      </div>

      {isExpanded && (
        <div className="px-12 pb-4">
          <ReasoningViewer decision={decision} compact />
        </div>
      )}
    </div>
  );
}
```

---

### 2. ReasoningViewer Component

**Purpose:** Display step-by-step reasoning chains with evidence linking.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Reasoning Chain                                                    [Expand All]|
+--------------------------------------------------------------------------------+
|                                                                                  |
|  Input: "Apply security patch for CVE-2024-1234 in authentication module"       |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Step 1                                                        [95%]  |     |
|  |  -------------------------------------------------------------------- |     |
|  |  Identified vulnerability CVE-2024-1234 as a critical SQL injection   |     |
|  |  vulnerability in the authentication module.                          |     |
|  |                                                                        |     |
|  |  Evidence:                                                             |     |
|  |  - CVE database entry confirms CVSS 9.8 (Critical)                    |     |
|  |  - Static analysis detected pattern in auth/login.py:147             |     |
|  |                                                                        |     |
|  |  References: [CVE-2024-1234] [auth/login.py]                          |     |
|  +------------------------------------------------------------------------+     |
|       |                                                                          |
|       v                                                                          |
|  +------------------------------------------------------------------------+     |
|  |  Step 2                                                        [88%]  |     |
|  |  -------------------------------------------------------------------- |     |
|  |  Generated parameterized query patch to replace string concatenation  |     |
|  |  with prepared statements.                                            |     |
|  |                                                                        |     |
|  |  Evidence:                                                             |     |
|  |  - OWASP remediation guidelines recommend prepared statements         |     |
|  |  - Semantic similarity to 47 successful patches in knowledge base     |     |
|  |                                                                        |     |
|  |  References: [OWASP Guide] [Patch #4521] [Patch #3892]                |     |
|  +------------------------------------------------------------------------+     |
|       |                                                                          |
|       v                                                                          |
|  +------------------------------------------------------------------------+     |
|  |  Step 3                                                        [92%]  |     |
|  |  -------------------------------------------------------------------- |     |
|  |  Validated patch in sandbox environment. All existing tests pass      |     |
|  |  (127/127), security regression tests pass (34/34).                   |     |
|  |                                                                        |     |
|  |  Evidence:                                                             |     |
|  |  - Sandbox execution log: PASS                                        |     |
|  |  - Test coverage maintained at 94.7%                                  |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Output: Recommend patch approval with HIGH confidence                          |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Reasoning Step Component:**

```jsx
function ReasoningStep({ step, isLast }) {
  return (
    <div className="relative">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-6 top-16 w-0.5 h-8 bg-surface-300 dark:bg-surface-600" />
      )}

      <div className="bg-white dark:bg-surface-800 rounded-xl border
                      border-surface-200 dark:border-surface-700 p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-aura-100 dark:bg-aura-900/30
                           flex items-center justify-center
                           text-aura-600 dark:text-aura-400 font-medium text-sm">
              {step.stepNumber}
            </div>
            <span className="font-medium text-surface-900 dark:text-surface-100">
              Step {step.stepNumber}
            </span>
          </div>
          <ConfidenceBadge value={step.confidence} size="sm" />
        </div>

        {/* Description */}
        <p className="text-surface-700 dark:text-surface-300 mb-4">
          {step.description}
        </p>

        {/* Evidence */}
        {step.evidence.length > 0 && (
          <div className="mb-4">
            <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400
                          uppercase tracking-wide mb-2">
              Evidence
            </h5>
            <ul className="space-y-1">
              {step.evidence.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-sm
                                      text-surface-600 dark:text-surface-400">
                  <CheckCircleIcon className="w-4 h-4 text-olive-500 flex-shrink-0 mt-0.5" />
                  {e}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* References */}
        {step.references.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-surface-500 dark:text-surface-400">References:</span>
            {step.references.map((ref, i) => (
              <button
                key={i}
                className="px-2 py-1 text-xs rounded bg-surface-100 dark:bg-surface-700
                          text-aura-600 dark:text-aura-400 hover:bg-aura-50
                          dark:hover:bg-aura-900/20 transition-colors"
              >
                {ref}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### 3. AlternativesComparison Component

**Purpose:** Show what alternatives were considered and why they were rejected.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Alternatives Considered                                                        |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  Comparison Criteria: Security, Performance, Maintainability, Compatibility     |
|                                                                                  |
|  +----------------------------+  +----------------------------+                  |
|  |  [*] Option A (Chosen)     |  |  [ ] Option B              |                  |
|  |  Parameterized Queries     |  |  Input Sanitization        |                  |
|  |                            |  |                            |                  |
|  |  Score: 92/100             |  |  Score: 76/100             |                  |
|  |                            |  |                            |                  |
|  |  + Complete SQL injection  |  |  + Simpler implementation  |                  |
|  |    prevention              |  |  + Lower code changes      |                  |
|  |  + Industry best practice  |  |                            |                  |
|  |  + Forward compatible      |  |  - Can be bypassed with    |                  |
|  |                            |  |    encoded payloads        |                  |
|  |  - Requires refactoring    |  |  - Not comprehensive       |                  |
|  |    existing queries        |  |    protection              |                  |
|  +----------------------------+  +----------------------------+                  |
|                                                                                  |
|  +----------------------------+  +----------------------------+                  |
|  |  [ ] Option C              |  |  [ ] Option D              |                  |
|  |  Stored Procedures         |  |  WAF Rules Only            |                  |
|  |                            |  |                            |                  |
|  |  Score: 84/100             |  |  Score: 58/100             |                  |
|  |                            |  |                            |                  |
|  |  Rejection: Database       |  |  Rejection: External       |                  |
|  |  vendor lock-in concerns   |  |  defense insufficient      |                  |
|  +----------------------------+  +----------------------------+                  |
|                                                                                  |
|  Decision Rationale:                                                             |
|  Parameterized queries provide the strongest protection against SQL injection   |
|  while maintaining code portability. The refactoring effort is justified by     |
|  the critical severity of the vulnerability.                                    |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Alternative Card Component:**

```jsx
function AlternativeCard({ alternative, isChosen }) {
  return (
    <div className={`
      rounded-xl border p-4 transition-all
      ${isChosen
        ? 'border-2 border-olive-500 bg-olive-50 dark:bg-olive-900/10'
        : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800'
      }
    `}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        {isChosen ? (
          <CheckCircleIcon className="w-5 h-5 text-olive-500" />
        ) : (
          <div className="w-5 h-5 rounded-full border-2 border-surface-300 dark:border-surface-600" />
        )}
        <span className="font-medium text-surface-900 dark:text-surface-100">
          {alternative.name}
        </span>
        {isChosen && (
          <span className="px-2 py-0.5 text-xs rounded-full bg-olive-100
                         dark:bg-olive-900/30 text-olive-700 dark:text-olive-400">
            Chosen
          </span>
        )}
      </div>

      <p className="text-sm text-surface-600 dark:text-surface-400 mb-3">
        {alternative.description}
      </p>

      {/* Score Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-surface-500">Score</span>
          <span className="font-medium text-surface-700 dark:text-surface-300">
            {alternative.score}/100
          </span>
        </div>
        <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              alternative.score >= 80 ? 'bg-olive-500' :
              alternative.score >= 60 ? 'bg-warning-500' : 'bg-critical-500'
            }`}
            style={{ width: `${alternative.score}%` }}
          />
        </div>
      </div>

      {/* Pros */}
      {alternative.pros.length > 0 && (
        <div className="mb-3">
          {alternative.pros.map((pro, i) => (
            <div key={i} className="flex items-start gap-2 text-sm mb-1">
              <PlusCircleIcon className="w-4 h-4 text-olive-500 flex-shrink-0 mt-0.5" />
              <span className="text-surface-600 dark:text-surface-400">{pro}</span>
            </div>
          ))}
        </div>
      )}

      {/* Cons */}
      {alternative.cons.length > 0 && (
        <div className="mb-3">
          {alternative.cons.map((con, i) => (
            <div key={i} className="flex items-start gap-2 text-sm mb-1">
              <MinusCircleIcon className="w-4 h-4 text-critical-500 flex-shrink-0 mt-0.5" />
              <span className="text-surface-600 dark:text-surface-400">{con}</span>
            </div>
          ))}
        </div>
      )}

      {/* Rejection Reason (for non-chosen) */}
      {!isChosen && alternative.rejectionReason && (
        <div className="mt-3 pt-3 border-t border-surface-200 dark:border-surface-700">
          <p className="text-xs text-surface-500 dark:text-surface-400">
            <span className="font-medium">Rejection:</span> {alternative.rejectionReason}
          </p>
        </div>
      )}
    </div>
  );
}
```

---

### 4. ConfidenceVisualization Component

**Purpose:** Display confidence intervals with uncertainty visualization.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Confidence Analysis                                                            |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  Overall Decision Confidence                                                     |
|                                                                                  |
|        +-------------------------------------------+                             |
|    0%  |         [====|======*======|====]        |  100%                       |
|        +-------------------------------------------+                             |
|                   71%    87%    94%                                             |
|                  Lower  Point  Upper                                            |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Uncertainty Sources                                                   |     |
|  |  -----------------------------------------------------------------    |     |
|  |  [!] Limited training data for similar vulnerabilities       +8%      |     |
|  |  [!] Novel code pattern not seen in knowledge base           +5%      |     |
|  |  [i] Partial test coverage in affected module                +3%      |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Calibration Status: Well-calibrated                                            |
|  Method: Ensemble disagreement + Monte Carlo dropout                            |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Confidence by Reasoning Step                                         |     |
|  |                                                                        |     |
|  |  Step 1: Identify vulnerability      [==================] 95%         |     |
|  |  Step 2: Generate patch              [===============]    88%         |     |
|  |  Step 3: Validate in sandbox         [=================]  92%         |     |
|  |  Step 4: Assess compatibility        [===========]        78%         |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Confidence Interval Visualization:**

```jsx
function ConfidenceIntervalChart({ interval }) {
  const { pointEstimate, lowerBound, upperBound } = interval;

  // Scale values to percentage positions
  const lower = lowerBound * 100;
  const point = pointEstimate * 100;
  const upper = upperBound * 100;

  return (
    <div className="relative pt-8 pb-4">
      {/* Scale labels */}
      <div className="absolute top-0 left-0 right-0 flex justify-between text-xs text-surface-400">
        <span>0%</span>
        <span>50%</span>
        <span>100%</span>
      </div>

      {/* Track */}
      <div className="relative h-8 bg-surface-200 dark:bg-surface-700 rounded-full">
        {/* Confidence range */}
        <div
          className="absolute top-1 bottom-1 bg-aura-200 dark:bg-aura-800 rounded-full"
          style={{ left: `${lower}%`, width: `${upper - lower}%` }}
        />

        {/* Point estimate marker */}
        <div
          className="absolute top-0 bottom-0 w-1 bg-aura-600"
          style={{ left: `${point}%` }}
        >
          <div className="absolute -top-6 left-1/2 -translate-x-1/2
                         px-2 py-1 rounded bg-aura-600 text-white text-xs font-medium">
            {point.toFixed(0)}%
          </div>
        </div>

        {/* Lower bound marker */}
        <div
          className="absolute top-2 bottom-2 w-0.5 bg-surface-400"
          style={{ left: `${lower}%` }}
        />

        {/* Upper bound marker */}
        <div
          className="absolute top-2 bottom-2 w-0.5 bg-surface-400"
          style={{ left: `${upper}%` }}
        />
      </div>

      {/* Value labels */}
      <div className="mt-2 flex justify-between text-xs">
        <span className="text-surface-500" style={{ marginLeft: `${lower}%` }}>
          {lower.toFixed(0)}%
        </span>
        <span className="text-surface-500" style={{ marginLeft: `${upper - lower}%` }}>
          {upper.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}
```

---

### 5. ContradictionAlerts Component

**Purpose:** Highlight and explain detected contradictions between reasoning and actions.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  [!] Contradiction Detected                                          [Dismiss] |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  Decision: #DEC-2024-5678                                                       |
|  Agent: Validator Agent                                                         |
|  Severity: MAJOR                                                                |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  What was claimed:                                                     |     |
|  |  "Selected Option A (Parameterized Queries) due to superior security   |     |
|  |   and industry best practice compliance."                              |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  What was done:                                                        |     |
|  |  Applied Option B (Input Sanitization) to the codebase.               |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Analysis:                                                             |     |
|  |  The stated reasoning indicated parameterized queries were chosen,    |     |
|  |  but the actual code change implements input sanitization. This       |     |
|  |  mismatch requires investigation.                                     |     |
|  |                                                                        |     |
|  |  Possible causes:                                                     |     |
|  |  - Reasoning chain generated before final decision                    |     |
|  |  - Action execution error                                             |     |
|  |  - Agent confusion or hallucination                                   |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Recommended Action: HITL Review Required                                       |
|                                                                                  |
|  [View Full Decision]  [Escalate to Security Team]  [Mark as Investigated]     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Contradiction Alert Component:**

```jsx
function ContradictionAlert({ contradiction, onDismiss, onEscalate, onInvestigate }) {
  const severityConfig = {
    minor: {
      bg: 'bg-warning-50 dark:bg-warning-900/10',
      border: 'border-warning-200 dark:border-warning-800',
      icon: 'text-warning-500'
    },
    moderate: {
      bg: 'bg-warning-50 dark:bg-warning-900/10',
      border: 'border-warning-300 dark:border-warning-700',
      icon: 'text-warning-600'
    },
    major: {
      bg: 'bg-critical-50 dark:bg-critical-900/10',
      border: 'border-critical-200 dark:border-critical-800',
      icon: 'text-critical-500'
    },
    critical: {
      bg: 'bg-critical-50 dark:bg-critical-900/10',
      border: 'border-critical-300 dark:border-critical-700',
      icon: 'text-critical-600'
    },
  };

  const config = severityConfig[contradiction.severity];

  return (
    <div className={`rounded-xl border-2 ${config.bg} ${config.border} overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3
                     border-b border-current/10">
        <div className="flex items-center gap-2">
          <ExclamationTriangleIcon className={`w-5 h-5 ${config.icon}`} />
          <span className="font-semibold text-surface-900 dark:text-surface-100">
            Contradiction Detected
          </span>
          <span className={`px-2 py-0.5 text-xs rounded-full font-medium
                          ${config.bg} ${config.icon}`}>
            {contradiction.severity.toUpperCase()}
          </span>
        </div>
        <button
          onClick={onDismiss}
          className="p-1 rounded hover:bg-surface-200 dark:hover:bg-surface-700"
        >
          <XMarkIcon className="w-5 h-5 text-surface-400" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Claimed */}
        <div>
          <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
            What was claimed
          </h4>
          <div className="p-3 rounded-lg bg-white dark:bg-surface-800 border
                         border-surface-200 dark:border-surface-700">
            <p className="text-sm text-surface-700 dark:text-surface-300 italic">
              "{contradiction.claimedAction}"
            </p>
          </div>
        </div>

        {/* Actual */}
        <div>
          <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
            What was done
          </h4>
          <div className="p-3 rounded-lg bg-white dark:bg-surface-800 border
                         border-surface-200 dark:border-surface-700">
            <p className="text-sm text-surface-700 dark:text-surface-300">
              {contradiction.actualAction}
            </p>
          </div>
        </div>

        {/* Analysis */}
        <div>
          <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
            Analysis
          </h4>
          <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-900">
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {contradiction.analysis}
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-4 py-3
                     border-t border-current/10 bg-surface-50 dark:bg-surface-900/50">
        <button className="px-3 py-1.5 text-sm font-medium text-aura-600
                          hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded">
          View Full Decision
        </button>
        <button
          onClick={onEscalate}
          className="px-3 py-1.5 text-sm font-medium text-critical-600
                    hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded"
        >
          Escalate to Security Team
        </button>
        <button
          onClick={onInvestigate}
          className="ml-auto px-3 py-1.5 text-sm font-medium bg-surface-200
                    dark:bg-surface-700 text-surface-700 dark:text-surface-300
                    hover:bg-surface-300 dark:hover:bg-surface-600 rounded"
        >
          Mark as Investigated
        </button>
      </div>
    </div>
  );
}
```

---

### 6. InterAgentTrustGraph Component

**Purpose:** Visualize trust relationships between agents.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Inter-Agent Trust Network                                   [Reset] [Fullscreen]|
+--------------------------------------------------------------------------------+
|                                                                                  |
|                           [Orchestrator]                                         |
|                               94%                                                |
|                            /   |   \                                             |
|                          /     |     \                                           |
|                        /       |       \                                         |
|                      /         |         \                                       |
|              [Coder]       [Reviewer]    [Validator]                            |
|                88%            92%           87%                                  |
|                  \             |           /                                     |
|                   \            |          /                                      |
|                    \           |         /                                       |
|                     \          |        /                                        |
|                      +----- [Context] -----+                                     |
|                              Service                                             |
|                               91%                                                |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Selected: Coder Agent                                                 |     |
|  |                                                                        |     |
|  |  Trust Score: 88%                                                      |     |
|  |  Verified Claims: 1,247 / 1,312 (95.0%)                               |     |
|  |  Failed Verifications: 65 (4.9%)                                       |     |
|  |  Last Verification: 2 minutes ago                                      |     |
|  |                                                                        |     |
|  |  Recent Trust Adjustments:                                             |     |
|  |  - -2% : Inconsistent security assessment (1h ago)                    |     |
|  |  - +1% : Accurate patch generation (3h ago)                           |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

This component can extend the existing `CapabilityGraph.jsx` pattern with trust-specific styling.

---

## ADR-071: Capability Graph Completion

### Status: COMPLETE (Jan 27, 2026)

All features have been implemented in the Capability Graph visualization:

**Completed Features:**
1. Escalation path highlighting with visual emphasis (red edges, arrowhead markers)
2. Advanced filtering controls (agent types, classifications, risk analysis)
3. Drill-down capability details (hover tooltips, detail drawer)

### Components Implemented

1. **CapabilityGraphFilters.jsx** - Filter panel for graph (469 lines)
2. **CapabilityGraph.jsx** - Enhanced with filter integration (1,204 lines)
3. **CapabilityDetailDrawer.jsx** - Slide-out detail panel

---

### 1. CapabilityGraphFilters Component

**Purpose:** Filter capabilities by classification, agent, or relationship type.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  Filters                                                            [Clear All] |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  Classification                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  [x] SAFE  [x] MONITORING  [x] DANGEROUS  [x] CRITICAL                |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Relationship Type                                                               |
|  +------------------------------------------------------------------------+     |
|  |  [x] HAS_CAPABILITY  [x] INHERITS_FROM  [x] DELEGATES_TO              |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Highlight Paths                                                                 |
|  +------------------------------------------------------------------------+     |
|  |  [x] Show escalation paths     [x] Show toxic combinations            |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  Agent Filter                                                                    |
|  +------------------------------------------------------------------------+     |
|  |  [Search agents...]                                              [v]  |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Filter Panel Component:**

```jsx
function CapabilityGraphFilters({ filters, onChange, onClear }) {
  const classifications = ['safe', 'monitoring', 'dangerous', 'critical'];
  const relationships = ['HAS_CAPABILITY', 'INHERITS_FROM', 'DELEGATES_TO'];

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border
                   border-surface-200 dark:border-surface-700 p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-surface-900 dark:text-surface-100">Filters</h3>
        <button
          onClick={onClear}
          className="text-sm text-aura-600 hover:text-aura-700"
        >
          Clear All
        </button>
      </div>

      {/* Classification Filter */}
      <div>
        <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
          Classification
        </h4>
        <div className="flex flex-wrap gap-2">
          {classifications.map((cls) => (
            <FilterChip
              key={cls}
              label={cls.toUpperCase()}
              active={filters.classifications.includes(cls)}
              color={NODE_COLORS[cls]}
              onChange={(active) => {
                const newClassifications = active
                  ? [...filters.classifications, cls]
                  : filters.classifications.filter(c => c !== cls);
                onChange({ ...filters, classifications: newClassifications });
              }}
            />
          ))}
        </div>
      </div>

      {/* Relationship Type Filter */}
      <div>
        <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
          Relationship Type
        </h4>
        <div className="flex flex-wrap gap-2">
          {relationships.map((rel) => (
            <FilterChip
              key={rel}
              label={rel.replace('_', ' ')}
              active={filters.relationships.includes(rel)}
              onChange={(active) => {
                const newRelationships = active
                  ? [...filters.relationships, rel]
                  : filters.relationships.filter(r => r !== rel);
                onChange({ ...filters, relationships: newRelationships });
              }}
            />
          ))}
        </div>
      </div>

      {/* Path Highlighting */}
      <div>
        <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
          Highlight Paths
        </h4>
        <div className="space-y-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={filters.showEscalationPaths}
              onChange={(e) => onChange({ ...filters, showEscalationPaths: e.target.checked })}
              className="rounded border-surface-300 text-critical-600 focus:ring-critical-500"
            />
            <span className="text-sm text-surface-700 dark:text-surface-300">
              Show escalation paths
            </span>
            <span className="w-3 h-0.5 bg-critical-500" />
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={filters.showToxicCombinations}
              onChange={(e) => onChange({ ...filters, showToxicCombinations: e.target.checked })}
              className="rounded border-surface-300 text-warning-600 focus:ring-warning-500"
            />
            <span className="text-sm text-surface-700 dark:text-surface-300">
              Show toxic combinations
            </span>
            <span className="w-3 h-0.5 bg-warning-500 border-dashed border-t-2 border-warning-500" />
          </label>
        </div>
      </div>
    </div>
  );
}

function FilterChip({ label, active, color, onChange }) {
  return (
    <button
      onClick={() => onChange(!active)}
      className={`
        px-3 py-1.5 rounded-full text-xs font-medium transition-all
        ${active
          ? 'text-white'
          : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400'
        }
      `}
      style={active ? { backgroundColor: color } : {}}
    >
      {label}
    </button>
  );
}
```

---

### 2. EscalationPathHighlighter Enhancement

**Purpose:** Visually emphasize escalation paths in the graph.

**Visual Specification:**

Escalation paths should be rendered with:
- **Thicker stroke:** 3px vs 1px normal
- **Dashed pattern:** `strokeDasharray="8,4"`
- **Red color:** `#DC2626`
- **Animated pulse:** Subtle pulsing animation
- **Path label:** "Escalation Risk" tooltip on hover

**Implementation Enhancement (for existing CapabilityGraph.jsx):**

```jsx
// Add to edges rendering in CapabilityGraph.jsx
{edges.map((edge, i) => {
  const sourcePos = positions[edge.source];
  const targetPos = positions[edge.target];
  if (!sourcePos || !targetPos) return null;

  const isEscalation = edge.is_escalation_path;
  const isToxic = edge.is_toxic_combination;

  return (
    <g key={`edge-${i}`}>
      {/* Glow effect for escalation paths */}
      {isEscalation && (
        <line
          x1={sourcePos.x}
          y1={sourcePos.y}
          x2={targetPos.x}
          y2={targetPos.y}
          stroke="#DC2626"
          strokeWidth={6}
          opacity={0.3}
          className="animate-pulse"
        />
      )}

      {/* Main edge */}
      <line
        x1={sourcePos.x}
        y1={sourcePos.y}
        x2={targetPos.x}
        y2={targetPos.y}
        stroke={isEscalation ? '#DC2626' : isToxic ? '#F59E0B' : '#4B5563'}
        strokeWidth={isEscalation ? 3 : isToxic ? 2 : 1}
        strokeDasharray={isEscalation ? '8,4' : isToxic ? '4,4' : 'none'}
        opacity={0.8}
        markerEnd={isEscalation ? 'url(#arrowhead-critical)' : 'url(#arrowhead)'}
      />

      {/* Animated dots for escalation paths */}
      {isEscalation && (
        <circle r="3" fill="#DC2626">
          <animateMotion
            dur="2s"
            repeatCount="indefinite"
            path={`M${sourcePos.x},${sourcePos.y} L${targetPos.x},${targetPos.y}`}
          />
        </circle>
      )}
    </g>
  );
})}
```

---

### 3. CapabilityDetailDrawer Component

**Purpose:** Show detailed capability information in a slide-out panel.

**Visual Specification:**

```
+--------------------------------------------------------------------------------+
|  [<] Capability Details                                                         |
+--------------------------------------------------------------------------------+
|                                                                                  |
|  [CRITICAL]  delete_file                                                        |
|                                                                                  |
|  Risk Score: 95/100                                                             |
|  [==================================================]                           |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Description                                                           |     |
|  |  Permanently deletes files from the repository. This action is        |     |
|  |  irreversible and requires HITL approval.                             |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Agents with this Capability                                          |     |
|  |  -----------------------------------------------------------------    |     |
|  |  Agent                    Grant Type     Expires                      |     |
|  |  Coder Agent              Permanent      -                            |     |
|  |  DevOps Agent             Temporary      2024-02-15                   |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Required Capabilities                                                 |     |
|  |  -----------------------------------------------------------------    |     |
|  |  [read_file] Prerequisite                                             |     |
|  |  [write_file] Prerequisite                                            |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Conflicts With                                                        |     |
|  |  -----------------------------------------------------------------    |     |
|  |  [create_credentials] Separation of duties violation                  |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
|  +------------------------------------------------------------------------+     |
|  |  Recent Usage (Last 7 Days)                                           |     |
|  |  -----------------------------------------------------------------    |     |
|  |  Total Invocations: 12                                                |     |
|  |  HITL Approvals: 12 (100%)                                            |     |
|  |  Avg Response Time: 4.2 minutes                                       |     |
|  +------------------------------------------------------------------------+     |
|                                                                                  |
+--------------------------------------------------------------------------------+
```

**Drawer Component:**

```jsx
function CapabilityDetailDrawer({ capability, isOpen, onClose }) {
  if (!capability) return null;

  const classificationColors = {
    safe: { bg: 'bg-olive-100 dark:bg-olive-900/30', text: 'text-olive-700 dark:text-olive-400' },
    monitoring: { bg: 'bg-warning-100 dark:bg-warning-900/30', text: 'text-warning-700 dark:text-warning-400' },
    dangerous: { bg: 'bg-high-100 dark:bg-high-900/30', text: 'text-high-700 dark:text-high-400' },
    critical: { bg: 'bg-critical-100 dark:bg-critical-900/30', text: 'text-critical-700 dark:text-critical-400' },
  };

  const colors = classificationColors[capability.classification] || classificationColors.safe;

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div className={`
        fixed inset-y-0 right-0 w-full max-w-md bg-white dark:bg-surface-900
        shadow-xl z-50 transform transition-transform duration-300
        ${isOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b
                       border-surface-200 dark:border-surface-700">
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800"
          >
            <ChevronLeftIcon className="w-5 h-5 text-surface-500" />
          </button>
          <h2 className="font-semibold text-surface-900 dark:text-surface-100">
            Capability Details
          </h2>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 overflow-y-auto h-[calc(100%-60px)]">
          {/* Title & Classification */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-1 text-xs font-medium rounded ${colors.bg} ${colors.text}`}>
                {capability.classification.toUpperCase()}
              </span>
            </div>
            <h3 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
              {capability.name}
            </h3>
          </div>

          {/* Risk Score */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-surface-500">Risk Score</span>
              <span className="font-medium text-surface-700 dark:text-surface-300">
                {capability.riskScore}/100
              </span>
            </div>
            <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  capability.riskScore >= 80 ? 'bg-critical-500' :
                  capability.riskScore >= 60 ? 'bg-warning-500' :
                  capability.riskScore >= 40 ? 'bg-high-500' : 'bg-olive-500'
                }`}
                style={{ width: `${capability.riskScore}%` }}
              />
            </div>
          </div>

          {/* Description */}
          <DetailSection title="Description">
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {capability.description}
            </p>
          </DetailSection>

          {/* Agents with Capability */}
          <DetailSection title="Agents with this Capability">
            <div className="space-y-2">
              {capability.agents?.map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-2 rounded-lg
                            bg-surface-50 dark:bg-surface-800"
                >
                  <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
                    {agent.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-500">
                      {agent.grantType}
                    </span>
                    {agent.expires && (
                      <span className="text-xs text-warning-600">
                        Expires {agent.expires}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </DetailSection>

          {/* Required Capabilities */}
          {capability.requires?.length > 0 && (
            <DetailSection title="Required Capabilities">
              <div className="flex flex-wrap gap-2">
                {capability.requires.map((req) => (
                  <span
                    key={req}
                    className="px-2 py-1 text-xs rounded bg-aura-100 dark:bg-aura-900/30
                              text-aura-700 dark:text-aura-400"
                  >
                    {req}
                  </span>
                ))}
              </div>
            </DetailSection>
          )}

          {/* Conflicts */}
          {capability.conflicts?.length > 0 && (
            <DetailSection title="Conflicts With">
              <div className="space-y-2">
                {capability.conflicts.map((conflict) => (
                  <div
                    key={conflict.capability}
                    className="flex items-center gap-2 p-2 rounded-lg
                              bg-critical-50 dark:bg-critical-900/20"
                  >
                    <ExclamationTriangleIcon className="w-4 h-4 text-critical-500" />
                    <span className="text-sm text-critical-700 dark:text-critical-400">
                      {conflict.capability}
                    </span>
                    <span className="text-xs text-surface-500">
                      ({conflict.reason})
                    </span>
                  </div>
                ))}
              </div>
            </DetailSection>
          )}
        </div>
      </div>
    </>
  );
}

function DetailSection({ title, children }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-lg border
                   border-surface-200 dark:border-surface-700 p-4">
      <h4 className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-3">
        {title}
      </h4>
      {children}
    </div>
  );
}
```

---

## Shared Components

### ConfidenceBadge

Used across Explainability Dashboard and other contexts.

```jsx
function ConfidenceBadge({ value, size = 'md' }) {
  const percentage = Math.round(value * 100);

  const getColor = () => {
    if (percentage >= 90) return 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400';
    if (percentage >= 75) return 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400';
    if (percentage >= 60) return 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400';
    return 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400';
  };

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <span className={`rounded-full font-medium ${getColor()} ${sizeClasses[size]}`}>
      {percentage}%
    </span>
  );
}
```

### Tooltip

Reusable tooltip for contextual help.

```jsx
function Tooltip({ content, children, position = 'top' }) {
  const [isVisible, setIsVisible] = useState(false);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        {children}
      </div>
      {isVisible && (
        <div className={`
          absolute z-50 ${positionClasses[position]}
          px-2 py-1 text-xs text-white bg-surface-900 dark:bg-surface-100
          dark:text-surface-900 rounded shadow-lg whitespace-nowrap
        `}>
          {content}
          {/* Arrow */}
          <div className={`
            absolute w-2 h-2 bg-surface-900 dark:bg-surface-100
            transform rotate-45
            ${position === 'top' ? 'top-full -mt-1 left-1/2 -translate-x-1/2' : ''}
            ${position === 'bottom' ? 'bottom-full -mb-1 left-1/2 -translate-x-1/2' : ''}
          `} />
        </div>
      )}
    </div>
  );
}
```

---

## Implementation Roadmap

### Phase 1: ADR-069 Guardrail Configuration UI (3-4 Sprints)

| Sprint | Deliverables |
|--------|-------------|
| Sprint 1 | SecurityProfileSelector, basic GuardrailSettings page, API integration |
| Sprint 2 | AdvancedGuardrailSettings, slider/segmented controls, validation |
| Sprint 3 | GuardrailActivityDashboard widget, metrics integration |
| Sprint 4 | ImpactPreviewModal, ComplianceProfileBadge, audit logging |

### Phase 2: ADR-068 Explainability Dashboard (4-6 Sprints)

| Sprint | Deliverables |
|--------|-------------|
| Sprint 1 | DecisionExplorer with search/filter, basic table |
| Sprint 2 | ReasoningViewer with step rendering, evidence linking |
| Sprint 3 | AlternativesComparison, side-by-side cards |
| Sprint 4 | ConfidenceVisualization, interval charts |
| Sprint 5 | ContradictionAlerts, escalation workflow |
| Sprint 6 | InterAgentTrustGraph, polish and integration |

### Phase 3: ADR-071 Capability Graph Completion - COMPLETE (Jan 27, 2026)

| Sprint | Deliverables | Status |
|--------|-------------|--------|
| Sprint 1 | CapabilityGraphFilters, enhanced escalation highlighting | COMPLETE |
| Sprint 2 | CapabilityDetailDrawer, drill-down integration | COMPLETE |

**Implementation Summary:**
- Agent Type filters: Coder, Reviewer, Validator, Security, Orchestrator checkboxes
- Tool Classification badges: SAFE (green), MONITORING (amber), DANGEROUS (orange), CRITICAL (red)
- Risk Analysis toggles: Show Escalation Paths, Highlight Coverage Gaps, Show Toxic Combinations
- Risk Threshold slider (0-100%) for escalation path filtering
- Visual indicators: Red edges for escalation paths, amber "?" badges for coverage gaps, pulsing red ring for toxic combinations
- Dynamic legend showing active indicator explanations

---

## Accessibility Checklist

All components must meet WCAG 2.1 AA standards:

- [ ] Color contrast 4.5:1 minimum for all text
- [ ] Interactive elements have 44px minimum touch targets
- [ ] All controls keyboard accessible (Tab, Enter, Escape)
- [ ] Focus indicators visible (2px ring)
- [ ] ARIA labels for icon-only buttons
- [ ] Screen reader-friendly table structure
- [ ] Reduced motion support (`prefers-reduced-motion`)
- [ ] Form inputs have associated labels
- [ ] Error messages linked to inputs via `aria-describedby`

---

## File Structure

```
frontend/src/components/
├── guardrails/
│   ├── GuardrailSettings.jsx
│   ├── SecurityProfileSelector.jsx
│   ├── AdvancedGuardrailSettings.jsx
│   ├── GuardrailActivityDashboard.jsx
│   ├── ComplianceProfileBadge.jsx
│   ├── ImpactPreviewModal.jsx
│   ├── GuardrailAuditLog.jsx
│   └── index.js
├── explainability/
│   ├── ExplainabilityDashboard.jsx
│   ├── DecisionExplorer.jsx
│   ├── ReasoningViewer.jsx
│   ├── AlternativesComparison.jsx
│   ├── ConfidenceVisualization.jsx
│   ├── ContradictionAlerts.jsx
│   ├── InterAgentTrustGraph.jsx
│   └── index.js
├── capability/
│   ├── CapabilityGraph.jsx (existing, enhance)
│   ├── CapabilityGraphFilters.jsx
│   ├── CapabilityDetailDrawer.jsx
│   ├── useCapabilityGraph.js (existing)
│   └── index.js
└── shared/
    ├── ConfidenceBadge.jsx
    ├── Tooltip.jsx
    ├── SegmentedControl.jsx
    ├── FilterChip.jsx
    └── index.js
```

---

## References

- Project Aura Design Principles: `/agent-config/design-workflows/design-principles.md`
- App UI Blueprint: `/agent-config/design-workflows/app-ui-blueprint.md`
- ADR-064 Dashboard Widgets: `/docs/architecture-decisions/ADR-064-customizable-dashboard-widgets.md`
- ADR-068 Explainability Framework: `/docs/architecture-decisions/ADR-068-universal-explainability-framework.md`
- ADR-069 Guardrail Configuration: `/docs/architecture-decisions/ADR-069-guardrail-configuration-ui.md`
- ADR-071 Capability Graph: `/docs/architecture-decisions/ADR-071-cross-agent-capability-graph.md`
- Existing Components: `/frontend/src/components/` (AlignmentDashboard, SecurityAlertSettings, CapabilityGraph)

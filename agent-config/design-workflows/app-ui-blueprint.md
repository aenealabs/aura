# Project Aura: App UI Blueprint

> Comprehensive UI/UX design plan for the Project Aura enterprise platform.
>
> **Last Updated:** 2025-12-14
> **Status:** Planning
> **Related:** [design-principles.md](./design-principles.md), [design-review-workflow.md](./design-review-workflow.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [User Personas](#2-user-personas)
3. [Core Workflows](#3-core-workflows)
4. [UI Screen Inventory](#4-ui-screen-inventory)
5. [Key UI Components](#5-key-ui-components)
6. [Interaction Patterns](#6-interaction-patterns)
7. [Design Recommendations](#7-design-recommendations)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Executive Summary

### What is Project Aura?

Project Aura is an enterprise-grade autonomous AI SaaS platform designed to reason across entire enterprise codebases. It functions as an "AI DevSecOps co-pilot" that:

- **Detects** security vulnerabilities automatically via threat intelligence and code scanning
- **Generates** patches using AI agents (Coder, Reviewer, Validator)
- **Tests** patches in isolated sandbox environments
- **Routes** critical changes through human-in-the-loop (HITL) approval workflows
- **Deploys** approved patches with full audit trails

### Core Value Proposition

| Capability | Benefit |
|------------|---------|
| Autonomous vulnerability detection | 80% of security patching automated |
| Code-aware incident response | LLM-powered root cause analysis (RCA) |
| Hybrid GraphRAG architecture | Structural + semantic code understanding |
| Compliance-ready | CMMC Level 3, SOX, NIST 800-53, FedRAMP |
| Human oversight | Full audit trails for critical decisions |

### Platform Differentiators

1. **Code Intelligence:** Full visibility into codebases via Code Knowledge Graph Entity (CKGE)
2. **GovCloud Ready:** Designed for defense and federal deployments from day one
3. **Adaptive Security Intelligence:** Proactive threat monitoring with automated remediation
4. **Dual-Track Architecture:** Defense mode (air-gapped) and Enterprise mode (full integrations)

---

## 2. User Personas

### Persona 1: Security Engineer (Primary)

| Attribute | Details |
|-----------|---------|
| **Role** | Senior Security Engineer at a defense contractor |
| **Goals** | Quickly triage vulnerabilities, approve/reject AI-generated patches, maintain compliance audit trails |
| **Pain Points** | Overwhelmed by alert volume, manual patch review is time-consuming, fear of deploying untested changes |
| **Key Workflows** | Patch approval, sandbox test review, incident investigation, compliance reporting |
| **Success Metrics** | Mean Time to Remediation (MTTR), approval throughput, zero production incidents from approved patches |

**User Story:** "As a Security Engineer, I need to review AI-generated patches with full context so I can confidently approve or reject them without spending hours on manual analysis."

### Persona 2: DevOps Engineer (Secondary)

| Attribute | Details |
|-----------|---------|
| **Role** | Platform engineer managing CI/CD and infrastructure |
| **Goals** | Ensure smooth deployments, monitor agent health, integrate security into pipelines |
| **Pain Points** | Alert fatigue, unclear deployment status, difficult rollback procedures |
| **Key Workflows** | Monitor agent orchestration, review deployment correlations, configure integrations |
| **Success Metrics** | Deployment success rate, agent uptime, pipeline velocity |

**User Story:** "As a DevOps Engineer, I need visibility into agent status and deployment pipelines so I can quickly identify and resolve issues."

### Persona 3: Platform Administrator (Tertiary)

| Attribute | Details |
|-----------|---------|
| **Role** | IT administrator or compliance officer |
| **Goals** | Configure security policies, manage user access, ensure compliance posture |
| **Pain Points** | Complex compliance requirements, audit preparation burden, policy enforcement gaps |
| **Key Workflows** | Configure integration modes, set HITL policies, generate compliance reports |
| **Success Metrics** | Compliance audit pass rate, policy adherence, configuration drift |

**User Story:** "As a Platform Admin, I need to configure security policies and generate compliance reports so the organization stays audit-ready."

### Persona 4: Engineering Leadership (Observer)

| Attribute | Details |
|-----------|---------|
| **Role** | VP of Engineering or CISO |
| **Goals** | Understand ROI of AI automation, track security posture, justify investment |
| **Pain Points** | Lack of visibility into AI effectiveness, difficulty measuring productivity gains |
| **Key Workflows** | Review dashboards, analyze trends, approve major configuration changes |
| **Success Metrics** | Engineering hours saved, vulnerability remediation rate, cost per patch |

**User Story:** "As a CISO, I need executive dashboards showing security posture trends so I can report to the board and justify continued investment."

---

## 3. Core Workflows

### 3.1 Primary Workflow: Vulnerability Detection to Production Deployment

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  [1] DETECTION                                                          │
│       │                                                                 │
│       └──► Threat Intelligence Feed / Code Scan / Runtime Alert         │
│                                                                         │
│  [2] ANALYSIS                                                           │
│       │                                                                 │
│       ├──► GraphRAG Context Retrieval (Neptune + OpenSearch)            │
│       └──► Code Impact Analysis (AST Parser, Dependency Graph)          │
│                                                                         │
│  [3] PATCH GENERATION                                                   │
│       │                                                                 │
│       ├──► Coder Agent generates fix                                    │
│       └──► Reviewer Agent validates correctness                         │
│                                                                         │
│  [4] SANDBOX TESTING                    ◄── User Touchpoint: Monitor    │
│       │                                                                 │
│       ├──► Isolated ECS/Fargate environment provisioned                 │
│       ├──► Test suite executed (unit, integration, security)            │
│       └──► Results recorded in DynamoDB                                 │
│                                                                         │
│  [5] HITL APPROVAL                      ◄── User Touchpoint: Decide     │
│       │                                                                 │
│       ├──► Notification sent (email, Slack, dashboard alert)            │
│       ├──► Security engineer reviews:                                   │
│       │     • Original vulnerability                                    │
│       │     • AI-generated patch (diff view)                            │
│       │     • Sandbox test results                                      │
│       │     • Deployment plan                                           │
│       └──► Decision: APPROVE / REJECT / REQUEST CHANGES                 │
│                                                                         │
│  [6] PRODUCTION DEPLOYMENT              ◄── User Touchpoint: Verify     │
│       │                                                                 │
│       ├──► CI/CD pipeline triggered                                     │
│       ├──► Canary/progressive rollout via ArgoCD                        │
│       └──► Post-deployment monitoring (24 hours)                        │
│                                                                         │
│  [7] AUDIT & REPORTING                  ◄── User Touchpoint: Review     │
│       │                                                                 │
│       ├──► Immutable audit log recorded                                 │
│       └──► Compliance report generated                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Secondary Workflow: Runtime Incident Investigation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  [1] INCIDENT ALERT                                                     │
│       │                                                                 │
│       └──► CloudWatch Alarm / PagerDuty / Datadog alert                 │
│                                                                         │
│  [2] CORRELATION                                                        │
│       │                                                                 │
│       ├──► Query Neptune for code entities in stack trace               │
│       ├──► Query OpenSearch for recent deployments/changes              │
│       └──► Correlate with deployment history (ArgoCD, CodeBuild)        │
│                                                                         │
│  [3] RCA GENERATION                     ◄── AI-Powered                  │
│       │                                                                 │
│       ├──► RuntimeIncidentAgent calls Bedrock LLM                       │
│       ├──► Generates hypothesis with confidence score (0-100%)          │
│       └──► Produces mitigation plan with rollback strategies            │
│                                                                         │
│  [4] HITL REVIEW                        ◄── User Touchpoint: Decide     │
│       │                                                                 │
│       ├──► Engineer reviews RCA hypothesis                              │
│       ├──► Reviews code entities and deployment correlation             │
│       └──► Approves/rejects mitigation plan                             │
│                                                                         │
│  [5] REMEDIATION                                                        │
│       │                                                                 │
│       ├──► If approved: Execute mitigation (auto or manual)             │
│       └──► If rejected: Escalate for manual investigation               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Tertiary Workflow: Code Knowledge Graph Exploration

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  [1] REPOSITORY INGESTION                                               │
│       │                                                                 │
│       └──► Git webhook triggers ingestion pipeline                      │
│                                                                         │
│  [2] CODE PARSING                                                       │
│       │                                                                 │
│       ├──► AST Parser extracts entities (files, classes, functions)     │
│       └──► Dependency analyzer maps relationships                       │
│                                                                         │
│  [3] GRAPH CONSTRUCTION                                                 │
│       │                                                                 │
│       ├──► Neptune stores structural relationships                      │
│       └──► OpenSearch indexes semantic embeddings                       │
│                                                                         │
│  [4] EXPLORATION                        ◄── User Touchpoint: Explore    │
│       │                                                                 │
│       ├──► Interactive graph visualization                              │
│       ├──► Search by entity name, type, or semantic query               │
│       └──► Filter by file path, complexity, or change frequency         │
│                                                                         │
│  [5] ANALYSIS                           ◄── User Touchpoint: Analyze    │
│       │                                                                 │
│       ├──► View entity details and relationships                        │
│       ├──► Identify high-risk code areas                                │
│       └──► Track vulnerability associations                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. UI Screen Inventory

### 4.1 Currently Implemented

| Screen | Route | Purpose | Status |
|--------|-------|---------|--------|
| **Dashboard** | `/` | Overview metrics, activity feed, quick actions | Placeholder |
| **Projects (CKGE Console)** | `/projects` | Code Knowledge Graph exploration | Basic |
| **Approval Dashboard** | `/approvals` | Review and approve/reject security patches | Complete |
| **Incident Investigations** | `/incidents` | Code-aware RCA with HITL approval | Complete |
| **Settings** | `/settings` | Platform configuration | Complete |
| **Collapsible Sidebar** | N/A | Persistent navigation | Complete |

### 4.2 Required Additional Screens

| Screen | Route | Priority | Purpose |
|--------|-------|----------|---------|
| **Dashboard (Full)** | `/` | P0 | Command center with metrics, trends, activity |
| **Vulnerability Management** | `/vulnerabilities` | P0 | Track all detected vulnerabilities |
| **Agent Orchestration** | `/agents` | P1 | Monitor AI agent activity and health |
| **Code Knowledge Graph** | `/graph` | P1 | Interactive CKGE visualization |
| **Sandbox Management** | `/sandboxes` | P2 | Manage test environments |
| **Audit Logs** | `/audit` | P2 | Compliance audit trail |
| **Compliance Dashboard** | `/compliance` | P2 | Compliance posture overview |
| **User Management** | `/users` | P3 | Admin user and role management |
| **Notifications Center** | `/notifications` | P3 | Unified notification management |

### 4.3 Screen Specifications

#### Dashboard (Full Implementation)

**Purpose:** Command center providing at-a-glance platform status

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  Dashboard                                              [Time Range ▼]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ Critical     │ │ Pending      │ │ Agents       │ │ Uptime       │   │
│  │ Vulns: 3     │ │ Approvals: 5 │ │ Active: 7/8  │ │ 99.9%        │   │
│  │ [+12% ↑]     │ │ [Urgent]     │ │ [1 idle]     │ │ [7 days]     │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                                         │
│  ┌────────────────────────────────┐ ┌────────────────────────────────┐ │
│  │  Vulnerability Trend (30d)    │ │  Recent Activity               │ │
│  │  ┌────────────────────────┐   │ │  ────────────────────────────  │ │
│  │  │    [Line Chart]        │   │ │  10:30 - Patch approved #142   │ │
│  │  │                        │   │ │  10:25 - Vuln detected CVE-... │ │
│  │  │                        │   │ │  10:15 - Agent completed task  │ │
│  │  └────────────────────────┘   │ │  10:05 - Sandbox provisioned   │ │
│  └────────────────────────────────┘ └────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Quick Actions                                                  │   │
│  │  [🔍 Run Full Scan] [⚠️ View Critical] [✅ Approval Queue]      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Components:**
- MetricCard (x4): Critical vulns, pending approvals, agent status, uptime
- LineChart: 30-day vulnerability trend
- ActivityFeed: Real-time event timeline
- QuickActionBar: Navigation shortcuts

#### Vulnerability Management

**Purpose:** Central hub for tracking and managing all detected vulnerabilities

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  Vulnerabilities                              [+ New Scan] [Export ▼]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [All] [Critical: 3] [High: 12] [Medium: 45] [Low: 89]          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────┬──────────┬────────────┬──────────────────┬────────┬───────┐  │
│  │ ☐    │ Severity │ CVE        │ Title            │ Status │ Date  │  │
│  ├──────┼──────────┼────────────┼──────────────────┼────────┼───────┤  │
│  │ ☐    │ CRITICAL │ CVE-2025-  │ SQL Injection in │ Open   │ 2h    │  │
│  │ ☐    │ HIGH     │ CVE-2025-  │ XSS in user inp  │ Patch  │ 5h    │  │
│  │ ☐    │ MEDIUM   │ N/A        │ Outdated depend  │ Open   │ 1d    │  │
│  └──────┴──────────┴────────────┴──────────────────┴────────┴───────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [Delete Selected] [Assign] [Change Status ▼]    Showing 1-20    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Table Columns:**

| Column | Width | Content |
|--------|-------|---------|
| Checkbox | 40px | Bulk select |
| Severity | 80px | Badge (Critical/High/Medium/Low) |
| CVE | 140px | CVE-XXXX-XXXXX or "N/A" |
| Title | Flexible | Vulnerability description |
| Status | 100px | Badge (Open/In Progress/Patched) |
| Affected | 150px | Service/file name |
| Detected | 100px | Relative time |
| Actions | 60px | Overflow menu |

#### Code Knowledge Graph

**Purpose:** Interactive visualization of codebase structure and relationships

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  Code Knowledge Graph                    [Search...        ] [Filters]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────┐ ┌───────────────────┐ │
│  │                                             │ │ Entity Details    │ │
│  │                                             │ │ ─────────────────│ │
│  │           [D3.js Force Graph]               │ │ Name: UserAuth    │ │
│  │                                             │ │ Type: Class       │ │
│  │      ○────○                                 │ │ File: auth.py:42  │ │
│  │     /      \                                │ │                   │ │
│  │    ○        ◇────○                          │ │ Connections: 12   │ │
│  │     \      /                                │ │ Complexity: High  │ │
│  │      ○────○                                 │ │                   │ │
│  │                                             │ │ Vulnerabilities:  │ │
│  │                                             │ │ • CVE-2025-1234   │ │
│  └─────────────────────────────────────────────┘ └───────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Show: [✓ Files] [✓ Classes] [✓ Functions] [○ Dependencies]     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Node Types:**
- **Files:** Circle, gray fill, size by LOC
- **Classes:** Rectangle, blue stroke, size by method count
- **Functions:** Diamond, orange stroke, size by complexity
- **Dependencies:** Dotted lines showing import relationships

**Interactions:**
- Hover: Tooltip with entity summary
- Click: Select node, show details in sidebar
- Drag: Reposition nodes
- Zoom: Mouse wheel or pinch gestures
- Search: Filter visible nodes by text
- Filter: Toggle visibility by entity type

#### Agent Orchestration

**Purpose:** Monitor and control AI agent activity

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent Orchestration                                        [Refresh]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  Coder       │ │  Reviewer    │ │  Validator   │ │  AST Parser  │   │
│  │  ● Active    │ │  ● Active    │ │  ○ Idle      │ │  ● Active    │   │
│  │  Task: CVE-  │ │  Task: —     │ │  Task: —     │ │  Task: repo  │   │
│  │  CPU: 45%    │ │  CPU: 12%    │ │  CPU: 0%     │ │  CPU: 78%    │   │
│  │  [Stop]      │ │  [Stop]      │ │  [Start]     │ │  [Stop]      │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  Graph Build │ │  Threat Int  │ │  Orchestratr │ │  Monitor     │   │
│  │  ● Active    │ │  ⚠ Error     │ │  ● Active    │ │  ● Active    │   │
│  │  Task: idx   │ │  Task: —     │ │  Task: coord │ │  Task: logs  │   │
│  │  CPU: 34%    │ │  CPU: 0%     │ │  CPU: 23%    │ │  CPU: 8%     │   │
│  │  [Stop]      │ │  [Restart]   │ │  [Stop]      │ │  [Stop]      │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Agent Logs                                          [Download] │   │
│  │  ─────────────────────────────────────────────────────────────  │   │
│  │  10:30:15 [Coder] Starting patch generation for CVE-2025-1234   │   │
│  │  10:30:12 [Reviewer] Validation complete, no issues found       │   │
│  │  10:30:08 [Orchestrator] Assigned task #142 to Coder agent      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Card States:**
- **Active:** Green indicator (●), pulsing animation
- **Idle:** Gray indicator (○), static
- **Error:** Red indicator (⚠), warning icon
- **Disabled:** Muted colors, disabled text

---

## 5. Key UI Components

### 5.1 Navigation & Layout

| Component | Purpose | Specs |
|-----------|---------|-------|
| `CollapsibleSidebar` | Primary navigation | 240px expanded, 64px collapsed, localStorage persistence |
| `TopBar` | Global search, notifications, user menu | 64px height, sticky |
| `PageHeader` | Page title, breadcrumbs, actions | Consistent padding |
| `ContentArea` | Main workspace container | Flex layout, overflow handling |
| `RightPanel` | Contextual details sidebar | 320px width, slide-in animation |

### 5.2 Data Display

| Component | Purpose | Specs |
|-----------|---------|-------|
| `MetricCard` | Key statistics display | Gradient top border, icon, value, trend |
| `DataTable` | Lists with sorting/filtering | Sticky headers, expandable rows |
| `StatusBadge` | Severity/status indicators | Pill shape, semantic colors |
| `ConfidenceBadge` | RCA confidence display | 0-100 scale, color thresholds |
| `DiffViewer` | Code change visualization | Syntax highlighting, line colors |
| `TimelineCard` | Activity/event timeline | Timestamp, user, action |

### 5.3 Interaction Components

| Component | Purpose | Specs |
|-----------|---------|-------|
| `ApprovalActionBar` | Approve/Reject buttons | Sticky bottom, confirmation |
| `FilterPills` | Quick status/severity filters | Toggle buttons with counts |
| `SearchInput` | Global and contextual search | Icon prefix, keyboard hints |
| `ToggleSwitch` | Boolean settings | 44px touch target |
| `SelectCard` | Mode/option selection | Border highlight, checkmark |

### 5.4 Feedback & Status

| Component | Purpose | Specs |
|-----------|---------|-------|
| `Toast` | Temporary notifications | Bottom-right, 3s auto-dismiss |
| `AlertBanner` | Page-level persistent alerts | Full-width, severity colors |
| `LoadingSpinner` | Async operation indicator | Indigo-500, center aligned |
| `SkeletonLoader` | Progressive loading | Shimmer animation |
| `EmptyState` | No data placeholder | Icon, message, CTA |

### 5.5 Data Visualization

| Component | Purpose | Library |
|-----------|---------|---------|
| `LineChart` | Trend visualization | Recharts |
| `BarChart` | Comparison visualization | Recharts |
| `DonutChart` | Distribution visualization | Recharts |
| `ForceGraph` | Code Knowledge Graph | D3.js |
| `HeatMap` | Activity patterns | D3.js |

---

## 6. Interaction Patterns

### 6.1 Master-Detail Layout

**Use Case:** Browsing lists with detailed preview (Approvals, Incidents)

```
┌──────────────────────┬─────────────────────────────────────────────────┐
│  List Sidebar        │     Detail Panel                                │
│  (384px fixed)       │     (fluid width)                               │
│                      │                                                 │
│  ┌────────────────┐  │   ┌─────────────────────────────────────────┐  │
│  │ Card 1         │  │   │  Header                                 │  │
│  └────────────────┘  │   ├─────────────────────────────────────────┤  │
│  ┌────────────────┐  │   │                                         │  │
│  │ Card 2 ◄───────│──│───│  Content Sections                       │  │
│  └────────────────┘  │   │                                         │  │
│  ┌────────────────┐  │   ├─────────────────────────────────────────┤  │
│  │ Card 3         │  │   │  [Reject]              [Approve]        │  │
│  └────────────────┘  │   └─────────────────────────────────────────┘  │
│                      │                                                 │
└──────────────────────┴─────────────────────────────────────────────────┘
```

**Behaviors:**
- Click card → Load details in panel
- Show loading state while fetching
- Actions sticky at bottom
- Optimistic UI updates on actions

### 6.2 Tabbed Configuration

**Use Case:** Organizing complex settings (Settings page)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Tab 1] [Tab 2] [Tab 3] [Tab 4]                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Section 1                                                      │   │
│  │  [Toggle] [Input] [Dropdown]                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Section 2                                                      │   │
│  │  [Selection Cards]                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Behaviors:**
- Tab navigation with underline indicator
- Content persists across tabs (no data loss)
- Real-time save with success toast
- Confirmation for destructive changes

### 6.3 HITL Approval Flow

**Critical Interaction:** Human decision on AI-generated content

**Step 1: Notification**
- Email/Slack with summary and direct link
- Dashboard indicator (badge on Approvals nav item)

**Step 2: Review**
1. Vulnerability context (CVE, severity, description)
2. AI-generated patch (syntax-highlighted diff)
3. Sandbox test results (pass/fail with logs)
4. Deployment plan (target environment, rollout strategy)

**Step 3: Decision**
- **Approve:** Single click, triggers deployment
- **Reject:** Requires reason (text input prompt)
- **Request Changes:** Opens comment form

**Step 4: Confirmation**
- Toast notification
- Optimistic UI update
- Background API call with error retry

### 6.4 Progressive Disclosure

**Use Case:** Hiding complexity from novice users

**Levels:**
1. **Default View:** Essential information only
2. **Expanded View:** Click to reveal details (accordion)
3. **Advanced Settings:** Hidden behind "Advanced" toggle
4. **Expert Mode:** Keyboard shortcuts, CLI hints

---

## 7. Design Recommendations

### 7.1 Apple-Inspired Design Principles

| Principle | Application |
|-----------|-------------|
| **Clarity** | Bold metric numbers, clear labels, obvious hierarchy |
| **Deference** | Content-first, minimal chrome, charts serve data |
| **Depth** | Subtle shadows, layering creates visual hierarchy |
| **Consistency** | Uniform spacing, predictable interactions |

### 7.2 Color System

**Semantic Colors (from design-principles.md):**

| Purpose | Light Mode | Dark Mode |
|---------|------------|-----------|
| Critical/Error | `#DC2626` | `#EF4444` |
| High Priority | `#EA580C` | `#F97316` |
| Medium Priority | `#F59E0B` | `#FBBF24` |
| Success | `#10B981` | `#34D399` |
| Info/Primary | `#3B82F6` | `#60A5FA` |

**Surface Colors:**

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| Background | `#F9FAFB` | `#0F172A` |
| Surface | `#FFFFFF` | `#1E293B` |
| Border | `#E5E7EB` | `#334155` |
| Text Primary | `#111827` | `#F1F5F9` |
| Text Secondary | `#4B5563` | `#94A3B8` |

### 7.3 Animation Guidelines

| Type | Duration | Easing |
|------|----------|--------|
| Hover/Focus | 150ms | ease-out |
| Modal Open | 250ms | ease-out |
| Modal Close | 200ms | ease-in |
| Page Transition | 350ms | ease-in-out |
| Sidebar Toggle | 300ms | ease-in-out |

**Reduced Motion:**
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 7.4 Responsive Breakpoints

| Breakpoint | Width | Adjustments |
|------------|-------|-------------|
| Desktop XL | 1440px+ | Full 12-column, sidebar expanded |
| Desktop | 1024-1439px | 12-column, sidebar collapsible |
| Tablet | 768-1023px | 8-column, sidebar collapsed default |
| Mobile | 320-767px | Single column, bottom nav |

### 7.5 Accessibility Requirements

**Keyboard Navigation:**
- Tab order follows visual hierarchy
- Focus: 2px blue ring (`focus:ring-2 focus:ring-blue-500`)
- Escape closes modals/dropdowns
- Enter activates buttons

**Screen Reader:**
- Semantic HTML (`<nav>`, `<main>`, `<aside>`)
- ARIA labels on icon-only buttons
- Live regions for dynamic updates
- Descriptive alt text for charts

**Color Independence:**
- Severity badges: icons + color
- Status: text labels + color
- Charts: patterns for colorblind users

---

## 8. Implementation Roadmap

### Phase 1: Dashboard Enhancement

**Duration:** Week 1-2

**Deliverables:**
- [ ] Dashboard MetricCards (vulnerability counts, agent status, uptime)
- [ ] Trend chart component (30-day vulnerability trend)
- [ ] Activity feed component (real-time events)
- [ ] Quick action buttons (navigation shortcuts)

**Files to Create/Modify:**
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/MetricCard.jsx`
- `frontend/src/components/TrendChart.jsx`
- `frontend/src/components/ActivityFeed.jsx`

### Phase 2: Vulnerability Management

**Duration:** Week 3-4

**Deliverables:**
- [ ] VulnerabilityTable component (sortable, filterable)
- [ ] VulnerabilityDetail modal (full context)
- [ ] Bulk action toolbar (multi-select operations)
- [ ] Status workflow (Open → In Progress → Patched)

**Files to Create:**
- `frontend/src/pages/Vulnerabilities.jsx`
- `frontend/src/components/VulnerabilityTable.jsx`
- `frontend/src/components/VulnerabilityDetail.jsx`

### Phase 3: Agent Monitoring

**Duration:** Week 5-6

**Deliverables:**
- [ ] AgentStatusGrid (visual grid of all agents)
- [ ] AgentDetailPanel (execution logs, resource usage)
- [ ] AgentControls (Start/Stop/Restart actions)
- [ ] LogViewer component (streaming log output)

**Files to Create:**
- `frontend/src/pages/Agents.jsx`
- `frontend/src/components/AgentStatusCard.jsx`
- `frontend/src/components/LogViewer.jsx`

### Phase 4: Code Knowledge Graph

**Duration:** Week 7-8

**Deliverables:**
- [ ] CodeKnowledgeGraph (D3.js force graph)
- [ ] EntityDetailSidebar (node context panel)
- [ ] GraphFilters (entity type toggles)
- [ ] GraphSearch (text search with highlighting)

**Files to Create:**
- `frontend/src/pages/CodeGraph.jsx`
- `frontend/src/components/ForceGraph.jsx`
- `frontend/src/components/EntityDetail.jsx`

### Phase 5: Polish & Compliance

**Duration:** Week 9-10

**Deliverables:**
- [ ] Dark mode implementation (CSS variables, toggle)
- [ ] Accessibility audit (screen reader, keyboard nav)
- [ ] Performance optimization (virtual scrolling, lazy loading)
- [ ] Component documentation (Storybook)

**Files to Modify:**
- `frontend/src/index.css` (CSS variables)
- `frontend/src/components/SettingsPage.jsx` (theme toggle)
- All components (a11y fixes)

---

## References

**Existing Implementation:**
- `frontend/src/App.jsx` - Router configuration
- `frontend/src/components/CollapsibleSidebar.jsx` - Navigation
- `frontend/src/components/ApprovalDashboard.jsx` - HITL approval
- `frontend/src/components/IncidentInvestigations.jsx` - RCA dashboard
- `frontend/src/components/SettingsPage.jsx` - Configuration

**Design Documentation:**
- `agent-config/design-workflows/design-principles.md` - Design system
- `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - HITL workflow

**Backend API:**
- `/api/v1/approvals/*` - Approval operations
- `/api/v1/incidents/*` - Incident endpoints
- `/api/v1/settings/*` - Configuration

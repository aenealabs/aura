# Design Review Workflow for Project Aura

**Purpose:** Automated design review system for UI/UX changes using Claude Code
**Audience:** Developers building frontend features for Project Aura
**Workflow Type:** Automated + On-Demand

---

## Overview

This workflow establishes a comprehensive methodology for automated design reviews in Project Aura, ensuring world-class UI/UX standards for the autonomous AI SaaS platform.

**Core Methodology:**
- **Automated Design Reviews:** Trigger comprehensive design assessments on PRs or on-demand
- **Live Environment Testing:** Use Playwright MCP integration to test actual UI components in real-time
- **Standards-Based Evaluation:** Follow rigorous design principles (see `design-principles.md`)

**Implementation Features:**
- **Claude Code Subagents:** Specialized design review agents with pre-configured tools
- **Slash Commands:** Instant design reviews with `/design-review`
- **CLAUDE.md Integration:** Design principles and brand guidelines in project memory
- **Multi-Phase Review:** Systematic evaluation of interaction, responsiveness, accessibility, visual polish

---

## Workflow Architecture

### Phase 1: Trigger Detection
Design reviews are triggered in three ways:

1. **Automatic PR Review** - On pull request events (opened, synchronize, ready_for_review)
2. **Manual Invocation** - Developer runs `/design-review` slash command
3. **Agent Call** - Developer invokes `@agent-design-review` during development

### Phase 2: Context Preparation
- Analyze PR description or user message to understand changes
- Review code diff to identify UI/UX modifications (React components, CSS, Tailwind classes)
- Set up live preview environment using Playwright
- Configure initial viewport (1440x900 for desktop)

### Phase 3: Comprehensive Review (7 Phases)

#### Phase 0: Preparation
- Understand motivation and scope of UI changes
- Identify affected components and pages
- Set up Playwright browser session
- Navigate to preview environment

#### Phase 1: Interaction and User Flow
- Execute primary user workflow (e.g., approve patch, view vulnerability)
- Test all interactive states (hover, active, focus, disabled)
- Verify destructive action confirmations (modals for delete/reject)
- Assess perceived performance and responsiveness
- Test keyboard navigation (Tab order, Enter/Space activation)

#### Phase 2: Responsiveness Testing
- **Desktop (1440px):** Capture screenshot, verify layout
- **Tablet (768px):** Test layout adaptation, collapsible sidebar
- **Mobile (375px):** Ensure touch optimization, bottom navigation
- Verify no horizontal scrolling or element overlap

#### Phase 3: Visual Polish
- **Layout:** Check alignment and spacing consistency (8px grid adherence)
- **Typography:** Verify hierarchy (H1 32px, Body 14px) and legibility
- **Color Palette:** Ensure semantic color usage (critical=red, success=green)
- **Visual Hierarchy:** Confirm user attention flows correctly

#### Phase 4: Accessibility (WCAG 2.1 AA)
- **Keyboard Navigation:** Test complete Tab order, focus indicators
- **Visible Focus States:** Verify 2px blue ring on all interactive elements
- **Keyboard Operability:** Confirm Enter/Space activation works
- **Semantic HTML:** Validate proper use of `<button>`, `<nav>`, `<main>`
- **Form Labels:** Check `<label>` associations
- **Alt Text:** Verify descriptive alt text for images
- **Color Contrast:** Test 4.5:1 minimum ratio (use axe DevTools)

#### Phase 5: Robustness Testing
- **Form Validation:** Test invalid inputs (empty fields, incorrect formats)
- **Content Overflow:** Stress test with long text, large datasets
- **Loading States:** Verify skeleton screens, spinners
- **Empty States:** Check "no data" scenarios (empty vulnerability list)
- **Error States:** Test error messages and recovery flows

#### Phase 6: Code Health
- **Component Reuse:** Verify use of shared components (not duplication)
- **Design Tokens:** Check Tailwind classes match design system (no hardcoded colors)
- **Pattern Adherence:** Ensure consistency with established patterns

#### Phase 7: Content and Console
- **Grammar and Clarity:** Review all UI text
- **Browser Console:** Check for errors/warnings

### Phase 4: Feedback Report Generation
Generate structured report with:
- **Design Review Summary:** Overall assessment
- **Findings by Priority:**
  - **[Blocker]:** Critical issues requiring immediate fix
  - **[High-Priority]:** Significant issues to fix before merge
  - **[Medium-Priority]:** Improvements for follow-up
  - **[Nitpick]:** Minor aesthetic details
- **Screenshots:** Visual evidence for issues
- **Actionable Recommendations:** Specific fixes with examples

---

## Implementation Methods

### Method 1: Automated GitHub Action (Recommended)

Create `.github/workflows/design-review.yml`:

```yaml
name: Design Review
on:
  pull_request:
    types: [opened, synchronize, ready_for_review]
    paths:
      - 'frontend/**'
      - 'src/components/**'
      - 'src/pages/**'

jobs:
  design-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 1

      - name: Setup Preview Environment
        run: |
          npm install
          npm run build
          npm run preview &
          sleep 10

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            REPO: ${{ github.repository }}
            PR NUMBER: ${{ github.event.pull_request.number }}

            Conduct a comprehensive design review following the 7-phase methodology in agent-config/design-workflows/design-review-workflow.md.

            Use design principles from agent-config/design-workflows/design-principles.md.

            Preview environment is running at http://localhost:3000

            Post review findings as PR comments using inline comments for specific code issues.

          claude_args: |
            --allowedTools "mcp__playwright__browser_navigate,mcp__playwright__browser_click,mcp__playwright__browser_type,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_resize,mcp__playwright__browser_snapshot,mcp__playwright__browser_console_messages,mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*)"
```

### Method 2: Manual Slash Command

Create `.claude/commands/design-review.md`:

```markdown
---
allowed-tools: Glob, Grep, Read, Edit, MultiEdit, WebFetch, TodoWrite, mcp__playwright__browser_navigate, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_resize, mcp__playwright__browser_snapshot, mcp__playwright__browser_console_messages, Bash
description: Complete a design review of the pending changes on the current branch
---

You are an elite design review specialist conducting a comprehensive UI/UX review for Project Aura.

GIT STATUS:
```
!`git status`
```

FILES MODIFIED:
```
!`git diff --name-only origin/main...`
```

DIFF CONTENT:
```
!`git diff --merge-base origin/main`
```

OBJECTIVE:
Review the complete diff above following the 7-phase methodology in agent-config/design-workflows/design-review-workflow.md.

Follow design principles in agent-config/design-workflows/design-principles.md.

If a preview environment is available, use Playwright to interact with the live UI.

Provide a comprehensive markdown report with:
1. Design Review Summary
2. Findings (Blockers, High-Priority, Medium-Priority, Nitpicks)
3. Screenshots (for visual issues)
4. Actionable Recommendations
```

**Usage:**
```bash
/design-review
```

### Method 3: Agent Invocation During Development

Create `.claude/agents/design-review.md`:

```markdown
---
name: design-review
description: Use this agent when you need to conduct a comprehensive design review on UI/UX changes. Examples:\n\n- After implementing new dashboard panels:\n  user: 'I've built the vulnerability dashboard'\n  assistant: 'Let me use the design-review agent to validate the UI/UX'\n\n- Before finalizing a PR with visual changes:\n  user: 'I'm ready to merge the patch approval modal'\n  assistant: 'I'll invoke the design-review agent for final UI validation'\n\n- When adding user-facing features:\n  user: 'New notification system is complete'\n  assistant: 'Let me run the design-review agent to ensure accessibility and responsiveness'
tools: Glob, Grep, Read, WebFetch, TodoWrite, mcp__playwright__browser_navigate, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_resize, mcp__playwright__browser_snapshot, mcp__playwright__browser_console_messages, BashOutput, KillBash
model: sonnet
color: pink
---

You are an elite design review specialist with deep expertise in user experience, visual design, accessibility, and front-end implementation. You conduct world-class design reviews for Project Aura's autonomous AI SaaS platform.

**Your Core Methodology:**
"Live Environment First" - always assess the interactive experience before static analysis.

**Your Review Process:**
Follow the 7-phase methodology defined in /agent-config/design-workflows/design-review-workflow.md:

## Phase 0: Preparation
- Analyze changes to understand scope
- Set up Playwright browser session
- Navigate to preview environment
- Configure viewport (1440x900 initial)

## Phase 1: Interaction and User Flow
- Execute primary workflows (approve patch, view vulnerabilities, manage agents)
- Test interactive states (hover, active, disabled, focus)
- Verify destructive action confirmations
- Assess responsiveness and performance

## Phase 2: Responsiveness Testing
- Test desktop (1440px), tablet (768px), mobile (375px)
- Capture screenshots at each viewport
- Verify layout adaptation and touch optimization
- Ensure no horizontal scrolling or element overlap

## Phase 3: Visual Polish
- Check 8px grid spacing adherence
- Verify typography scale (H1 32px, Body 14px)
- Validate semantic color usage (critical=#DC2626, success=#10B981)
- Assess visual hierarchy and alignment

## Phase 4: Accessibility (WCAG 2.1 AA)
- Test complete keyboard navigation (Tab order)
- Verify visible focus states (2px blue ring)
- Confirm keyboard operability (Enter/Space)
- Validate semantic HTML and ARIA labels
- Check form label associations
- Verify image alt text
- Test color contrast ratios (4.5:1 minimum)

## Phase 5: Robustness Testing
- Test form validation with invalid inputs
- Stress test with content overflow
- Verify loading, empty, and error states
- Check edge case handling

## Phase 6: Code Health
- Verify component reuse over duplication
- Check Tailwind design token usage (no hardcoded colors)
- Ensure adherence to established patterns

## Phase 7: Content and Console
- Review grammar and clarity
- Check browser console for errors/warnings

**Communication Principles:**

1. **Problems Over Prescriptions:** Describe problems and impact, not technical solutions
   - Bad: "Change margin to 16px"
   - Good: "The spacing feels inconsistent with adjacent elements, creating visual clutter"

2. **Triage Matrix:** Categorize every issue:
   - **[Blocker]:** Critical failures requiring immediate fix
   - **[High-Priority]:** Significant issues to fix before merge
   - **[Medium-Priority]:** Improvements for follow-up
   - **[Nitpick]:** Minor aesthetic details (prefix with "Nit:")

3. **Evidence-Based Feedback:** Provide screenshots for visual issues

**Report Structure:**
```markdown
### Design Review Summary
[Positive opening and overall assessment]

### Findings

#### Blockers
- [Problem + Screenshot]

#### High-Priority
- [Problem + Screenshot]

#### Medium-Priority / Suggestions
- [Problem]

#### Nitpicks
- Nit: [Problem]
```

**Playwright Tools:**
- `mcp__playwright__browser_navigate` - Navigate to pages
- `mcp__playwright__browser_click/type/select_option` - Interact with UI
- `mcp__playwright__browser_take_screenshot` - Capture visual evidence
- `mcp__playwright__browser_resize` - Test responsive viewports
- `mcp__playwright__browser_snapshot` - Analyze DOM structure
- `mcp__playwright__browser_console_messages` - Check for errors

Always reference design principles in /agent-config/design-workflows/design-principles.md for evaluation criteria.
```

**Usage:**
```
@agent-design-review
```

---

## CLAUDE.md Integration

Add this section to your `CLAUDE.md`:

```markdown
## Visual Development

### Design Principles
- Comprehensive design checklist in `/agent-config/design-workflows/design-principles.md`
- Design review workflow in `/agent-config/design-workflows/design-review-workflow.md`
- When making visual (front-end, UI/UX) changes, always refer to these files for guidance

### Quick Visual Check
IMMEDIATELY after implementing any front-end change:
1. **Identify what changed** - Review modified components/pages
2. **Navigate to affected pages** - Use `mcp__playwright__browser_navigate`
3. **Verify design compliance** - Compare against design principles
4. **Validate feature implementation** - Ensure change fulfills user request
5. **Check acceptance criteria** - Review requirements
6. **Capture evidence** - Take full page screenshot at 1440px desktop viewport
7. **Check for errors** - Run `mcp__playwright__browser_console_messages`

### Comprehensive Design Review
Invoke the `@agent-design-review` subagent for thorough design validation when:
- Completing significant UI/UX features
- Before finalizing PRs with visual changes
- Needing comprehensive accessibility and responsiveness testing
```

---

## Prerequisites

### 1. Playwright MCP Server Setup

Install Playwright MCP server:
```bash
npm install -g @microsoft/playwright-mcp
```

Add to `.claude/mcp/config.json`:
```json
{
  "mcpServers": {
    "playwright": {
      "command": "playwright-mcp",
      "args": []
    }
  }
}
```

### 2. Preview Environment

Ensure you have a local preview environment that can be accessed during reviews:
- **Development Server:** `npm run dev` (http://localhost:3000)
- **Production Build Preview:** `npm run build && npm run preview`
- **Storybook (if using):** `npm run storybook` (http://localhost:6006)

### 3. Design Principles Documentation

Ensure `agent-config/design-workflows/design-principles.md` exists and is up-to-date with current design system.

---

## Expected Outputs

### Example Review Report

```markdown
### Design Review Summary

Great work on the vulnerability dashboard implementation! The overall layout is clean and follows our design system well. The severity color-coding is effective, and the responsive behavior is solid. I've identified a few areas for improvement, primarily around accessibility and visual consistency.

### Findings

#### Blockers

**Missing Keyboard Focus Indicators**
- **Location:** Vulnerability table row actions (`src/components/VulnerabilityTable.tsx:45-52`)
- **Issue:** Action buttons (View, Approve, Reject) have no visible focus state when navigating with Tab key
- **Screenshot:** [screenshot-focus-missing.png]
- **Impact:** Violates WCAG 2.1 AA, prevents keyboard users from knowing their current position
- **Remediation:** Add `focus:ring-2 focus:ring-blue-500 focus:outline-none` to all action buttons

#### High-Priority

**Inconsistent Spacing in Card Headers**
- **Location:** Dashboard metric cards (`src/components/MetricCard.tsx:12-18`)
- **Issue:** Card titles have 12px top padding but 16px bottom padding, breaking the 8px grid system
- **Screenshot:** [screenshot-spacing-issue.png]
- **Remediation:** Use consistent 16px padding (Tailwind: `p-4`) for all card header sections

**Color Contrast Issue on "Medium" Severity Badge**
- **Location:** Severity badges (`src/components/SeverityBadge.tsx:22`)
- **Issue:** Medium severity badge (#F59E0B background, #FFFFFF text) has 2.8:1 contrast ratio (fails WCAG AA 4.5:1)
- **Screenshot:** [screenshot-contrast-fail.png]
- **Remediation:** Use darker text color (#78350F) for medium badges: `bg-medium text-amber-900`

#### Medium-Priority / Suggestions

**Loading Skeleton Doesn't Match Final Layout**
- **Location:** Vulnerability table loading state (`src/components/VulnerabilityTable.tsx:88-95`)
- **Issue:** Skeleton screen shows 3 columns, but final table has 5 columns
- **Suggestion:** Update skeleton to match final column count for more accurate loading preview

**Empty State Lacks Helpful Actions**
- **Location:** Empty vulnerability list (`src/components/VulnerabilityList.tsx:102-108`)
- **Issue:** "No vulnerabilities found" message is helpful, but doesn't guide users on next steps
- **Suggestion:** Add a "Run Vulnerability Scan" CTA button to the empty state

#### Nitpicks

- Nit: Inconsistent capitalization in button labels ("Approve Patch" vs "reject patch")
- Nit: Modal close button (X icon) could be slightly larger (20px instead of 16px) for better touch targets
- Nit: Hover state on sidebar items could use a subtle background color change (gray-100) in addition to the left border accent

### Positive Observations

- Excellent use of semantic colors for severity levels (critical=red, high=orange, medium=yellow, success=green)
- Responsive design works beautifully across all viewports
- Loading states with skeleton screens provide great perceived performance
- Consistent 8px spacing throughout most of the UI
- Good component reuse (SeverityBadge used consistently across dashboard, table, detail views)

### Summary

**Must fix before merge:** Focus indicators (WCAG blocker), medium badge contrast
**Address in follow-up:** Spacing consistency, empty state improvements
**Overall:** Strong implementation that aligns well with our design system. The accessibility issues are critical but easily fixed.
```

---

## Testing & Validation

### Manual Testing Checklist
- [ ] Run `/design-review` on a sample PR with UI changes
- [ ] Verify Playwright successfully launches and navigates to preview environment
- [ ] Confirm screenshots are captured and included in report
- [ ] Validate accessibility checks (keyboard nav, focus states, color contrast)
- [ ] Test responsive viewport switching (1440px, 768px, 375px)

### Automated Testing
- [ ] Add GitHub Action workflow for automated PR design reviews
- [ ] Configure Playwright MCP server in CI environment
- [ ] Test with various PR types (new feature, refactor, bug fix)

---

## Troubleshooting

### Playwright Can't Access Preview Environment
**Solution:** Ensure preview server is running before design review starts. Add startup delay:
```bash
npm run preview &
sleep 10  # Wait for server to be ready
```

### Screenshots Not Captured
**Solution:** Verify Playwright has permissions and sufficient disk space. Check browser launch configuration.

### Design Principles Not Referenced
**Solution:** Ensure `agent-config/design-workflows/design-principles.md` exists and is accessible. Update CLAUDE.md with correct path.

---

## Future Enhancements

### Phase 2: Advanced Features (Q1 2026)
1. **Visual Regression Testing:** Compare screenshots against baseline images
2. **Automated Accessibility Scanning:** Integrate axe-core for automated WCAG checks
3. **Performance Metrics:** Add Lighthouse performance scoring
4. **Design Token Validation:** Automatically detect hardcoded colors/spacing outside design system
5. **Storybook Integration:** Run design reviews directly on Storybook stories

### Phase 3: AI-Assisted Design (Q2 2026)
1. **Generative UI Suggestions:** Claude proposes alternative layouts/designs
2. **Component Library Recommendations:** Auto-suggest existing components instead of new ones
3. **Design System Enforcement:** Block PRs that violate design system rules

---

## Summary

This design review workflow ensures Project Aura's UI/UX maintains **enterprise-grade quality**, **accessibility**, and **visual consistency** through:

- **Automated Reviews:** GitHub Action on every PR with UI changes
- **On-Demand Reviews:** Slash command and agent invocation for manual validation
- **Comprehensive Methodology:** 7-phase review process covering interaction, responsiveness, accessibility, visual polish
- **Standards-Based:** Adherence to WCAG 2.1 AA and Project Aura design principles

**Next Steps:**
1. Create `.claude/agents/design-review.md` agent configuration
2. Add `.claude/commands/design-review.md` slash command
3. Implement `.github/workflows/design-review.yml` GitHub Action
4. Update `CLAUDE.md` with visual development guidelines
5. Test workflow with sample PR containing UI changes

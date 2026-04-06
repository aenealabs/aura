# Frontend Development Guide

> Universal security rules and AI attribution policy are in the root `CLAUDE.md`.

---

## Design System

- **Primary Brand Color:** `#3B82F6` (blue)
- **Semantic Colors:**
  - Critical/Error: `#DC2626` (red)
  - High Priority: `#EA580C` (orange)
  - Medium Priority: `#F59E0B` (amber)
  - Success: `#10B981` (green)
  - Info: `#3B82F6` (blue)
- **Typography:** Inter font family, H1 32px, H2 24px, Body 14px, Code 13px (JetBrains Mono)
- **Spacing:** 8px base unit (4px, 8px, 12px, 16px, 24px, 32px, 48px)
- **Accessibility:** WCAG 2.1 AA compliance required (4.5:1 contrast minimum)
- **CSS Framework:** Tailwind CSS (utility-first, LLM-friendly)

---

## Technology Stack

- **Framework:** React 18+, Next.js 14+
- **Language:** TypeScript (strict mode, avoid `any`)
- **Styling:** Tailwind CSS
- **State Management:** Follow existing patterns in the codebase
- **Build:** Node 20 (private ECR base image: `aura-base-images/node:20-slim`)

---

## Design References

- **Design Principles:** `agent-config/design-workflows/design-principles.md`
- **Design Review Workflow:** `agent-config/design-workflows/design-review-workflow.md`
- **App UI Blueprint:** `agent-config/design-workflows/app-ui-blueprint.md`

---

## Component Conventions

- Components use PascalCase filenames (e.g., `ProfilePage.jsx`)
- Auth components live in `src/components/auth/`
- Form field names like "Password" are UI labels, not secrets (excluded from secrets scanning)

# Project Aura - Frontend

React-based console for Project Aura: HITL (Human-in-the-Loop) patch approvals, repository onboarding, security operations, and platform settings.

> **Data sources:** many pages call the FastAPI backend, but some pages and widgets render built-in demo data. Many service modules in `src/services/` (30 of the 48 non-test API modules contain a `catch` path that returns mock, demo, or default data; some of those paths are limited to dev mode or to specific errors) substitute that data when their API call fails, and pages such as Agent Registry, Knowledge Graph (`CKGEConsole`), Red Team, and Agent Manager do not call an API at all. Widgets whose backend does not exist yet show a **Demo data** badge (`DemoDataBadge.jsx`). Check a page's service module before relying on what it displays.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server (with API proxy to localhost:8000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Configuration

Copy `.env.example` to `.env.local` and configure:

```bash
# API endpoint (relative path uses Vite proxy)
VITE_API_URL=/api/v1

# Cognito (required unless VITE_DEV_MODE=true)
VITE_COGNITO_USER_POOL_ID=...
VITE_COGNITO_CLIENT_ID=...
VITE_COGNITO_DOMAIN=...

# Local development without Cognito (mock user)
VITE_DEV_MODE=true

# Chat assistant API Gateway (mock chat responses when unset)
VITE_CHAT_API_URL=...
VITE_CHAT_WS_URL=...
```

See `.env.example` for the full list.

## Routes

Routes are defined in `src/App.jsx`. Key routes:

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Dashboard | Overview metrics (some panels call `/api/v1/dashboard/*` routes that are not implemented yet) |
| `/graph` | CKGEConsole | Code knowledge graph explorer (built-in demo data) |
| `/repositories` | RepositoriesList | Repository onboarding (GitHub/GitLab OAuth) |
| `/approvals` | ApprovalDashboard | HITL patch approval workflow |
| `/settings` | SettingsPage | Platform settings (several tabs use demo or default data) |

Other routes include `/sandboxes`, `/environments`, `/incidents`, `/security/*`, `/agents/*`, `/observability/traces`, `/trust-center`, `/guardrails`, `/explainability`, `/capability-graph`, and `/documentation`.

## Customer Onboarding System

The frontend includes a comprehensive customer onboarding system to improve user activation and retention.

### Onboarding Features

| Priority | Feature | Component | Description |
|----------|---------|-----------|-------------|
| P0 | Welcome Modal | `WelcomeModal.jsx` | First-time user modal with glass morphism design |
| P1 | Onboarding Checklist | `OnboardingChecklist.jsx` | Fixed bottom-right widget tracking 5 setup steps |
| P2 | Welcome Tour | `WelcomeTour.jsx` | Joyride-style guided tour with 7 steps |
| P3 | Feature Tooltips | `FeatureTooltip.jsx` | In-app tooltips for complex features |
| P4 | Getting-Started Videos | `VideoModal.jsx` | Video catalog with chapter navigation |
| P5 | Team Invite Wizard | `TeamInviteWizard.jsx` | Multi-step wizard for team invitations (sending is simulated; not yet wired to `/api/v1/team/invitations`) |

### Key Implementation Details

- **State Management:** `OnboardingContext.jsx` provides centralized state with localStorage persistence
- **Dev Mode:** `DevToolbar.jsx` enables testing onboarding flows without backend
- **API Service:** `onboardingApi.js` handles backend sync with localStorage fallback
- **Accessibility:** WCAG 2.1 AA compliant with full keyboard navigation
- **Dark Mode:** Full dark mode support across all onboarding components

### Directory Structure

```
src/components/onboarding/
  index.js                    # Barrel export
  WelcomeModal.jsx           # P0 - Welcome modal
  OnboardingChecklist.jsx    # P1 - Checklist widget
  ChecklistItem.jsx          # Checklist item component
  WelcomeTour.jsx            # P2 - Guided tour
  TourTooltip.jsx            # Tour tooltip component
  TourSpotlight.jsx          # Tour spotlight overlay
  FeatureTooltip.jsx         # P3 - Feature tooltips
  TooltipIndicator.jsx       # Pulsing tooltip indicator
  VideoModal.jsx             # P4 - Video catalog
  VideoPlayer.jsx            # Video player component
  TeamInviteWizard.jsx       # P5 - Team invite wizard
  DevToolbar.jsx             # Dev-only testing toolbar
  steps/
    EmailEntryStep.jsx       # Team invite step 1
    RoleAssignmentStep.jsx   # Team invite step 2
    InviteReviewStep.jsx     # Team invite step 3
    InviteCompletionStep.jsx # Team invite step 4
```

## API Integration

The approval workflow connects to the FastAPI backend at `/api/v1/approvals/*`:

- `GET /approvals` - List approval requests
- `GET /approvals/:id` - Get approval details
- `POST /approvals/:id/approve` - Approve a patch
- `POST /approvals/:id/reject` - Reject a patch
- `GET /approvals/stats` - Get statistics

## Development

The Vite dev server proxies `/api` requests to `http://localhost:8000` (see `vite.config.js`).

To develop with live API:

1. Start the FastAPI backend: `uvicorn src.api.main:app --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000/approvals (the dev server runs on port 3000; see `vite.config.js`)

## Tech Stack

- React 19 + Vite 8
- Tailwind CSS 4
- Heroicons
- React Router 7

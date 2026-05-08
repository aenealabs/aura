# react-grid-layout Fallback Runbook

**Last Updated:** 2026-05-08
**Tracked As:** Healthy in `docs/security/DEPENDENCY_RISK_REGISTER.md`
**Owner:** Frontend Engineering

---

## Why this runbook exists

`react-grid-layout` (Samuel Reed / STRML) is the grid library powering ADR-064 customizable dashboard widgets. As of May 2026 the package is Healthy: same author as v1, v2 TypeScript rewrite shipped Dec 2025, eight releases through Mar 2026, native React 19 support.

This runbook is the documented contingency for *if* maintenance ever slows (the Mar 2024 audit incorrectly assessed it as already slowing -- the actual signal was the opposite). The plan is documented now so we don't have to write it under pressure later.

## Trigger conditions for executing the swap

Execute the swap only if at least one of:

1. **React compatibility lag**: `react-grid-layout` does not support a React major we need within 6 months of that React's GA.
2. **Unpatched CVE**: a CVE in `react-grid-layout` lacks a fix release within 30 days of disclosure.
3. **Project EOL**: the maintainer (Samuel Reed) explicitly announces end-of-life of the package or the GitHub repo is archived.

The recurring dependency audit (`.github/workflows/dependency-risk-audit.yml`) tracks the Watch / At-Risk tiers; if `react-grid-layout` re-enters one of those tiers in a future audit, the trigger conditions above are the next gate before action.

Until then: **track, don't swap**. The package is the right tool today.

## Structural readiness already in place

`frontend/src/lib/grid-layout.js` is the single import seam. Both consumers (`frontend/src/components/ui/DashboardGrid.jsx` and `frontend/src/components/dashboard/DashboardEditor.jsx`) import the grid library through this wrapper, never directly from the package.

To swap, replace the wrapper's internals with the new implementation. The named-export surface that must be preserved:

| Export | Used by |
| --- | --- |
| `default` | `DashboardEditor.jsx` (`import GridLayout from '...'`) |
| `GridLayout` (named) | `DashboardGrid.jsx` |
| `useContainerWidth` | `DashboardGrid.jsx` |
| `useResponsiveLayout` | `DashboardGrid.jsx` |
| `verticalCompactor` | `DashboardGrid.jsx` |

`frontend/src/lib/grid-layout.test.js` asserts these exports exist and that the default and named `GridLayout` are the same component. Any swap that breaks the surface will fail this test.

## Replacement candidates

When trigger conditions fire, evaluate in this order:

1. **Stay on a fork**: If a community fork of `react-grid-layout` is healthier (same author moved, different organization, etc.), pin to the fork. Lowest risk -- the API surface is identical.

2. **`muuri-react`**: Different DOM model (Muuri uses absolute positioning + transforms differently), but supports drag-and-drop and responsive grids. Wrapping it behind our seam requires emulating the v2 hooks API (`useContainerWidth`, `useResponsiveLayout`, `verticalCompactor`). Medium effort.

3. **Custom CSS Grid + react-dnd**: Build a minimal grid using CSS Grid for layout and `react-dnd` for drag-and-drop. Most work, but yields zero third-party dashboard libraries -- the React, react-dnd, and CSS dependencies are all already on the Healthy tier.

4. **`@dnd-kit/core` + CSS Grid**: Similar to (3), but using `@dnd-kit` (corporate-backed, modern) instead of react-dnd. Probably the right answer if (1) and (2) aren't viable.

The wrapper makes the cost of evaluation low: each candidate can be prototyped in `grid-layout.js` without touching either consumer file. If the candidate's surface differs significantly, write a thin adapter inside the wrapper.

## Testing the swap

Before merging a swap PR:

1. The wrapper surface tests pass (`src/lib/grid-layout.test.js`).
2. The DashboardGrid behavior tests pass (`src/components/ui/DashboardGrid.test.jsx`).
3. The DashboardEditor behavior tests pass (`src/components/dashboard/DashboardEditor.test.jsx`).
4. The 94 widget tests still pass (no regression in widget rendering).
5. Manual smoke: `npm run dev`, navigate to the dashboard, verify drag, resize, save, and load a saved layout.

The first three are fast and run on every PR. The widget tests confirm that no widget broke as a side effect. The manual smoke is the final gate.

## What this runbook is not

- A justification for swapping today. No trigger has fired; the package is healthy.
- A complete API reference for any candidate. Each candidate's docs are the source of truth.
- A blueprint for moving the dashboard system to a different paradigm (server-side rendered, no drag-and-drop, etc.). That would be a much larger ADR.

## References

- Register entry: `docs/security/DEPENDENCY_RISK_REGISTER.md` -- `react-grid-layout` row in the Healthy tier
- Wrapper: `frontend/src/lib/grid-layout.js`
- Wrapper tests: `frontend/src/lib/grid-layout.test.js`
- Consumer: `frontend/src/components/ui/DashboardGrid.jsx`
- Consumer: `frontend/src/components/dashboard/DashboardEditor.jsx`
- Tracking issue (recurring audit): #138

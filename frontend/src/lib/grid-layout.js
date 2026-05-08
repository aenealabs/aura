/**
 * react-grid-layout import seam (ADR-064 dashboard widgets).
 *
 * All dashboard consumers should import the grid library through
 * this module rather than directly from `react-grid-layout`. Today
 * this is a thin pass-through; if we ever need to swap the underlying
 * implementation (see
 * `docs/runbooks/REACT_GRID_LAYOUT_FALLBACK_RUNBOOK.md`), this is
 * the only file that changes.
 *
 * Surface preserved exactly:
 *
 * - **Default export**: `GridLayout` -- used by
 *   `frontend/src/components/dashboard/DashboardEditor.jsx` with the
 *   v1-style flat-props API (`cols`, `rowHeight`, `isDraggable`,
 *   etc.). v2 supports both flat props (legacy) and grouped
 *   `gridConfig`/`dragConfig` configs.
 *
 * - **Named exports**:
 *   - `GridLayout`: direct named alternative to default.
 *   - `useContainerWidth`: v2 hook for ResizeObserver-based width
 *     tracking. Used by `DashboardGrid.jsx`.
 *   - `useResponsiveLayout`: v2 hook returning
 *     `{ layout, cols, breakpoint }` for the active viewport. Used
 *     by `DashboardGrid.jsx`.
 *   - `verticalCompactor`: v2 layout compaction strategy. Used by
 *     `DashboardGrid.jsx`.
 *
 * If a consumer needs an additional export (e.g., `Responsive`,
 * `GridItem`, `useGridLayout`), add it here rather than reaching
 * around the wrapper. CSS imports are deliberately NOT bundled here:
 * each consumer continues to own its own `import 'react-grid-layout/
 * css/styles.css'` so the bundler dedupes naturally.
 */

export {
  GridLayout,
  useContainerWidth,
  useResponsiveLayout,
  verticalCompactor,
} from 'react-grid-layout';

// Re-export the default so consumers using `import GridLayout from ...`
// continue to work. v2 declares `GridLayout as default` in its index
// barrel, so this matches the package's intent.
export { default } from 'react-grid-layout';

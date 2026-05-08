/**
 * Surface-shape test for the react-grid-layout wrapper.
 *
 * The wrapper exists so dashboard consumers do not couple directly
 * to the package; if a future swap (see
 * `docs/runbooks/REACT_GRID_LAYOUT_FALLBACK_RUNBOOK.md`) removes or
 * renames an export, this test fails loudly instead of letting the
 * dashboards silently break at runtime.
 */

import { describe, it, expect } from 'vitest';
import * as wrapper from './grid-layout';
import gridLayoutDefault from './grid-layout';

describe('grid-layout wrapper surface', () => {
  it('exposes every named export the dashboards consume', () => {
    expect(wrapper.GridLayout).toBeDefined();
    expect(wrapper.useContainerWidth).toBeDefined();
    expect(wrapper.useResponsiveLayout).toBeDefined();
    expect(wrapper.verticalCompactor).toBeDefined();
  });

  it('exposes a default export for `import GridLayout from ...`', () => {
    expect(gridLayoutDefault).toBeDefined();
  });

  it('default export and named GridLayout are the same component', () => {
    // The package declares `GridLayout as default` in its index
    // barrel. The wrapper must preserve that identity so consumers
    // using either form get the same component.
    expect(gridLayoutDefault).toBe(wrapper.GridLayout);
  });

  it('hooks are callable functions', () => {
    expect(typeof wrapper.useContainerWidth).toBe('function');
    expect(typeof wrapper.useResponsiveLayout).toBe('function');
  });

  it('verticalCompactor is a non-null compaction strategy', () => {
    // v2's compactors are strategy objects (with apply / collide
    // methods), not bare functions. Whatever shape upstream chose,
    // the dashboard passes the value through to GridLayout's
    // ``compactor`` prop unchanged, so the wrapper just needs to
    // preserve identity.
    expect(wrapper.verticalCompactor).toBeDefined();
    expect(wrapper.verticalCompactor).not.toBeNull();
  });
});

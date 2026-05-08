/**
 * Behavior tests for DashboardEditor (ADR-064).
 *
 * Like DashboardGrid, the editor was previously uncovered. These
 * tests mock the `lib/grid-layout` wrapper so GridLayout becomes a
 * passthrough -- the test focuses on the editor's own state machine
 * (toolbar visibility, edit-mode transitions, save / cancel
 * callbacks, empty-state rendering) rather than drag-and-drop
 * mechanics, which belong to react-grid-layout's own test suite.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock the wrapper so GridLayout renders its children as-is.
vi.mock('../../lib/grid-layout', () => {
  const GridLayout = ({ children, onLayoutChange }) => (
    <div data-testid="mock-grid-layout" onClick={() => onLayoutChange && onLayoutChange([])}>
      {children}
    </div>
  );
  return {
    default: GridLayout,
    GridLayout,
    useContainerWidth: () => ({ width: 1280, containerRef: { current: null }, mounted: true }),
    useResponsiveLayout: ({ layouts }) => ({
      layout: (layouts && layouts.lg) || [],
      cols: 12,
      breakpoint: 'lg',
    }),
    verticalCompactor: { strategy: 'vertical' },
  };
});

import DashboardEditor from './DashboardEditor';


describe('DashboardEditor', () => {
  it('renders the empty state when no widgets are present', () => {
    render(<DashboardEditor />);
    expect(screen.getByText(/no widgets yet/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /get started/i })).toBeInTheDocument();
  });

  it('shows the Edit Layout button in non-edit mode', () => {
    render(<DashboardEditor />);
    expect(screen.getByRole('button', { name: /edit layout/i })).toBeInTheDocument();
    // The Save / Cancel toolbar buttons only appear in edit mode.
    expect(screen.queryByRole('button', { name: /^save$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^cancel$/i })).not.toBeInTheDocument();
  });

  it('switches to edit-mode toolbar after clicking Edit Layout', () => {
    render(<DashboardEditor />);
    fireEvent.click(screen.getByRole('button', { name: /edit layout/i }));

    // Edit-mode toolbar appears
    expect(screen.getByRole('button', { name: /add widget/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^save$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^cancel$/i })).toBeInTheDocument();
  });

  it('Save is disabled until there are unsaved changes', () => {
    render(<DashboardEditor />);
    fireEvent.click(screen.getByRole('button', { name: /edit layout/i }));

    const saveBtn = screen.getByRole('button', { name: /^save$/i });
    expect(saveBtn).toBeDisabled();
  });

  it('calls onSave with current layout and widgets', () => {
    const onSave = vi.fn();
    const initialLayout = [{ i: 'w1', x: 0, y: 0, w: 4, h: 3 }];
    const initialWidgets = [{ i: 'w1', definitionId: 'metric-criticals' }];
    render(
      <DashboardEditor
        initialLayout={initialLayout}
        initialWidgets={initialWidgets}
        onSave={onSave}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /edit layout/i }));

    // Trigger a layout change so hasChanges flips to true and Save
    // becomes enabled. Our mock GridLayout fires onLayoutChange([])
    // when clicked.
    fireEvent.click(screen.getByTestId('mock-grid-layout'));
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        widgets: initialWidgets,
      })
    );
  });

  it('calls onCancel when cancel is clicked in edit mode', () => {
    const onCancel = vi.fn();
    render(<DashboardEditor onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: /edit layout/i }));
    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows Share button only when both onShare and dashboard are provided', () => {
    const { rerender } = render(<DashboardEditor />);
    // No share button without props.
    expect(screen.queryByRole('button', { name: /share/i })).not.toBeInTheDocument();

    rerender(<DashboardEditor dashboard={{ dashboard_id: 'd1' }} onShare={() => {}} />);
    expect(screen.getByRole('button', { name: /share/i })).toBeInTheDocument();
  });

  it('shows unsaved-changes indicator when state has been modified', () => {
    // Provide initial widgets so GridLayout renders (the empty-state
    // branch hides it). Triggering the mocked GridLayout's onLayoutChange
    // is what flips hasChanges to true.
    render(
      <DashboardEditor
        initialLayout={[{ i: 'w1', x: 0, y: 0, w: 4, h: 3 }]}
        initialWidgets={[{ i: 'w1', definitionId: 'metric-criticals' }]}
      />
    );
    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /edit layout/i }));
    fireEvent.click(screen.getByTestId('mock-grid-layout'));

    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });
});

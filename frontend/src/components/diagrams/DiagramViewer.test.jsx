/**
 * Project Aura - DiagramViewer Component Tests
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';

// Mock ThemeContext
vi.mock('../../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false, toggleTheme: vi.fn() }),
}));

import DiagramViewer, { DiagramToolbar, DiagramCanvas } from './DiagramViewer';

// Sample SVG content for testing
const SAMPLE_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600" role="img">
  <title>Test Diagram</title>
  <rect x="100" y="100" width="200" height="100" fill="#3B82F6" rx="8"/>
  <text x="200" y="150" text-anchor="middle" fill="white">Node A</text>
  <rect x="400" y="100" width="200" height="100" fill="#10B981" rx="8"/>
  <text x="500" y="150" text-anchor="middle" fill="white">Node B</text>
  <path d="M300 150 L400 150" stroke="#94A3B8" stroke-width="2"/>
</svg>
`;

describe('DiagramViewer', () => {
  describe('rendering', () => {
    test('renders empty state when no SVG content provided', () => {
      render(<DiagramViewer />);

      expect(screen.getByText('No Diagram to Display')).toBeInTheDocument();
      expect(
        screen.getByText(/Generate an architecture diagram/i)
      ).toBeInTheDocument();
    });

    test('renders diagram when SVG content is provided', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      // Should display the diagram viewer with title
      expect(screen.getByText('Architecture Diagram')).toBeInTheDocument();
    });

    test('renders with custom title', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} title="My Custom Diagram" />);

      expect(screen.getByText('My Custom Diagram')).toBeInTheDocument();
    });

    test('renders status bar with dimensions', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByText(/800 x 600 px/)).toBeInTheDocument();
    });
  });

  describe('zoom controls', () => {
    test('displays current zoom level', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={1.0} />);

      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    test('zoom in button increases zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={1.0} />);

      const zoomInButton = screen.getByRole('button', { name: /zoom in/i });
      await user.click(zoomInButton);

      expect(screen.getByText('125%')).toBeInTheDocument();
    });

    test('zoom out button decreases zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={1.0} />);

      const zoomOutButton = screen.getByRole('button', { name: /zoom out/i });
      await user.click(zoomOutButton);

      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    test('zoom in button is disabled at max zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={4.0} />);

      const zoomInButton = screen.getByRole('button', { name: /zoom in/i });
      expect(zoomInButton).toBeDisabled();
    });

    test('zoom out button is disabled at min zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={0.1} />);

      const zoomOutButton = screen.getByRole('button', { name: /zoom out/i });
      expect(zoomOutButton).toBeDisabled();
    });
  });

  describe('view controls', () => {
    test('fit to view button exists', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByRole('button', { name: /fit diagram to view/i })).toBeInTheDocument();
    });

    test('reset view button exists', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByRole('button', { name: /reset view/i })).toBeInTheDocument();
    });

    test('reset view button sets zoom to 100%', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={2.0} />);

      expect(screen.getByText('200%')).toBeInTheDocument();

      const resetButton = screen.getByRole('button', { name: /reset view/i });
      await user.click(resetButton);

      expect(screen.getByText('100%')).toBeInTheDocument();
    });
  });

  describe('theme toggle', () => {
    test('theme toggle button exists', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(
        screen.getByRole('button', { name: /switch to dark theme/i })
      ).toBeInTheDocument();
    });

    test('theme toggle changes button label', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      const themeButton = screen.getByRole('button', { name: /switch to dark theme/i });
      await user.click(themeButton);

      expect(
        screen.getByRole('button', { name: /switch to light theme/i })
      ).toBeInTheDocument();
    });
  });

  describe('grid toggle', () => {
    test('grid toggle button exists', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByRole('button', { name: /show grid/i })).toBeInTheDocument();
    });

    test('grid toggle changes button aria-pressed state', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      const gridButton = screen.getByRole('button', { name: /show grid/i });
      expect(gridButton).toHaveAttribute('aria-pressed', 'false');

      await user.click(gridButton);

      expect(screen.getByRole('button', { name: /hide grid/i })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });
  });

  describe('export functionality', () => {
    test('export button opens menu', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      const exportButton = screen.getByRole('button', { name: /export diagram/i });
      await user.click(exportButton);

      expect(screen.getByRole('menu')).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /export as svg/i })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /export as png/i })).toBeInTheDocument();
    });

    test('export menu closes when clicking outside', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      const exportButton = screen.getByRole('button', { name: /export diagram/i });
      await user.click(exportButton);

      expect(screen.getByRole('menu')).toBeInTheDocument();

      // Click outside the menu
      fireEvent.mouseDown(document.body);

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    test('calls onExportComplete callback on export', async () => {
      const user = userEvent.setup();
      const mockOnExportComplete = vi.fn();

      // Mock URL.createObjectURL and URL.revokeObjectURL
      global.URL.createObjectURL = vi.fn(() => 'blob:test');
      global.URL.revokeObjectURL = vi.fn();

      render(
        <DiagramViewer
          svgContent={SAMPLE_SVG}
          onExportComplete={mockOnExportComplete}
        />
      );

      const exportButton = screen.getByRole('button', { name: /export diagram/i });
      await user.click(exportButton);

      const svgExport = screen.getByRole('menuitem', { name: /export as svg/i });
      await user.click(svgExport);

      await waitFor(() => {
        expect(mockOnExportComplete).toHaveBeenCalledWith('svg');
      });
    });
  });

  describe('accessibility', () => {
    test('toolbar has proper role', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByRole('toolbar', { name: /diagram controls/i })).toBeInTheDocument();
    });

    test('zoom level is announced via aria-live', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      const zoomDisplay = screen.getByText('100%');
      expect(zoomDisplay).toHaveAttribute('aria-live', 'polite');
    });

    test('canvas has img role', () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} />);

      expect(
        screen.getByRole('img', { name: /architecture diagram viewer/i })
      ).toBeInTheDocument();
    });
  });

  describe('keyboard shortcuts', () => {
    test('Ctrl++ zooms in', async () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={1.0} />);

      fireEvent.keyDown(window, { key: '+', ctrlKey: true });

      await waitFor(() => {
        expect(screen.getByText('125%')).toBeInTheDocument();
      });
    });

    test('Ctrl+- zooms out', async () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={1.0} />);

      fireEvent.keyDown(window, { key: '-', ctrlKey: true });

      await waitFor(() => {
        expect(screen.getByText('75%')).toBeInTheDocument();
      });
    });

    test('Ctrl+1 resets view', async () => {
      render(<DiagramViewer svgContent={SAMPLE_SVG} initialZoom={2.0} />);

      expect(screen.getByText('200%')).toBeInTheDocument();

      fireEvent.keyDown(window, { key: '1', ctrlKey: true });

      await waitFor(() => {
        expect(screen.getByText('100%')).toBeInTheDocument();
      });
    });
  });
});

describe('DiagramToolbar', () => {
  const defaultProps = {
    zoom: 1.0,
    onZoomIn: vi.fn(),
    onZoomOut: vi.fn(),
    onFitToView: vi.fn(),
    onResetView: vi.fn(),
    onExport: vi.fn(),
    onToggleTheme: vi.fn(),
    isDarkTheme: false,
    showGrid: false,
    onToggleGrid: vi.fn(),
    isExporting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders all control buttons', () => {
    render(<DiagramToolbar {...defaultProps} />);

    expect(screen.getByRole('button', { name: /zoom in/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /zoom out/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fit diagram to view/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset view/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export diagram/i })).toBeInTheDocument();
  });

  test('calls onZoomIn when zoom in button clicked', async () => {
    const user = userEvent.setup();
    render(<DiagramToolbar {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /zoom in/i }));

    expect(defaultProps.onZoomIn).toHaveBeenCalledTimes(1);
  });

  test('calls onZoomOut when zoom out button clicked', async () => {
    const user = userEvent.setup();
    render(<DiagramToolbar {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /zoom out/i }));

    expect(defaultProps.onZoomOut).toHaveBeenCalledTimes(1);
  });

  test('displays correct zoom percentage', () => {
    render(<DiagramToolbar {...defaultProps} zoom={1.5} />);

    expect(screen.getByText('150%')).toBeInTheDocument();
  });

  test('shows spinner when exporting', () => {
    const { container } = render(<DiagramToolbar {...defaultProps} isExporting={true} />);

    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });
});

describe('DiagramCanvas', () => {
  const defaultProps = {
    svgContent: SAMPLE_SVG,
    zoom: 1.0,
    pan: { x: 0, y: 0 },
    onPanChange: vi.fn(),
    showGrid: false,
    isDarkTheme: false,
    containerRef: { current: document.createElement('div') },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders SVG content', () => {
    const { container } = render(<DiagramCanvas {...defaultProps} />);

    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  test('applies correct transform based on zoom and pan', () => {
    const { container } = render(
      <DiagramCanvas {...defaultProps} zoom={2.0} pan={{ x: 100, y: 50 }} />
    );

    const transformDiv = container.querySelector('.origin-top-left');
    expect(transformDiv).toHaveStyle({
      transform: 'translate(100px, 50px) scale(2)',
    });
  });

  test('changes cursor on drag', () => {
    const { container } = render(<DiagramCanvas {...defaultProps} />);

    const canvas = container.querySelector('.cursor-grab');
    expect(canvas).toBeInTheDocument();

    fireEvent.mouseDown(canvas, { button: 0 });

    expect(container.querySelector('.cursor-grabbing')).toBeInTheDocument();
  });

  test('calls onPanChange during drag', () => {
    const { container } = render(<DiagramCanvas {...defaultProps} />);

    const canvas = container.querySelector('.cursor-grab');

    fireEvent.mouseDown(canvas, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 150 });

    expect(defaultProps.onPanChange).toHaveBeenCalled();
  });
});

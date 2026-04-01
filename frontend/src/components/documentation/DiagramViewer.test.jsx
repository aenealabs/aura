import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { DiagramViewer, DiagramGrid } from './DiagramViewer';

// Mock mermaid module
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg data-testid="mermaid-svg">Test SVG</svg>' }),
  },
}));

// Mock window.matchMedia for dark mode detection
const mockMatchMedia = (matches) => {
  return {
    matches,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
};

describe('DiagramViewer', () => {
  const sampleMermaidCode = `graph TB
    A[Start] --> B[Process]
    B --> C[End]`;

  beforeEach(() => {
    // Setup matchMedia mock
    window.matchMedia = vi.fn().mockReturnValue(mockMatchMedia(false));

    // Mock URL APIs
    global.URL.createObjectURL = vi.fn(() => 'blob:test-url');
    global.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('renders with default props', async () => {
    render(<DiagramViewer code={sampleMermaidCode} />);

    // Should show title
    expect(screen.getByText('Architecture Diagram')).toBeInTheDocument();

    // Should have diagram container with role="img"
    expect(screen.getByRole('img', { name: 'Architecture diagram' })).toBeInTheDocument();
  });

  test('renders loading skeleton when loading is true', () => {
    const { container } = render(<DiagramViewer loading={true} />);

    // Should not show the diagram container
    expect(screen.queryByRole('img')).not.toBeInTheDocument();

    // Should show skeleton elements
    expect(container.querySelector('[class*="animate-pulse"]')).toBeInTheDocument();
  });

  test('displays custom title', () => {
    render(<DiagramViewer code={sampleMermaidCode} title="Custom Title" />);

    expect(screen.getByText('Custom Title')).toBeInTheDocument();
  });

  test('displays formatted diagram type', () => {
    render(<DiagramViewer code={sampleMermaidCode} type="data_flow" />);

    expect(screen.getByText('Data Flow Diagram')).toBeInTheDocument();
  });

  test('shows confidence badge when confidence is provided', async () => {
    render(<DiagramViewer code={sampleMermaidCode} confidence={0.85} />);

    // Should render the confidence badge
    await waitFor(() => {
      expect(screen.getByText('High Confidence')).toBeInTheDocument();
    });
  });

  test('hides confidence badge when showConfidence is false', () => {
    render(
      <DiagramViewer code={sampleMermaidCode} confidence={0.85} showConfidence={false} />
    );

    expect(screen.queryByText('High Confidence')).not.toBeInTheDocument();
  });

  test('displays warnings when provided', () => {
    const warnings = ['Warning 1', 'Warning 2'];
    render(<DiagramViewer code={sampleMermaidCode} warnings={warnings} />);

    expect(screen.getByText('Warning 1')).toBeInTheDocument();
    expect(screen.getByText('Warning 2')).toBeInTheDocument();
  });

  test('hides warnings when showWarnings is false', () => {
    const warnings = ['Warning 1'];
    render(<DiagramViewer code={sampleMermaidCode} warnings={warnings} showWarnings={false} />);

    expect(screen.queryByText('Warning 1')).not.toBeInTheDocument();
  });

  test('hides controls when showControls is false', () => {
    render(<DiagramViewer code={sampleMermaidCode} showControls={false} />);

    expect(screen.queryByLabelText('Zoom in')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Zoom out')).not.toBeInTheDocument();
  });

  describe('zoom controls', () => {
    test('displays zoom percentage', () => {
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    test('zoom in button increases zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      const zoomInButton = screen.getByLabelText('Zoom in');
      await user.click(zoomInButton);

      // Zoom should increase by 1.25x
      expect(screen.getByText('125%')).toBeInTheDocument();
    });

    test('zoom out button decreases zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      const zoomOutButton = screen.getByLabelText('Zoom out');
      await user.click(zoomOutButton);

      // Zoom should decrease by 1.25x
      expect(screen.getByText('80%')).toBeInTheDocument();
    });

    test('expand to fullscreen button opens modal', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      // Click expand button
      const expandButton = screen.getByLabelText('Expand to fullscreen');
      await user.click(expandButton);

      // Modal should be visible with dialog role
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByLabelText('Close fullscreen')).toBeInTheDocument();
    });

    test('close button closes fullscreen modal', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      // Open fullscreen
      const expandButton = screen.getByLabelText('Expand to fullscreen');
      await user.click(expandButton);
      expect(screen.getByRole('dialog')).toBeInTheDocument();

      // Close fullscreen
      const closeButton = screen.getByLabelText('Close fullscreen');
      await user.click(closeButton);

      // Modal should be closed
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    test('fullscreen modal has zoom controls', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      // Open fullscreen
      const expandButton = screen.getByLabelText('Expand to fullscreen');
      await user.click(expandButton);

      // Modal should have zoom controls
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();

      // Should show initial zoom at 150%
      expect(screen.getByText('150%')).toBeInTheDocument();

      // Zoom controls should be present in modal
      const zoomInButtons = screen.getAllByLabelText('Zoom in');
      const zoomOutButtons = screen.getAllByLabelText('Zoom out');
      expect(zoomInButtons.length).toBeGreaterThanOrEqual(2); // One in card, one in modal
      expect(zoomOutButtons.length).toBeGreaterThanOrEqual(2);
    });

    test('fullscreen modal zoom in increases zoom', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      // Open fullscreen
      const expandButton = screen.getByLabelText('Expand to fullscreen');
      await user.click(expandButton);

      // Get the second zoom in button (in modal)
      const zoomInButtons = screen.getAllByLabelText('Zoom in');
      const modalZoomIn = zoomInButtons[zoomInButtons.length - 1];
      await user.click(modalZoomIn);

      // Zoom should increase from 150% to 188% (150 * 1.25)
      expect(screen.getByText('188%')).toBeInTheDocument();
    });

    test('fullscreen modal has reset view button', async () => {
      const user = userEvent.setup();
      render(<DiagramViewer code={sampleMermaidCode} initialZoom={1} />);

      // Open fullscreen
      const expandButton = screen.getByLabelText('Expand to fullscreen');
      await user.click(expandButton);

      // Reset view button should be present
      expect(screen.getByLabelText('Reset view')).toBeInTheDocument();
    });
  });

  describe('copy and download controls', () => {
    test('copy button is present', () => {
      render(<DiagramViewer code={sampleMermaidCode} />);

      const copyButton = screen.getByLabelText('Copy code');
      expect(copyButton).toBeInTheDocument();
    });

    test('download button is present', () => {
      render(<DiagramViewer code={sampleMermaidCode} />);

      const downloadButton = screen.getByLabelText('Download SVG');
      expect(downloadButton).toBeInTheDocument();
    });
  });

  describe('pan functionality', () => {
    test('container has cursor-grab class by default', () => {
      render(<DiagramViewer code={sampleMermaidCode} />);

      const container = screen.getByRole('img');
      expect(container).toHaveClass('cursor-grab');
    });

    test('changes cursor to grabbing on mouse down', () => {
      render(<DiagramViewer code={sampleMermaidCode} />);

      const container = screen.getByRole('img');

      // Simulate mouse down
      fireEvent.mouseDown(container, { button: 0, clientX: 100, clientY: 100 });

      // Should switch to cursor-grabbing
      expect(container).toHaveClass('cursor-grabbing');
    });

    test('resets cursor on mouse up', () => {
      render(<DiagramViewer code={sampleMermaidCode} />);

      const container = screen.getByRole('img');

      fireEvent.mouseDown(container, { button: 0, clientX: 100, clientY: 100 });
      expect(container).toHaveClass('cursor-grabbing');

      fireEvent.mouseUp(container);
      expect(container).toHaveClass('cursor-grab');
    });
  });

  test('shows code preview toggle', () => {
    render(<DiagramViewer code={sampleMermaidCode} />);

    const summary = screen.getByText('View Mermaid Code');
    expect(summary).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(
      <DiagramViewer code={sampleMermaidCode} className="custom-diagram" />
    );

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('custom-diagram');
  });

  test('renders with different diagram types', () => {
    const types = ['architecture', 'data_flow', 'dependency', 'sequence', 'component'];

    types.forEach((type) => {
      const { unmount } = render(<DiagramViewer code={sampleMermaidCode} type={type} />);
      expect(screen.getByRole('img')).toBeInTheDocument();
      unmount();
    });
  });
});

describe('DiagramGrid', () => {
  const sampleDiagrams = [
    {
      diagramType: 'architecture',
      mermaidCode: 'graph TB\n  A --> B',
      confidence: 0.85,
      warnings: [],
    },
    {
      diagramType: 'data_flow',
      mermaidCode: 'flowchart LR\n  C --> D',
      confidence: 0.75,
      warnings: ['Review needed'],
    },
  ];

  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue(mockMatchMedia(false));
  });

  test('renders empty message when no diagrams', () => {
    render(<DiagramGrid diagrams={[]} />);

    expect(screen.getByText('No diagrams available')).toBeInTheDocument();
  });

  test('renders multiple diagrams', () => {
    render(<DiagramGrid diagrams={sampleDiagrams} />);

    expect(screen.getByText('Architecture Diagram')).toBeInTheDocument();
    expect(screen.getByText('Data Flow Diagram')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(
      <DiagramGrid diagrams={sampleDiagrams} className="custom-grid" />
    );

    const grid = container.firstChild;
    expect(grid).toHaveClass('custom-grid');
  });

  test('uses correct number of columns', () => {
    const { container } = render(<DiagramGrid diagrams={sampleDiagrams} columns={3} />);

    const grid = container.firstChild;
    expect(grid).toHaveStyle('grid-template-columns: repeat(3, minmax(0, 1fr))');
  });

  test('uses default 2 columns', () => {
    const { container } = render(<DiagramGrid diagrams={sampleDiagrams} />);

    const grid = container.firstChild;
    expect(grid).toHaveStyle('grid-template-columns: repeat(2, minmax(0, 1fr))');
  });
});

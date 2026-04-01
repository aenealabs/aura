/**
 * Project Aura - AccessibleDiagramViewer Tests (ADR-060 Phase 3)
 *
 * WCAG 2.1 AA compliance tests for the accessible diagram viewer.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';

// Mock ThemeContext
vi.mock('../../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false, toggleTheme: vi.fn() }),
}));

// Mock accessibility hooks
vi.mock('../../hooks/useAccessibility', () => ({
  useReducedMotion: vi.fn(() => false),
  useHighContrast: vi.fn(() => false),
  useAnnouncer: () => vi.fn(),
  SkipLink: ({ href, children }) => (
    <a href={href} data-testid="skip-link">
      {children}
    </a>
  ),
  LiveRegion: ({ message }) => <div data-testid="live-region">{message}</div>,
}));

import AccessibleDiagramViewer, {
  NodeNavigator,
  KeyboardShortcutHelp,
} from './AccessibleDiagramViewer';
import { useReducedMotion, useHighContrast } from '../../hooks/useAccessibility';

const SAMPLE_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600">
  <rect data-node-id="node1" data-node-label="API Gateway" data-node-type="aws:api-gateway" x="100" y="100" width="200" height="100" fill="#3B82F6"/>
  <rect data-node-id="node2" data-node-label="Lambda" data-node-type="aws:lambda" x="400" y="100" width="200" height="100" fill="#10B981"/>
</svg>
`;

const SAMPLE_NODES = [
  { id: 'node1', label: 'API Gateway', type: 'aws:api-gateway' },
  { id: 'node2', label: 'Lambda', type: 'aws:lambda' },
  { id: 'node3', label: 'DynamoDB', type: 'aws:dynamodb' },
];

describe('AccessibleDiagramViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Skip Link', () => {
    test('renders skip link for keyboard navigation', () => {
      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByTestId('skip-link')).toBeInTheDocument();
      expect(screen.getByTestId('skip-link')).toHaveAttribute('href', '#diagram-canvas');
    });

    test('skip link text is descriptive', () => {
      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByTestId('skip-link')).toHaveTextContent(/skip to diagram/i);
    });
  });

  describe('Node Navigator', () => {
    test('can be toggled open and closed', async () => {
      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} nodes={SAMPLE_NODES} />);

      const user = userEvent.setup();

      // Find and click the navigator toggle
      const toggleButton = screen.getByRole('button', { name: /open node navigator/i });
      await user.click(toggleButton);

      // Navigator should now be expanded
      expect(screen.getByRole('region', { name: /node navigator/i })).toBeInTheDocument();
    });

    test('has searchable node list', async () => {
      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} nodes={SAMPLE_NODES} />);

      const user = userEvent.setup();

      // Open navigator
      await user.click(screen.getByRole('button', { name: /open node navigator/i }));

      // Find search input
      const searchInput = screen.getByRole('searchbox', { name: /search diagram nodes/i });
      expect(searchInput).toBeInTheDocument();
    });
  });

  describe('Keyboard Shortcuts', () => {
    test('? key toggles keyboard shortcut help', () => {
      const { container } = render(
        <AccessibleDiagramViewer svgContent={SAMPLE_SVG} nodes={SAMPLE_NODES} />
      );

      // Focus the container first
      container.querySelector('[tabindex]')?.focus();

      fireEvent.keyDown(document, { key: '?' });

      // Shortcut help should be visible
      expect(screen.getByRole('button', { name: /show keyboard shortcuts/i })).toBeInTheDocument();
    });

    test('Escape closes open panels', async () => {
      const { container } = render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} nodes={SAMPLE_NODES} />);

      const user = userEvent.setup();

      // Open navigator
      await user.click(screen.getByRole('button', { name: /open node navigator/i }));
      expect(screen.getByRole('region', { name: /node navigator/i })).toBeInTheDocument();

      // Focus must be within the container for Escape to work
      // Focus the close button inside the navigator (which is inside the container)
      const closeButton = screen.getByRole('button', { name: /close node navigator/i });
      closeButton.focus();

      // Press Escape on the focused element
      fireEvent.keyDown(closeButton, { key: 'Escape' });

      // Navigator should be closed
      await waitFor(() => {
        expect(screen.queryByRole('region', { name: /node navigator/i })).not.toBeInTheDocument();
      });
    });
  });

  describe('Reduced Motion Support', () => {
    test('applies motion-reduce class when user prefers reduced motion', () => {
      useReducedMotion.mockReturnValue(true);

      const { container } = render(
        <AccessibleDiagramViewer svgContent={SAMPLE_SVG} />
      );

      expect(container.firstChild).toHaveClass('motion-reduce');
    });

    test('does not apply motion-reduce class when user allows motion', () => {
      useReducedMotion.mockReturnValue(false);

      const { container } = render(
        <AccessibleDiagramViewer svgContent={SAMPLE_SVG} />
      );

      expect(container.firstChild).not.toHaveClass('motion-reduce');
    });
  });

  describe('High Contrast Mode', () => {
    test('shows indicator when high contrast mode is active', () => {
      useHighContrast.mockReturnValue(true);

      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByRole('status')).toHaveTextContent(/high contrast mode/i);
    });

    test('applies high contrast styles when mode is active', () => {
      useHighContrast.mockReturnValue(true);

      const { container } = render(
        <AccessibleDiagramViewer svgContent={SAMPLE_SVG} />
      );

      expect(container.firstChild).toHaveStyle({ filter: 'contrast(1.2)' });
    });
  });

  describe('Live Region', () => {
    test('renders live region for status announcements', () => {
      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} />);

      expect(screen.getByTestId('live-region')).toBeInTheDocument();
    });
  });

  describe('Diagram Canvas', () => {
    test('has id for skip link target', () => {
      render(<AccessibleDiagramViewer svgContent={SAMPLE_SVG} />);

      expect(document.getElementById('diagram-canvas')).toBeInTheDocument();
    });
  });
});

describe('NodeNavigator', () => {
  const defaultProps = {
    nodes: SAMPLE_NODES,
    selectedNodeId: null,
    onSelectNode: vi.fn(),
    onFocusNode: vi.fn(),
    isExpanded: true,
    onToggleExpanded: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Structure', () => {
    test('has region role with label', () => {
      render(<NodeNavigator {...defaultProps} />);

      expect(screen.getByRole('region', { name: /node navigator/i })).toBeInTheDocument();
    });

    test('has listbox role for node list', () => {
      render(<NodeNavigator {...defaultProps} />);

      expect(screen.getByRole('listbox', { name: /diagram nodes/i })).toBeInTheDocument();
    });

    test('each node has option role', () => {
      render(<NodeNavigator {...defaultProps} />);

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(SAMPLE_NODES.length);
    });
  });

  describe('Keyboard Navigation', () => {
    test('ArrowDown moves to next node', async () => {
      const onSelectNode = vi.fn();
      render(
        <NodeNavigator
          {...defaultProps}
          onSelectNode={onSelectNode}
          selectedNodeId="node1"
        />
      );

      const listbox = screen.getByRole('listbox');
      fireEvent.keyDown(listbox, { key: 'ArrowDown' });

      expect(onSelectNode).toHaveBeenCalledWith('node2');
    });

    test('ArrowUp moves to previous node', async () => {
      const onSelectNode = vi.fn();
      render(
        <NodeNavigator
          {...defaultProps}
          onSelectNode={onSelectNode}
          selectedNodeId="node2"
        />
      );

      const listbox = screen.getByRole('listbox');
      fireEvent.keyDown(listbox, { key: 'ArrowUp' });

      expect(onSelectNode).toHaveBeenCalledWith('node1');
    });

    test('Home moves to first node', async () => {
      const onSelectNode = vi.fn();
      render(
        <NodeNavigator
          {...defaultProps}
          onSelectNode={onSelectNode}
          selectedNodeId="node3"
        />
      );

      const listbox = screen.getByRole('listbox');
      fireEvent.keyDown(listbox, { key: 'Home' });

      expect(onSelectNode).toHaveBeenCalledWith('node1');
    });

    test('End moves to last node', async () => {
      const onSelectNode = vi.fn();
      render(
        <NodeNavigator
          {...defaultProps}
          onSelectNode={onSelectNode}
          selectedNodeId="node1"
        />
      );

      const listbox = screen.getByRole('listbox');
      fireEvent.keyDown(listbox, { key: 'End' });

      expect(onSelectNode).toHaveBeenCalledWith('node3');
    });

    test('Enter focuses the selected node', async () => {
      const onFocusNode = vi.fn();
      render(
        <NodeNavigator
          {...defaultProps}
          onFocusNode={onFocusNode}
          selectedNodeId="node1"
        />
      );

      const listbox = screen.getByRole('listbox');
      fireEvent.keyDown(listbox, { key: 'Enter' });

      expect(onFocusNode).toHaveBeenCalledWith('node1');
    });
  });

  describe('Search', () => {
    test('filters nodes based on search query', async () => {
      render(<NodeNavigator {...defaultProps} />);

      const user = userEvent.setup();
      const searchInput = screen.getByRole('searchbox');

      await user.type(searchInput, 'Lambda');

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('Lambda');
    });

    test('shows no nodes message when search has no results', async () => {
      render(<NodeNavigator {...defaultProps} />);

      const user = userEvent.setup();
      const searchInput = screen.getByRole('searchbox');

      await user.type(searchInput, 'nonexistent');

      expect(screen.getByText(/no nodes found/i)).toBeInTheDocument();
    });
  });

  describe('Selection', () => {
    test('selected node has aria-selected true', () => {
      render(<NodeNavigator {...defaultProps} selectedNodeId="node2" />);

      const options = screen.getAllByRole('option');
      const selectedOption = options.find(
        (opt) => opt.getAttribute('aria-selected') === 'true'
      );

      expect(selectedOption).toHaveTextContent('Lambda');
    });

    test('clicking a node calls onSelectNode', async () => {
      const onSelectNode = vi.fn();
      render(<NodeNavigator {...defaultProps} onSelectNode={onSelectNode} />);

      const user = userEvent.setup();
      const options = screen.getAllByRole('option');
      await user.click(options[1]);

      expect(onSelectNode).toHaveBeenCalledWith('node2');
    });

    test('double-clicking a node calls onFocusNode', async () => {
      const onFocusNode = vi.fn();
      render(<NodeNavigator {...defaultProps} onFocusNode={onFocusNode} />);

      const user = userEvent.setup();
      const options = screen.getAllByRole('option');
      await user.dblClick(options[0]);

      expect(onFocusNode).toHaveBeenCalledWith('node1');
    });
  });

  describe('Collapsed State', () => {
    test('shows toggle button when collapsed', () => {
      render(<NodeNavigator {...defaultProps} isExpanded={false} />);

      expect(
        screen.getByRole('button', { name: /open node navigator/i })
      ).toBeInTheDocument();
    });

    test('toggle button has aria-expanded false when collapsed', () => {
      render(<NodeNavigator {...defaultProps} isExpanded={false} />);

      expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false');
    });
  });
});

describe('KeyboardShortcutHelp', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  test('has dialog role when open', () => {
    render(<KeyboardShortcutHelp {...defaultProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('has accessible title', () => {
    render(<KeyboardShortcutHelp {...defaultProps} />);

    expect(screen.getByRole('dialog')).toHaveAttribute(
      'aria-labelledby',
      'shortcuts-title'
    );
    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
  });

  test('displays all shortcuts with key combinations', () => {
    render(<KeyboardShortcutHelp {...defaultProps} />);

    // Check for some expected shortcuts
    expect(screen.getByText('Zoom in')).toBeInTheDocument();
    expect(screen.getByText('Zoom out')).toBeInTheDocument();
    expect(screen.getByText('Pan diagram')).toBeInTheDocument();
  });

  test('close button is accessible', () => {
    render(<KeyboardShortcutHelp {...defaultProps} />);

    expect(
      screen.getByRole('button', { name: /close shortcuts panel/i })
    ).toBeInTheDocument();
  });

  test('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    render(<KeyboardShortcutHelp {...defaultProps} onClose={onClose} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /close shortcuts panel/i }));

    expect(onClose).toHaveBeenCalled();
  });

  test('does not render when isOpen is false', () => {
    render(<KeyboardShortcutHelp isOpen={false} onClose={vi.fn()} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

/**
 * Tests for ChecklistItem component
 *
 * Tests the individual checklist item including:
 * - Title and description display
 * - Completion status styling (icons, strikethrough, colors)
 * - Action button visibility and navigation
 * - Background styling based on state
 * - Icon rendering (outline vs solid)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import ChecklistItem from './ChecklistItem';

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

const defaultItem = {
  id: 'connect_repository',
  title: 'Connect your first repository',
  description: 'Link a GitHub, GitLab, or Bitbucket repository',
  action: {
    label: 'Connect',
    route: '/repositories',
  },
};

const itemWithoutAction = {
  id: 'review_docs',
  title: 'Review documentation',
  description: 'Read the getting started guide',
};

describe('ChecklistItem', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Content Display', () => {
    test('displays item title', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      expect(screen.getByText('Connect your first repository')).toBeInTheDocument();
    });

    test('displays item description', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      expect(
        screen.getByText('Link a GitHub, GitLab, or Bitbucket repository')
      ).toBeInTheDocument();
    });

    test('renders title in heading element', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const title = screen.getByText('Connect your first repository');
      expect(title.tagName).toBe('H4');
    });

    test('renders description in paragraph element', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const description = screen.getByText('Link a GitHub, GitLab, or Bitbucket repository');
      expect(description.tagName).toBe('P');
    });
  });

  describe('Incomplete State', () => {
    test('shows outline check icon when not completed', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      // Outline icon has text-surface-300 class
      const icon = container.querySelector('.text-surface-300');
      expect(icon).toBeInTheDocument();
    });

    test('title does not have strikethrough when not completed', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const title = screen.getByText('Connect your first repository');
      expect(title).not.toHaveClass('line-through');
    });

    test('title has normal text color when not completed', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const title = screen.getByText('Connect your first repository');
      expect(title).toHaveClass('text-surface-900');
    });

    test('has hover background when not completed', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('hover:bg-surface-100');
    });
  });

  describe('Completed State', () => {
    test('shows solid check icon when completed', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={true} />
      );

      // Solid icon has text-olive-500 class
      const icon = container.querySelector('.text-olive-500');
      expect(icon).toBeInTheDocument();
    });

    test('title has strikethrough when completed', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={true} />);

      const title = screen.getByText('Connect your first repository');
      expect(title).toHaveClass('line-through');
    });

    test('title has muted text color when completed', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={true} />);

      const title = screen.getByText('Connect your first repository');
      expect(title).toHaveClass('text-surface-500');
    });

    test('has olive background when completed', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={true} />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('bg-olive-50/50');
    });

    test('does not show action button when completed', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={true} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('Action Button', () => {
    test('shows action button when not completed and action exists', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument();
    });

    test('does not show action button when action is undefined', () => {
      render(<ChecklistItem item={itemWithoutAction} isCompleted={false} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    test('displays action label text', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      expect(screen.getByText('Connect')).toBeInTheDocument();
    });

    test('action button has arrow icon', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const button = screen.getByRole('button', { name: /connect/i });
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    test('action button has correct styling', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const button = screen.getByRole('button', { name: /connect/i });
      expect(button).toHaveClass('text-aura-600');
      expect(button).toHaveClass('bg-aura-50');
    });
  });

  describe('Navigation', () => {
    test('navigates to route when action button is clicked', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      fireEvent.click(screen.getByRole('button', { name: /connect/i }));

      expect(mockNavigate).toHaveBeenCalledWith('/repositories');
    });

    test('navigates to correct route for different items', () => {
      const settingsItem = {
        id: 'configure_analysis',
        title: 'Configure analysis',
        description: 'Set up your preferences',
        action: {
          label: 'Configure',
          route: '/settings/analysis',
        },
      };

      render(<ChecklistItem item={settingsItem} isCompleted={false} />);

      fireEvent.click(screen.getByRole('button', { name: /configure/i }));

      expect(mockNavigate).toHaveBeenCalledWith('/settings/analysis');
    });

    test('does not call navigate when action has no route', () => {
      const itemWithEmptyRoute = {
        ...defaultItem,
        action: { label: 'Click', route: undefined },
      };

      render(<ChecklistItem item={itemWithEmptyRoute} isCompleted={false} />);

      fireEvent.click(screen.getByRole('button', { name: /click/i }));

      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('Styling', () => {
    test('wrapper has rounded corners', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('rounded-lg');
    });

    test('wrapper has padding', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('p-3');
    });

    test('wrapper has transition effect', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('transition-all');
    });

    test('has group class for hover effects', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('group');
    });

    test('icon has correct size', () => {
      const { container } = render(
        <ChecklistItem item={defaultItem} isCompleted={false} />
      );

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-5', 'h-5');
    });
  });

  describe('Different Item Configurations', () => {
    test('handles item with only required fields', () => {
      const minimalItem = {
        id: 'minimal',
        title: 'Minimal item',
        description: 'Just basics',
      };

      render(<ChecklistItem item={minimalItem} isCompleted={false} />);

      expect(screen.getByText('Minimal item')).toBeInTheDocument();
      expect(screen.getByText('Just basics')).toBeInTheDocument();
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    test('handles long title and description', () => {
      const longItem = {
        id: 'long',
        title: 'This is a very long title that should still render properly',
        description:
          'This is an even longer description that explains the checklist item in great detail',
        action: { label: 'Go', route: '/somewhere' },
      };

      render(<ChecklistItem item={longItem} isCompleted={false} />);

      expect(
        screen.getByText('This is a very long title that should still render properly')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          'This is an even longer description that explains the checklist item in great detail'
        )
      ).toBeInTheDocument();
    });

    test('handles action with empty label', () => {
      const itemWithEmptyLabel = {
        ...defaultItem,
        action: { label: '', route: '/test' },
      };

      render(<ChecklistItem item={itemWithEmptyLabel} isCompleted={false} />);

      // Button should still render with empty text
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });
  });

  describe('onComplete Prop', () => {
    test('accepts onComplete prop without errors', () => {
      const onComplete = vi.fn();

      // Should not throw
      expect(() => {
        render(
          <ChecklistItem item={defaultItem} isCompleted={false} onComplete={onComplete} />
        );
      }).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    test('action button is focusable', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const button = screen.getByRole('button', { name: /connect/i });
      expect(button).not.toHaveAttribute('tabindex', '-1');
    });

    test('content is visible without interaction', () => {
      render(<ChecklistItem item={defaultItem} isCompleted={false} />);

      const title = screen.getByText('Connect your first repository');
      const description = screen.getByText('Link a GitHub, GitLab, or Bitbucket repository');

      expect(title).toBeVisible();
      expect(description).toBeVisible();
    });
  });
});

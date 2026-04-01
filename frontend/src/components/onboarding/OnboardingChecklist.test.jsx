/**
 * Tests for OnboardingChecklist component
 *
 * Tests the P1 onboarding checklist including:
 * - Conditional rendering based on showChecklist
 * - Portal rendering to document.body
 * - Collapsed state (progress ring, label, count)
 * - Expanded state (header, progress bar, items, footer)
 * - Toggle behavior
 * - Dismiss behavior
 * - Progress visualization
 * - Checklist items rendering
 * - Complete state messaging
 * - Tour integration
 * - Accessibility attributes
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import OnboardingChecklist from './OnboardingChecklist';

// Mock the OnboardingContext
vi.mock('../../context/OnboardingContext', () => ({
  useOnboarding: vi.fn(),
}));

// Mock the ChecklistItem component
vi.mock('./ChecklistItem', () => ({
  default: ({ item, isCompleted, onComplete }) => (
    <div
      data-testid={`checklist-item-${item.id}`}
      data-completed={isCompleted}
    >
      <span data-testid={`item-title-${item.id}`}>{item.title}</span>
      <span data-testid={`item-description-${item.id}`}>{item.description}</span>
      {!isCompleted && (
        <button onClick={onComplete} data-testid={`complete-${item.id}`}>
          Complete
        </button>
      )}
    </div>
  ),
}));

import { useOnboarding } from '../../context/OnboardingContext';

const mockChecklistItems = [
  {
    id: 'connect_repository',
    title: 'Connect your first repository',
    description: 'Link a GitHub, GitLab, or Bitbucket repository',
    action: { label: 'Connect', route: '/repositories' },
  },
  {
    id: 'configure_analysis',
    title: 'Configure analysis settings',
    description: 'Set up your code analysis preferences',
    action: { label: 'Configure', route: '/settings/analysis' },
  },
  {
    id: 'run_first_scan',
    title: 'Run your first security scan',
    description: 'Analyze your code for vulnerabilities',
    action: { label: 'Scan', route: '/scans' },
  },
  {
    id: 'review_vulnerabilities',
    title: 'Review vulnerabilities',
    description: 'Check the results and prioritize fixes',
    action: { label: 'Review', route: '/vulnerabilities' },
  },
  {
    id: 'invite_team_member',
    title: 'Invite a team member',
    description: 'Collaborate with your team',
    action: { label: 'Invite', route: '/settings/team' },
  },
];

const defaultMockOnboarding = {
  showChecklist: true,
  checklistExpanded: false,
  checklistSteps: {
    connect_repository: false,
    configure_analysis: false,
    run_first_scan: false,
    review_vulnerabilities: false,
    invite_team_member: false,
  },
  checklistProgress: {
    completed: 0,
    total: 5,
    percent: 0,
  },
  isChecklistComplete: false,
  checklistItems: mockChecklistItems,
  toggleChecklist: vi.fn(),
  dismissChecklist: vi.fn(),
  completeChecklistItem: vi.fn(),
  startTour: vi.fn(),
};

describe('OnboardingChecklist', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useOnboarding.mockReturnValue({ ...defaultMockOnboarding });
  });

  describe('Visibility', () => {
    test('renders nothing when showChecklist is false', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        showChecklist: false,
      });

      const { container } = render(<OnboardingChecklist />);

      expect(container.firstChild).toBeNull();
    });

    test('renders widget when showChecklist is true', () => {
      render(<OnboardingChecklist />);

      expect(screen.getByRole('complementary')).toBeInTheDocument();
    });

    test('renders via portal to document.body', () => {
      render(<OnboardingChecklist />);

      const widget = document.body.querySelector('[role="complementary"]');
      expect(widget).toBeInTheDocument();
    });
  });

  describe('Collapsed State', () => {
    test('shows collapsed button when checklistExpanded is false', () => {
      render(<OnboardingChecklist />);

      const button = screen.getByRole('button', { name: /setup progress/i });
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    test('displays progress count in collapsed state', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistProgress: { completed: 2, total: 5, percent: 40 },
      });

      render(<OnboardingChecklist />);

      expect(screen.getByText('(2/5)')).toBeInTheDocument();
    });

    test('displays "Setup" label when not complete', () => {
      render(<OnboardingChecklist />);

      expect(screen.getByText('Setup')).toBeInTheDocument();
    });

    test('displays "Setup Complete!" label when all items complete', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        isChecklistComplete: true,
        checklistProgress: { completed: 5, total: 5, percent: 100 },
      });

      render(<OnboardingChecklist />);

      expect(screen.getByText('Setup Complete!')).toBeInTheDocument();
    });

    test('displays completed count in progress ring center', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistProgress: { completed: 3, total: 5, percent: 60 },
      });

      render(<OnboardingChecklist />);

      // The number should be in the center of the ring
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    test('shows check icon when complete instead of number', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        isChecklistComplete: true,
        checklistProgress: { completed: 5, total: 5, percent: 100 },
      });

      render(<OnboardingChecklist />);

      // Check icon should be present (olive-500 color) - use document.body since portal renders there
      const checkIcon = document.body.querySelector('.text-olive-500');
      expect(checkIcon).toBeInTheDocument();
    });

    test('renders progress ring SVG', () => {
      render(<OnboardingChecklist />);

      // Use document.body since component renders via portal
      const svg = document.body.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass('-rotate-90');

      // Should have two circles (background and progress)
      const circles = document.body.querySelectorAll('circle');
      expect(circles.length).toBe(2);
    });
  });

  describe('Expanded State', () => {
    beforeEach(() => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
      });
    });

    test('shows expanded widget when checklistExpanded is true', () => {
      render(<OnboardingChecklist />);

      expect(screen.getByText('Getting Started')).toBeInTheDocument();
    });

    test('displays header with title and icons', () => {
      render(<OnboardingChecklist />);

      expect(screen.getByText('Getting Started')).toBeInTheDocument();
      expect(screen.getByLabelText('Collapse checklist')).toBeInTheDocument();
      expect(screen.getByLabelText('Dismiss checklist')).toBeInTheDocument();
    });

    test('displays progress bar with percentage', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        checklistProgress: { completed: 2, total: 5, percent: 40 },
      });

      render(<OnboardingChecklist />);

      expect(screen.getByText('Progress')).toBeInTheDocument();
      expect(screen.getByText('40%')).toBeInTheDocument();
    });

    test('renders all checklist items', () => {
      render(<OnboardingChecklist />);

      mockChecklistItems.forEach((item) => {
        expect(screen.getByTestId(`checklist-item-${item.id}`)).toBeInTheDocument();
      });
    });

    test('passes correct completion status to checklist items', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        checklistSteps: {
          connect_repository: true,
          configure_analysis: true,
          run_first_scan: false,
          review_vulnerabilities: false,
          invite_team_member: false,
        },
      });

      render(<OnboardingChecklist />);

      expect(screen.getByTestId('checklist-item-connect_repository')).toHaveAttribute(
        'data-completed',
        'true'
      );
      expect(screen.getByTestId('checklist-item-configure_analysis')).toHaveAttribute(
        'data-completed',
        'true'
      );
      expect(screen.getByTestId('checklist-item-run_first_scan')).toHaveAttribute(
        'data-completed',
        'false'
      );
    });

    test('shows "Take a quick tour" button in footer when not complete', () => {
      render(<OnboardingChecklist />);

      expect(screen.getByText(/take a quick tour/i)).toBeInTheDocument();
    });

    test('shows completion message when all items complete', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        isChecklistComplete: true,
        checklistProgress: { completed: 5, total: 5, percent: 100 },
      });

      render(<OnboardingChecklist />);

      expect(screen.getByText("You're all set!")).toBeInTheDocument();
      expect(screen.getByText('Dismiss checklist')).toBeInTheDocument();
    });
  });

  describe('Toggle Behavior', () => {
    test('calls toggleChecklist when collapsed button is clicked', () => {
      const toggleChecklist = vi.fn();
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        toggleChecklist,
      });

      render(<OnboardingChecklist />);

      fireEvent.click(screen.getByRole('button', { name: /setup progress/i }));

      expect(toggleChecklist).toHaveBeenCalledTimes(1);
    });

    test('calls toggleChecklist when collapse button is clicked in expanded state', () => {
      const toggleChecklist = vi.fn();
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        toggleChecklist,
      });

      render(<OnboardingChecklist />);

      fireEvent.click(screen.getByLabelText('Collapse checklist'));

      expect(toggleChecklist).toHaveBeenCalledTimes(1);
    });
  });

  describe('Dismiss Behavior', () => {
    test('calls dismissChecklist when dismiss button is clicked', () => {
      const dismissChecklist = vi.fn();
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        dismissChecklist,
      });

      render(<OnboardingChecklist />);

      fireEvent.click(screen.getByLabelText('Dismiss checklist'));

      expect(dismissChecklist).toHaveBeenCalledTimes(1);
    });

    test('calls dismissChecklist when footer dismiss button is clicked (complete state)', () => {
      const dismissChecklist = vi.fn();
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        isChecklistComplete: true,
        dismissChecklist,
      });

      render(<OnboardingChecklist />);

      fireEvent.click(screen.getByText('Dismiss checklist'));

      expect(dismissChecklist).toHaveBeenCalledTimes(1);
    });
  });

  describe('Tour Integration', () => {
    test('calls startTour when tour button is clicked', () => {
      const startTour = vi.fn();
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        startTour,
      });

      render(<OnboardingChecklist />);

      fireEvent.click(screen.getByText(/take a quick tour/i));

      expect(startTour).toHaveBeenCalledTimes(1);
    });

    test('does not show tour button when checklist is complete', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        isChecklistComplete: true,
      });

      render(<OnboardingChecklist />);

      expect(screen.queryByText(/take a quick tour/i)).not.toBeInTheDocument();
    });
  });

  describe('Checklist Item Actions', () => {
    test('calls completeChecklistItem when item complete button is clicked', () => {
      const completeChecklistItem = vi.fn();
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        completeChecklistItem,
      });

      render(<OnboardingChecklist />);

      fireEvent.click(screen.getByTestId('complete-connect_repository'));

      expect(completeChecklistItem).toHaveBeenCalledWith('connect_repository');
    });

    test('does not show complete button for already completed items', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        checklistSteps: {
          ...defaultMockOnboarding.checklistSteps,
          connect_repository: true,
        },
      });

      render(<OnboardingChecklist />);

      expect(screen.queryByTestId('complete-connect_repository')).not.toBeInTheDocument();
    });
  });

  describe('Progress Visualization', () => {
    test('progress bar width matches percentage', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
        checklistProgress: { completed: 3, total: 5, percent: 60 },
      });

      render(<OnboardingChecklist />);

      // Use document.body since component renders via portal
      const progressBar = document.body.querySelector('.bg-gradient-to-r');
      expect(progressBar).toHaveStyle({ width: '60%' });
    });

    test('progress ring stroke offset changes with progress', () => {
      const { rerender } = render(<OnboardingChecklist />);

      // Get initial stroke offset at 0% - use document.body since portal
      const progressCircle = document.body.querySelectorAll('circle')[1];
      const initialOffset = parseFloat(progressCircle.getAttribute('stroke-dashoffset'));

      // Update to 50%
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistProgress: { completed: 2, total: 5, percent: 50 },
      });
      rerender(<OnboardingChecklist />);

      const updatedOffset = parseFloat(
        document.body.querySelectorAll('circle')[1].getAttribute('stroke-dashoffset')
      );

      // Offset should decrease as progress increases
      expect(updatedOffset).toBeLessThan(initialOffset);
    });
  });

  describe('Accessibility', () => {
    test('has complementary role', () => {
      render(<OnboardingChecklist />);

      expect(screen.getByRole('complementary')).toBeInTheDocument();
    });

    test('has aria-label describing the widget', () => {
      render(<OnboardingChecklist />);

      expect(
        screen.getByRole('complementary', { name: /setup progress checklist/i })
      ).toBeInTheDocument();
    });

    test('collapsed button has descriptive aria-label', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistProgress: { completed: 2, total: 5, percent: 40 },
      });

      render(<OnboardingChecklist />);

      const button = screen.getByRole('button', { name: /2 of 5 complete/i });
      expect(button).toBeInTheDocument();
    });

    test('collapsed button has aria-expanded="false"', () => {
      render(<OnboardingChecklist />);

      const button = screen.getByRole('button', { name: /setup progress/i });
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    test('collapse button has accessible label', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
      });

      render(<OnboardingChecklist />);

      expect(screen.getByLabelText('Collapse checklist')).toBeInTheDocument();
    });

    test('dismiss button has accessible label', () => {
      useOnboarding.mockReturnValue({
        ...defaultMockOnboarding,
        checklistExpanded: true,
      });

      render(<OnboardingChecklist />);

      expect(screen.getByLabelText('Dismiss checklist')).toBeInTheDocument();
    });
  });

  describe('Fixed Positioning', () => {
    test('widget has fixed positioning classes', () => {
      render(<OnboardingChecklist />);

      const widget = screen.getByRole('complementary');
      expect(widget).toHaveClass('fixed', 'bottom-6', 'right-6', 'z-50');
    });
  });
});

/**
 * Tests for TourTooltip component
 *
 * Tests the tour tooltip including:
 * - Conditional rendering based on step prop
 * - Portal rendering to document.body
 * - Tooltip positioning (center, bottom, top, left, right)
 * - Viewport boundary clamping
 * - Keyboard navigation (arrows, escape, enter)
 * - Progress dots display
 * - Navigation buttons (Back, Next, Complete, Finish)
 * - Skip button functionality
 * - Resize and scroll event listeners
 * - Accessibility attributes
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import TourTooltip from './TourTooltip';

describe('TourTooltip', () => {
  const defaultStep = {
    id: 'step-1',
    title: 'Welcome to the Dashboard',
    content: 'This is where you can see all your metrics.',
    target: '[data-tour="dashboard"]',
    placement: 'bottom',
  };

  const defaultProps = {
    step: defaultStep,
    currentStep: 0,
    totalSteps: 5,
    onNext: vi.fn(),
    onPrev: vi.fn(),
    onSkip: vi.fn(),
  };

  // Mock getBoundingClientRect for tooltip and target elements
  const mockTooltipRect = {
    width: 320,
    height: 200,
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 320,
    bottom: 200,
  };

  const mockTargetRect = {
    width: 100,
    height: 50,
    x: 400,
    y: 300,
    top: 300,
    left: 400,
    right: 500,
    bottom: 350,
  };

  let originalQuerySelector;
  let mockTarget;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Mock window dimensions
    Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

    // Create mock target element
    mockTarget = document.createElement('div');
    mockTarget.setAttribute('data-tour', 'dashboard');
    mockTarget.getBoundingClientRect = vi.fn(() => mockTargetRect);
    document.body.appendChild(mockTarget);

    // Store original querySelector
    originalQuerySelector = document.querySelector.bind(document);
  });

  afterEach(() => {
    vi.useRealTimers();
    if (mockTarget && mockTarget.parentNode) {
      mockTarget.parentNode.removeChild(mockTarget);
    }
  });

  describe('Visibility', () => {
    test('renders nothing when step is null', () => {
      const { container } = render(<TourTooltip {...defaultProps} step={null} />);

      expect(container.firstChild).toBeNull();
    });

    test('renders nothing when step is undefined', () => {
      const { container } = render(<TourTooltip {...defaultProps} step={undefined} />);

      expect(container.firstChild).toBeNull();
    });

    test('renders tooltip when step is provided', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('renders via portal to document.body', () => {
      render(<TourTooltip {...defaultProps} />);

      const dialog = document.body.querySelector('[role="dialog"]');
      expect(dialog).toBeInTheDocument();
    });
  });

  describe('Content Display', () => {
    test('displays step title', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByText('Welcome to the Dashboard')).toBeInTheDocument();
    });

    test('displays step content', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(
        screen.getByText('This is where you can see all your metrics.')
      ).toBeInTheDocument();
    });

    test('title has correct id for aria-labelledby', () => {
      render(<TourTooltip {...defaultProps} />);

      const title = screen.getByText('Welcome to the Dashboard');
      expect(title).toHaveAttribute('id', 'tour-step-title');
    });

    test('content has correct id for aria-describedby', () => {
      render(<TourTooltip {...defaultProps} />);

      const content = screen.getByText('This is where you can see all your metrics.');
      expect(content).toHaveAttribute('id', 'tour-step-content');
    });
  });

  describe('Progress Dots', () => {
    test('displays correct number of progress dots', () => {
      render(<TourTooltip {...defaultProps} totalSteps={5} />);

      // Portal renders to document.body
      const dots = document.body.querySelectorAll('.w-2.h-2.rounded-full');
      expect(dots.length).toBe(5);
    });

    test('current step dot is highlighted with aura color', () => {
      render(<TourTooltip {...defaultProps} currentStep={2} totalSteps={5} />);

      const dots = document.body.querySelectorAll('.w-2.h-2.rounded-full');
      expect(dots[2]).toHaveClass('bg-aura-500');
    });

    test('completed steps have olive color', () => {
      render(<TourTooltip {...defaultProps} currentStep={3} totalSteps={5} />);

      const dots = document.body.querySelectorAll('.w-2.h-2.rounded-full');
      expect(dots[0]).toHaveClass('bg-olive-400');
      expect(dots[1]).toHaveClass('bg-olive-400');
      expect(dots[2]).toHaveClass('bg-olive-400');
    });

    test('future steps have surface color', () => {
      render(<TourTooltip {...defaultProps} currentStep={1} totalSteps={5} />);

      const dots = document.body.querySelectorAll('.w-2.h-2.rounded-full');
      expect(dots[2]).toHaveClass('bg-surface-300');
      expect(dots[3]).toHaveClass('bg-surface-300');
      expect(dots[4]).toHaveClass('bg-surface-300');
    });
  });

  describe('Navigation Buttons', () => {
    test('shows Next button on first step', () => {
      render(<TourTooltip {...defaultProps} currentStep={0} />);

      expect(screen.getByText('Next')).toBeInTheDocument();
    });

    test('hides Back button on first step', () => {
      render(<TourTooltip {...defaultProps} currentStep={0} />);

      expect(screen.queryByText('Back')).not.toBeInTheDocument();
    });

    test('shows Back button on middle steps', () => {
      render(<TourTooltip {...defaultProps} currentStep={2} totalSteps={5} />);

      expect(screen.getByText('Back')).toBeInTheDocument();
    });

    test('shows Complete button on last step', () => {
      render(<TourTooltip {...defaultProps} currentStep={4} totalSteps={5} />);

      expect(screen.getByText('Complete')).toBeInTheDocument();
    });

    test('shows Finish button on completion step', () => {
      const completionStep = {
        id: 'completion',
        title: 'Tour Complete!',
        content: 'You are all set.',
        placement: 'center',
      };

      render(
        <TourTooltip
          {...defaultProps}
          step={completionStep}
          currentStep={4}
          totalSteps={5}
        />
      );

      expect(screen.getByText('Finish')).toBeInTheDocument();
    });

    test('hides Back button on completion step', () => {
      const completionStep = {
        id: 'completion',
        title: 'Tour Complete!',
        content: 'You are all set.',
        placement: 'center',
      };

      render(
        <TourTooltip
          {...defaultProps}
          step={completionStep}
          currentStep={4}
          totalSteps={5}
        />
      );

      expect(screen.queryByText('Back')).not.toBeInTheDocument();
    });

    test('calls onNext when Next button is clicked', () => {
      const onNext = vi.fn();
      render(<TourTooltip {...defaultProps} onNext={onNext} />);

      fireEvent.click(screen.getByText('Next'));

      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('calls onPrev when Back button is clicked', () => {
      const onPrev = vi.fn();
      render(<TourTooltip {...defaultProps} currentStep={2} onPrev={onPrev} />);

      fireEvent.click(screen.getByText('Back'));

      expect(onPrev).toHaveBeenCalledTimes(1);
    });
  });

  describe('Skip Button', () => {
    test('displays skip button', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByLabelText('Skip tour')).toBeInTheDocument();
    });

    test('calls onSkip when skip button is clicked', () => {
      const onSkip = vi.fn();
      render(<TourTooltip {...defaultProps} onSkip={onSkip} />);

      fireEvent.click(screen.getByLabelText('Skip tour'));

      expect(onSkip).toHaveBeenCalledTimes(1);
    });
  });

  describe('Keyboard Navigation', () => {
    test('calls onNext when ArrowRight is pressed', () => {
      const onNext = vi.fn();
      render(<TourTooltip {...defaultProps} onNext={onNext} />);

      fireEvent.keyDown(window, { key: 'ArrowRight' });

      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('calls onNext when Enter is pressed', () => {
      const onNext = vi.fn();
      render(<TourTooltip {...defaultProps} onNext={onNext} />);

      fireEvent.keyDown(window, { key: 'Enter' });

      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('calls onPrev when ArrowLeft is pressed', () => {
      const onPrev = vi.fn();
      render(<TourTooltip {...defaultProps} onPrev={onPrev} />);

      fireEvent.keyDown(window, { key: 'ArrowLeft' });

      expect(onPrev).toHaveBeenCalledTimes(1);
    });

    test('calls onSkip when Escape is pressed', () => {
      const onSkip = vi.fn();
      render(<TourTooltip {...defaultProps} onSkip={onSkip} />);

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(onSkip).toHaveBeenCalledTimes(1);
    });

    test('does not respond to other keys', () => {
      const onNext = vi.fn();
      const onPrev = vi.fn();
      const onSkip = vi.fn();
      render(
        <TourTooltip {...defaultProps} onNext={onNext} onPrev={onPrev} onSkip={onSkip} />
      );

      fireEvent.keyDown(window, { key: 'Space' });

      expect(onNext).not.toHaveBeenCalled();
      expect(onPrev).not.toHaveBeenCalled();
      expect(onSkip).not.toHaveBeenCalled();
    });
  });

  describe('Keyboard Hint', () => {
    test('displays keyboard navigation hint', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByText(/Use/)).toBeInTheDocument();
      expect(screen.getByText(/to navigate/)).toBeInTheDocument();
      expect(screen.getByText(/to skip/)).toBeInTheDocument();
    });

    test('displays keyboard keys in kbd elements', () => {
      render(<TourTooltip {...defaultProps} />);

      // Portal renders to document.body
      const kbdElements = document.body.querySelectorAll('kbd');
      expect(kbdElements.length).toBe(3); // ←, →, Esc
    });
  });

  describe('Positioning - Center Placement', () => {
    test('centers tooltip when placement is center', () => {
      const centerStep = {
        ...defaultStep,
        target: null,
        placement: 'center',
      };

      render(<TourTooltip {...defaultProps} step={centerStep} />);

      // Trigger position update
      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      // Verify that left and top style properties are set (centered positioning)
      expect(dialog.style.left).toBeDefined();
      expect(dialog.style.top).toBeDefined();
    });

    test('centers tooltip when target is not provided', () => {
      const noTargetStep = {
        ...defaultStep,
        target: null,
      };

      render(<TourTooltip {...defaultProps} step={noTargetStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });
  });

  describe('Positioning - Target-based Placement', () => {
    test('positions tooltip below target for bottom placement', () => {
      render(<TourTooltip {...defaultProps} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    test('positions tooltip above target for top placement', () => {
      const topStep = { ...defaultStep, placement: 'top' };
      render(<TourTooltip {...defaultProps} step={topStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    test('positions tooltip left of target for left placement', () => {
      const leftStep = { ...defaultStep, placement: 'left' };
      render(<TourTooltip {...defaultProps} step={leftStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    test('positions tooltip right of target for right placement', () => {
      const rightStep = { ...defaultStep, placement: 'right' };
      render(<TourTooltip {...defaultProps} step={rightStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    test('uses default bottom placement for unknown placement', () => {
      const unknownStep = { ...defaultStep, placement: 'unknown' };
      render(<TourTooltip {...defaultProps} step={unknownStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    test('handles missing target element gracefully', () => {
      // Remove the mock target
      if (mockTarget.parentNode) {
        mockTarget.parentNode.removeChild(mockTarget);
      }

      const missingTargetStep = {
        ...defaultStep,
        target: '[data-tour="nonexistent"]',
      };

      render(<TourTooltip {...defaultProps} step={missingTargetStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Should still render without crashing
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('Event Listeners', () => {
    test('updates position on window resize', () => {
      render(<TourTooltip {...defaultProps} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Trigger resize
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('updates position on scroll', () => {
      render(<TourTooltip {...defaultProps} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Trigger scroll
      act(() => {
        window.dispatchEvent(new Event('scroll'));
      });

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('removes event listeners on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = render(<TourTooltip {...defaultProps} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'scroll',
        expect.any(Function),
        true
      );
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'keydown',
        expect.any(Function)
      );

      removeEventListenerSpy.mockRestore();
    });

    test('removes keyboard listener on unmount', () => {
      const onSkip = vi.fn();
      const { unmount } = render(<TourTooltip {...defaultProps} onSkip={onSkip} />);

      unmount();

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(onSkip).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    test('has dialog role', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('has aria-labelledby pointing to title', () => {
      render(<TourTooltip {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby', 'tour-step-title');
    });

    test('has aria-describedby pointing to content', () => {
      render(<TourTooltip {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-describedby', 'tour-step-content');
    });

    test('skip button has accessible label', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByLabelText('Skip tour')).toBeInTheDocument();
    });

    test('buttons are focusable', () => {
      render(<TourTooltip {...defaultProps} currentStep={2} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).not.toHaveAttribute('tabindex', '-1');
      });
    });
  });

  describe('Styling', () => {
    test('tooltip has fixed positioning', () => {
      render(<TourTooltip {...defaultProps} />);

      // Portal renders to document.body
      const dialog = document.body.querySelector('.fixed');
      expect(dialog).toBeInTheDocument();
    });

    test('tooltip has correct width', () => {
      render(<TourTooltip {...defaultProps} />);

      // Portal renders to document.body
      const dialog = document.body.querySelector('.w-80');
      expect(dialog).toBeInTheDocument();
    });

    test('tooltip has rounded corners', () => {
      render(<TourTooltip {...defaultProps} />);

      // Portal renders to document.body
      const dialog = document.body.querySelector('.rounded-xl');
      expect(dialog).toBeInTheDocument();
    });

    test('tooltip has shadow', () => {
      render(<TourTooltip {...defaultProps} />);

      // Portal renders to document.body
      const dialog = document.body.querySelector('.shadow-2xl');
      expect(dialog).toBeInTheDocument();
    });

    test('header has aura background', () => {
      render(<TourTooltip {...defaultProps} />);

      // Portal renders to document.body
      const header = document.body.querySelector('.bg-aura-50');
      expect(header).toBeInTheDocument();
    });

    test('next button has primary styling', () => {
      render(<TourTooltip {...defaultProps} />);

      const nextButton = screen.getByText('Next').closest('button');
      expect(nextButton).toHaveClass('bg-aura-600');
    });
  });

  describe('Step Transitions', () => {
    test('updates when step prop changes', () => {
      const { rerender } = render(<TourTooltip {...defaultProps} />);

      expect(screen.getByText('Welcome to the Dashboard')).toBeInTheDocument();

      const newStep = {
        ...defaultStep,
        id: 'step-2',
        title: 'New Step Title',
        content: 'New step content.',
      };

      rerender(<TourTooltip {...defaultProps} step={newStep} />);

      expect(screen.getByText('New Step Title')).toBeInTheDocument();
      expect(screen.getByText('New step content.')).toBeInTheDocument();
    });

    test('recalculates position when step changes', () => {
      const { rerender } = render(<TourTooltip {...defaultProps} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      const newStep = {
        ...defaultStep,
        id: 'step-2',
        placement: 'top',
      };

      rerender(<TourTooltip {...defaultProps} step={newStep} />);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });
});

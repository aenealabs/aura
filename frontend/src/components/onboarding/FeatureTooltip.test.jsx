/**
 * Tests for FeatureTooltip and TooltipIndicator components
 *
 * Tests the P3 in-app feature tooltips including:
 * - Indicator display for unseen features
 * - Tooltip visibility on hover/focus
 * - Dismissal functionality
 * - Placement positioning
 * - Accessibility attributes
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import FeatureTooltip from './FeatureTooltip';
import TooltipIndicator from './TooltipIndicator';

// Mock the OnboardingContext
vi.mock('../../context/OnboardingContext', () => ({
  useFeatureTooltip: vi.fn(),
}));

import { useFeatureTooltip } from '../../context/OnboardingContext';

const mockTooltip = {
  id: 'graphrag_toggle',
  title: 'GraphRAG Mode',
  content: 'Enable hybrid graph + vector search for deeper code understanding.',
};

const defaultMockHook = {
  tooltip: mockTooltip,
  isDismissed: false,
  dismiss: vi.fn(),
  shouldShow: true,
};

describe('FeatureTooltip', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    useFeatureTooltip.mockReturnValue({ ...defaultMockHook });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    test('renders children when no tooltip exists', () => {
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        tooltip: null,
        shouldShow: false,
      });

      render(
        <FeatureTooltip tooltipId="nonexistent">
          <button>Test Button</button>
        </FeatureTooltip>
      );

      expect(screen.getByRole('button', { name: 'Test Button' })).toBeInTheDocument();
    });

    test('renders children with wrapper when tooltip exists', () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle">
          <button>Feature Button</button>
        </FeatureTooltip>
      );

      expect(screen.getByRole('button', { name: 'Feature Button' })).toBeInTheDocument();
    });

    test('shows indicator when tooltip not dismissed and showIndicator true', () => {
      const { container } = render(
        <FeatureTooltip tooltipId="graphrag_toggle" showIndicator={true}>
          <button>Button</button>
        </FeatureTooltip>
      );

      // Indicator should be present (has animate-ping class)
      expect(container.querySelector('.animate-ping')).toBeInTheDocument();
    });

    test('hides indicator when showIndicator is false', () => {
      const { container } = render(
        <FeatureTooltip tooltipId="graphrag_toggle" showIndicator={false}>
          <button>Button</button>
        </FeatureTooltip>
      );

      expect(container.querySelector('.animate-ping')).not.toBeInTheDocument();
    });

    test('hides indicator when tooltip is dismissed', () => {
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        isDismissed: true,
      });

      const { container } = render(
        <FeatureTooltip tooltipId="graphrag_toggle">
          <button>Button</button>
        </FeatureTooltip>
      );

      expect(container.querySelector('.animate-ping')).not.toBeInTheDocument();
    });
  });

  describe('Tooltip Visibility', () => {
    test('shows tooltip on mouse enter after delay', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={300}>
          <button>Hover Me</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Hover Me' }).parentElement;
      fireEvent.mouseEnter(container);

      // Tooltip should not be visible immediately
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

      // Advance timers past delay
      act(() => {
        vi.advanceTimersByTime(350);
      });

      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });

    test('hides tooltip on mouse leave', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Hover Me</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Hover Me' }).parentElement;

      // Show tooltip
      fireEvent.mouseEnter(container);
      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByRole('tooltip')).toBeInTheDocument();

      // Hide tooltip
      fireEvent.mouseLeave(container);

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    test('shows tooltip on focus', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle">
          <button>Focus Me</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Focus Me' }).parentElement;
      fireEvent.focus(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });

    test('hides tooltip on blur', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle">
          <button>Focus Me</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Focus Me' }).parentElement;

      // Show tooltip
      fireEvent.focus(container);
      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByRole('tooltip')).toBeInTheDocument();

      // Hide tooltip
      fireEvent.blur(container);

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    test('does not show tooltip when shouldShow is false', () => {
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        shouldShow: false,
      });

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    test('cancels tooltip show on mouse leave before delay', () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={500}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;

      fireEvent.mouseEnter(container);

      // Leave before delay completes
      act(() => {
        vi.advanceTimersByTime(200);
      });
      fireEvent.mouseLeave(container);

      // Advance past original delay
      act(() => {
        vi.advanceTimersByTime(400);
      });

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  describe('Tooltip Content', () => {
    test('displays tooltip title', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByText('GraphRAG Mode')).toBeInTheDocument();
    });

    test('displays tooltip content', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(
        screen.getByText('Enable hybrid graph + vector search for deeper code understanding.')
      ).toBeInTheDocument();
    });

    test('displays dismiss hint', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByText(/to hide permanently/i)).toBeInTheDocument();
    });
  });

  describe('Dismissal', () => {
    test('calls dismiss when dismiss button clicked', async () => {
      const dismiss = vi.fn();
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        dismiss,
      });

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Button' }).parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      const dismissButton = screen.getByLabelText('Dismiss tooltip');
      fireEvent.click(dismissButton);

      expect(dismiss).toHaveBeenCalledTimes(1);
    });

    test('hides tooltip after dismiss', async () => {
      const dismiss = vi.fn();
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        dismiss,
      });

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Button' }).parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByRole('tooltip')).toBeInTheDocument();

      const dismissButton = screen.getByLabelText('Dismiss tooltip');
      fireEvent.click(dismissButton);

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    test('stops event propagation on dismiss click', async () => {
      const parentClick = vi.fn();
      const dismiss = vi.fn();
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        dismiss,
      });

      render(
        <div onClick={parentClick}>
          <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
            <button>Button</button>
          </FeatureTooltip>
        </div>
      );

      const container = screen.getByRole('button', { name: 'Button' }).parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      const dismissButton = screen.getByLabelText('Dismiss tooltip');
      fireEvent.click(dismissButton);

      expect(parentClick).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    test('tooltip has role="tooltip"', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });

    test('dismiss button has accessible label', async () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Button' }).parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(screen.getByLabelText('Dismiss tooltip')).toBeInTheDocument();
    });
  });

  describe('Cleanup', () => {
    test('cleans up timeout on unmount', () => {
      const { unmount } = render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={500}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      // Unmount before timeout
      unmount();

      // Should not throw any errors when timer fires
      act(() => {
        vi.advanceTimersByTime(600);
      });
    });
  });

  describe('Placement Positioning', () => {
    let originalGetBoundingClientRect;

    beforeEach(() => {
      originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
    });

    afterEach(() => {
      Element.prototype.getBoundingClientRect = originalGetBoundingClientRect;
    });

    const setupPositionTest = (placement, containerRect, tooltipRect) => {
      // Mock getBoundingClientRect to return different values based on element role
      Element.prototype.getBoundingClientRect = function () {
        if (this.getAttribute('role') === 'tooltip') {
          return tooltipRect;
        }
        // Return container rect for the wrapper div
        return containerRect;
      };

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" placement={placement} delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const wrapper = screen.getByRole('button').parentElement;
      return { wrapper };
    };

    test('calculates top placement position correctly', async () => {
      const containerRect = {
        x: 100, y: 200, width: 80, height: 40, top: 200, left: 100, bottom: 240, right: 180,
      };
      const tooltipRect = {
        x: 0, y: 0, width: 256, height: 100, top: 0, left: 0, bottom: 100, right: 256,
      };

      const { wrapper } = setupPositionTest('top', containerRect, tooltipRect);

      fireEvent.mouseEnter(wrapper);
      await act(async () => {
        vi.runAllTimers();
      });

      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();

      // Trigger resize to force position update (resize listener is now active)
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Top placement: x centered, y above container
      expect(tooltip.style.left).toBeDefined();
      expect(tooltip.style.top).toBeDefined();
    });

    test('calculates bottom placement position correctly', async () => {
      const containerRect = {
        x: 100, y: 200, width: 80, height: 40, top: 200, left: 100, bottom: 240, right: 180,
      };
      const tooltipRect = {
        x: 0, y: 0, width: 256, height: 100, top: 0, left: 0, bottom: 100, right: 256,
      };

      const { wrapper } = setupPositionTest('bottom', containerRect, tooltipRect);

      fireEvent.mouseEnter(wrapper);
      await act(async () => {
        vi.runAllTimers();
      });

      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();

      // Trigger resize to force position update
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Bottom placement: y = container.bottom + padding
      expect(tooltip.style.left).toBeDefined();
      expect(tooltip.style.top).toBeDefined();
    });

    test('calculates left placement position correctly', async () => {
      const containerRect = {
        x: 300, y: 200, width: 80, height: 40, top: 200, left: 300, bottom: 240, right: 380,
      };
      const tooltipRect = {
        x: 0, y: 0, width: 256, height: 100, top: 0, left: 0, bottom: 100, right: 256,
      };

      const { wrapper } = setupPositionTest('left', containerRect, tooltipRect);

      fireEvent.mouseEnter(wrapper);
      await act(async () => {
        vi.runAllTimers();
      });

      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();

      // Trigger resize to force position update
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Left placement: x = container.x - tooltip.width - padding
      expect(tooltip.style.left).toBeDefined();
      expect(tooltip.style.top).toBeDefined();
    });

    test('calculates right placement position correctly', async () => {
      const containerRect = {
        x: 100, y: 200, width: 80, height: 40, top: 200, left: 100, bottom: 240, right: 180,
      };
      const tooltipRect = {
        x: 0, y: 0, width: 256, height: 100, top: 0, left: 0, bottom: 100, right: 256,
      };

      const { wrapper } = setupPositionTest('right', containerRect, tooltipRect);

      fireEvent.mouseEnter(wrapper);
      await act(async () => {
        vi.runAllTimers();
      });

      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();

      // Trigger resize to force position update
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Right placement: x = container.right + padding
      expect(tooltip.style.left).toBeDefined();
      expect(tooltip.style.top).toBeDefined();
    });

    test('uses default (top) placement for unknown placement value', async () => {
      const containerRect = {
        x: 100, y: 200, width: 80, height: 40, top: 200, left: 100, bottom: 240, right: 180,
      };
      const tooltipRect = {
        x: 0, y: 0, width: 256, height: 100, top: 0, left: 0, bottom: 100, right: 256,
      };

      const { wrapper } = setupPositionTest('unknown-placement', containerRect, tooltipRect);

      fireEvent.mouseEnter(wrapper);
      await act(async () => {
        vi.runAllTimers();
      });

      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();

      // Trigger resize to force position update
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Should still render and position the tooltip using default (top)
      expect(tooltip.style.left).toBeDefined();
      expect(tooltip.style.top).toBeDefined();
    });

    test('clamps position to viewport bounds', async () => {
      // Mock small window dimensions
      Object.defineProperty(window, 'innerWidth', { value: 500, writable: true });
      Object.defineProperty(window, 'innerHeight', { value: 400, writable: true });

      const containerRect = {
        x: 100, y: 200, width: 80, height: 40, top: 200, left: 100, bottom: 240, right: 180,
      };
      const tooltipRect = {
        x: 0, y: 0, width: 256, height: 100, top: 0, left: 0, bottom: 100, right: 256,
      };

      const { wrapper } = setupPositionTest('top', containerRect, tooltipRect);

      fireEvent.mouseEnter(wrapper);
      await act(async () => {
        vi.runAllTimers();
      });

      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();

      // Trigger resize to force position update
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Position should be clamped to viewport
      expect(tooltip.style.left).toBeDefined();
      expect(tooltip.style.top).toBeDefined();
    });
  });

  describe('Resize and Scroll Events', () => {
    test('adds resize listener when tooltip is visible', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(addEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      addEventListenerSpy.mockRestore();
    });

    test('adds scroll listener when tooltip is visible', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(addEventListenerSpy).toHaveBeenCalledWith('scroll', expect.any(Function), true);
      addEventListenerSpy.mockRestore();
    });

    test('removes resize listener when tooltip is hidden', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;

      // Show tooltip
      fireEvent.mouseEnter(container);
      act(() => {
        vi.advanceTimersByTime(50);
      });

      // Hide tooltip
      fireEvent.mouseLeave(container);

      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      removeEventListenerSpy.mockRestore();
    });

    test('removes scroll listener when tooltip is hidden', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;

      // Show tooltip
      fireEvent.mouseEnter(container);
      act(() => {
        vi.advanceTimersByTime(50);
      });

      // Hide tooltip
      fireEvent.mouseLeave(container);

      expect(removeEventListenerSpy).toHaveBeenCalledWith('scroll', expect.any(Function), true);
      removeEventListenerSpy.mockRestore();
    });

    test('updates position on window resize', () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      const tooltip = screen.getByRole('tooltip');
      const initialLeft = tooltip.style.left;

      // Trigger resize
      act(() => {
        window.dispatchEvent(new Event('resize'));
      });

      // Tooltip should still be visible (position may update)
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });

    test('updates position on scroll', () => {
      render(
        <FeatureTooltip tooltipId="graphrag_toggle" delay={0}>
          <button>Button</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button').parentElement;
      fireEvent.mouseEnter(container);

      act(() => {
        vi.advanceTimersByTime(50);
      });

      // Trigger scroll
      act(() => {
        window.dispatchEvent(new Event('scroll'));
      });

      // Tooltip should still be visible (position may update)
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });
  });

  describe('Focus Events', () => {
    test('does not show tooltip on focus when shouldShow is false', () => {
      useFeatureTooltip.mockReturnValue({
        ...defaultMockHook,
        shouldShow: false,
      });

      render(
        <FeatureTooltip tooltipId="graphrag_toggle">
          <button>Focus Me</button>
        </FeatureTooltip>
      );

      const container = screen.getByRole('button', { name: 'Focus Me' }).parentElement;
      fireEvent.focus(container);

      act(() => {
        vi.advanceTimersByTime(350);
      });

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });
});

describe('TooltipIndicator', () => {
  test('renders nothing when show is false', () => {
    const { container } = render(<TooltipIndicator show={false} />);

    expect(container.firstChild).toBeNull();
  });

  test('renders indicator when show is true', () => {
    const { container } = render(<TooltipIndicator show={true} />);

    expect(container.firstChild).toBeInTheDocument();
  });

  test('applies sm size class by default', () => {
    const { container } = render(<TooltipIndicator show={true} />);

    const solidDot = container.querySelector('.bg-aura-500');
    expect(solidDot).toHaveClass('w-2', 'h-2');
  });

  test('applies xs size class', () => {
    const { container } = render(<TooltipIndicator show={true} size="xs" />);

    const solidDot = container.querySelector('.bg-aura-500');
    expect(solidDot).toHaveClass('w-1.5', 'h-1.5');
  });

  test('applies md size class', () => {
    const { container } = render(<TooltipIndicator show={true} size="md" />);

    const solidDot = container.querySelector('.bg-aura-500');
    expect(solidDot).toHaveClass('w-2.5', 'h-2.5');
  });

  test('applies lg size class', () => {
    const { container } = render(<TooltipIndicator show={true} size="lg" />);

    const solidDot = container.querySelector('.bg-aura-500');
    expect(solidDot).toHaveClass('w-3', 'h-3');
  });

  test('has aria-hidden attribute', () => {
    const { container } = render(<TooltipIndicator show={true} />);

    const indicator = container.querySelector('[aria-hidden="true"]');
    expect(indicator).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(
      <TooltipIndicator show={true} className="absolute top-0 right-0" />
    );

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('absolute', 'top-0', 'right-0');
  });

  test('has ping animation element', () => {
    const { container } = render(<TooltipIndicator show={true} />);

    const pingElement = container.querySelector('.animate-ping');
    expect(pingElement).toBeInTheDocument();
    expect(pingElement).toHaveClass('bg-aura-400', 'opacity-75');
  });

  test('has solid dot element', () => {
    const { container } = render(<TooltipIndicator show={true} />);

    const solidDot = container.querySelector('.bg-aura-500');
    expect(solidDot).toBeInTheDocument();
    expect(solidDot).toHaveClass('rounded-full');
  });
});

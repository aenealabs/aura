/**
 * Tests for WelcomeTour, TourTooltip, and TourSpotlight components
 *
 * Tests the P2 guided tour including:
 * - Tour orchestration and visibility
 * - Tooltip positioning and content
 * - Spotlight overlay rendering
 * - Keyboard navigation
 * - Progress indicators
 * - Body scroll prevention
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import WelcomeTour from './WelcomeTour';
import TourTooltip from './TourTooltip';
import TourSpotlight from './TourSpotlight';

// Mock the OnboardingContext
vi.mock('../../context/OnboardingContext', () => ({
  useTour: vi.fn(),
}));

import { useTour } from '../../context/OnboardingContext';

const mockStepData = {
  id: 'dashboard',
  title: 'Dashboard Overview',
  content: 'This is your main dashboard where you can see all your metrics.',
  target: '[data-tour="dashboard"]',
  placement: 'bottom',
};

const defaultMockTour = {
  isActive: false,
  currentStep: 0,
  totalSteps: 5,
  currentStepData: null,
  next: vi.fn(),
  prev: vi.fn(),
  skip: vi.fn(),
};

describe('WelcomeTour', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTour.mockReturnValue({ ...defaultMockTour });
    // Reset body overflow
    document.body.style.overflow = '';
  });

  afterEach(() => {
    document.body.style.overflow = '';
  });

  describe('Visibility', () => {
    test('renders nothing when isActive is false', () => {
      useTour.mockReturnValue({ ...defaultMockTour, isActive: false });

      const { container } = render(<WelcomeTour />);

      expect(container.firstChild).toBeNull();
    });

    test('renders nothing when currentStepData is null', () => {
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: null,
      });

      const { container } = render(<WelcomeTour />);

      expect(container.firstChild).toBeNull();
    });

    test('renders tour components when active with step data', () => {
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
      });

      render(<WelcomeTour />);

      // TourTooltip should render the step title
      expect(screen.getByText('Dashboard Overview')).toBeInTheDocument();
    });
  });

  describe('Body Scroll Prevention', () => {
    test('prevents body scroll when tour is active', () => {
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
      });

      render(<WelcomeTour />);

      expect(document.body.style.overflow).toBe('hidden');
    });

    test('restores body scroll when tour becomes inactive', () => {
      const { rerender } = render(<WelcomeTour />);

      // Start with active tour
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
      });
      rerender(<WelcomeTour />);
      expect(document.body.style.overflow).toBe('hidden');

      // Deactivate tour
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: false,
        currentStepData: null,
      });
      rerender(<WelcomeTour />);
      expect(document.body.style.overflow).toBe('');
    });

    test('cleans up body scroll on unmount', () => {
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
      });

      const { unmount } = render(<WelcomeTour />);
      expect(document.body.style.overflow).toBe('hidden');

      unmount();
      expect(document.body.style.overflow).toBe('');
    });
  });

  describe('Navigation Handlers', () => {
    test('calls context next() when Next button is clicked', async () => {
      const mockNext = vi.fn();
      const user = userEvent.setup();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        currentStep: 0,
        next: mockNext,
      });

      render(<WelcomeTour />);

      // Click the Next button in TourTooltip
      await user.click(screen.getByRole('button', { name: /Next/i }));

      expect(mockNext).toHaveBeenCalledTimes(1);
    });

    test('calls context prev() when Back button is clicked', async () => {
      const mockPrev = vi.fn();
      const user = userEvent.setup();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        currentStep: 2, // Middle step to show Back button
        prev: mockPrev,
      });

      render(<WelcomeTour />);

      // Click the Back button in TourTooltip
      await user.click(screen.getByRole('button', { name: /Back/i }));

      expect(mockPrev).toHaveBeenCalledTimes(1);
    });

    test('calls context skip() when Skip button is clicked', async () => {
      const mockSkip = vi.fn();
      const user = userEvent.setup();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        skip: mockSkip,
      });

      render(<WelcomeTour />);

      // Click the Skip (X) button in TourTooltip
      await user.click(screen.getByLabelText('Skip tour'));

      expect(mockSkip).toHaveBeenCalledTimes(1);
    });

    test('calls context next() on keyboard ArrowRight', () => {
      const mockNext = vi.fn();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        next: mockNext,
      });

      render(<WelcomeTour />);

      fireEvent.keyDown(window, { key: 'ArrowRight' });

      expect(mockNext).toHaveBeenCalledTimes(1);
    });

    test('calls context prev() on keyboard ArrowLeft', () => {
      const mockPrev = vi.fn();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        prev: mockPrev,
      });

      render(<WelcomeTour />);

      fireEvent.keyDown(window, { key: 'ArrowLeft' });

      expect(mockPrev).toHaveBeenCalledTimes(1);
    });

    test('calls context skip() on keyboard Escape', () => {
      const mockSkip = vi.fn();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        skip: mockSkip,
      });

      render(<WelcomeTour />);

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(mockSkip).toHaveBeenCalledTimes(1);
    });

    test('calls context next() on keyboard Enter', () => {
      const mockNext = vi.fn();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        next: mockNext,
      });

      render(<WelcomeTour />);

      fireEvent.keyDown(window, { key: 'Enter' });

      expect(mockNext).toHaveBeenCalledTimes(1);
    });

    test('calls context next() when Complete button is clicked on last step', async () => {
      const mockNext = vi.fn();
      const user = userEvent.setup();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        currentStep: 4,
        totalSteps: 5,
        next: mockNext,
      });

      render(<WelcomeTour />);

      // Click the Complete button on last step
      await user.click(screen.getByRole('button', { name: /Complete/i }));

      expect(mockNext).toHaveBeenCalledTimes(1);
    });
  });

  describe('Component Integration', () => {
    test('renders TourSpotlight with correct target', () => {
      // Create target element for spotlight to find
      const targetEl = document.createElement('div');
      targetEl.setAttribute('data-tour', 'dashboard');
      document.body.appendChild(targetEl);

      targetEl.getBoundingClientRect = vi.fn(() => ({
        x: 100,
        y: 100,
        width: 200,
        height: 100,
        top: 100,
        left: 100,
        bottom: 200,
        right: 300,
      }));

      // Mock scrollIntoView
      targetEl.scrollIntoView = vi.fn();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
      });

      const { baseElement } = render(<WelcomeTour />);

      // TourSpotlight should render SVG with spotlight when target exists
      expect(baseElement.querySelector('svg')).toBeInTheDocument();

      // Clean up
      document.body.removeChild(targetEl);
    });

    test('renders TourTooltip with correct step data', () => {
      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        currentStep: 2,
        totalSteps: 5,
      });

      render(<WelcomeTour />);

      // Should display step content
      expect(screen.getByText('Dashboard Overview')).toBeInTheDocument();
      expect(
        screen.getByText('This is your main dashboard where you can see all your metrics.')
      ).toBeInTheDocument();

      // Should show Back button (middle step)
      expect(screen.getByRole('button', { name: /Back/i })).toBeInTheDocument();
    });

    test('passes all required props to TourTooltip', () => {
      const mockNext = vi.fn();
      const mockPrev = vi.fn();
      const mockSkip = vi.fn();

      useTour.mockReturnValue({
        ...defaultMockTour,
        isActive: true,
        currentStepData: mockStepData,
        currentStep: 1,
        totalSteps: 5,
        next: mockNext,
        prev: mockPrev,
        skip: mockSkip,
      });

      render(<WelcomeTour />);

      // Verify TourTooltip receives and uses props correctly
      // Check progress dots (should be 5)
      const dots = document.querySelectorAll('.rounded-full.w-2.h-2');
      expect(dots.length).toBe(5);

      // Current step (1) should be highlighted
      expect(dots[1]).toHaveClass('bg-aura-500');
    });
  });
});

describe('TourTooltip', () => {
  const defaultProps = {
    step: mockStepData,
    currentStep: 0,
    totalSteps: 5,
    onNext: vi.fn(),
    onPrev: vi.fn(),
    onSkip: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    test('renders nothing when step is null', () => {
      const { container } = render(
        <TourTooltip {...defaultProps} step={null} />
      );

      expect(container.firstChild).toBeNull();
    });

    test('displays step title', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByText('Dashboard Overview')).toBeInTheDocument();
    });

    test('displays step content', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(
        screen.getByText('This is your main dashboard where you can see all your metrics.')
      ).toBeInTheDocument();
    });

    test('has dialog role for accessibility', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('has accessible title and description', () => {
      render(<TourTooltip {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby', 'tour-step-title');
      expect(dialog).toHaveAttribute('aria-describedby', 'tour-step-content');
    });
  });

  describe('Progress Dots', () => {
    test('renders correct number of progress dots', () => {
      render(<TourTooltip {...defaultProps} totalSteps={5} />);

      // Progress dots are rendered in document.body via portal
      const dots = document.querySelectorAll('.rounded-full.w-2.h-2');
      expect(dots.length).toBe(5);
    });

    test('highlights current step dot', () => {
      render(<TourTooltip {...defaultProps} currentStep={2} totalSteps={5} />);

      // Progress dots are rendered in document.body via portal
      const dots = document.querySelectorAll('.rounded-full.w-2.h-2');
      expect(dots[2]).toHaveClass('bg-aura-500');
    });
  });

  describe('Navigation Buttons', () => {
    test('shows Next button on first step', () => {
      render(<TourTooltip {...defaultProps} currentStep={0} />);

      expect(screen.getByRole('button', { name: /Next/i })).toBeInTheDocument();
    });

    test('hides Back button on first step', () => {
      render(<TourTooltip {...defaultProps} currentStep={0} />);

      expect(screen.queryByRole('button', { name: /Back/i })).not.toBeInTheDocument();
    });

    test('shows Back button on middle steps', () => {
      render(<TourTooltip {...defaultProps} currentStep={2} />);

      expect(screen.getByRole('button', { name: /Back/i })).toBeInTheDocument();
    });

    test('shows Complete button on last step', () => {
      render(<TourTooltip {...defaultProps} currentStep={4} totalSteps={5} />);

      expect(screen.getByRole('button', { name: /Complete/i })).toBeInTheDocument();
    });

    test('shows Finish button on completion step', () => {
      const completionStep = {
        id: 'completion',
        title: 'Tour Complete',
        content: 'You have completed the tour!',
      };

      render(<TourTooltip {...defaultProps} step={completionStep} />);

      expect(screen.getByRole('button', { name: /Finish/i })).toBeInTheDocument();
    });

    test('shows skip button (X icon)', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByLabelText('Skip tour')).toBeInTheDocument();
    });
  });

  describe('Button Interactions', () => {
    test('calls onNext when Next button clicked', async () => {
      const onNext = vi.fn();
      const user = userEvent.setup();

      render(<TourTooltip {...defaultProps} onNext={onNext} />);

      await user.click(screen.getByRole('button', { name: /Next/i }));
      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('calls onPrev when Back button clicked', async () => {
      const onPrev = vi.fn();
      const user = userEvent.setup();

      render(<TourTooltip {...defaultProps} currentStep={2} onPrev={onPrev} />);

      await user.click(screen.getByRole('button', { name: /Back/i }));
      expect(onPrev).toHaveBeenCalledTimes(1);
    });

    test('calls onSkip when X button clicked', async () => {
      const onSkip = vi.fn();
      const user = userEvent.setup();

      render(<TourTooltip {...defaultProps} onSkip={onSkip} />);

      await user.click(screen.getByLabelText('Skip tour'));
      expect(onSkip).toHaveBeenCalledTimes(1);
    });
  });

  describe('Keyboard Navigation', () => {
    test('calls onNext when ArrowRight pressed', () => {
      const onNext = vi.fn();
      render(<TourTooltip {...defaultProps} onNext={onNext} />);

      fireEvent.keyDown(window, { key: 'ArrowRight' });
      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('calls onNext when Enter pressed', () => {
      const onNext = vi.fn();
      render(<TourTooltip {...defaultProps} onNext={onNext} />);

      fireEvent.keyDown(window, { key: 'Enter' });
      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('calls onPrev when ArrowLeft pressed', () => {
      const onPrev = vi.fn();
      render(<TourTooltip {...defaultProps} onPrev={onPrev} />);

      fireEvent.keyDown(window, { key: 'ArrowLeft' });
      expect(onPrev).toHaveBeenCalledTimes(1);
    });

    test('calls onSkip when Escape pressed', () => {
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
        <TourTooltip
          {...defaultProps}
          onNext={onNext}
          onPrev={onPrev}
          onSkip={onSkip}
        />
      );

      fireEvent.keyDown(window, { key: 'Tab' });
      expect(onNext).not.toHaveBeenCalled();
      expect(onPrev).not.toHaveBeenCalled();
      expect(onSkip).not.toHaveBeenCalled();
    });
  });

  describe('Keyboard Hints', () => {
    test('displays keyboard navigation hints', () => {
      render(<TourTooltip {...defaultProps} />);

      expect(screen.getByText(/to navigate/i)).toBeInTheDocument();
      expect(screen.getByText(/to skip/i)).toBeInTheDocument();
    });
  });

  describe('Cleanup', () => {
    test('removes keyboard event listener on unmount', () => {
      const onNext = vi.fn();
      const { unmount } = render(<TourTooltip {...defaultProps} onNext={onNext} />);

      unmount();

      fireEvent.keyDown(window, { key: 'ArrowRight' });
      expect(onNext).not.toHaveBeenCalled();
    });
  });
});

describe('TourSpotlight', () => {
  let targetEl = null;

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    // Clean up target element if added
    if (targetEl && targetEl.parentNode) {
      targetEl.parentNode.removeChild(targetEl);
      targetEl = null;
    }
  });

  test('renders backdrop overlay when no target (center placement)', () => {
    const { baseElement } = render(<TourSpotlight target={null} />);

    // Backdrop is rendered via portal to document.body
    const backdrop = baseElement.querySelector('.backdrop-blur-sm');
    expect(backdrop).toBeInTheDocument();
  });

  test('returns null when target element not found', () => {
    const { container } = render(
      <TourSpotlight target="[data-tour='nonexistent']" />
    );

    // Component should render nothing when target not found
    expect(container.firstChild).toBeNull();
  });

  test('renders SVG spotlight when target element exists', () => {
    // Create a target element
    targetEl = document.createElement('div');
    targetEl.setAttribute('data-tour', 'test-target');
    document.body.appendChild(targetEl);

    // Mock getBoundingClientRect
    targetEl.getBoundingClientRect = vi.fn(() => ({
      x: 100,
      y: 200,
      width: 100,
      height: 50,
      top: 200,
      left: 100,
      bottom: 250,
      right: 200,
    }));

    const { baseElement } = render(
      <TourSpotlight target="[data-tour='test-target']" />
    );

    // Should render SVG with mask in document.body via portal
    expect(baseElement.querySelector('svg')).toBeInTheDocument();
    expect(baseElement.querySelector('mask')).toBeInTheDocument();
  });

  test('scrolls target element into view', () => {
    targetEl = document.createElement('div');
    targetEl.setAttribute('data-tour', 'scroll-target');
    document.body.appendChild(targetEl);

    targetEl.getBoundingClientRect = vi.fn(() => ({
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      top: 0,
      left: 0,
      bottom: 100,
      right: 100,
    }));

    render(<TourSpotlight target="[data-tour='scroll-target']" />);

    expect(targetEl.scrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'center',
      inline: 'center',
    });
  });

  test('renders spotlight with glow border', () => {
    targetEl = document.createElement('div');
    targetEl.setAttribute('data-tour', 'glow-target');
    document.body.appendChild(targetEl);

    targetEl.getBoundingClientRect = vi.fn(() => ({
      x: 100,
      y: 100,
      width: 100,
      height: 100,
      top: 100,
      left: 100,
      bottom: 200,
      right: 200,
    }));

    const { baseElement } = render(
      <TourSpotlight target="[data-tour='glow-target']" />
    );

    // Should have an animated pulse border rect
    const glowRect = baseElement.querySelector('.animate-pulse');
    expect(glowRect).toBeInTheDocument();
  });

  test('has pointer-events-none to allow clicking through', () => {
    targetEl = document.createElement('div');
    targetEl.setAttribute('data-tour', 'clickthrough');
    document.body.appendChild(targetEl);

    targetEl.getBoundingClientRect = vi.fn(() => ({
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      top: 0,
      left: 0,
      bottom: 100,
      right: 100,
    }));

    const { baseElement } = render(
      <TourSpotlight target="[data-tour='clickthrough']" />
    );

    const svg = baseElement.querySelector('svg.pointer-events-none');
    expect(svg).toBeInTheDocument();
  });
});

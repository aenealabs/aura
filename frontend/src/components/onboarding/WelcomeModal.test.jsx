/**
 * Tests for WelcomeModal component
 *
 * Tests the P0 first-time user modal including:
 * - Conditional rendering based on showWelcome state
 * - User greeting with name
 * - Feature cards display
 * - Tour start and skip actions
 * - Keyboard navigation (Escape)
 * - Backdrop click to dismiss
 * - Accessibility attributes
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import WelcomeModal from './WelcomeModal';

// Mock the OnboardingContext
vi.mock('../../context/OnboardingContext', () => ({
  useOnboarding: vi.fn(),
}));

import { useOnboarding } from '../../context/OnboardingContext';

const defaultMockContext = {
  showWelcome: false,
  dismissWelcomeModal: vi.fn(),
  startTour: vi.fn(),
  user: { name: 'John Doe', email: 'john@example.com' },
};

describe('WelcomeModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useOnboarding.mockReturnValue({ ...defaultMockContext });
  });

  test('renders nothing when showWelcome is false', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: false });

    const { container } = render(<WelcomeModal />);

    expect(container.firstChild).toBeNull();
  });

  test('renders modal when showWelcome is true', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/Welcome/)).toBeInTheDocument();
  });

  test('displays personalized greeting with user first name', () => {
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      user: { name: 'Jane Smith' },
    });

    render(<WelcomeModal />);

    expect(screen.getByText('Welcome, Jane!')).toBeInTheDocument();
  });

  test('displays default greeting when user name is not available', () => {
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      user: null,
    });

    render(<WelcomeModal />);

    expect(screen.getByText('Welcome, there!')).toBeInTheDocument();
  });

  test('displays subtitle text', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(screen.getByText(/Let's get you set up with Project Aura/)).toBeInTheDocument();
  });

  test('displays all three feature cards', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(screen.getByText('Automated Security')).toBeInTheDocument();
    expect(screen.getByText('Code Intelligence')).toBeInTheDocument();
    expect(screen.getByText('Human-in-the-Loop')).toBeInTheDocument();
  });

  test('displays feature descriptions', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(
      screen.getByText('AI-powered vulnerability detection and patch generation')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Deep code understanding with GraphRAG technology')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Review and approve changes before they go live')
    ).toBeInTheDocument();
  });

  test('displays Take a Quick Tour button', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(screen.getByRole('button', { name: /Take a Quick Tour/i })).toBeInTheDocument();
  });

  test('displays Skip to Setup Checklist button', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(screen.getByRole('button', { name: /Skip to Setup Checklist/i })).toBeInTheDocument();
  });

  test('calls startTour when Take a Quick Tour button is clicked', async () => {
    const startTour = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      startTour,
    });
    const user = userEvent.setup();

    render(<WelcomeModal />);

    await user.click(screen.getByRole('button', { name: /Take a Quick Tour/i }));
    expect(startTour).toHaveBeenCalledTimes(1);
  });

  test('calls dismissWelcomeModal when Skip button is clicked', async () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });
    const user = userEvent.setup();

    render(<WelcomeModal />);

    await user.click(screen.getByRole('button', { name: /Skip to Setup Checklist/i }));
    expect(dismissWelcomeModal).toHaveBeenCalledTimes(1);
  });

  test('calls dismissWelcomeModal when X close button is clicked', async () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });
    const user = userEvent.setup();

    render(<WelcomeModal />);

    await user.click(screen.getByRole('button', { name: /Close welcome modal/i }));
    expect(dismissWelcomeModal).toHaveBeenCalledTimes(1);
  });

  test('calls dismissWelcomeModal when Escape key is pressed', () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });

    render(<WelcomeModal />);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dismissWelcomeModal).toHaveBeenCalledTimes(1);
  });

  test('does not call dismissWelcomeModal for other keys', () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });

    render(<WelcomeModal />);

    fireEvent.keyDown(document, { key: 'Enter' });
    expect(dismissWelcomeModal).not.toHaveBeenCalled();
  });

  test('calls dismissWelcomeModal when backdrop is clicked', async () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });
    const user = userEvent.setup();

    render(<WelcomeModal />);

    // Click on the dialog backdrop (the outer container)
    const dialog = screen.getByRole('dialog');
    await user.click(dialog);
    expect(dismissWelcomeModal).toHaveBeenCalledTimes(1);
  });

  test('does not dismiss when clicking inside modal content', async () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });
    const user = userEvent.setup();

    render(<WelcomeModal />);

    // Click on the modal title (inside the modal)
    await user.click(screen.getByText('Welcome, John!'));
    expect(dismissWelcomeModal).not.toHaveBeenCalled();
  });

  test('has proper accessibility role and aria attributes', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'welcome-modal-title');
  });

  test('has accessible title with correct id', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    const title = screen.getByText('Welcome, John!');
    expect(title).toHaveAttribute('id', 'welcome-modal-title');
  });

  test('displays keyboard hint in footer', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    expect(screen.getByText(/Press/)).toBeInTheDocument();
    expect(screen.getByText('Esc')).toBeInTheDocument();
    expect(screen.getByText(/to close/)).toBeInTheDocument();
  });

  test('renders close button with X icon', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    const closeButton = screen.getByRole('button', { name: /Close welcome modal/i });
    expect(closeButton).toBeInTheDocument();
    // The button should contain an SVG icon
    expect(closeButton.querySelector('svg')).toBeInTheDocument();
  });

  test('renders Play icon in Tour button', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    const tourButton = screen.getByRole('button', { name: /Take a Quick Tour/i });
    expect(tourButton.querySelector('svg')).toBeInTheDocument();
  });

  test('renders CheckCircle icon in Skip button', () => {
    useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

    render(<WelcomeModal />);

    const skipButton = screen.getByRole('button', { name: /Skip to Setup Checklist/i });
    expect(skipButton.querySelector('svg')).toBeInTheDocument();
  });

  test('handles user with only first name', () => {
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      user: { name: 'Alice' },
    });

    render(<WelcomeModal />);

    expect(screen.getByText('Welcome, Alice!')).toBeInTheDocument();
  });

  test('handles user with empty name string', () => {
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      user: { name: '' },
    });

    render(<WelcomeModal />);

    expect(screen.getByText('Welcome, there!')).toBeInTheDocument();
  });

  test('cleans up event listener on unmount', () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: true,
      dismissWelcomeModal,
    });

    const { unmount } = render(<WelcomeModal />);

    // Unmount the component
    unmount();

    // Fire escape after unmount - should not call dismissWelcomeModal
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dismissWelcomeModal).not.toHaveBeenCalled();
  });

  test('does not add event listener when modal is not shown', () => {
    const dismissWelcomeModal = vi.fn();
    useOnboarding.mockReturnValue({
      ...defaultMockContext,
      showWelcome: false,
      dismissWelcomeModal,
    });

    render(<WelcomeModal />);

    // Fire escape when modal is hidden - should not call dismissWelcomeModal
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dismissWelcomeModal).not.toHaveBeenCalled();
  });

  describe('Portal Rendering', () => {
    test('renders via portal to document.body', () => {
      useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

      render(<WelcomeModal />);

      const dialog = document.body.querySelector('[role="dialog"]');
      expect(dialog).toBeInTheDocument();
    });
  });

  describe('Focus Management', () => {
    test('Skip button receives focus when modal opens', async () => {
      useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

      render(<WelcomeModal />);

      // Wait for requestAnimationFrame-based focus to complete
      await waitFor(() => {
        const skipButton = screen.getByRole('button', { name: /skip to setup checklist/i });
        expect(document.activeElement).toBe(skipButton);
      });
    });
  });

  describe('Visual Elements', () => {
    test('has backdrop with blur effect', () => {
      useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

      render(<WelcomeModal />);

      const backdrop = document.body.querySelector('.backdrop-blur-sm');
      expect(backdrop).toBeInTheDocument();
    });

    test('modal has glass morphism styling', () => {
      useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

      render(<WelcomeModal />);

      const modalContent = document.body.querySelector('.backdrop-blur-xl');
      expect(modalContent).toBeInTheDocument();
    });

    test('has high z-index for overlay', () => {
      useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

      render(<WelcomeModal />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('z-[100]');
    });

    test('displays Aura logo image', () => {
      useOnboarding.mockReturnValue({ ...defaultMockContext, showWelcome: true });

      render(<WelcomeModal />);

      // Logo should be an img element with the Aura spiral logo
      const logo = document.body.querySelector('img[alt="Aura Logo"]');
      expect(logo).toBeInTheDocument();
      expect(logo).toHaveAttribute('src', '/assets/aura-spiral.png');
    });
  });
});

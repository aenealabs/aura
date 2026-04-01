/**
 * Tests for TeamInviteWizard component
 *
 * Tests the P5 team invite wizard including:
 * - Conditional rendering based on isOpen
 * - Portal rendering
 * - Progress indicator display
 * - Step navigation
 * - Escape key handling
 * - Backdrop click handling
 * - State reset on reopen
 * - Accessibility attributes
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import TeamInviteWizard from './TeamInviteWizard';

// Mock the OnboardingContext
vi.mock('../../context/OnboardingContext', () => ({
  useOnboarding: vi.fn(() => ({
    completeChecklistItem: vi.fn(),
  })),
}));

// Mock the step components with unique button text to avoid conflicts
vi.mock('./steps/EmailEntryStep', () => ({
  default: ({ emails, onEmailsChange, onNext }) => (
    <div data-testid="email-entry-step">
      <span data-testid="email-count">{emails.length} emails</span>
      <button
        onClick={() => {
          onEmailsChange(['test@example.com', 'user@example.com']);
        }}
        data-testid="add-emails"
      >
        Set Emails
      </button>
      <button onClick={onNext} data-testid="emails-next">
        Continue
      </button>
    </div>
  ),
}));

vi.mock('./steps/RoleAssignmentStep', () => ({
  default: ({ invitees, onInviteesChange, onNext, onBack }) => (
    <div data-testid="role-assignment-step">
      <span data-testid="invitee-count">{invitees.length} invitees</span>
      <button onClick={onBack} data-testid="roles-back">
        Back
      </button>
      <button onClick={onNext} data-testid="roles-next">
        Continue
      </button>
    </div>
  ),
}));

vi.mock('./steps/InviteReviewStep', () => ({
  default: ({ invitees, message, onMessageChange, onSend, onBack, isSending }) => (
    <div data-testid="invite-review-step">
      <span data-testid="review-invitee-count">{invitees.length} to send</span>
      <span data-testid="is-sending">{isSending ? 'Sending...' : 'Ready'}</span>
      <button onClick={onBack} data-testid="review-back">
        Back
      </button>
      <button onClick={() => onSend(message)} data-testid="send-invites">
        Send
      </button>
    </div>
  ),
}));

vi.mock('./steps/InviteCompletionStep', () => ({
  default: ({ invitees, inviteLink, onClose, onAddMore }) => (
    <div data-testid="invite-completion-step">
      <span data-testid="completion-count">{invitees.length} sent</span>
      <span data-testid="invite-link">{inviteLink || 'No link'}</span>
      <button onClick={onAddMore} data-testid="add-more">
        Invite More
      </button>
      <button onClick={onClose} data-testid="done">
        Done
      </button>
    </div>
  ),
}));

import { useOnboarding } from '../../context/OnboardingContext';

// Helper to navigate to completion step - async due to Promise-based timer in handleSend
const navigateToCompletion = async () => {
  // Add emails
  act(() => {
    fireEvent.click(screen.getByTestId('add-emails'));
  });
  // Navigate to roles
  act(() => {
    fireEvent.click(screen.getByTestId('emails-next'));
  });
  // Navigate to review
  act(() => {
    fireEvent.click(screen.getByTestId('roles-next'));
  });
  // Send invites (this triggers an async Promise with setTimeout)
  act(() => {
    fireEvent.click(screen.getByTestId('send-invites'));
  });
  // Advance timers and flush promises - need async version for Promise-based timers
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
};

describe('TeamInviteWizard', () => {
  // Note: Line 180 (default case in renderStep switch) is defensive code that
  // returns null for invalid step values. This is unreachable because currentStep
  // is only ever set to 0, 1, 2, or 3 via controlled state updates.

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    useOnboarding.mockReturnValue({
      completeChecklistItem: vi.fn(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Visibility', () => {
    test('renders nothing when isOpen is false', () => {
      const { container } = render(
        <TeamInviteWizard isOpen={false} onClose={vi.fn()} />
      );

      expect(container.firstChild).toBeNull();
    });

    test('renders modal when isOpen is true', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('renders via portal to document.body', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      const dialog = document.body.querySelector('[role="dialog"]');
      expect(dialog).toBeInTheDocument();
    });
  });

  describe('Header', () => {
    test('displays title', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText('Invite Team Members')).toBeInTheDocument();
    });

    test('displays close button on non-completion steps', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByLabelText('Close')).toBeInTheDocument();
    });

    test('calls onClose when close button is clicked', () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      fireEvent.click(screen.getByLabelText('Close'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Progress Indicator', () => {
    test('displays progress steps', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Use getAllByText since the progress nav contains these labels
      expect(screen.getByText('Add Emails')).toBeInTheDocument();
      expect(screen.getByText('Assign Roles')).toBeInTheDocument();
      expect(screen.getByText('Review')).toBeInTheDocument();
    });

    test('highlights current step', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // The step number circles should be present, first one should be active
      // Active step has bg-aura-600, inactive has bg-surface-200
      // The "1" text is inside the circle div, so check that element itself
      const stepOneNumber = screen.getByText('1');
      expect(stepOneNumber).toHaveClass('bg-aura-600');
    });
  });

  describe('Step Navigation', () => {
    test('starts on email entry step', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByTestId('email-entry-step')).toBeInTheDocument();
    });

    test('navigates to role assignment step after adding emails', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Add emails first
      fireEvent.click(screen.getByTestId('add-emails'));
      // Navigate to next step
      fireEvent.click(screen.getByTestId('emails-next'));

      expect(screen.getByTestId('role-assignment-step')).toBeInTheDocument();
    });

    test('navigates to review step from role assignment', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Add emails and navigate to roles
      fireEvent.click(screen.getByTestId('add-emails'));
      fireEvent.click(screen.getByTestId('emails-next'));

      // Navigate to review
      fireEvent.click(screen.getByTestId('roles-next'));

      expect(screen.getByTestId('invite-review-step')).toBeInTheDocument();
    });

    test('can navigate back from role assignment to emails', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Navigate to roles
      fireEvent.click(screen.getByTestId('add-emails'));
      fireEvent.click(screen.getByTestId('emails-next'));
      expect(screen.getByTestId('role-assignment-step')).toBeInTheDocument();

      // Navigate back
      fireEvent.click(screen.getByTestId('roles-back'));

      expect(screen.getByTestId('email-entry-step')).toBeInTheDocument();
    });

    test('can navigate back from review to role assignment', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Navigate to review
      fireEvent.click(screen.getByTestId('add-emails'));
      fireEvent.click(screen.getByTestId('emails-next'));
      fireEvent.click(screen.getByTestId('roles-next'));
      expect(screen.getByTestId('invite-review-step')).toBeInTheDocument();

      // Navigate back
      fireEvent.click(screen.getByTestId('review-back'));

      expect(screen.getByTestId('role-assignment-step')).toBeInTheDocument();
    });
  });

  describe('Send Invitations', () => {
    test('navigates to completion step after sending', async () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      await navigateToCompletion();

      expect(screen.getByTestId('invite-completion-step')).toBeInTheDocument();
    });

    test('generates invite link on completion', async () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      await navigateToCompletion();

      // Invite link should be generated (starts with https://app.aenealabs.com/invite/)
      const linkElement = screen.getByTestId('invite-link');
      expect(linkElement.textContent).toContain('https://app.aenealabs.com/invite/');
    });

    test('calls completeChecklistItem on successful send', async () => {
      const completeChecklistItem = vi.fn();
      useOnboarding.mockReturnValue({ completeChecklistItem });

      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      await navigateToCompletion();

      expect(completeChecklistItem).toHaveBeenCalledWith('invite_team_member');
    });
  });

  describe('Completion Step', () => {
    test('hides close button on completion step', async () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      await navigateToCompletion();

      // Close button should be hidden
      expect(screen.queryByLabelText('Close')).not.toBeInTheDocument();
    });

    test('hides progress indicator on completion step', async () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      await navigateToCompletion();

      // Progress step labels should be hidden on completion
      expect(screen.queryByText('Add Emails')).not.toBeInTheDocument();
      expect(screen.queryByText('Assign Roles')).not.toBeInTheDocument();
    });

    test('can invite more people from completion', async () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      await navigateToCompletion();

      // Click invite more
      fireEvent.click(screen.getByTestId('add-more'));

      // Should be back on email entry step
      expect(screen.getByTestId('email-entry-step')).toBeInTheDocument();
    });

    test('calls onClose when Done is clicked', async () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      await navigateToCompletion();

      // Click done
      fireEvent.click(screen.getByTestId('done'));

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Escape Key Handling', () => {
    test('calls onClose when Escape is pressed on non-completion step', () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    test('does not call onClose for Escape on completion step', async () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      await navigateToCompletion();

      // Reset mock to clear previous calls
      onClose.mockClear();

      // Press Escape on completion step
      fireEvent.keyDown(window, { key: 'Escape' });

      expect(onClose).not.toHaveBeenCalled();
    });

    test('does not respond to other keys', () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      fireEvent.keyDown(window, { key: 'Enter' });

      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('Backdrop Click', () => {
    test('calls onClose when backdrop is clicked on non-completion step', () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      const dialog = screen.getByRole('dialog');
      fireEvent.click(dialog);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    test('does not call onClose when clicking inside modal content', () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={true} onClose={onClose} />);

      fireEvent.click(screen.getByText('Invite Team Members'));

      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('State Reset', () => {
    test('resets state when modal is reopened', () => {
      const { rerender } = render(
        <TeamInviteWizard isOpen={true} onClose={vi.fn()} />
      );

      // Add emails and navigate
      fireEvent.click(screen.getByTestId('add-emails'));
      expect(screen.getByTestId('email-count').textContent).toBe('2 emails');

      fireEvent.click(screen.getByTestId('emails-next'));
      expect(screen.getByTestId('role-assignment-step')).toBeInTheDocument();

      // Close modal
      rerender(<TeamInviteWizard isOpen={false} onClose={vi.fn()} />);

      // Reopen modal
      rerender(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Should be back on email entry with no emails
      expect(screen.getByTestId('email-entry-step')).toBeInTheDocument();
      expect(screen.getByTestId('email-count').textContent).toBe('0 emails');
    });
  });

  describe('Accessibility', () => {
    test('has dialog role', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('has aria-modal attribute', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true');
    });

    test('has aria-labelledby pointing to title', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby', 'team-invite-title');

      const title = screen.getByText('Invite Team Members');
      expect(title).toHaveAttribute('id', 'team-invite-title');
    });

    test('close button has accessible label', () => {
      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByLabelText('Close')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    test('handles send error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Navigate to review step
      fireEvent.click(screen.getByTestId('add-emails'));
      fireEvent.click(screen.getByTestId('emails-next'));
      fireEvent.click(screen.getByTestId('roles-next'));

      // Mock setTimeout to reject instead of resolve
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = vi.fn((callback) => {
        // Don't call the callback, instead throw to trigger catch
        throw new Error('Network error');
      });

      // Click send
      await act(async () => {
        fireEvent.click(screen.getByTestId('send-invites'));
      });

      // Verify error was logged
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to send invitations:',
        expect.any(Error)
      );

      // Restore setTimeout
      global.setTimeout = originalSetTimeout;
      consoleSpy.mockRestore();
    });

    test('resets isSending state after error', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {});

      render(<TeamInviteWizard isOpen={true} onClose={vi.fn()} />);

      // Navigate to review step
      fireEvent.click(screen.getByTestId('add-emails'));
      fireEvent.click(screen.getByTestId('emails-next'));
      fireEvent.click(screen.getByTestId('roles-next'));

      // Should show Ready initially
      expect(screen.getByTestId('is-sending').textContent).toBe('Ready');

      // Mock setTimeout to throw
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = vi.fn(() => {
        throw new Error('Network error');
      });

      await act(async () => {
        fireEvent.click(screen.getByTestId('send-invites'));
      });

      // Should reset to Ready after error (via finally block)
      expect(screen.getByTestId('is-sending').textContent).toBe('Ready');

      global.setTimeout = originalSetTimeout;
    });
  });

  describe('Cleanup', () => {
    test('removes escape key listener on unmount', () => {
      const onClose = vi.fn();

      const { unmount } = render(
        <TeamInviteWizard isOpen={true} onClose={onClose} />
      );

      unmount();

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(onClose).not.toHaveBeenCalled();
    });

    test('does not add escape listener when modal is closed', () => {
      const onClose = vi.fn();

      render(<TeamInviteWizard isOpen={false} onClose={onClose} />);

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(onClose).not.toHaveBeenCalled();
    });
  });
});

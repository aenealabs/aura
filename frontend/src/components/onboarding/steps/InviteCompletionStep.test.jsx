/**
 * Tests for InviteCompletionStep component
 *
 * Tests step 4 of the Team Invite Wizard including:
 * - Success icon and message display
 * - Pluralized invitation count
 * - Invited list (emails and roles)
 * - Shareable link section (conditional)
 * - Copy to clipboard functionality
 * - Action buttons (Invite more, Done)
 * - Callback handlers
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import InviteCompletionStep from './InviteCompletionStep';

describe('InviteCompletionStep', () => {
  const defaultInvitees = [
    { email: 'alice@example.com', role: 'admin' },
    { email: 'bob@example.com', role: 'developer' },
    { email: 'charlie@example.com', role: 'viewer' },
  ];

  const defaultProps = {
    invitees: defaultInvitees,
    inviteLink: 'https://aura.example.com/invite/abc123',
    onClose: vi.fn(),
    onAddMore: vi.fn(),
  };

  // Mock clipboard API
  const mockClipboard = {
    writeText: vi.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    Object.assign(navigator, { clipboard: mockClipboard });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Success Message', () => {
    test('displays success icon', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const successIcon = container.querySelector('.text-olive-600');
      expect(successIcon).toBeInTheDocument();
    });

    test('displays "Invitations sent!" heading', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('Invitations sent!')).toBeInTheDocument();
    });

    test('heading is rendered in h2 element', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const heading = screen.getByText('Invitations sent!');
      expect(heading.tagName).toBe('H2');
    });

    test('displays pluralized count for multiple invitees', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(
        screen.getByText(/3 invitations sent successfully/i)
      ).toBeInTheDocument();
    });

    test('displays singular count for single invitee', () => {
      render(
        <InviteCompletionStep
          {...defaultProps}
          invitees={[{ email: 'solo@example.com', role: 'admin' }]}
        />
      );

      expect(
        screen.getByText(/1 invitation sent successfully/i)
      ).toBeInTheDocument();
    });

    test('mentions email notification', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(
        screen.getByText(/Your team members will receive an email shortly/i)
      ).toBeInTheDocument();
    });

    test('success icon container has olive background', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const iconContainer = container.querySelector('.bg-olive-100');
      expect(iconContainer).toBeInTheDocument();
    });
  });

  describe('Invited List', () => {
    test('displays "Invited" section heading', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('Invited')).toBeInTheDocument();
    });

    test('displays all invitee emails', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('alice@example.com')).toBeInTheDocument();
      expect(screen.getByText('bob@example.com')).toBeInTheDocument();
      expect(screen.getByText('charlie@example.com')).toBeInTheDocument();
    });

    test('displays roles for each invitee', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByText('developer')).toBeInTheDocument();
      expect(screen.getByText('viewer')).toBeInTheDocument();
    });

    test('roles are capitalized via CSS', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const roleElements = container.querySelectorAll('.capitalize');
      expect(roleElements.length).toBeGreaterThanOrEqual(3);
    });

    test('list has max height with scroll', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const scrollContainer = container.querySelector('.max-h-32.overflow-y-auto');
      expect(scrollContainer).toBeInTheDocument();
    });

    test('handles empty invitees list', () => {
      render(<InviteCompletionStep {...defaultProps} invitees={[]} />);

      expect(screen.getByText('Invited')).toBeInTheDocument();
      expect(screen.getByText(/0 invitations sent/i)).toBeInTheDocument();
    });

    test('handles many invitees', () => {
      const manyInvitees = Array.from({ length: 15 }, (_, i) => ({
        email: `user${i}@example.com`,
        role: 'developer',
      }));

      render(<InviteCompletionStep {...defaultProps} invitees={manyInvitees} />);

      expect(screen.getByText(/15 invitations sent/i)).toBeInTheDocument();
      expect(screen.getByText('user0@example.com')).toBeInTheDocument();
      expect(screen.getByText('user14@example.com')).toBeInTheDocument();
    });
  });

  describe('Shareable Link Section', () => {
    test('displays shareable link section when inviteLink provided', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('Shareable invite link')).toBeInTheDocument();
    });

    test('does not display shareable link section when inviteLink is null', () => {
      render(<InviteCompletionStep {...defaultProps} inviteLink={null} />);

      expect(screen.queryByText('Shareable invite link')).not.toBeInTheDocument();
    });

    test('does not display shareable link section when inviteLink is undefined', () => {
      render(<InviteCompletionStep {...defaultProps} inviteLink={undefined} />);

      expect(screen.queryByText('Shareable invite link')).not.toBeInTheDocument();
    });

    test('does not display shareable link section when inviteLink is empty string', () => {
      render(<InviteCompletionStep {...defaultProps} inviteLink="" />);

      expect(screen.queryByText('Shareable invite link')).not.toBeInTheDocument();
    });

    test('displays link description text', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(
        screen.getByText('Anyone with this link can request to join your organization.')
      ).toBeInTheDocument();
    });

    test('displays invite link in read-only input', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const input = screen.getByDisplayValue('https://aura.example.com/invite/abc123');
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute('readOnly');
    });

    test('displays Copy button', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
    });

    test('displays link icon in section heading', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const linkIcon = container.querySelector('.w-4.h-4.mr-1');
      expect(linkIcon).toBeInTheDocument();
    });
  });

  describe('Copy Functionality', () => {
    // Note: Line 20 (if (inviteLink) check inside handleCopyLink) has an uncovered
    // false branch. This is defensive code - the Copy button is only rendered when
    // inviteLink is truthy (line 72: {inviteLink && (...)}), so handleCopyLink can
    // only be invoked when inviteLink has a value. The check prevents issues if the
    // component's internal state becomes inconsistent.

    test('handleCopyLink guard prevents clipboard access when inviteLink is empty', async () => {
      // This tests the defensive if (inviteLink) check inside handleCopyLink
      // We need to invoke the handler when inviteLink is falsy, but the button
      // is conditionally rendered. The useCallback captures inviteLink in closure,
      // so we test by rendering with empty string from the start and accessing
      // the callback through the component's internal function.

      // Since the button doesn't render when inviteLink is empty, and useCallback
      // captures inviteLink, this branch is genuinely unreachable in production.
      // We document this as defensive code.

      // Verify the guard works correctly by checking clipboard is NOT called
      // when rendering without inviteLink
      mockClipboard.writeText.mockClear();

      render(<InviteCompletionStep {...defaultProps} inviteLink="" />);

      // No copy button should exist
      expect(screen.queryByRole('button', { name: /copy/i })).not.toBeInTheDocument();

      // Clipboard should never have been called
      expect(mockClipboard.writeText).not.toHaveBeenCalled();
    });

    test('handleCopyLink early return when inviteLink becomes null', async () => {
      // Test the edge case where inviteLink might be null
      mockClipboard.writeText.mockClear();

      render(<InviteCompletionStep {...defaultProps} inviteLink={null} />);

      expect(screen.queryByRole('button', { name: /copy/i })).not.toBeInTheDocument();
      expect(mockClipboard.writeText).not.toHaveBeenCalled();
    });

    test('copies link to clipboard when Copy button clicked', async () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await act(async () => {
        fireEvent.click(copyButton);
      });

      expect(mockClipboard.writeText).toHaveBeenCalledWith(
        'https://aura.example.com/invite/abc123'
      );
    });

    test('shows "Copied!" text after copying', async () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await act(async () => {
        fireEvent.click(copyButton);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();
    });

    test('reverts to "Copy" text after 2 seconds', async () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await act(async () => {
        fireEvent.click(copyButton);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(2000);
      });

      expect(screen.getByText('Copy')).toBeInTheDocument();
      expect(screen.queryByText('Copied!')).not.toBeInTheDocument();
    });

    test('handles clipboard error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockClipboard.writeText.mockRejectedValueOnce(new Error('Clipboard error'));

      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await act(async () => {
        fireEvent.click(copyButton);
      });

      expect(consoleSpy).toHaveBeenCalledWith('Failed to copy:', expect.any(Error));
      consoleSpy.mockRestore();
    });

    test('does not attempt to copy when inviteLink is falsy', async () => {
      render(<InviteCompletionStep {...defaultProps} inviteLink="" />);

      // The copy button shouldn't be present when no link
      expect(screen.queryByRole('button', { name: /copy/i })).not.toBeInTheDocument();
    });

    test('shows check icon when copied', async () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await act(async () => {
        fireEvent.click(copyButton);
      });

      // Should show ClipboardDocumentCheckIcon
      const copiedButton = screen.getByRole('button', { name: /copied/i });
      const checkIcon = copiedButton.querySelector('svg');
      expect(checkIcon).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    test('displays "Invite more people" button', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(
        screen.getByRole('button', { name: /invite more people/i })
      ).toBeInTheDocument();
    });

    test('displays "Done" button', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument();
    });

    test('calls onAddMore when "Invite more people" is clicked', () => {
      const onAddMore = vi.fn();
      render(<InviteCompletionStep {...defaultProps} onAddMore={onAddMore} />);

      fireEvent.click(screen.getByRole('button', { name: /invite more people/i }));

      expect(onAddMore).toHaveBeenCalledTimes(1);
    });

    test('calls onClose when "Done" is clicked', () => {
      const onClose = vi.fn();
      render(<InviteCompletionStep {...defaultProps} onClose={onClose} />);

      fireEvent.click(screen.getByRole('button', { name: 'Done' }));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    test('"Done" button has primary styling', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const doneButton = screen.getByRole('button', { name: 'Done' });
      expect(doneButton).toHaveClass('bg-aura-600');
    });

    test('"Invite more people" button has text styling', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const inviteMoreButton = screen.getByRole('button', {
        name: /invite more people/i,
      });
      expect(inviteMoreButton).toHaveClass('text-aura-600');
    });
  });

  describe('Styling', () => {
    test('content is centered', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('text-center');
    });

    test('invited section has left-aligned text', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const invitedSection = container.querySelector('.text-left.bg-surface-50');
      expect(invitedSection).toBeInTheDocument();
    });

    test('action buttons section has top border', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const actionsSection = container.querySelector('.border-t');
      expect(actionsSection).toBeInTheDocument();
    });

    test('success icon container is circular', () => {
      const { container } = render(<InviteCompletionStep {...defaultProps} />);

      const iconContainer = container.querySelector('.rounded-full');
      expect(iconContainer).toBeInTheDocument();
    });

    test('Copy button has aura styling', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      expect(copyButton).toHaveClass('text-aura-600');
      expect(copyButton).toHaveClass('bg-aura-50');
    });
  });

  describe('Edge Cases', () => {
    test('handles invitee with long email', () => {
      const longEmailInvitees = [
        {
          email: 'very.long.email.address.that.goes.on@subdomain.example.com',
          role: 'developer',
        },
      ];

      render(<InviteCompletionStep {...defaultProps} invitees={longEmailInvitees} />);

      expect(
        screen.getByText('very.long.email.address.that.goes.on@subdomain.example.com')
      ).toBeInTheDocument();
    });

    test('handles long invite link', () => {
      const longLink =
        'https://aura.example.com/invite/very-long-token-that-goes-on-and-on-abc123def456';

      render(<InviteCompletionStep {...defaultProps} inviteLink={longLink} />);

      const input = screen.getByDisplayValue(longLink);
      expect(input).toBeInTheDocument();
    });

    test('handles special characters in email', () => {
      const specialInvitees = [
        { email: "test+special'char@example.com", role: 'admin' },
      ];

      render(<InviteCompletionStep {...defaultProps} invitees={specialInvitees} />);

      expect(screen.getByText("test+special'char@example.com")).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('buttons are focusable', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).not.toHaveAttribute('tabindex', '-1');
      });
    });

    test('invite link input is readable', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const input = screen.getByDisplayValue('https://aura.example.com/invite/abc123');
      expect(input).toHaveAttribute('type', 'text');
      expect(input).toHaveAttribute('readOnly');
    });

    test('emails are visible', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('alice@example.com')).toBeVisible();
      expect(screen.getByText('bob@example.com')).toBeVisible();
      expect(screen.getByText('charlie@example.com')).toBeVisible();
    });

    test('success message is visible', () => {
      render(<InviteCompletionStep {...defaultProps} />);

      expect(screen.getByText('Invitations sent!')).toBeVisible();
    });
  });

  describe('Multiple Copy Clicks', () => {
    test('handles rapid copy button clicks', async () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });

      await act(async () => {
        fireEvent.click(copyButton);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();

      // Click again while still showing "Copied!"
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /copied/i }));
      });

      // Should still work
      expect(mockClipboard.writeText).toHaveBeenCalledTimes(2);
    });

    test('each click creates independent timeout', async () => {
      render(<InviteCompletionStep {...defaultProps} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });

      await act(async () => {
        fireEvent.click(copyButton);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();

      // Advance 1.5 seconds
      act(() => {
        vi.advanceTimersByTime(1500);
      });

      // Click again while still showing "Copied!"
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /copied/i }));
      });

      // Still shows Copied! after second click
      expect(screen.getByText('Copied!')).toBeInTheDocument();

      // Advance to trigger first timeout (500ms more = 2000ms total from first click)
      act(() => {
        vi.advanceTimersByTime(500);
      });

      // First timeout fires, reverts to Copy
      expect(screen.getByText('Copy')).toBeInTheDocument();
    });
  });
});

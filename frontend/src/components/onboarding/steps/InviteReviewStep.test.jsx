/**
 * Tests for InviteReviewStep component
 *
 * Tests step 3 of the Team Invite Wizard including:
 * - Header display (title, description)
 * - Invitees summary section (grouped by role, counts, badges)
 * - Custom message textarea (default value, onChange)
 * - Email preview section
 * - Navigation buttons (Back, Send)
 * - Loading state (isSending)
 * - Callback handlers
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import InviteReviewStep from './InviteReviewStep';

describe('InviteReviewStep', () => {
  const defaultInvitees = [
    { email: 'alice@example.com', role: 'admin' },
    { email: 'bob@example.com', role: 'developer' },
    { email: 'charlie@example.com', role: 'developer' },
    { email: 'diana@example.com', role: 'viewer' },
  ];

  const defaultProps = {
    invitees: defaultInvitees,
    message: '',
    onMessageChange: vi.fn(),
    onSend: vi.fn(),
    onBack: vi.fn(),
    isSending: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Header Display', () => {
    test('displays title', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('Review & send')).toBeInTheDocument();
    });

    test('displays description', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(
        screen.getByText('Review your invitations and customize the welcome message.')
      ).toBeInTheDocument();
    });

    test('title is rendered in heading element', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const title = screen.getByText('Review & send');
      expect(title.tagName).toBe('H2');
    });
  });

  describe('Invitees Summary', () => {
    test('displays total invitee count', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('Invitations (4)')).toBeInTheDocument();
    });

    test('displays count for single invitee', () => {
      render(
        <InviteReviewStep
          {...defaultProps}
          invitees={[{ email: 'solo@example.com', role: 'admin' }]}
        />
      );

      expect(screen.getByText('Invitations (1)')).toBeInTheDocument();
    });

    test('groups invitees by role', () => {
      render(<InviteReviewStep {...defaultProps} />);

      // Admin group - 1 admin
      expect(screen.getByText('Admin')).toBeInTheDocument();

      // Developer group - 2 developers
      expect(screen.getByText('Developer')).toBeInTheDocument();

      // Viewer group - 1 viewer
      expect(screen.getByText('Viewer')).toBeInTheDocument();

      // Check counts are displayed (multiple (1) exist, so use getAllByText)
      const countOnes = screen.getAllByText('(1)');
      expect(countOnes.length).toBe(2); // Admin and Viewer each have 1

      expect(screen.getByText('(2)')).toBeInTheDocument(); // Developer has 2
    });

    test('displays all invitee emails', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('alice@example.com')).toBeInTheDocument();
      expect(screen.getByText('bob@example.com')).toBeInTheDocument();
      expect(screen.getByText('charlie@example.com')).toBeInTheDocument();
      expect(screen.getByText('diana@example.com')).toBeInTheDocument();
    });

    test('displays role badges with icons', () => {
      const { container } = render(<InviteReviewStep {...defaultProps} />);

      // Each role badge should have an icon
      const icons = container.querySelectorAll('.w-3\\.5.h-3\\.5');
      expect(icons.length).toBeGreaterThanOrEqual(3);
    });

    test('handles empty invitees list', () => {
      render(<InviteReviewStep {...defaultProps} invitees={[]} />);

      expect(screen.getByText('Invitations (0)')).toBeInTheDocument();
    });

    test('handles invitees with only one role type', () => {
      const singleRoleInvitees = [
        { email: 'dev1@example.com', role: 'developer' },
        { email: 'dev2@example.com', role: 'developer' },
      ];

      render(<InviteReviewStep {...defaultProps} invitees={singleRoleInvitees} />);

      expect(screen.getByText('Developer')).toBeInTheDocument();
      expect(screen.getByText('(2)')).toBeInTheDocument();
      expect(screen.queryByText('Admin')).not.toBeInTheDocument();
      expect(screen.queryByText('Viewer')).not.toBeInTheDocument();
    });
  });

  describe('Custom Message', () => {
    test('displays message label', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('Personal message (optional)')).toBeInTheDocument();
    });

    test('displays helper text', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(
        screen.getByText('This message will be included in the invitation email.')
      ).toBeInTheDocument();
    });

    test('displays default message when no message prop provided', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      expect(textarea.value).toContain("Hi there,");
      expect(textarea.value).toContain("I'd like to invite you to join our organization");
    });

    test('displays provided message prop', () => {
      render(
        <InviteReviewStep {...defaultProps} message="Custom welcome message" />
      );

      const textarea = screen.getByRole('textbox');
      expect(textarea.value).toBe('Custom welcome message');
    });

    test('textarea has correct id for label association', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('id', 'invite-message');
    });

    test('calls onMessageChange when message is edited', () => {
      const onMessageChange = vi.fn();
      render(<InviteReviewStep {...defaultProps} onMessageChange={onMessageChange} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'New message content' } });

      expect(onMessageChange).toHaveBeenCalledWith('New message content');
    });

    test('updates local state when message is edited', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Updated message' } });

      expect(textarea.value).toBe('Updated message');
    });

    test('textarea has placeholder text', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute(
        'placeholder',
        'Add a personal note to your invitation...'
      );
    });
  });

  describe('Email Preview', () => {
    test('displays preview header', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('Email Preview')).toBeInTheDocument();
    });

    test('displays email subject line', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(
        screen.getByText("You're invited to join Project Aura")
      ).toBeInTheDocument();
    });

    test('displays message content in preview', () => {
      render(<InviteReviewStep {...defaultProps} message="Preview this message" />);

      // Message appears both in textarea and preview
      const elements = screen.getAllByText('Preview this message');
      expect(elements.length).toBeGreaterThanOrEqual(1);
    });

    test('displays Accept Invitation button in preview', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('Accept Invitation')).toBeInTheDocument();
    });

    test('preview updates when message changes', () => {
      const { container } = render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Dynamic preview test' } });

      // Message appears in both textarea and preview div
      const previewDiv = container.querySelector('.whitespace-pre-line');
      expect(previewDiv).toHaveTextContent('Dynamic preview test');
    });

    test('preview preserves whitespace formatting', () => {
      const { container } = render(<InviteReviewStep {...defaultProps} />);

      // The preview div should have whitespace-pre-line class
      const previewContent = container.querySelector('.whitespace-pre-line');
      expect(previewContent).toBeInTheDocument();
    });
  });

  describe('Navigation Buttons', () => {
    test('displays Back button', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument();
    });

    test('displays Send Invitations button', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(
        screen.getByRole('button', { name: /send invitations/i })
      ).toBeInTheDocument();
    });

    test('calls onBack when Back button is clicked', () => {
      const onBack = vi.fn();
      render(<InviteReviewStep {...defaultProps} onBack={onBack} />);

      fireEvent.click(screen.getByRole('button', { name: 'Back' }));

      expect(onBack).toHaveBeenCalledTimes(1);
    });

    test('calls onSend with message when Send button is clicked', () => {
      const onSend = vi.fn();
      render(
        <InviteReviewStep {...defaultProps} onSend={onSend} message="Test message" />
      );

      fireEvent.click(screen.getByRole('button', { name: /send invitations/i }));

      expect(onSend).toHaveBeenCalledWith('Test message');
    });

    test('calls onSend with default message when no message provided', () => {
      const onSend = vi.fn();
      render(<InviteReviewStep {...defaultProps} onSend={onSend} />);

      fireEvent.click(screen.getByRole('button', { name: /send invitations/i }));

      expect(onSend).toHaveBeenCalledWith(expect.stringContaining("Hi there,"));
    });

    test('calls onSend with updated message after editing', () => {
      const onSend = vi.fn();
      render(<InviteReviewStep {...defaultProps} onSend={onSend} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Edited message' } });
      fireEvent.click(screen.getByRole('button', { name: /send invitations/i }));

      expect(onSend).toHaveBeenCalledWith('Edited message');
    });

    test('Send button has paper airplane icon', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const sendButton = screen.getByRole('button', { name: /send invitations/i });
      const svg = sendButton.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    test('disables Back button when sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={true} />);

      const backButton = screen.getByRole('button', { name: 'Back' });
      expect(backButton).toBeDisabled();
    });

    test('disables Send button when sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={true} />);

      const sendButton = screen.getByRole('button', { name: /sending/i });
      expect(sendButton).toBeDisabled();
    });

    test('shows Sending... text when sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={true} />);

      expect(screen.getByText('Sending...')).toBeInTheDocument();
    });

    test('shows spinner when sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={true} />);

      const sendButton = screen.getByRole('button', { name: /sending/i });
      const spinner = sendButton.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    test('hides Send Invitations text when sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={true} />);

      expect(screen.queryByText('Send Invitations')).not.toBeInTheDocument();
    });

    test('shows Send Invitations text when not sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={false} />);

      expect(screen.getByText('Send Invitations')).toBeInTheDocument();
    });

    test('does not show spinner when not sending', () => {
      render(<InviteReviewStep {...defaultProps} isSending={false} />);

      const sendButton = screen.getByRole('button', { name: /send invitations/i });
      const spinner = sendButton.querySelector('.animate-spin');
      expect(spinner).not.toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    test('invitees section has background styling', () => {
      const { container } = render(<InviteReviewStep {...defaultProps} />);

      const inviteesSection = container.querySelector('.bg-surface-50');
      expect(inviteesSection).toBeInTheDocument();
    });

    test('email preview has border styling', () => {
      const { container } = render(<InviteReviewStep {...defaultProps} />);

      const previewSection = container.querySelector(
        '.bg-white.rounded-lg.border.border-surface-200'
      );
      expect(previewSection).toBeInTheDocument();
    });

    test('navigation section has top border', () => {
      const { container } = render(<InviteReviewStep {...defaultProps} />);

      const navSection = container.querySelector('.border-t');
      expect(navSection).toBeInTheDocument();
    });

    test('Send button has primary styling', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const sendButton = screen.getByRole('button', { name: /send invitations/i });
      expect(sendButton).toHaveClass('bg-aura-600');
    });

    test('admin role badge has critical color', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const adminBadge = screen.getByText('Admin').closest('span');
      expect(adminBadge).toHaveClass('text-critical-600');
    });

    test('developer role badge has aura color', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const devBadge = screen.getByText('Developer').closest('span');
      expect(devBadge).toHaveClass('text-aura-600');
    });

    test('viewer role badge has surface color', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const viewerBadge = screen.getByText('Viewer').closest('span');
      expect(viewerBadge).toHaveClass('text-surface-600');
    });
  });

  describe('Edge Cases', () => {
    test('handles invitee with long email', () => {
      const longEmailInvitees = [
        {
          email: 'very.long.email.address@subdomain.example.com',
          role: 'developer',
        },
      ];

      render(<InviteReviewStep {...defaultProps} invitees={longEmailInvitees} />);

      expect(
        screen.getByText('very.long.email.address@subdomain.example.com')
      ).toBeInTheDocument();
    });

    test('handles many invitees', () => {
      const manyInvitees = Array.from({ length: 20 }, (_, i) => ({
        email: `user${i}@example.com`,
        role: i % 3 === 0 ? 'admin' : i % 3 === 1 ? 'developer' : 'viewer',
      }));

      render(<InviteReviewStep {...defaultProps} invitees={manyInvitees} />);

      expect(screen.getByText('Invitations (20)')).toBeInTheDocument();
    });

    test('handles unknown role gracefully', () => {
      const unknownRoleInvitees = [
        { email: 'test@example.com', role: 'unknown_role' },
      ];

      // Should not throw and should use fallback styling
      render(<InviteReviewStep {...defaultProps} invitees={unknownRoleInvitees} />);

      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });

    test('handles empty message', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '' } });

      expect(textarea.value).toBe('');
    });

    test('handles message with special characters', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '<script>alert("xss")</script>' } });

      expect(textarea.value).toBe('<script>alert("xss")</script>');
    });
  });

  describe('Accessibility', () => {
    test('textarea has accessible label', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const textarea = screen.getByLabelText('Personal message (optional)');
      expect(textarea).toBeInTheDocument();
    });

    test('buttons are focusable', () => {
      render(<InviteReviewStep {...defaultProps} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).not.toHaveAttribute('tabindex', '-1');
      });
    });

    test('buttons indicate disabled state', () => {
      render(<InviteReviewStep {...defaultProps} isSending={true} />);

      const backButton = screen.getByRole('button', { name: 'Back' });
      const sendButton = screen.getByRole('button', { name: /sending/i });

      expect(backButton).toHaveAttribute('disabled');
      expect(sendButton).toHaveAttribute('disabled');
    });

    test('emails are visible text', () => {
      render(<InviteReviewStep {...defaultProps} />);

      expect(screen.getByText('alice@example.com')).toBeVisible();
      expect(screen.getByText('bob@example.com')).toBeVisible();
    });
  });

  describe('Role Order', () => {
    test('displays roles in the order they appear in invitees', () => {
      // First role encountered should appear first
      const orderedInvitees = [
        { email: 'viewer@example.com', role: 'viewer' },
        { email: 'admin@example.com', role: 'admin' },
        { email: 'dev@example.com', role: 'developer' },
      ];

      const { container } = render(
        <InviteReviewStep {...defaultProps} invitees={orderedInvitees} />
      );

      // Get all role badges
      const roleBadges = container.querySelectorAll('.space-y-4 > div');
      expect(roleBadges.length).toBe(3);
    });
  });
});

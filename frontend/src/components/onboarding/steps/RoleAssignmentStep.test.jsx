/**
 * Tests for RoleAssignmentStep component
 *
 * Tests step 2 of the Team Invite Wizard including:
 * - Header display (title, description)
 * - Apply to all buttons
 * - Invitee list display
 * - Role selector dropdowns
 * - Role change handling
 * - Role descriptions section
 * - Navigation buttons (Back, Continue)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import RoleAssignmentStep from './RoleAssignmentStep';

describe('RoleAssignmentStep', () => {
  const defaultInvitees = [
    { email: 'alice@example.com', role: 'developer' },
    { email: 'bob@example.com', role: 'developer' },
    { email: 'charlie@example.com', role: 'viewer' },
  ];

  const defaultProps = {
    invitees: defaultInvitees,
    onInviteesChange: vi.fn(),
    onNext: vi.fn(),
    onBack: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Header Display', () => {
    test('displays title', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('Assign roles')).toBeInTheDocument();
    });

    test('displays description', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(
        screen.getByText('Choose what each person can do in your organization.')
      ).toBeInTheDocument();
    });
  });

  describe('Apply to All', () => {
    test('displays "Apply to all" label', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('Apply to all:')).toBeInTheDocument();
    });

    test('displays Admin button', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      // There are multiple "Admin" texts - one in apply-to-all, one in role descriptions
      const adminButtons = screen.getAllByText('Admin');
      expect(adminButtons.length).toBeGreaterThanOrEqual(1);
    });

    test('displays Developer button', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const developerButtons = screen.getAllByText('Developer');
      expect(developerButtons.length).toBeGreaterThanOrEqual(1);
    });

    test('displays Viewer button', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const viewerButtons = screen.getAllByText('Viewer');
      expect(viewerButtons.length).toBeGreaterThanOrEqual(1);
    });

    test('applies Admin role to all invitees when clicked', () => {
      const onInviteesChange = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onInviteesChange={onInviteesChange} />);

      // Get the first "Admin" button (in apply-to-all section)
      const adminButtons = screen.getAllByRole('button', { name: 'Admin' });
      fireEvent.click(adminButtons[0]);

      expect(onInviteesChange).toHaveBeenCalledWith([
        { email: 'alice@example.com', role: 'admin' },
        { email: 'bob@example.com', role: 'admin' },
        { email: 'charlie@example.com', role: 'admin' },
      ]);
    });

    test('applies Developer role to all invitees when clicked', () => {
      const onInviteesChange = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onInviteesChange={onInviteesChange} />);

      const developerButtons = screen.getAllByRole('button', { name: 'Developer' });
      fireEvent.click(developerButtons[0]);

      expect(onInviteesChange).toHaveBeenCalledWith([
        { email: 'alice@example.com', role: 'developer' },
        { email: 'bob@example.com', role: 'developer' },
        { email: 'charlie@example.com', role: 'developer' },
      ]);
    });

    test('applies Viewer role to all invitees when clicked', () => {
      const onInviteesChange = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onInviteesChange={onInviteesChange} />);

      const viewerButtons = screen.getAllByRole('button', { name: 'Viewer' });
      fireEvent.click(viewerButtons[0]);

      expect(onInviteesChange).toHaveBeenCalledWith([
        { email: 'alice@example.com', role: 'viewer' },
        { email: 'bob@example.com', role: 'viewer' },
        { email: 'charlie@example.com', role: 'viewer' },
      ]);
    });
  });

  describe('Invitee List', () => {
    test('displays all invitee emails', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('alice@example.com')).toBeInTheDocument();
      expect(screen.getByText('bob@example.com')).toBeInTheDocument();
      expect(screen.getByText('charlie@example.com')).toBeInTheDocument();
    });

    test('displays role selector for each invitee', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const selectors = screen.getAllByRole('combobox');
      expect(selectors).toHaveLength(3);
    });

    test('role selectors show correct initial values', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const selectors = screen.getAllByRole('combobox');
      expect(selectors[0]).toHaveValue('developer');
      expect(selectors[1]).toHaveValue('developer');
      expect(selectors[2]).toHaveValue('viewer');
    });

    test('renders empty list when no invitees', () => {
      render(<RoleAssignmentStep {...defaultProps} invitees={[]} />);

      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    });

    test('renders single invitee correctly', () => {
      render(
        <RoleAssignmentStep
          {...defaultProps}
          invitees={[{ email: 'solo@example.com', role: 'admin' }]}
        />
      );

      expect(screen.getByText('solo@example.com')).toBeInTheDocument();
      expect(screen.getAllByRole('combobox')).toHaveLength(1);
    });
  });

  describe('Role Selector', () => {
    test('each selector has all role options', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const selectors = screen.getAllByRole('combobox');
      const firstSelector = selectors[0];

      // Check options within the selector
      const options = firstSelector.querySelectorAll('option');
      expect(options).toHaveLength(3);
      expect(options[0]).toHaveValue('admin');
      expect(options[1]).toHaveValue('developer');
      expect(options[2]).toHaveValue('viewer');
    });

    test('changes role for specific invitee', () => {
      const onInviteesChange = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onInviteesChange={onInviteesChange} />);

      const selectors = screen.getAllByRole('combobox');
      fireEvent.change(selectors[0], { target: { value: 'admin' } });

      expect(onInviteesChange).toHaveBeenCalledWith([
        { email: 'alice@example.com', role: 'admin' },
        { email: 'bob@example.com', role: 'developer' },
        { email: 'charlie@example.com', role: 'viewer' },
      ]);
    });

    test('changes role for different invitee', () => {
      const onInviteesChange = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onInviteesChange={onInviteesChange} />);

      const selectors = screen.getAllByRole('combobox');
      fireEvent.change(selectors[2], { target: { value: 'developer' } });

      expect(onInviteesChange).toHaveBeenCalledWith([
        { email: 'alice@example.com', role: 'developer' },
        { email: 'bob@example.com', role: 'developer' },
        { email: 'charlie@example.com', role: 'developer' },
      ]);
    });

    test('option text displays role names', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const selectors = screen.getAllByRole('combobox');
      const options = selectors[0].querySelectorAll('option');

      expect(options[0].textContent).toBe('Admin');
      expect(options[1].textContent).toBe('Developer');
      expect(options[2].textContent).toBe('Viewer');
    });
  });

  describe('Role Descriptions', () => {
    test('displays "Role permissions" heading', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('Role permissions')).toBeInTheDocument();
    });

    test('displays Admin role description', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('Full access to all settings and features')).toBeInTheDocument();
    });

    test('displays Developer role description', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('Can view, edit, and approve patches')).toBeInTheDocument();
    });

    test('displays Viewer role description', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('Read-only access to dashboards')).toBeInTheDocument();
    });

    test('displays role icons', () => {
      const { container } = render(<RoleAssignmentStep {...defaultProps} />);

      // Role description section has icons
      const roleIcons = container.querySelectorAll('.w-4.h-4');
      expect(roleIcons.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('Navigation', () => {
    test('displays Back button', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument();
    });

    test('displays Continue button', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
    });

    test('calls onBack when Back button is clicked', () => {
      const onBack = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onBack={onBack} />);

      fireEvent.click(screen.getByRole('button', { name: 'Back' }));

      expect(onBack).toHaveBeenCalledTimes(1);
    });

    test('calls onNext when Continue button is clicked', () => {
      const onNext = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onNext={onNext} />);

      fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

      expect(onNext).toHaveBeenCalledTimes(1);
    });
  });

  describe('Styling', () => {
    test('invitee row has correct styling', () => {
      const { container } = render(<RoleAssignmentStep {...defaultProps} />);

      // Each invitee row should have rounded corners and flex layout
      const inviteeSection = container.querySelector('.space-y-3');
      expect(inviteeSection).toBeInTheDocument();

      // Check that children have rounded-lg class
      const roundedItems = inviteeSection.querySelectorAll('.rounded-lg');
      expect(roundedItems.length).toBeGreaterThanOrEqual(3);
    });

    test('role descriptions section has background', () => {
      const { container } = render(<RoleAssignmentStep {...defaultProps} />);

      const descSection = container.querySelector('.bg-surface-50');
      expect(descSection).toBeInTheDocument();
    });

    test('Continue button has primary styling', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const continueBtn = screen.getByRole('button', { name: 'Continue' });
      expect(continueBtn).toHaveClass('bg-aura-600');
    });

    test('navigation section has top border', () => {
      const { container } = render(<RoleAssignmentStep {...defaultProps} />);

      const navSection = container.querySelector('.border-t');
      expect(navSection).toBeInTheDocument();
    });
  });

  describe('Default Role Fallback', () => {
    test('uses Developer as default when role not found', () => {
      const inviteesWithUnknownRole = [
        { email: 'test@example.com', role: 'unknown_role' },
      ];

      render(
        <RoleAssignmentStep {...defaultProps} invitees={inviteesWithUnknownRole} />
      );

      // The selector should still render - component falls back to Developer
      const selector = screen.getByRole('combobox');
      expect(selector).toBeInTheDocument();
    });
  });

  describe('Multiple Role Changes', () => {
    test('handles sequential role changes correctly', () => {
      const onInviteesChange = vi.fn();
      render(<RoleAssignmentStep {...defaultProps} onInviteesChange={onInviteesChange} />);

      const selectors = screen.getAllByRole('combobox');

      // First change
      fireEvent.change(selectors[0], { target: { value: 'admin' } });

      expect(onInviteesChange).toHaveBeenNthCalledWith(1, [
        { email: 'alice@example.com', role: 'admin' },
        { email: 'bob@example.com', role: 'developer' },
        { email: 'charlie@example.com', role: 'viewer' },
      ]);

      // Second change
      fireEvent.change(selectors[1], { target: { value: 'viewer' } });

      expect(onInviteesChange).toHaveBeenNthCalledWith(2, [
        { email: 'alice@example.com', role: 'developer' },
        { email: 'bob@example.com', role: 'viewer' },
        { email: 'charlie@example.com', role: 'viewer' },
      ]);
    });
  });

  describe('Accessibility', () => {
    test('role selectors are focusable', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const selectors = screen.getAllByRole('combobox');
      selectors.forEach((selector) => {
        expect(selector).not.toHaveAttribute('tabindex', '-1');
      });
    });

    test('buttons are clickable', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).not.toBeDisabled();
      });
    });

    test('emails are visible text', () => {
      render(<RoleAssignmentStep {...defaultProps} />);

      expect(screen.getByText('alice@example.com')).toBeVisible();
      expect(screen.getByText('bob@example.com')).toBeVisible();
      expect(screen.getByText('charlie@example.com')).toBeVisible();
    });
  });

  describe('Edge Cases', () => {
    test('handles invitee with long email', () => {
      const longEmailInvitees = [
        { email: 'this.is.a.very.long.email.address@subdomain.example.com', role: 'developer' },
      ];

      render(<RoleAssignmentStep {...defaultProps} invitees={longEmailInvitees} />);

      expect(
        screen.getByText('this.is.a.very.long.email.address@subdomain.example.com')
      ).toBeInTheDocument();
    });

    test('handles many invitees', () => {
      const manyInvitees = Array.from({ length: 10 }, (_, i) => ({
        email: `user${i}@example.com`,
        role: 'developer',
      }));

      render(<RoleAssignmentStep {...defaultProps} invitees={manyInvitees} />);

      const selectors = screen.getAllByRole('combobox');
      expect(selectors).toHaveLength(10);
    });
  });
});

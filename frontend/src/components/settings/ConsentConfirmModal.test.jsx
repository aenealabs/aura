import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import ConsentConfirmModal from './ConsentConfirmModal';

// Mock the consentApi module
vi.mock('../../services/consentApi', () => ({
  CONSENT_TYPE_CONFIG: {
    training_data: {
      label: 'Training Data',
      description: 'Allow failed debugging attempts as anonymous training data',
      details: [
        'Code snippets are stripped of comments, strings, and identifiers',
        'Only structural patterns are retained for training',
        'Data is encrypted at rest and in transit',
        'Retained for 2 years or until consent withdrawal',
      ],
      category: 'training',
      tier: 2,
      icon: 'CpuChipIcon',
    },
    synthetic_bugs: {
      label: 'Synthetic Bugs',
      description: 'Generate test scenarios from your codebase patterns',
      details: [
        'Synthetic bugs are created from code patterns, not actual code',
        'Used to train bug-solving agents',
      ],
      category: 'training',
      tier: 2,
      icon: 'BugAntIcon',
    },
  },
  getConsentVersion: () => '1.0.0',
}));

describe('ConsentConfirmModal', () => {
  const defaultProps = {
    isOpen: true,
    consentType: 'training_data',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    test('does not render when closed', () => {
      render(<ConsentConfirmModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    test('renders when open', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('renders modal title', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByText('Confirm AI Training Participation')).toBeInTheDocument();
    });

    test('displays consent type label', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByText('Training Data')).toBeInTheDocument();
    });

    test('displays consent type description', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(
        screen.getByText('Allow failed debugging attempts as anonymous training data')
      ).toBeInTheDocument();
    });

    test('displays consent details', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(
        screen.getByText('Code snippets are stripped of comments, strings, and identifiers')
      ).toBeInTheDocument();
      expect(screen.getByText('Data is encrypted at rest and in transit')).toBeInTheDocument();
    });

    test('displays withdrawal information', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByText('You can withdraw consent at any time from Settings')).toBeInTheDocument();
      expect(screen.getByText('Data is deleted within 30 days of withdrawal')).toBeInTheDocument();
    });

    test('displays consent version', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByText(/Consent Version: 1.0.0/)).toBeInTheDocument();
    });

    test('displays expiration date', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByText(/Expires:.*\(2 years\)/)).toBeInTheDocument();
    });

    test('displays learn more link', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      const link = screen.getByRole('link', { name: /learn more about our data practices/i });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/privacy#training_data');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    test('returns null for invalid consent type', () => {
      const { container } = render(
        <ConsentConfirmModal {...defaultProps} consentType="invalid_type" />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('acknowledgment checkbox', () => {
    test('renders acknowledgment checkbox', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('checkbox')).toBeInTheDocument();
      expect(
        screen.getByLabelText('I understand and consent to this data use')
      ).toBeInTheDocument();
    });

    test('checkbox is unchecked by default', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('checkbox')).not.toBeChecked();
    });

    test('checkbox can be toggled', async () => {
      const user = userEvent.setup();
      render(<ConsentConfirmModal {...defaultProps} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeChecked();

      await user.click(checkbox);
      expect(checkbox).toBeChecked();

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  describe('buttons', () => {
    test('renders cancel and confirm buttons', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /grant consent/i })).toBeInTheDocument();
    });

    test('grant consent button is disabled when not acknowledged', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /grant consent/i })).toBeDisabled();
    });

    test('grant consent button is enabled when acknowledged', async () => {
      const user = userEvent.setup();
      render(<ConsentConfirmModal {...defaultProps} />);

      await user.click(screen.getByRole('checkbox'));

      expect(screen.getByRole('button', { name: /grant consent/i })).not.toBeDisabled();
    });

    test('calls onCancel when cancel button clicked', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      render(<ConsentConfirmModal {...defaultProps} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    test('calls onConfirm when grant consent button clicked after acknowledgment', async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      render(<ConsentConfirmModal {...defaultProps} onConfirm={onConfirm} />);

      await user.click(screen.getByRole('checkbox'));
      await user.click(screen.getByRole('button', { name: /grant consent/i }));

      expect(onConfirm).toHaveBeenCalledTimes(1);
    });

    test('does not call onConfirm when not acknowledged', async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn();
      render(<ConsentConfirmModal {...defaultProps} onConfirm={onConfirm} />);

      // Try to click the disabled button (won't work but tests the guard)
      const button = screen.getByRole('button', { name: /grant consent/i });
      expect(button).toBeDisabled();

      expect(onConfirm).not.toHaveBeenCalled();
    });

    test('shows loading state during confirmation', async () => {
      const user = userEvent.setup();
      let resolveConfirm;
      const onConfirm = vi.fn().mockImplementation(
        () => new Promise((resolve) => {
          resolveConfirm = resolve;
        })
      );
      render(<ConsentConfirmModal {...defaultProps} onConfirm={onConfirm} />);

      await user.click(screen.getByRole('checkbox'));
      await user.click(screen.getByRole('button', { name: /grant consent/i }));

      expect(screen.getByRole('button', { name: /granting/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /granting/i })).toBeDisabled();

      // Resolve the promise
      resolveConfirm();
    });
  });

  describe('keyboard navigation', () => {
    test('closes on escape key', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      render(<ConsentConfirmModal {...defaultProps} onCancel={onCancel} />);

      await user.keyboard('{Escape}');

      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  describe('accessibility', () => {
    test('has dialog role', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('has aria-modal attribute', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true');
    });

    test('has aria-labelledby pointing to title', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby', 'consent-modal-title');
    });

    test('close button has aria-label', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /close dialog/i })).toBeInTheDocument();
    });

    test('checkbox has proper label association', () => {
      render(<ConsentConfirmModal {...defaultProps} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('id', 'consent-acknowledge');

      const label = screen.getByText('I understand and consent to this data use');
      expect(label).toHaveAttribute('for', 'consent-acknowledge');
    });
  });

  describe('backdrop interaction', () => {
    test('calls onCancel when backdrop clicked', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      render(<ConsentConfirmModal {...defaultProps} onCancel={onCancel} />);

      // Click the backdrop (first child of the modal container)
      const backdrop = document.querySelector('[aria-hidden="true"]');
      await user.click(backdrop);

      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  describe('close button', () => {
    test('calls onCancel when close button clicked', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      render(<ConsentConfirmModal {...defaultProps} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: /close dialog/i }));

      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  describe('state reset on open', () => {
    test('resets acknowledgment when modal reopens', async () => {
      const user = userEvent.setup();
      const { rerender } = render(<ConsentConfirmModal {...defaultProps} />);

      // Check the checkbox
      await user.click(screen.getByRole('checkbox'));
      expect(screen.getByRole('checkbox')).toBeChecked();

      // Close modal
      rerender(<ConsentConfirmModal {...defaultProps} isOpen={false} />);

      // Reopen modal
      rerender(<ConsentConfirmModal {...defaultProps} isOpen={true} />);

      // Checkbox should be unchecked again
      expect(screen.getByRole('checkbox')).not.toBeChecked();
    });
  });

  describe('different consent types', () => {
    test('renders synthetic_bugs consent type correctly', () => {
      render(<ConsentConfirmModal {...defaultProps} consentType="synthetic_bugs" />);

      expect(screen.getByText('Synthetic Bugs')).toBeInTheDocument();
      expect(
        screen.getByText('Generate test scenarios from your codebase patterns')
      ).toBeInTheDocument();
    });
  });
});

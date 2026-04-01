import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import PrivacyTrainingSettings from './PrivacyTrainingSettings';

// Mock consent API
const mockGetConsents = vi.fn();
const mockGrantConsent = vi.fn();
const mockWithdrawConsent = vi.fn();
const mockWithdrawAllDataConsents = vi.fn();
const mockGetConsentAuditLog = vi.fn();
const mockExportCustomerData = vi.fn();
const mockRequestDataErasure = vi.fn();
const mockGetJurisdiction = vi.fn();

vi.mock('../../services/consentApi', () => ({
  ConsentType: {
    TRAINING_DATA: 'training_data',
    SYNTHETIC_BUGS: 'synthetic_bugs',
    MODEL_UPDATES: 'model_updates',
    TELEMETRY: 'telemetry',
    FEEDBACK: 'feedback',
    ANONYMIZED_BENCHMARKS: 'anonymized_benchmarks',
  },
  ConsentStatus: {
    GRANTED: 'granted',
    DENIED: 'denied',
    WITHDRAWN: 'withdrawn',
    PENDING: 'pending',
    EXPIRED: 'expired',
  },
  CONSENT_TYPE_CONFIG: {
    training_data: {
      label: 'Training Data',
      description: 'Allow failed debugging attempts as anonymous training data',
      details: ['Code snippets are stripped', 'Only structural patterns retained'],
      category: 'training',
      tier: 2,
      icon: 'CpuChipIcon',
    },
    synthetic_bugs: {
      label: 'Synthetic Bugs',
      description: 'Generate test scenarios from your codebase patterns',
      details: ['Synthetic bugs created from patterns'],
      category: 'training',
      tier: 2,
      icon: 'BugAntIcon',
    },
    anonymized_benchmarks: {
      label: 'Benchmark Reports',
      description: 'Include anonymized metrics in public benchmarks',
      details: ['Only aggregate statistics shared'],
      category: 'training',
      tier: 2,
      icon: 'ChartBarIcon',
    },
    telemetry: {
      label: 'Performance Telemetry',
      description: 'System performance and usage analytics',
      details: ['Page load times', 'Feature usage'],
      category: 'platform',
      tier: 1,
      icon: 'SignalIcon',
    },
    feedback: {
      label: 'User Feedback',
      description: 'Thumbs up/down ratings for AI responses',
      details: ['Explicit feedback on AI quality'],
      category: 'platform',
      tier: 1,
      icon: 'HandThumbUpIcon',
    },
    model_updates: {
      label: 'Model Updates',
      description: 'Receive AI improvements from aggregate training',
      details: ['Access to improved AI models'],
      category: 'platform',
      tier: 1,
      icon: 'ArrowPathIcon',
    },
  },
  getConsents: (...args) => mockGetConsents(...args),
  grantConsent: (...args) => mockGrantConsent(...args),
  withdrawConsent: (...args) => mockWithdrawConsent(...args),
  withdrawAllDataConsents: (...args) => mockWithdrawAllDataConsents(...args),
  getConsentAuditLog: (...args) => mockGetConsentAuditLog(...args),
  exportCustomerData: (...args) => mockExportCustomerData(...args),
  requestDataErasure: (...args) => mockRequestDataErasure(...args),
  getJurisdiction: (...args) => mockGetJurisdiction(...args),
  getConsentVersion: () => '1.0.0',
  getDaysUntilExpiry: (date) => (date ? 730 : null),
  formatConsentStatus: (status) =>
    ({
      granted: { label: 'Granted', color: 'olive' },
      pending: { label: 'Pending', color: 'warning' },
      withdrawn: { label: 'Withdrawn', color: 'critical' },
      denied: { label: 'Denied', color: 'surface' },
      expired: { label: 'Expired', color: 'surface' },
    })[status] || { label: status, color: 'surface' },
}));

// Mock URL.createObjectURL for export test
global.URL.createObjectURL = vi.fn(() => 'blob:test-url');
global.URL.revokeObjectURL = vi.fn();

// Mock window.confirm and window.alert for erasure flow
const originalConfirm = window.confirm;
const originalAlert = window.alert;

describe('PrivacyTrainingSettings', () => {
  const mockConsents = [
    {
      consent_id: '1',
      consent_type: 'training_data',
      status: 'pending',
      granted_at: null,
      expires_at: null,
    },
    {
      consent_id: '2',
      consent_type: 'synthetic_bugs',
      status: 'pending',
      granted_at: null,
      expires_at: null,
    },
    {
      consent_id: '3',
      consent_type: 'anonymized_benchmarks',
      status: 'denied',
      granted_at: null,
      expires_at: null,
    },
    {
      consent_id: '4',
      consent_type: 'telemetry',
      status: 'granted',
      granted_at: '2025-12-15T10:00:00Z',
      expires_at: '2027-12-15T10:00:00Z',
    },
    {
      consent_id: '5',
      consent_type: 'feedback',
      status: 'granted',
      granted_at: '2025-12-15T10:00:00Z',
      expires_at: '2027-12-15T10:00:00Z',
    },
    {
      consent_id: '6',
      consent_type: 'model_updates',
      status: 'granted',
      granted_at: '2025-12-15T10:00:00Z',
      expires_at: '2027-12-15T10:00:00Z',
    },
  ];

  const mockAuditLog = [
    {
      audit_id: 'a1',
      consent_type: 'telemetry',
      action: 'granted',
      timestamp: '2025-12-15T10:00:00Z',
    },
    {
      audit_id: 'a2',
      consent_type: 'feedback',
      action: 'granted',
      timestamp: '2025-12-15T10:00:00Z',
    },
  ];

  const defaultProps = {
    onSuccess: vi.fn(),
    onError: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetConsents.mockResolvedValue(mockConsents);
    mockGetConsentAuditLog.mockResolvedValue(mockAuditLog);
    mockGetJurisdiction.mockResolvedValue({ jurisdiction: 'GDPR', country: 'US', region: 'CA' });
    mockGrantConsent.mockResolvedValue({ status: 'granted' });
    mockWithdrawConsent.mockResolvedValue({ status: 'withdrawn' });
    mockWithdrawAllDataConsents.mockResolvedValue([]);
    mockExportCustomerData.mockResolvedValue({ customer_id: 'test', consents: [] });
    mockRequestDataErasure.mockResolvedValue({ request_id: 'req-1', status: 'pending' });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.confirm = originalConfirm;
    window.alert = originalAlert;
  });

  describe('loading and initial render', () => {
    test('renders page title', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Privacy & AI Training')).toBeInTheDocument();
      });
    });

    test('loads consents on mount', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(mockGetConsents).toHaveBeenCalled();
      });
    });

    test('loads audit log on mount', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(mockGetConsentAuditLog).toHaveBeenCalled();
      });
    });
  });

  describe('section rendering', () => {
    test('renders AI Training Participation section', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('AI Training Participation')).toBeInTheDocument();
      });
    });

    test('renders Platform Improvement section', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Platform Improvement')).toBeInTheDocument();
      });
    });

    test('renders Quick Actions section', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Quick Actions')).toBeInTheDocument();
      });
    });

    test('renders Data Rights section', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Your Data Rights')).toBeInTheDocument();
      });
    });

    test('renders Consent History section', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Consent History')).toBeInTheDocument();
      });
    });
  });

  describe('training consent cards (Tier 2)', () => {
    test('displays Training Data consent', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Training Data')).toBeInTheDocument();
      });
    });

    test('displays Synthetic Bugs consent', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Synthetic Bugs')).toBeInTheDocument();
      });
    });

    test('displays Benchmark Reports consent', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Benchmark Reports')).toBeInTheDocument();
      });
    });
  });

  describe('platform consent cards (Tier 1)', () => {
    test('displays Performance Telemetry consent', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Performance Telemetry')).toBeInTheDocument();
      });
    });

    test('displays User Feedback consent', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('User Feedback')).toBeInTheDocument();
      });
    });

    test('displays Model Updates consent', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Model Updates')).toBeInTheDocument();
      });
    });
  });

  describe('toggle switches', () => {
    test('renders toggle switches for consents', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        const toggles = screen.getAllByRole('switch');
        expect(toggles.length).toBeGreaterThan(0);
      });
    });

    test('granted consents show toggle as checked', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        const toggles = screen.getAllByRole('switch');
        const checkedToggles = toggles.filter((t) => t.getAttribute('aria-checked') === 'true');
        expect(checkedToggles.length).toBeGreaterThan(0);
      });
    });

    test('pending consents show toggle as unchecked', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        const toggles = screen.getAllByRole('switch');
        const uncheckedToggles = toggles.filter((t) => t.getAttribute('aria-checked') === 'false');
        expect(uncheckedToggles.length).toBeGreaterThan(0);
      });
    });
  });

  describe('tier 1 consent interactions', () => {
    test('clicking tier 1 toggle calls withdrawConsent when granted', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Performance Telemetry')).toBeInTheDocument();
      });

      const toggles = screen.getAllByRole('switch');
      const checkedToggle = toggles.find((t) => t.getAttribute('aria-checked') === 'true');

      if (checkedToggle) {
        await user.click(checkedToggle);
        await waitFor(() => {
          expect(mockWithdrawConsent).toHaveBeenCalled();
        });
      }
    });
  });

  describe('quick actions', () => {
    test('renders Withdraw All Data Consents button', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });
    });

    test('withdraw all button is enabled when training consents are granted', async () => {
      mockGetConsents.mockResolvedValue([
        { ...mockConsents[0], status: 'granted' },
        ...mockConsents.slice(1),
      ]);

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        const button = screen.getByText('Withdraw All Data Consents').closest('button');
        expect(button).not.toBeDisabled();
      });
    });
  });

  describe('data rights', () => {
    test('renders Download My Data button', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Download My Data')).toBeInTheDocument();
      });
    });

    test('clicking download calls exportCustomerData', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Download My Data')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Download My Data'));

      await waitFor(() => {
        expect(mockExportCustomerData).toHaveBeenCalled();
      });
    });
  });

  describe('consent history', () => {
    test('renders consent history section', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Consent History')).toBeInTheDocument();
      });
    });

    test('history section is collapsible', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Consent History')).toBeInTheDocument();
      });

      const historyButton = screen.getByText('Consent History').closest('button');
      if (historyButton) {
        await user.click(historyButton);
      }
    });
  });

  describe('consent descriptions', () => {
    test('displays consent descriptions', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(
          screen.getByText('Allow failed debugging attempts as anonymous training data')
        ).toBeInTheDocument();
      });
    });

    test('displays category labels', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getAllByText('Data Contribution').length).toBeGreaterThan(0);
      });
    });
  });

  describe('jurisdiction display', () => {
    test('displays GDPR jurisdiction when detected', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        // Multiple GDPR elements may exist, check at least one is present
        const gdprElements = screen.getAllByText(/GDPR/);
        expect(gdprElements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('data erasure flow', () => {
    test('renders Request Deletion button', async () => {
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Request Deletion')).toBeInTheDocument();
      });
    });

    test('clicking Request Deletion with confirm calls requestDataErasure', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      window.alert = vi.fn();

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Request Deletion')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Request Deletion'));

      await waitFor(() => {
        expect(window.confirm).toHaveBeenCalledWith(
          'Are you sure you want to request deletion of all your training data? This cannot be undone.'
        );
        expect(mockRequestDataErasure).toHaveBeenCalled();
      });
    });

    test('clicking Request Deletion with cancel does not call requestDataErasure', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => false);

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Request Deletion')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Request Deletion'));

      await waitFor(() => {
        expect(window.confirm).toHaveBeenCalled();
      });

      expect(mockRequestDataErasure).not.toHaveBeenCalled();
    });

    test('shows alert with request ID after successful erasure request', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      window.alert = vi.fn();
      mockRequestDataErasure.mockResolvedValue({
        request_id: 'erasure-123',
        status: 'pending',
        estimated_completion: '2026-02-01T00:00:00Z',
      });

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Request Deletion')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Request Deletion'));

      await waitFor(() => {
        expect(window.alert).toHaveBeenCalledWith(
          expect.stringContaining('erasure-123')
        );
      });
    });
  });

  describe('withdraw all modal', () => {
    test('clicking Withdraw All Data Consents opens modal', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Withdraw All Data Consents'));

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents?')).toBeInTheDocument();
      });
    });

    test('withdraw all modal shows warning message', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Withdraw All Data Consents'));

      await waitFor(() => {
        expect(
          screen.getByText(/This will withdraw consent for Training Data, Synthetic Bugs, and Benchmark Reports/)
        ).toBeInTheDocument();
      });
    });

    test('clicking Cancel in modal closes it', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Withdraw All Data Consents'));

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents?')).toBeInTheDocument();
      });

      // Click the Cancel button in the modal
      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByText('Withdraw All Data Consents?')).not.toBeInTheDocument();
      });
    });

    test('clicking Withdraw All in modal calls withdrawAllDataConsents', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Withdraw All Data Consents'));

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents?')).toBeInTheDocument();
      });

      // Click the Withdraw All button in the modal
      const withdrawButton = screen.getByRole('button', { name: 'Withdraw All' });
      await user.click(withdrawButton);

      await waitFor(() => {
        expect(mockWithdrawAllDataConsents).toHaveBeenCalled();
      });
    });

    test('modal closes after successful withdrawal', async () => {
      const user = userEvent.setup();
      mockWithdrawAllDataConsents.mockResolvedValue([
        { consent_type: 'training_data', status: 'withdrawn' },
        { consent_type: 'synthetic_bugs', status: 'withdrawn' },
        { consent_type: 'anonymized_benchmarks', status: 'withdrawn' },
      ]);

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Withdraw All Data Consents'));

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents?')).toBeInTheDocument();
      });

      const withdrawButton = screen.getByRole('button', { name: 'Withdraw All' });
      await user.click(withdrawButton);

      await waitFor(() => {
        expect(screen.queryByText('Withdraw All Data Consents?')).not.toBeInTheDocument();
      });
    });

    test('modal refreshes consents after withdrawal', async () => {
      const user = userEvent.setup();
      mockWithdrawAllDataConsents.mockResolvedValue([]);

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Withdraw All Data Consents'));

      await waitFor(() => {
        expect(screen.getByText('Withdraw All Data Consents?')).toBeInTheDocument();
      });

      const withdrawButton = screen.getByRole('button', { name: 'Withdraw All' });
      await user.click(withdrawButton);

      await waitFor(() => {
        // Should refresh consents after withdrawal
        expect(mockGetConsents).toHaveBeenCalledTimes(2); // Initial + after withdrawal
      });
    });
  });

  describe('tier 2 consent confirmation modal', () => {
    test('clicking tier 2 consent toggle opens confirmation modal', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Training Data')).toBeInTheDocument();
      });

      // Find an unchecked toggle (tier 2 consent in pending state)
      const toggles = screen.getAllByRole('switch');
      const uncheckedToggle = toggles.find((t) => t.getAttribute('aria-checked') === 'false');

      if (uncheckedToggle) {
        await user.click(uncheckedToggle);

        await waitFor(() => {
          expect(screen.getByText('Confirm AI Training Participation')).toBeInTheDocument();
        });
      }
    });
  });

  describe('error handling', () => {
    test('displays error alert when erasure request fails', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      mockRequestDataErasure.mockRejectedValue(new Error('Network error'));

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Request Deletion')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Request Deletion'));

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    test('error alert can be dismissed', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      mockRequestDataErasure.mockRejectedValue(new Error('Network error'));

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Request Deletion')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Request Deletion'));

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Dismiss'));

      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      });
    });
  });

  describe('consent card interactions', () => {
    test('clicking Learn more expands consent details', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Training Data')).toBeInTheDocument();
      });

      const learnMoreButtons = screen.getAllByText('Learn more');
      await user.click(learnMoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Hide details')).toBeInTheDocument();
      });
    });

    test('clicking Hide details collapses consent details', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Training Data')).toBeInTheDocument();
      });

      // Expand
      const learnMoreButtons = screen.getAllByText('Learn more');
      await user.click(learnMoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Hide details')).toBeInTheDocument();
      });

      // Collapse
      await user.click(screen.getByText('Hide details'));

      await waitFor(() => {
        expect(screen.queryByText('Hide details')).not.toBeInTheDocument();
      });
    });

    test('expanded details show policy link', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Training Data')).toBeInTheDocument();
      });

      const learnMoreButtons = screen.getAllByText('Learn more');
      await user.click(learnMoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Read full policy')).toBeInTheDocument();
      });
    });
  });

  describe('export functionality', () => {
    test('export creates downloadable JSON file', async () => {
      const user = userEvent.setup();
      const mockClick = vi.fn();
      const mockCreateElement = vi.spyOn(document, 'createElement');

      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Download My Data')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Download My Data'));

      await waitFor(() => {
        expect(mockExportCustomerData).toHaveBeenCalled();
        expect(global.URL.createObjectURL).toHaveBeenCalled();
      });

      mockCreateElement.mockRestore();
    });

    test('export from history panel also works', async () => {
      const user = userEvent.setup();
      render(<PrivacyTrainingSettings {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export (JSON)')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Export (JSON)'));

      await waitFor(() => {
        expect(mockExportCustomerData).toHaveBeenCalled();
      });
    });
  });
});

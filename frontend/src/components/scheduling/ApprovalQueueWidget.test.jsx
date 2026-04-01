/**
 * ApprovalQueueWidget Component Tests
 *
 * Tests for the HITL approval queue widget with expiration countdown.
 * ADR-055 Phase 2: Timeline and HITL Integration
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import ApprovalQueueWidget from './ApprovalQueueWidget';

// Mock react-router-dom's useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock the schedulingApi
vi.mock('../../services/schedulingApi', () => ({
  getPendingApprovals: vi.fn(),
  approveRequest: vi.fn(),
  rejectRequest: vi.fn(),
}));

import { getPendingApprovals, approveRequest, rejectRequest } from '../../services/schedulingApi';

const mockApprovals = {
  approvals: [
    {
      approval_id: 'approval-1',
      patch_id: 'PATCH-2024-001',
      vulnerability_id: 'CVE-2024-12345',
      severity: 'CRITICAL',
      reviewer_email: 'security@example.com',
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(), // 30 min
      escalation_count: 0,
      created_at: new Date().toISOString(),
    },
    {
      approval_id: 'approval-2',
      patch_id: 'PATCH-2024-002',
      vulnerability_id: 'CVE-2024-67890',
      severity: 'HIGH',
      reviewer_email: 'devops@example.com',
      expires_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(), // 2 hours
      escalation_count: 1,
      created_at: new Date().toISOString(),
    },
    {
      approval_id: 'approval-3',
      patch_id: 'PATCH-2024-003',
      severity: 'MEDIUM',
      expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // 24 hours
      escalation_count: 0,
      created_at: new Date().toISOString(),
    },
    {
      approval_id: 'approval-4',
      patch_id: 'PATCH-2024-004',
      severity: 'LOW',
      escalation_count: 0,
      created_at: new Date().toISOString(),
    },
  ],
  total: 4,
};

const renderComponent = (props = {}) => {
  return render(
    <BrowserRouter>
      <ApprovalQueueWidget onApprovalAction={vi.fn()} {...props} />
    </BrowserRouter>
  );
};

describe('ApprovalQueueWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPendingApprovals.mockResolvedValue(mockApprovals);
    approveRequest.mockResolvedValue({ success: true });
    rejectRequest.mockResolvedValue({ success: true });
    mockNavigate.mockClear();
  });

  describe('Loading State', () => {
    test('shows loading state while fetching data', () => {
      getPendingApprovals.mockImplementation(() => new Promise(() => {}));

      renderComponent();

      expect(screen.getByText('Loading approvals...')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    test('displays error message when API fails', async () => {
      getPendingApprovals.mockRejectedValue(new Error('Network error'));

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Header', () => {
    test('renders header with title', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('HITL Approval Queue')).toBeInTheDocument();
      });
    });

    test('shows pending approval count', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/4 pending approvals/i)).toBeInTheDocument();
      });
    });

    test('shows View All link in non-compact mode', async () => {
      renderComponent({ compact: false });

      await waitFor(() => {
        expect(screen.getByText('View All')).toBeInTheDocument();
      });
    });
  });

  describe('Severity Summary', () => {
    test('displays severity counts in non-compact mode', async () => {
      renderComponent({ compact: false });

      await waitFor(() => {
        // Severity labels appear in both summary and items - use getAllByText
        expect(screen.getAllByText('CRITICAL').length).toBeGreaterThan(0);
        expect(screen.getAllByText('HIGH').length).toBeGreaterThan(0);
        expect(screen.getAllByText('MEDIUM').length).toBeGreaterThan(0);
        expect(screen.getAllByText('LOW').length).toBeGreaterThan(0);
      });
    });
  });

  describe('Approval List', () => {
    test('displays approval items', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
        expect(screen.getByText('PATCH-2024-002')).toBeInTheDocument();
      });
    });

    test('shows severity badges', async () => {
      renderComponent();

      await waitFor(() => {
        // Look for severity badges (multiple CRITICAL elements - in summary and items)
        const criticalBadges = screen.getAllByText('CRITICAL');
        expect(criticalBadges.length).toBeGreaterThan(0);
      });
    });

    test('shows escalation indicator when escalated', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/Escalated ×1/)).toBeInTheDocument();
      });
    });

    test('shows vulnerability ID when available', async () => {
      renderComponent({ compact: false });

      await waitFor(() => {
        expect(screen.getByText(/CVE-2024-12345/)).toBeInTheDocument();
      });
    });

    test('shows reviewer email when available', async () => {
      renderComponent({ compact: false });

      await waitFor(() => {
        expect(screen.getByText(/security@example.com/)).toBeInTheDocument();
      });
    });
  });

  describe('Expiration Countdown', () => {
    test('displays time remaining until expiration', async () => {
      renderComponent();

      await waitFor(() => {
        // Should show countdown - look for the time display pattern (e.g., "30m" or "1h 30m")
        // The text contains "Expires in" or "Expiring soon" followed by time
        const expiresElements = document.querySelectorAll('[class*="text-xs"]');
        const hasExpirationText = Array.from(expiresElements).some(el =>
          el.textContent?.toLowerCase().includes('expire')
        );
        expect(hasExpirationText).toBe(true);
      });
    });

    test('highlights items expiring soon with critical styling', async () => {
      const soonExpiringApprovals = {
        approvals: [
          {
            approval_id: 'approval-urgent',
            patch_id: 'PATCH-URGENT',
            severity: 'CRITICAL',
            expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(), // 10 min
            escalation_count: 0,
          },
        ],
        total: 1,
      };

      getPendingApprovals.mockResolvedValue(soonExpiringApprovals);

      renderComponent();

      await waitFor(() => {
        // Should have critical styling for expiring soon items
        const criticalElements = document.querySelectorAll('[class*="critical"]');
        expect(criticalElements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Approve Action', () => {
    test('calls approveRequest when approve button clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
      });

      // Find approve buttons by their title attribute
      const approveButtons = screen.getAllByTitle('Approve');
      await user.click(approveButtons[0]);

      expect(approveRequest).toHaveBeenCalledWith('approval-1', expect.any(String));
    });

    test('removes item from list after approval', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
      });

      const approveButtons = screen.getAllByTitle('Approve');
      await user.click(approveButtons[0]);

      await waitFor(() => {
        expect(screen.queryByText('PATCH-2024-001')).not.toBeInTheDocument();
      });
    });

    test('calls onApprovalAction callback after approval', async () => {
      const onApprovalAction = vi.fn();
      const user = userEvent.setup();

      renderComponent({ onApprovalAction });

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
      });

      const approveButtons = screen.getAllByTitle('Approve');
      await user.click(approveButtons[0]);

      await waitFor(() => {
        expect(onApprovalAction).toHaveBeenCalled();
      });
    });
  });

  describe('Reject Action', () => {
    test('calls rejectRequest when reject button clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
      });

      const rejectButtons = screen.getAllByTitle('Reject');
      await user.click(rejectButtons[0]);

      expect(rejectRequest).toHaveBeenCalledWith('approval-1', expect.any(String));
    });

    test('removes item from list after rejection', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
      });

      const rejectButtons = screen.getAllByTitle('Reject');
      await user.click(rejectButtons[0]);

      await waitFor(() => {
        expect(screen.queryByText('PATCH-2024-001')).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    test('shows empty state when no pending approvals', async () => {
      getPendingApprovals.mockResolvedValue({ approvals: [], total: 0 });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('No pending approvals')).toBeInTheDocument();
        expect(screen.getByText(/all HITL requests have been processed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Compact Mode', () => {
    test('limits displayed items in compact mode', async () => {
      const manyApprovals = {
        approvals: Array.from({ length: 10 }, (_, i) => ({
          approval_id: `approval-${i}`,
          patch_id: `PATCH-${i}`,
          severity: 'MEDIUM',
          escalation_count: 0,
        })),
        total: 10,
      };

      getPendingApprovals.mockResolvedValue(manyApprovals);

      renderComponent({ compact: true });

      await waitFor(() => {
        // In compact mode, should show max 5 items
        const patchItems = screen.getAllByText(/PATCH-\d+/);
        expect(patchItems.length).toBeLessThanOrEqual(5);
      });
    });

    test('shows "View all" link when more items available in compact mode', async () => {
      const manyApprovals = {
        approvals: Array.from({ length: 10 }, (_, i) => ({
          approval_id: `approval-${i}`,
          patch_id: `PATCH-${i}`,
          severity: 'MEDIUM',
          escalation_count: 0,
        })),
        total: 10,
      };

      getPendingApprovals.mockResolvedValue(manyApprovals);

      renderComponent({ compact: true });

      await waitFor(() => {
        expect(screen.getByText(/view all 10 pending approvals/i)).toBeInTheDocument();
      });
    });
  });

  describe('Navigation', () => {
    test('navigates to approval dashboard when View All clicked', async () => {
      const user = userEvent.setup();
      renderComponent({ compact: false });

      await waitFor(() => {
        expect(screen.getByText('View All')).toBeInTheDocument();
      });

      await user.click(screen.getByText('View All'));

      expect(mockNavigate).toHaveBeenCalledWith('/approvals');
    });
  });

  describe('Processing State', () => {
    test('disables buttons while processing', async () => {
      const user = userEvent.setup();

      // Make approval take some time
      approveRequest.mockImplementation(() => new Promise(resolve =>
        setTimeout(() => resolve({ success: true }), 100)
      ));

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('PATCH-2024-001')).toBeInTheDocument();
      });

      const approveButtons = screen.getAllByTitle('Approve');

      // Click and check for disabled state
      await user.click(approveButtons[0]);

      // Button should be disabled while processing
      expect(approveButtons[0]).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    test('approve buttons have title attribute', async () => {
      renderComponent();

      await waitFor(() => {
        const approveButtons = screen.getAllByTitle('Approve');
        expect(approveButtons.length).toBeGreaterThan(0);
      });
    });

    test('reject buttons have title attribute', async () => {
      renderComponent();

      await waitFor(() => {
        const rejectButtons = screen.getAllByTitle('Reject');
        expect(rejectButtons.length).toBeGreaterThan(0);
      });
    });
  });
});

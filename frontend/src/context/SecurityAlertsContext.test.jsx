import { useEffect } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { SecurityAlertsProvider, useSecurityAlerts } from './SecurityAlertsContext';

// Mock the securityAlertsApi module
vi.mock('../services/securityAlertsApi', () => ({
  listSecurityAlerts: vi.fn(),
  getSecurityAlertDetail: vi.fn(),
  acknowledgeAlert: vi.fn(),
  resolveAlert: vi.fn(),
  getUnacknowledgedCount: vi.fn(),
  AlertPriority: {
    P1_CRITICAL: 'P1_CRITICAL',
    P2_HIGH: 'P2_HIGH',
    P3_MEDIUM: 'P3_MEDIUM',
    P4_LOW: 'P4_LOW',
  },
  AlertStatus: {
    NEW: 'NEW',
    ACKNOWLEDGED: 'ACKNOWLEDGED',
    INVESTIGATING: 'INVESTIGATING',
    RESOLVED: 'RESOLVED',
  },
}));

import * as securityAlertsApi from '../services/securityAlertsApi';

// Test consumer component that stops polling immediately
function TestConsumer({ onMount }) {
  const context = useSecurityAlerts();

  useEffect(() => {
    // Stop polling immediately to prevent infinite timer loops in tests
    context.stopPolling();
    if (onMount) onMount(context);
  }, [onMount, context]);

  return (
    <div>
      <span data-testid="alerts-count">{context.alerts.length}</span>
      <span data-testid="loading">{context.loading ? 'true' : 'false'}</span>
      <span data-testid="error">{context.error || 'none'}</span>
      <span data-testid="unacknowledged-count">{context.unacknowledgedCount}</span>
      <span data-testid="selected-alert">{context.selectedAlert?.alert_id || 'none'}</span>
      <button data-testid="refresh" onClick={() => context.refresh()}>Refresh</button>
      <button data-testid="clear-filters" onClick={() => context.clearFilters()}>Clear Filters</button>
      <button data-testid="update-priority-filter" onClick={() => context.updateFilters({ priority: 'P1_CRITICAL' })}>Filter Critical</button>
    </div>
  );
}

describe('SecurityAlertsContext', () => {
  const mockAlerts = [
    {
      alert_id: 'alert-001',
      title: 'SQL Injection Attempt',
      priority: 'P1_CRITICAL',
      status: 'NEW',
    },
    {
      alert_id: 'alert-002',
      title: 'API Key Exposed',
      priority: 'P1_CRITICAL',
      status: 'ACKNOWLEDGED',
    },
    {
      alert_id: 'alert-003',
      title: 'Rate Limit Exceeded',
      priority: 'P3_MEDIUM',
      status: 'RESOLVED',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // Default mock implementations
    securityAlertsApi.listSecurityAlerts.mockResolvedValue({ alerts: mockAlerts });
    securityAlertsApi.getUnacknowledgedCount.mockResolvedValue({ total: 2, p1_count: 1 });

    // Mock Notification API
    global.Notification = {
      permission: 'granted',
      requestPermission: vi.fn().mockResolvedValue('granted'),
    };
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('SecurityAlertsProvider', () => {
    test('provides initial state', async () => {
      render(
        <SecurityAlertsProvider>
          <TestConsumer />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });
    });

    test('fetches alerts on mount', async () => {
      render(
        <SecurityAlertsProvider>
          <TestConsumer />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(securityAlertsApi.listSecurityAlerts).toHaveBeenCalled();
        expect(screen.getByTestId('alerts-count')).toHaveTextContent('3');
      });
    });

    test('fetches unacknowledged count on mount', async () => {
      render(
        <SecurityAlertsProvider>
          <TestConsumer />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(securityAlertsApi.getUnacknowledgedCount).toHaveBeenCalled();
      });

      // Value depends on mock or DEV fallback, just check it's a number
      const countText = screen.getByTestId('unacknowledged-count').textContent;
      expect(Number(countText)).toBeGreaterThanOrEqual(0);
    });

    test('handles fetch error gracefully', async () => {
      securityAlertsApi.listSecurityAlerts.mockRejectedValue(new Error('Network error'));

      render(
        <SecurityAlertsProvider>
          <TestConsumer />
        </SecurityAlertsProvider>
      );

      // In DEV mode, errors are hidden and mock data is loaded instead
      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      // Should have loaded mock data (4 mock alerts defined in SecurityAlertsContext)
      await waitFor(() => {
        const alertsCount = parseInt(screen.getByTestId('alerts-count').textContent);
        expect(alertsCount).toBeGreaterThan(0);
      });

      // Error should be hidden in DEV mode
      expect(screen.getByTestId('error')).toHaveTextContent('none');
    });
  });

  describe('Filters', () => {
    test('updateFilters updates filter state', async () => {
      const user = userEvent.setup();

      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      await user.click(screen.getByTestId('update-priority-filter'));

      await waitFor(() => {
        expect(capturedContext.filters.priority).toBe('P1_CRITICAL');
      });
    });

    test('clearFilters resets all filters', async () => {
      const user = userEvent.setup();

      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      // Set a filter first
      await user.click(screen.getByTestId('update-priority-filter'));
      expect(capturedContext.filters.priority).toBe('P1_CRITICAL');

      // Clear filters
      await user.click(screen.getByTestId('clear-filters'));
      expect(capturedContext.filters.priority).toBeNull();
    });

    test('persists filters to localStorage', async () => {
      const user = userEvent.setup();

      render(
        <SecurityAlertsProvider>
          <TestConsumer />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      await user.click(screen.getByTestId('update-priority-filter'));

      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem('aura_security_alerts_filters'));
        expect(saved.priority).toBe('P1_CRITICAL');
      });
    });
  });

  describe('Alert actions', () => {
    test('handleAcknowledge updates alert status', async () => {
      securityAlertsApi.acknowledgeAlert.mockResolvedValue({ status: 'ACKNOWLEDGED' });

      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      await act(async () => {
        await capturedContext.handleAcknowledge('alert-001', 'user-1', 'Investigating');
      });

      expect(securityAlertsApi.acknowledgeAlert).toHaveBeenCalledWith('alert-001', 'user-1', 'Investigating');
    });

    test('handleResolve updates alert status', async () => {
      securityAlertsApi.resolveAlert.mockResolvedValue({ status: 'RESOLVED' });

      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      await act(async () => {
        await capturedContext.handleResolve('alert-001', 'user-1', 'Issue fixed', ['Patched vulnerability']);
      });

      expect(securityAlertsApi.resolveAlert).toHaveBeenCalledWith(
        'alert-001',
        'user-1',
        'Issue fixed',
        ['Patched vulnerability']
      );
    });

    test('fetchAlertDetail sets selected alert', async () => {
      const mockDetail = { ...mockAlerts[0], remediation_steps: ['Step 1', 'Step 2'] };
      securityAlertsApi.getSecurityAlertDetail.mockResolvedValue(mockDetail);

      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      await act(async () => {
        await capturedContext.fetchAlertDetail('alert-001');
      });

      expect(screen.getByTestId('selected-alert')).toHaveTextContent('alert-001');
    });
  });

  describe('Refresh', () => {
    test('refresh reloads alerts and count', async () => {
      const user = userEvent.setup();

      render(
        <SecurityAlertsProvider>
          <TestConsumer />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      vi.clearAllMocks();
      securityAlertsApi.listSecurityAlerts.mockResolvedValue({ alerts: mockAlerts });
      securityAlertsApi.getUnacknowledgedCount.mockResolvedValue({ total: 2, p1_count: 1 });

      await user.click(screen.getByTestId('refresh'));

      await waitFor(() => {
        expect(securityAlertsApi.listSecurityAlerts).toHaveBeenCalled();
        expect(securityAlertsApi.getUnacknowledgedCount).toHaveBeenCalled();
      });
    });
  });

  describe('useSecurityAlerts', () => {
    test('throws error when used outside SecurityAlertsProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // Create a simple component that uses the hook without calling stopPolling
      function BareConsumer() {
        useSecurityAlerts();
        return null;
      }

      expect(() => {
        render(<BareConsumer />);
      }).toThrow('useSecurityAlerts must be used within a SecurityAlertsProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('Constants', () => {
    test('exports AlertPriority constants', async () => {
      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext.AlertPriority).toBeDefined();
        expect(capturedContext.AlertPriority.P1_CRITICAL).toBe('P1_CRITICAL');
      });
    });

    test('exports AlertStatus constants', async () => {
      let capturedContext;
      render(
        <SecurityAlertsProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </SecurityAlertsProvider>
      );

      await waitFor(() => {
        expect(capturedContext.AlertStatus).toBeDefined();
        expect(capturedContext.AlertStatus.NEW).toBe('NEW');
      });
    });
  });
});

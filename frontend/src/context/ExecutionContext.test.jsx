import { useEffect } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { ExecutionProvider, useExecution } from './ExecutionContext';

// Mock the executionApi module
vi.mock('../services/executionApi', () => ({
  ActionStatus: {
    PENDING: 'PENDING',
    AWAITING_APPROVAL: 'AWAITING_APPROVAL',
    APPROVED: 'APPROVED',
    DENIED: 'DENIED',
    EXECUTING: 'EXECUTING',
    COMPLETED: 'COMPLETED',
    FAILED: 'FAILED',
    TIMED_OUT: 'TIMED_OUT',
  },
  RiskLevel: {
    LOW: 'LOW',
    MEDIUM: 'MEDIUM',
    HIGH: 'HIGH',
    CRITICAL: 'CRITICAL',
  },
  TrustScope: {
    SESSION: 'SESSION',
    REPOSITORY: 'REPOSITORY',
    GLOBAL: 'GLOBAL',
  },
  WSMessageType: {
    EXECUTION_STARTED: 'EXECUTION_STARTED',
    ACTION_AWAITING_APPROVAL: 'ACTION_AWAITING_APPROVAL',
    ACTION_APPROVED: 'ACTION_APPROVED',
    ACTION_DENIED: 'ACTION_DENIED',
    ACTION_MODIFIED: 'ACTION_MODIFIED',
    ACTION_EXECUTING: 'ACTION_EXECUTING',
    ACTION_COMPLETED: 'ACTION_COMPLETED',
    ACTION_FAILED: 'ACTION_FAILED',
    ACTION_TIMED_OUT: 'ACTION_TIMED_OUT',
    EXECUTION_COMPLETED: 'EXECUTION_COMPLETED',
    EXECUTION_ABORTED: 'EXECUTION_ABORTED',
    EXECUTION_FAILED: 'EXECUTION_FAILED',
    THINKING_UPDATE: 'THINKING_UPDATE',
    LOG_ENTRY: 'LOG_ENTRY',
  },
  RISK_LEVEL_CONFIG: {},
  ACTION_TYPE_CONFIG: {},
  ExecutionWebSocket: vi.fn(),
  createMockWebSocket: vi.fn(() => ({
    on: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    send: vi.fn(),
  })),
  approveAction: vi.fn(),
  denyAction: vi.fn(),
  modifyAction: vi.fn(),
  abortExecution: vi.fn(),
  getTrustSettings: vi.fn(),
  updateTrustSettings: vi.fn(),
  MOCK_TRUST_SETTINGS: {
    default_auto_approve: [],
    always_require_approval: ['file_delete'],
    session_trusts: [],
    approval_timeout_seconds: 300,
    auto_deny_on_timeout: false,
  },
}));

import * as executionApi from '../services/executionApi';

// Test consumer component
function TestConsumer({ onMount }) {
  const context = useExecution();

  useEffect(() => {
    if (onMount) onMount(context);
  }, [onMount, context]);

  return (
    <div>
      <span data-testid="connection-status">{context.connectionStatus}</span>
      <span data-testid="execution-status">{context.executionStatus}</span>
      <span data-testid="actions-count">{context.actions.length}</span>
      <span data-testid="current-action">{context.currentAction?.action_id || 'none'}</span>
      <span data-testid="modify-modal-open">{context.modifyModalOpen ? 'true' : 'false'}</span>
      <span data-testid="trust-panel-open">{context.trustPanelOpen ? 'true' : 'false'}</span>
      <span data-testid="error">{context.error || 'none'}</span>
      <button data-testid="open-trust-panel" onClick={() => context.setTrustPanelOpen(true)}>Open Trust Panel</button>
      <button data-testid="close-trust-panel" onClick={() => context.setTrustPanelOpen(false)}>Close Trust Panel</button>
    </div>
  );
}

describe('ExecutionContext', () => {
  let mockWebSocket;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // Create mock WebSocket instance
    mockWebSocket = {
      on: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      send: vi.fn(),
    };

    executionApi.createMockWebSocket.mockReturnValue(mockWebSocket);
    executionApi.getTrustSettings.mockResolvedValue(executionApi.MOCK_TRUST_SETTINGS);
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('ExecutionProvider', () => {
    test('provides initial state', async () => {
      render(
        <ExecutionProvider>
          <TestConsumer />
        </ExecutionProvider>
      );

      expect(screen.getByTestId('execution-status')).toHaveTextContent('idle');
      expect(screen.getByTestId('actions-count')).toHaveTextContent('0');
      expect(screen.getByTestId('current-action')).toHaveTextContent('none');
    });

    test('creates mock WebSocket in dev mode', async () => {
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer />
        </ExecutionProvider>
      );

      expect(executionApi.createMockWebSocket).toHaveBeenCalled();
    });

    test('sets up WebSocket event listeners', async () => {
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer />
        </ExecutionProvider>
      );

      expect(mockWebSocket.on).toHaveBeenCalledWith('connected', expect.any(Function));
      expect(mockWebSocket.on).toHaveBeenCalledWith('disconnected', expect.any(Function));
      expect(mockWebSocket.on).toHaveBeenCalledWith('error', expect.any(Function));
    });
  });

  describe('Connection status', () => {
    test('updates connection status on connect', async () => {
      let connectedCallback;
      mockWebSocket.on.mockImplementation((event, callback) => {
        if (event === 'connected') {
          connectedCallback = callback;
        }
      });

      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer />
        </ExecutionProvider>
      );

      // Simulate connection
      act(() => {
        connectedCallback();
      });

      expect(screen.getByTestId('connection-status')).toHaveTextContent('connected');
    });

    test('updates connection status on disconnect', async () => {
      let disconnectedCallback;
      mockWebSocket.on.mockImplementation((event, callback) => {
        if (event === 'disconnected') {
          disconnectedCallback = callback;
        }
      });

      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer />
        </ExecutionProvider>
      );

      act(() => {
        disconnectedCallback({ reason: 'Server closed' });
      });

      expect(screen.getByTestId('connection-status')).toHaveTextContent('disconnected');
    });
  });

  describe('Trust panel', () => {
    test('setTrustPanelOpen toggles trust panel', async () => {
      const user = userEvent.setup();

      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer />
        </ExecutionProvider>
      );

      expect(screen.getByTestId('trust-panel-open')).toHaveTextContent('false');

      await user.click(screen.getByTestId('open-trust-panel'));
      expect(screen.getByTestId('trust-panel-open')).toHaveTextContent('true');

      await user.click(screen.getByTestId('close-trust-panel'));
      expect(screen.getByTestId('trust-panel-open')).toHaveTextContent('false');
    });
  });

  describe('Action approval', () => {
    test('approveAction is available as a function', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      // In mock mode with no active execution, function should be available but do nothing
      expect(typeof capturedContext.approveAction).toBe('function');
    });

    test('denyAction is available as a function', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      expect(typeof capturedContext.denyAction).toBe('function');
    });
  });

  describe('Execution control', () => {
    test('abortExecution is available as a function', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      expect(typeof capturedContext.abortExecution).toBe('function');
    });
  });

  describe('Trust settings', () => {
    test('loads trust settings using mock settings in mock mode', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        // In mock mode, uses MOCK_TRUST_SETTINGS instead of calling API
        expect(capturedContext).toBeDefined();
        expect(capturedContext.trustSettings).toBeDefined();
      });
    });

    test('saveTrustSettings updates settings in mock mode', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      const newSettings = { approval_timeout_seconds: 600 };
      await act(async () => {
        await capturedContext.saveTrustSettings(newSettings);
      });

      // In mock mode, API is not called but settings are updated
      expect(capturedContext.trustSettings.approval_timeout_seconds).toBe(600);
    });

    // Note: Testing with useMock=false requires properly mocking ExecutionWebSocket class
    // which would require more setup. The mock mode tests cover the trust settings logic.
  });

  describe('useExecution', () => {
    test('throws error when used outside ExecutionProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useExecution must be used within an ExecutionProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('Constants', () => {
    test('provides ActionStatus constants', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        expect(capturedContext.ActionStatus).toBeDefined();
        expect(capturedContext.ActionStatus.APPROVED).toBe('APPROVED');
      });
    });

    test('provides RiskLevel constants', async () => {
      let capturedContext;
      render(
        <ExecutionProvider useMock={true}>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ExecutionProvider>
      );

      await waitFor(() => {
        expect(capturedContext.RiskLevel).toBeDefined();
        expect(capturedContext.RiskLevel.CRITICAL).toBe('CRITICAL');
      });
    });
  });
});

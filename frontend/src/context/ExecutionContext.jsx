/**
 * Project Aura - Real-Time Execution Context Provider
 *
 * Provides global state management for agent execution streaming,
 * action approvals, and trust settings. Manages WebSocket connections
 * for real-time updates.
 *
 * Features:
 * - Real-time execution streaming via WebSocket
 * - Action approval/deny/modify state management
 * - Trust settings per action type
 * - Keyboard shortcut support
 * - Auto-timeout handling
 *
 * @see ADR-032 Configurable Autonomy Framework
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from 'react';

import {
  ActionStatus,
  RiskLevel,
  TrustScope,
  WSMessageType,
  RISK_LEVEL_CONFIG,
  ACTION_TYPE_CONFIG,
  ExecutionWebSocket,
  createMockWebSocket,
  approveAction as apiApproveAction,
  denyAction as apiDenyAction,
  modifyAction as apiModifyAction,
  abortExecution as apiAbortExecution,
  getTrustSettings,
  updateTrustSettings,
  MOCK_TRUST_SETTINGS,
} from '../services/executionApi';

// =============================================================================
// CONTEXT CREATION
// =============================================================================

const ExecutionContext = createContext(null);

// =============================================================================
// DEFAULT VALUES
// =============================================================================

const DEFAULT_TRUST_SETTINGS = {
  default_auto_approve: [],
  always_require_approval: ['file_delete', 'database_write', 'deployment', 'configuration_change', 'secret_access'],
  session_trusts: [],
  approval_timeout_seconds: 300,
  auto_deny_on_timeout: false,
};

const DEFAULT_EXECUTION_STATE = {
  execution: null,
  actions: [],
  currentAction: null,
  thinking: [],
  logs: [],
  status: 'idle', // idle, connecting, connected, executing, completed, failed, aborted
};

// =============================================================================
// PROVIDER COMPONENT
// =============================================================================

/**
 * Execution Provider Component
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 * @param {boolean} props.useMock - Use mock WebSocket for development
 * @param {string} props.organizationId - Organization ID for trust settings
 */
export function ExecutionProvider({
  children,
  useMock = import.meta.env.DEV,
  organizationId = 'org-aura-001',
}) {
  // ==========================================================================
  // STATE
  // ==========================================================================

  // Execution state
  const [executionState, setExecutionState] = useState(DEFAULT_EXECUTION_STATE);

  // Trust settings
  const [trustSettings, setTrustSettings] = useState(DEFAULT_TRUST_SETTINGS);
  const [sessionTrusts, setSessionTrusts] = useState(new Map());

  // Connection state
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [connectionError, setConnectionError] = useState(null);

  // UI state
  const [modifyModalOpen, setModifyModalOpen] = useState(false);
  const [modifyingAction, setModifyingAction] = useState(null);
  const [trustPanelOpen, setTrustPanelOpen] = useState(false);

  // Loading states
  const [loading, setLoading] = useState({
    approve: false,
    deny: false,
    modify: false,
    abort: false,
    trustSettings: false,
  });

  // Error state
  const [error, setError] = useState(null);

  // Refs
  const wsRef = useRef(null);
  const currentExecutionIdRef = useRef(null);

  // ==========================================================================
  // WEBSOCKET INITIALIZATION
  // ==========================================================================

  useEffect(() => {
    // Create WebSocket instance
    if (useMock) {
      wsRef.current = createMockWebSocket();
    } else {
      wsRef.current = new ExecutionWebSocket({
        token: localStorage.getItem('auth_token'),
      });
    }

    // Set up event listeners
    const ws = wsRef.current;

    ws.on('connected', () => {
      setConnectionStatus('connected');
      setConnectionError(null);
    });

    ws.on('disconnected', ({ reason }) => {
      setConnectionStatus('disconnected');
      if (reason && reason !== 'Client disconnect') {
        setConnectionError(reason);
      }
    });

    ws.on('reconnecting', ({ attempt, maxAttempts }) => {
      setConnectionStatus('reconnecting');
      setConnectionError(`Reconnecting (${attempt}/${maxAttempts})...`);
    });

    ws.on('error', (error) => {
      setConnectionError(error.message || 'Connection error');
    });

    ws.on(WSMessageType.EXECUTION_STARTED, handleExecutionStarted);
    ws.on(WSMessageType.ACTION_AWAITING_APPROVAL, handleActionAwaitingApproval);
    ws.on(WSMessageType.ACTION_APPROVED, handleActionApproved);
    ws.on(WSMessageType.ACTION_DENIED, handleActionDenied);
    ws.on(WSMessageType.ACTION_MODIFIED, handleActionModified);
    ws.on(WSMessageType.ACTION_EXECUTING, handleActionExecuting);
    ws.on(WSMessageType.ACTION_COMPLETED, handleActionCompleted);
    ws.on(WSMessageType.ACTION_FAILED, handleActionFailed);
    ws.on(WSMessageType.ACTION_TIMED_OUT, handleActionTimedOut);
    ws.on(WSMessageType.EXECUTION_COMPLETED, handleExecutionCompleted);
    ws.on(WSMessageType.EXECUTION_ABORTED, handleExecutionAborted);
    ws.on(WSMessageType.EXECUTION_FAILED, handleExecutionFailed);
    ws.on(WSMessageType.THINKING_UPDATE, handleThinkingUpdate);
    ws.on(WSMessageType.LOG_ENTRY, handleLogEntry);

    // Load trust settings
    loadTrustSettings();

    // Cleanup on unmount
    return () => {
      if (ws) {
        ws.disconnect();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useMock]);

  // ==========================================================================
  // WEBSOCKET EVENT HANDLERS
  // ==========================================================================

  const handleExecutionStarted = useCallback(({ execution }) => {
    setExecutionState({
      execution,
      actions: execution.actions || [],
      currentAction: execution.actions?.find(a => a.status === ActionStatus.AWAITING_APPROVAL) || null,
      thinking: execution.thinking || [],
      logs: execution.logs || [],
      status: 'executing',
    });
  }, []);

  const handleActionAwaitingApproval = useCallback(({ action }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action.action_id ? action : a
      );

      // Check if this action type is auto-approved via session trust
      const shouldAutoApprove = sessionTrusts.get(action.type);

      if (shouldAutoApprove) {
        // Auto-approve via WebSocket
        setTimeout(() => {
          wsRef.current?.sendApprove(prev.execution?.execution_id, action.action_id, {
            trustScope: TrustScope.THIS_SESSION,
          });
        }, 100);
      }

      return {
        ...prev,
        actions,
        currentAction: shouldAutoApprove ? prev.currentAction : action,
      };
    });
  }, [sessionTrusts]);

  const handleActionApproved = useCallback(({ action_id, trust_scope: _trust_scope }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id ? { ...a, status: ActionStatus.APPROVED } : a
      );
      return {
        ...prev,
        actions,
        currentAction: prev.currentAction?.action_id === action_id ? null : prev.currentAction,
      };
    });
  }, []);

  const handleActionDenied = useCallback(({ action_id, reason }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id ? { ...a, status: ActionStatus.DENIED, deny_reason: reason } : a
      );
      return {
        ...prev,
        actions,
        currentAction: prev.currentAction?.action_id === action_id ? null : prev.currentAction,
      };
    });
  }, []);

  const handleActionModified = useCallback(({ action_id, modified_parameters }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id
          ? { ...a, status: ActionStatus.MODIFIED, parameters: { ...a.parameters, ...modified_parameters } }
          : a
      );
      return {
        ...prev,
        actions,
        currentAction: prev.currentAction?.action_id === action_id ? null : prev.currentAction,
      };
    });
    setModifyModalOpen(false);
    setModifyingAction(null);
  }, []);

  const handleActionExecuting = useCallback(({ action_id }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id ? { ...a, status: ActionStatus.EXECUTING } : a
      );
      return { ...prev, actions };
    });
  }, []);

  const handleActionCompleted = useCallback(({ action_id, result }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id
          ? { ...a, status: ActionStatus.COMPLETED, result, completed_at: new Date().toISOString() }
          : a
      );
      return { ...prev, actions };
    });
  }, []);

  const handleActionFailed = useCallback(({ action_id, error }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id
          ? { ...a, status: ActionStatus.FAILED, error, completed_at: new Date().toISOString() }
          : a
      );
      return { ...prev, actions };
    });
  }, []);

  const handleActionTimedOut = useCallback(({ action_id }) => {
    setExecutionState((prev) => {
      const actions = prev.actions.map((a) =>
        a.action_id === action_id ? { ...a, status: ActionStatus.TIMED_OUT } : a
      );
      return {
        ...prev,
        actions,
        currentAction: prev.currentAction?.action_id === action_id ? null : prev.currentAction,
      };
    });
  }, []);

  const handleExecutionCompleted = useCallback(() => {
    setExecutionState((prev) => ({
      ...prev,
      status: 'completed',
      currentAction: null,
    }));
  }, []);

  const handleExecutionAborted = useCallback(({ reason }) => {
    setExecutionState((prev) => ({
      ...prev,
      status: 'aborted',
      currentAction: null,
      abortReason: reason,
    }));
  }, []);

  const handleExecutionFailed = useCallback(({ error }) => {
    setExecutionState((prev) => ({
      ...prev,
      status: 'failed',
      currentAction: null,
      error,
    }));
  }, []);

  const handleThinkingUpdate = useCallback(({ thought }) => {
    setExecutionState((prev) => ({
      ...prev,
      thinking: [...prev.thinking, thought],
    }));
  }, []);

  const handleLogEntry = useCallback(({ log }) => {
    setExecutionState((prev) => ({
      ...prev,
      logs: [...prev.logs, log],
    }));
  }, []);

  // ==========================================================================
  // TRUST SETTINGS
  // ==========================================================================

  const loadTrustSettings = useCallback(async () => {
    setLoading((prev) => ({ ...prev, trustSettings: true }));
    try {
      if (useMock) {
        setTrustSettings(MOCK_TRUST_SETTINGS);
      } else {
        const settings = await getTrustSettings(organizationId);
        setTrustSettings(settings);
      }
    } catch (err) {
      console.error('Failed to load trust settings:', err);
      setError('Failed to load trust settings');
    } finally {
      setLoading((prev) => ({ ...prev, trustSettings: false }));
    }
  }, [organizationId, useMock]);

  const saveTrustSettings = useCallback(async (newSettings) => {
    setLoading((prev) => ({ ...prev, trustSettings: true }));
    try {
      if (!useMock) {
        await updateTrustSettings(organizationId, newSettings);
      }
      setTrustSettings(newSettings);
    } catch (err) {
      console.error('Failed to save trust settings:', err);
      throw err;
    } finally {
      setLoading((prev) => ({ ...prev, trustSettings: false }));
    }
  }, [organizationId, useMock]);

  const addSessionTrust = useCallback((actionType, scope = TrustScope.THIS_SESSION) => {
    setSessionTrusts((prev) => {
      const newMap = new Map(prev);
      newMap.set(actionType, scope);
      return newMap;
    });
  }, []);

  const removeSessionTrust = useCallback((actionType) => {
    setSessionTrusts((prev) => {
      const newMap = new Map(prev);
      newMap.delete(actionType);
      return newMap;
    });
  }, []);

  const clearSessionTrusts = useCallback(() => {
    setSessionTrusts(new Map());
  }, []);

  // ==========================================================================
  // CONNECTION MANAGEMENT
  // ==========================================================================

  const connect = useCallback(async () => {
    if (!wsRef.current) return;

    setConnectionStatus('connecting');
    setConnectionError(null);

    try {
      await wsRef.current.connect();
    } catch (err) {
      setConnectionStatus('disconnected');
      setConnectionError(err.message || 'Failed to connect');
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
    }
    setConnectionStatus('disconnected');
    currentExecutionIdRef.current = null;
  }, []);

  const subscribeToExecution = useCallback(async (executionId) => {
    if (!wsRef.current) return;

    // Connect if not already connected
    if (connectionStatus !== 'connected') {
      await connect();
    }

    currentExecutionIdRef.current = executionId;
    wsRef.current.subscribe(executionId);
    setExecutionState((prev) => ({ ...prev, status: 'connecting' }));
  }, [connectionStatus, connect]);

  const unsubscribeFromExecution = useCallback(() => {
    if (wsRef.current && currentExecutionIdRef.current) {
      wsRef.current.unsubscribe(currentExecutionIdRef.current);
    }
    currentExecutionIdRef.current = null;
    setExecutionState(DEFAULT_EXECUTION_STATE);
  }, []);

  // ==========================================================================
  // ACTION HANDLERS
  // ==========================================================================

  const approveAction = useCallback(async (actionId, options = {}) => {
    const executionId = executionState.execution?.execution_id;
    if (!executionId || !actionId) return;

    setLoading((prev) => ({ ...prev, approve: true }));
    setError(null);

    try {
      // Add session trust if requested
      if (options.trustScope === TrustScope.THIS_ACTION_TYPE || options.trustScope === TrustScope.THIS_SESSION) {
        const action = executionState.actions.find(a => a.action_id === actionId);
        if (action) {
          addSessionTrust(action.type, options.trustScope);
        }
      }

      if (wsRef.current) {
        wsRef.current.sendApprove(executionId, actionId, options);
      } else {
        await apiApproveAction(executionId, actionId, options);
      }
    } catch (err) {
      setError(`Failed to approve action: ${err.message}`);
    } finally {
      setLoading((prev) => ({ ...prev, approve: false }));
    }
  }, [executionState.execution, executionState.actions, addSessionTrust]);

  const denyAction = useCallback(async (actionId, reason = '') => {
    const executionId = executionState.execution?.execution_id;
    if (!executionId || !actionId) return;

    setLoading((prev) => ({ ...prev, deny: true }));
    setError(null);

    try {
      if (wsRef.current) {
        wsRef.current.sendDeny(executionId, actionId, reason);
      } else {
        await apiDenyAction(executionId, actionId, reason);
      }
    } catch (err) {
      setError(`Failed to deny action: ${err.message}`);
    } finally {
      setLoading((prev) => ({ ...prev, deny: false }));
    }
  }, [executionState.execution]);

  const modifyAction = useCallback(async (actionId, modifiedParameters, trustScope = TrustScope.THIS_ACTION) => {
    const executionId = executionState.execution?.execution_id;
    if (!executionId || !actionId) return;

    setLoading((prev) => ({ ...prev, modify: true }));
    setError(null);

    try {
      if (wsRef.current) {
        wsRef.current.sendModify(executionId, actionId, modifiedParameters, trustScope);
      } else {
        await apiModifyAction(executionId, actionId, modifiedParameters, trustScope);
      }
    } catch (err) {
      setError(`Failed to modify action: ${err.message}`);
    } finally {
      setLoading((prev) => ({ ...prev, modify: false }));
    }
  }, [executionState.execution]);

  const abortExecution = useCallback(async (reason = '') => {
    const executionId = executionState.execution?.execution_id;
    if (!executionId) return;

    setLoading((prev) => ({ ...prev, abort: true }));
    setError(null);

    try {
      if (wsRef.current) {
        wsRef.current.sendAbort(executionId, reason);
      } else {
        await apiAbortExecution(executionId, reason);
      }
    } catch (err) {
      setError(`Failed to abort execution: ${err.message}`);
    } finally {
      setLoading((prev) => ({ ...prev, abort: false }));
    }
  }, [executionState.execution]);

  const openModifyModal = useCallback((action) => {
    setModifyingAction(action);
    setModifyModalOpen(true);
  }, []);

  const closeModifyModal = useCallback(() => {
    setModifyModalOpen(false);
    setModifyingAction(null);
  }, []);

  // ==========================================================================
  // KEYBOARD SHORTCUTS
  // ==========================================================================

  useEffect(() => {
    const handleKeyDown = (event) => {
      // Only handle shortcuts when there's a current action awaiting approval
      if (!executionState.currentAction || executionState.currentAction.status !== ActionStatus.AWAITING_APPROVAL) {
        return;
      }

      // Don't handle if user is typing in an input
      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.isContentEditable) {
        return;
      }

      const actionId = executionState.currentAction.action_id;

      switch (event.key.toLowerCase()) {
        case 'a':
          event.preventDefault();
          approveAction(actionId);
          break;
        case 'd':
          event.preventDefault();
          denyAction(actionId);
          break;
        case 'm':
          event.preventDefault();
          openModifyModal(executionState.currentAction);
          break;
        case 'escape':
          if (modifyModalOpen) {
            event.preventDefault();
            closeModifyModal();
          } else {
            event.preventDefault();
            // Show abort confirmation
          }
          break;
        case 't':
          event.preventDefault();
          // Trust this action type for session
          approveAction(actionId, { trustScope: TrustScope.THIS_ACTION_TYPE });
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [executionState.currentAction, modifyModalOpen, approveAction, denyAction, openModifyModal, closeModifyModal]);

  // ==========================================================================
  // COMPUTED VALUES
  // ==========================================================================

  const completedActions = useMemo(() => {
    return executionState.actions.filter((a) =>
      [ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.DENIED, ActionStatus.TIMED_OUT].includes(a.status)
    );
  }, [executionState.actions]);

  const pendingActions = useMemo(() => {
    return executionState.actions.filter((a) =>
      [ActionStatus.PENDING, ActionStatus.AWAITING_APPROVAL].includes(a.status)
    );
  }, [executionState.actions]);

  const executingActions = useMemo(() => {
    return executionState.actions.filter((a) =>
      [ActionStatus.EXECUTING, ActionStatus.APPROVED, ActionStatus.MODIFIED].includes(a.status)
    );
  }, [executionState.actions]);

  const progress = useMemo(() => {
    const total = executionState.actions.length;
    if (total === 0) return 0;
    return Math.round((completedActions.length / total) * 100);
  }, [executionState.actions, completedActions]);

  const hasCurrentAction = useMemo(() => {
    return executionState.currentAction && executionState.currentAction.status === ActionStatus.AWAITING_APPROVAL;
  }, [executionState.currentAction]);

  // ==========================================================================
  // CONTEXT VALUE
  // ==========================================================================

  const value = useMemo(() => ({
    // Execution state
    execution: executionState.execution,
    actions: executionState.actions,
    currentAction: executionState.currentAction,
    thinking: executionState.thinking,
    logs: executionState.logs,
    executionStatus: executionState.status,

    // Computed values
    completedActions,
    pendingActions,
    executingActions,
    progress,
    hasCurrentAction,

    // Connection state
    connectionStatus,
    connectionError,

    // Trust settings
    trustSettings,
    sessionTrusts,

    // UI state
    modifyModalOpen,
    modifyingAction,
    trustPanelOpen,

    // Loading states
    loading,

    // Error state
    error,

    // Connection actions
    connect,
    disconnect,
    subscribeToExecution,
    unsubscribeFromExecution,

    // Action handlers
    approveAction,
    denyAction,
    modifyAction,
    abortExecution,

    // Modal handlers
    openModifyModal,
    closeModifyModal,
    setTrustPanelOpen,

    // Trust actions
    loadTrustSettings,
    saveTrustSettings,
    addSessionTrust,
    removeSessionTrust,
    clearSessionTrusts,

    // Error handling
    setError,
    clearError: () => setError(null),

    // Configuration
    RISK_LEVEL_CONFIG,
    ACTION_TYPE_CONFIG,
    ActionStatus,
    RiskLevel,
    TrustScope,
  }), [
    executionState,
    completedActions,
    pendingActions,
    executingActions,
    progress,
    hasCurrentAction,
    connectionStatus,
    connectionError,
    trustSettings,
    sessionTrusts,
    modifyModalOpen,
    modifyingAction,
    trustPanelOpen,
    loading,
    error,
    connect,
    disconnect,
    subscribeToExecution,
    unsubscribeFromExecution,
    approveAction,
    denyAction,
    modifyAction,
    abortExecution,
    openModifyModal,
    closeModifyModal,
    loadTrustSettings,
    saveTrustSettings,
    addSessionTrust,
    removeSessionTrust,
    clearSessionTrusts,
  ]);

  return (
    <ExecutionContext.Provider value={value}>
      {children}
    </ExecutionContext.Provider>
  );
}

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Hook to access execution context
 */
export function useExecution() {
  const context = useContext(ExecutionContext);
  if (!context) {
    throw new Error('useExecution must be used within an ExecutionProvider');
  }
  return context;
}

/**
 * Hook to get current action with approval controls
 */
export function useCurrentAction() {
  const {
    currentAction,
    hasCurrentAction,
    approveAction,
    denyAction,
    openModifyModal,
    loading,
  } = useExecution();

  return {
    action: currentAction,
    hasAction: hasCurrentAction,
    approve: useCallback((options) => approveAction(currentAction?.action_id, options), [currentAction, approveAction]),
    deny: useCallback((reason) => denyAction(currentAction?.action_id, reason), [currentAction, denyAction]),
    modify: useCallback(() => openModifyModal(currentAction), [currentAction, openModifyModal]),
    isApproving: loading.approve,
    isDenying: loading.deny,
  };
}

/**
 * Hook to get execution timeline data
 */
export function useExecutionTimeline() {
  const { actions, completedActions, pendingActions, executingActions, progress } = useExecution();

  return {
    actions,
    completedActions,
    pendingActions,
    executingActions,
    progress,
    total: actions.length,
    completed: completedActions.length,
    pending: pendingActions.length,
    executing: executingActions.length,
  };
}

/**
 * Hook to get trust settings and controls
 */
export function useTrustSettings() {
  const {
    trustSettings,
    sessionTrusts,
    loadTrustSettings,
    saveTrustSettings,
    addSessionTrust,
    removeSessionTrust,
    clearSessionTrusts,
    loading,
    trustPanelOpen,
    setTrustPanelOpen,
  } = useExecution();

  return {
    settings: trustSettings,
    sessionTrusts,
    load: loadTrustSettings,
    save: saveTrustSettings,
    addSessionTrust,
    removeSessionTrust,
    clearSessionTrusts,
    isLoading: loading.trustSettings,
    isPanelOpen: trustPanelOpen,
    setPanelOpen: setTrustPanelOpen,
  };
}

export default ExecutionContext;

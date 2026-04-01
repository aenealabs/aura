/**
 * Project Aura - Real-Time Execution API Service
 *
 * Provides WebSocket connection management and REST API endpoints
 * for real-time agent action streaming and intervention.
 *
 * Implements the API contract for Claude Code-style tool approval workflow.
 *
 * @see ADR-032 Configurable Autonomy Framework
 */

// =============================================================================
// CONSTANTS & CONFIGURATION
// =============================================================================

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8080';

/**
 * Action statuses in execution lifecycle
 */
export const ActionStatus = {
  PENDING: 'pending',
  AWAITING_APPROVAL: 'awaiting_approval',
  APPROVED: 'approved',
  DENIED: 'denied',
  MODIFIED: 'modified',
  EXECUTING: 'executing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  TIMED_OUT: 'timed_out',
};

/**
 * Risk levels for actions
 */
export const RiskLevel = {
  SAFE: 'safe',
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
};

/**
 * Action types that agents can perform
 */
export const ActionType = {
  FILE_READ: 'file_read',
  FILE_WRITE: 'file_write',
  FILE_CREATE: 'file_create',
  FILE_DELETE: 'file_delete',
  COMMAND_EXECUTE: 'command_execute',
  API_CALL: 'api_call',
  DATABASE_QUERY: 'database_query',
  DATABASE_WRITE: 'database_write',
  NETWORK_REQUEST: 'network_request',
  DEPLOYMENT: 'deployment',
  CONFIGURATION_CHANGE: 'configuration_change',
  SECRET_ACCESS: 'secret_access',
};

/**
 * WebSocket message types
 */
export const WSMessageType = {
  // Client -> Server
  SUBSCRIBE: 'subscribe',
  UNSUBSCRIBE: 'unsubscribe',
  APPROVE_ACTION: 'approve_action',
  DENY_ACTION: 'deny_action',
  MODIFY_ACTION: 'modify_action',
  ABORT_EXECUTION: 'abort_execution',
  UPDATE_TRUST: 'update_trust',

  // Server -> Client
  EXECUTION_STARTED: 'execution_started',
  ACTION_PENDING: 'action_pending',
  ACTION_AWAITING_APPROVAL: 'action_awaiting_approval',
  ACTION_APPROVED: 'action_approved',
  ACTION_DENIED: 'action_denied',
  ACTION_MODIFIED: 'action_modified',
  ACTION_EXECUTING: 'action_executing',
  ACTION_COMPLETED: 'action_completed',
  ACTION_FAILED: 'action_failed',
  ACTION_TIMED_OUT: 'action_timed_out',
  EXECUTION_COMPLETED: 'execution_completed',
  EXECUTION_ABORTED: 'execution_aborted',
  EXECUTION_FAILED: 'execution_failed',
  THINKING_UPDATE: 'thinking_update',
  LOG_ENTRY: 'log_entry',
  ERROR: 'error',
  HEARTBEAT: 'heartbeat',
};

/**
 * Trust scope options
 */
export const TrustScope = {
  THIS_ACTION: 'this_action',         // Trust only this specific action
  THIS_ACTION_TYPE: 'this_action_type', // Trust all actions of this type in session
  THIS_SESSION: 'this_session',       // Trust all similar actions in current session
  PERMANENT: 'permanent',             // Trust permanently (stored in policy)
};

/**
 * Risk level configuration with UI metadata
 */
export const RISK_LEVEL_CONFIG = {
  [RiskLevel.SAFE]: {
    label: 'Safe',
    color: 'olive',
    description: 'Read-only operation with no side effects',
    badgeClass: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    borderClass: 'border-olive-300 dark:border-olive-700',
    bgClass: 'bg-olive-50 dark:bg-olive-900/10',
  },
  [RiskLevel.LOW]: {
    label: 'Low Risk',
    color: 'aura',
    description: 'Minimal impact, easily reversible',
    badgeClass: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    borderClass: 'border-aura-300 dark:border-aura-700',
    bgClass: 'bg-aura-50 dark:bg-aura-900/10',
  },
  [RiskLevel.MEDIUM]: {
    label: 'Medium Risk',
    color: 'warning',
    description: 'May affect system state, review recommended',
    badgeClass: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    borderClass: 'border-warning-300 dark:border-warning-700',
    bgClass: 'bg-warning-50 dark:bg-warning-900/10',
  },
  [RiskLevel.HIGH]: {
    label: 'High Risk',
    color: 'orange',
    description: 'Significant impact, careful review required',
    badgeClass: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    borderClass: 'border-orange-300 dark:border-orange-700',
    bgClass: 'bg-orange-50 dark:bg-orange-900/10',
  },
  [RiskLevel.CRITICAL]: {
    label: 'Critical',
    color: 'critical',
    description: 'Production impact, mandatory human approval',
    badgeClass: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    borderClass: 'border-critical-300 dark:border-critical-700',
    bgClass: 'bg-critical-50 dark:bg-critical-900/10',
  },
};

/**
 * Action type configuration with UI metadata
 */
export const ACTION_TYPE_CONFIG = {
  [ActionType.FILE_READ]: {
    label: 'Read File',
    icon: 'DocumentTextIcon',
    defaultRisk: RiskLevel.SAFE,
  },
  [ActionType.FILE_WRITE]: {
    label: 'Write File',
    icon: 'PencilSquareIcon',
    defaultRisk: RiskLevel.MEDIUM,
  },
  [ActionType.FILE_CREATE]: {
    label: 'Create File',
    icon: 'DocumentPlusIcon',
    defaultRisk: RiskLevel.LOW,
  },
  [ActionType.FILE_DELETE]: {
    label: 'Delete File',
    icon: 'TrashIcon',
    defaultRisk: RiskLevel.HIGH,
  },
  [ActionType.COMMAND_EXECUTE]: {
    label: 'Execute Command',
    icon: 'CommandLineIcon',
    defaultRisk: RiskLevel.MEDIUM,
  },
  [ActionType.API_CALL]: {
    label: 'API Call',
    icon: 'ServerStackIcon',
    defaultRisk: RiskLevel.LOW,
  },
  [ActionType.DATABASE_QUERY]: {
    label: 'Database Query',
    icon: 'CircleStackIcon',
    defaultRisk: RiskLevel.SAFE,
  },
  [ActionType.DATABASE_WRITE]: {
    label: 'Database Write',
    icon: 'CircleStackIcon',
    defaultRisk: RiskLevel.HIGH,
  },
  [ActionType.NETWORK_REQUEST]: {
    label: 'Network Request',
    icon: 'GlobeAltIcon',
    defaultRisk: RiskLevel.MEDIUM,
  },
  [ActionType.DEPLOYMENT]: {
    label: 'Deployment',
    icon: 'CloudArrowUpIcon',
    defaultRisk: RiskLevel.CRITICAL,
  },
  [ActionType.CONFIGURATION_CHANGE]: {
    label: 'Configuration Change',
    icon: 'CogIcon',
    defaultRisk: RiskLevel.HIGH,
  },
  [ActionType.SECRET_ACCESS]: {
    label: 'Secret Access',
    icon: 'KeyIcon',
    defaultRisk: RiskLevel.HIGH,
  },
};

// =============================================================================
// REST API ENDPOINTS
// =============================================================================

/**
 * Approve an action
 */
export async function approveAction(executionId, actionId, options = {}) {
  const response = await fetch(`${API_BASE}/execution/${executionId}/actions/${actionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      trust_scope: options.trustScope || TrustScope.THIS_ACTION,
      modified_parameters: options.modifiedParameters || null,
      comment: options.comment || null,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to approve action: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Deny an action
 */
export async function denyAction(executionId, actionId, reason = '') {
  const response = await fetch(`${API_BASE}/execution/${executionId}/actions/${actionId}/deny`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });

  if (!response.ok) {
    throw new Error(`Failed to deny action: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Modify and approve an action
 */
export async function modifyAction(executionId, actionId, modifiedParameters, trustScope = TrustScope.THIS_ACTION) {
  const response = await fetch(`${API_BASE}/execution/${executionId}/actions/${actionId}/modify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      modified_parameters: modifiedParameters,
      trust_scope: trustScope,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to modify action: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Abort entire execution
 */
export async function abortExecution(executionId, reason = '') {
  const response = await fetch(`${API_BASE}/execution/${executionId}/abort`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });

  if (!response.ok) {
    throw new Error(`Failed to abort execution: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get execution details
 */
export async function getExecution(executionId) {
  const response = await fetch(`${API_BASE}/execution/${executionId}`);

  if (!response.ok) {
    throw new Error(`Failed to get execution: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get execution history for an agent session
 */
export async function getExecutionHistory(sessionId, options = {}) {
  const params = new URLSearchParams({
    limit: options.limit || 50,
    offset: options.offset || 0,
    ...(options.status && { status: options.status }),
  });

  const response = await fetch(`${API_BASE}/sessions/${sessionId}/executions?${params}`);

  if (!response.ok) {
    throw new Error(`Failed to get execution history: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get trust settings
 */
export async function getTrustSettings(organizationId) {
  const response = await fetch(`${API_BASE}/organizations/${organizationId}/trust-settings`);

  if (!response.ok) {
    throw new Error(`Failed to get trust settings: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update trust settings
 */
export async function updateTrustSettings(organizationId, settings) {
  const response = await fetch(`${API_BASE}/organizations/${organizationId}/trust-settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    throw new Error(`Failed to update trust settings: ${response.statusText}`);
  }

  return response.json();
}

// =============================================================================
// WEBSOCKET CONNECTION CLASS
// =============================================================================

/**
 * WebSocket connection manager for real-time execution streaming
 */
export class ExecutionWebSocket {
  constructor(options = {}) {
    this.url = options.url || `${WS_BASE}/ws/execution`;
    this.token = options.token || null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
    this.reconnectDelay = options.reconnectDelay || 1000;
    this.heartbeatInterval = options.heartbeatInterval || 30000;
    this.socket = null;
    this.heartbeatTimer = null;
    this.reconnectTimer = null;
    this.subscriptions = new Set();
    this.listeners = new Map();
    this.isConnecting = false;
    this.isConnected = false;
  }

  /**
   * Connect to WebSocket server
   */
  connect() {
    if (this.isConnecting || this.isConnected) {
      return Promise.resolve();
    }

    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      try {
        const url = this.token ? `${this.url}?token=${this.token}` : this.url;
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
          this.isConnecting = false;
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.startHeartbeat();

          // Re-subscribe to any active subscriptions
          this.subscriptions.forEach((executionId) => {
            this.send({
              type: WSMessageType.SUBSCRIBE,
              execution_id: executionId,
            });
          });

          this.emit('connected');
          resolve();
        };

        this.socket.onclose = (event) => {
          this.isConnecting = false;
          this.isConnected = false;
          this.stopHeartbeat();

          this.emit('disconnected', { code: event.code, reason: event.reason });

          // Attempt reconnection if not intentionally closed
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          }
        };

        this.socket.onerror = (error) => {
          this.emit('error', error);
          if (this.isConnecting) {
            reject(error);
          }
        };

        this.socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect() {
    this.stopHeartbeat();
    clearTimeout(this.reconnectTimer);
    this.subscriptions.clear();

    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }

    this.isConnected = false;
    this.isConnecting = false;
  }

  /**
   * Subscribe to an execution's real-time updates
   */
  subscribe(executionId) {
    this.subscriptions.add(executionId);

    if (this.isConnected) {
      this.send({
        type: WSMessageType.SUBSCRIBE,
        execution_id: executionId,
      });
    }
  }

  /**
   * Unsubscribe from an execution's updates
   */
  unsubscribe(executionId) {
    this.subscriptions.delete(executionId);

    if (this.isConnected) {
      this.send({
        type: WSMessageType.UNSUBSCRIBE,
        execution_id: executionId,
      });
    }
  }

  /**
   * Send approve action message
   */
  sendApprove(executionId, actionId, options = {}) {
    this.send({
      type: WSMessageType.APPROVE_ACTION,
      execution_id: executionId,
      action_id: actionId,
      trust_scope: options.trustScope || TrustScope.THIS_ACTION,
      modified_parameters: options.modifiedParameters || null,
    });
  }

  /**
   * Send deny action message
   */
  sendDeny(executionId, actionId, reason = '') {
    this.send({
      type: WSMessageType.DENY_ACTION,
      execution_id: executionId,
      action_id: actionId,
      reason,
    });
  }

  /**
   * Send modify action message
   */
  sendModify(executionId, actionId, modifiedParameters, trustScope = TrustScope.THIS_ACTION) {
    this.send({
      type: WSMessageType.MODIFY_ACTION,
      execution_id: executionId,
      action_id: actionId,
      modified_parameters: modifiedParameters,
      trust_scope: trustScope,
    });
  }

  /**
   * Send abort execution message
   */
  sendAbort(executionId, reason = '') {
    this.send({
      type: WSMessageType.ABORT_EXECUTION,
      execution_id: executionId,
      reason,
    });
  }

  /**
   * Send message through WebSocket
   */
  send(message) {
    if (!this.isConnected || !this.socket) {
      console.warn('WebSocket not connected, message not sent:', message);
      return false;
    }

    try {
      this.socket.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  /**
   * Add event listener
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  /**
   * Remove event listener
   */
  off(event, callback) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  /**
   * Emit event to listeners
   */
  emit(event, data) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in ${event} listener:`, error);
        }
      });
    }
  }

  /**
   * Handle incoming WebSocket message
   */
  handleMessage(message) {
    const { type, ...data } = message;

    // Handle heartbeat separately
    if (type === WSMessageType.HEARTBEAT) {
      return;
    }

    // Emit typed event
    this.emit(type, data);

    // Emit generic message event
    this.emit('message', message);
  }

  /**
   * Start heartbeat timer
   */
  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: WSMessageType.HEARTBEAT });
    }, this.heartbeatInterval);
  }

  /**
   * Stop heartbeat timer
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Schedule reconnection attempt
   */
  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    this.emit('reconnecting', {
      attempt: this.reconnectAttempts,
      maxAttempts: this.maxReconnectAttempts,
      delay,
    });

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch((error) => {
        console.error('Reconnection failed:', error);
      });
    }, delay);
  }
}

// =============================================================================
// MOCK DATA FOR DEVELOPMENT
// =============================================================================

export const MOCK_EXECUTION = {
  execution_id: 'exec-7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d',
  session_id: 'session-4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a',
  request_id: 'req-a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
  correlation_id: 'corr-9f8e7d6c-5b4a-3c2d-1e0f-a9b8c7d6e5f4',
  organization_id: 'org-acme-corp-7x2',
  organization_name: 'Acme Corporation',
  team_id: 'team-security-eng',
  team_name: 'Security Engineering',
  project_id: 'proj-payment-svc-4a5',
  project_name: 'Payment Service Security Hardening',
  repository_id: 'repo-payment-svc-2b3',
  repository_name: 'payment-service',
  repository_url: 'https://github.com/acme-corp/payment-service',
  branch: 'fix/sqli-user-controller',
  commit_sha: 'a8f3e2d1c4b5a6e7f8d9c0b1a2e3f4d5c6b7a8e9',
  initiated_by: {
    user_id: 'usr-j3l8m1p4',
    email: 'david.kumar@acme-corp.com',
    name: 'David Kumar',
    role: 'Security Engineer',
  },
  agent_id: 'coder-agent-alpha',
  agent_name: 'Coder Agent Alpha',
  agent_version: '2.4.1',
  task: 'Fix SQL injection vulnerability in UserController.java',
  task_type: 'vulnerability_remediation',
  vulnerability_id: 'CVE-2026-1234',
  vulnerability_severity: 'HIGH',
  status: 'in_progress',
  priority: 'high',
  started_at: new Date(Date.now() - 120000).toISOString(),
  estimated_completion: new Date(Date.now() + 180000).toISOString(),
  current_action_index: 2,
  total_actions: 5,
  cost_estimate_usd: 0.045,
  tokens_used: { input: 12450, output: 3280, total: 15730 },
  model_id: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
  sandbox_environment: 'sandbox-sec-exec-01',
  tags: ['security', 'sql-injection', 'java', 'payment-service', 'high-priority'],
  compliance_requirements: ['SOC2-CC6.1', 'PCI-DSS-6.5.1', 'NIST-SI-10'],
  actions: [
    {
      action_id: 'action-a1b2c3d4-001',
      sequence_number: 1,
      type: ActionType.FILE_READ,
      target: 'src/controllers/UserController.java',
      description: 'Read current implementation to understand context',
      parameters: { path: 'src/controllers/UserController.java' },
      risk_level: RiskLevel.SAFE,
      risk_score: 0.05,
      status: ActionStatus.COMPLETED,
      started_at: new Date(Date.now() - 100000).toISOString(),
      completed_at: new Date(Date.now() - 95000).toISOString(),
      duration_ms: 5000,
      result: { lines_read: 245, file_size_bytes: 8420 },
      tokens_used: { input: 2100, output: 50, total: 2150 },
      approved_by: null,
      approval_type: 'auto_approved',
    },
    {
      action_id: 'action-a1b2c3d4-002',
      sequence_number: 2,
      type: ActionType.FILE_WRITE,
      target: 'src/controllers/UserController.java',
      description: 'Replace string concatenation with PreparedStatement',
      parameters: {
        path: 'src/controllers/UserController.java',
        changes: {
          additions: 8,
          deletions: 4,
          net_change: 4,
        },
      },
      risk_level: RiskLevel.MEDIUM,
      risk_score: 0.45,
      status: ActionStatus.COMPLETED,
      started_at: new Date(Date.now() - 90000).toISOString(),
      completed_at: new Date(Date.now() - 85000).toISOString(),
      duration_ms: 5000,
      approved_by: { user_id: 'usr-j3l8m1p4', email: 'david.kumar@acme-corp.com', name: 'David Kumar' },
      approved_at: new Date(Date.now() - 91000).toISOString(),
      approval_type: 'human_approved',
      approval_comment: 'Reviewed fix - PreparedStatement approach is correct',
      tokens_used: { input: 3200, output: 850, total: 4050 },
      diff: `@@ -45,10 +45,16 @@ public class UserController {
     public User getUserById(String userId) {
-        String query = "SELECT * FROM users WHERE id = '" + userId + "'";
-        return db.executeQuery(query);
+        // Use parameterized query to prevent SQL injection
+        String query = "SELECT * FROM users WHERE id = ?";
+        PreparedStatement stmt = db.prepareStatement(query);
+        stmt.setString(1, userId);
+        return db.executeQuery(stmt);
     }`,
    },
    {
      action_id: 'action-a1b2c3d4-003',
      sequence_number: 3,
      type: ActionType.FILE_WRITE,
      target: 'src/tests/UserControllerTest.java',
      description: 'Add test case for SQL injection prevention',
      parameters: {
        path: 'src/tests/UserControllerTest.java',
        changes: {
          additions: 15,
          deletions: 0,
          net_change: 15,
        },
      },
      risk_level: RiskLevel.LOW,
      risk_score: 0.15,
      status: ActionStatus.AWAITING_APPROVAL,
      timeout_at: new Date(Date.now() + 300000).toISOString(),
      timeout_seconds: 300,
      reviewers_notified: ['david.kumar@acme-corp.com', 'sarah.chen@acme-corp.com'],
      tokens_used: { input: 2800, output: 720, total: 3520 },
      diff: `@@ -100,6 +100,21 @@ public class UserControllerTest {
+    @Test
+    public void testSqlInjectionPrevention() {
+        // Attempt SQL injection
+        String maliciousInput = "'; DROP TABLE users; --";
+        User result = controller.getUserById(maliciousInput);
+
+        // Should return null, not execute injection
+        assertNull(result);
+
+        // Verify table still exists
+        assertTrue(userTableExists());
+    }`,
    },
    {
      action_id: 'action-a1b2c3d4-004',
      sequence_number: 4,
      type: ActionType.COMMAND_EXECUTE,
      target: 'mvn test -Dtest=UserControllerTest',
      description: 'Run unit tests to verify fix',
      parameters: {
        command: 'mvn test -Dtest=UserControllerTest',
        working_directory: '/project',
        timeout: 120000,
        environment: 'sandbox-sec-exec-01',
      },
      risk_level: RiskLevel.LOW,
      risk_score: 0.20,
      status: ActionStatus.PENDING,
      estimated_duration_ms: 45000,
    },
    {
      action_id: 'action-a1b2c3d4-005',
      sequence_number: 5,
      type: ActionType.DEPLOYMENT,
      target: 'development',
      description: 'Deploy fix to development environment',
      parameters: {
        environment: 'development',
        version: 'fix-sqli-usercontroller-001',
        rollback_version: '1.2.3',
        health_check_endpoint: '/health',
      },
      risk_level: RiskLevel.HIGH,
      risk_score: 0.75,
      status: ActionStatus.PENDING,
      requires_approval: true,
      required_approvers: 2,
      estimated_duration_ms: 120000,
    },
  ],
  thinking: [
    {
      id: 'thought-001',
      type: 'analysis',
      content: 'Analyzing the vulnerability report and identifying affected code locations...',
      timestamp: new Date(Date.now() - 110000).toISOString(),
      confidence: 0.92,
      tokens_used: 450,
    },
    {
      id: 'thought-002',
      type: 'planning',
      content: 'The SQL injection occurs in getUserById() method where user input is directly concatenated into the SQL query. I need to replace string concatenation with parameterized queries.',
      timestamp: new Date(Date.now() - 100000).toISOString(),
      confidence: 0.95,
      tokens_used: 380,
      related_cve: 'CVE-2026-1234',
    },
    {
      id: 'thought-003',
      type: 'decision',
      content: 'I will use PreparedStatement with parameterized queries to prevent SQL injection. This is the industry-standard approach and maintains database compatibility.',
      timestamp: new Date(Date.now() - 90000).toISOString(),
      confidence: 0.98,
      tokens_used: 290,
      references: ['OWASP SQL Injection Prevention Cheat Sheet', 'Java PreparedStatement Documentation'],
    },
  ],
  logs: [
    { timestamp: new Date(Date.now() - 100000).toISOString(), level: 'info', message: 'Starting vulnerability analysis...', source: 'coder-agent', span_id: 'span-001' },
    { timestamp: new Date(Date.now() - 95000).toISOString(), level: 'info', message: 'Loaded context from GraphRAG: 12 relevant code entities', source: 'context-retrieval', span_id: 'span-002' },
    { timestamp: new Date(Date.now() - 90000).toISOString(), level: 'info', message: 'Identified 2 vulnerable code locations', source: 'vulnerability-scanner', span_id: 'span-003' },
    { timestamp: new Date(Date.now() - 85000).toISOString(), level: 'warning', message: 'High-risk SQL injection pattern detected in getUserById()', source: 'security-analyzer', span_id: 'span-004' },
    { timestamp: new Date(Date.now() - 80000).toISOString(), level: 'info', message: 'Generating fix using parameterized query pattern', source: 'coder-agent', span_id: 'span-005' },
    { timestamp: new Date(Date.now() - 75000).toISOString(), level: 'success', message: 'Fix applied to UserController.java', source: 'file-writer', span_id: 'span-006' },
    { timestamp: new Date(Date.now() - 70000).toISOString(), level: 'info', message: 'Preparing test case for SQL injection prevention...', source: 'test-generator', span_id: 'span-007' },
  ],
  metrics: {
    total_duration_ms: 50000,
    graph_queries: 8,
    llm_calls: 12,
    files_analyzed: 24,
    files_modified: 2,
    tests_generated: 1,
    cost_breakdown: { llm: 0.038, compute: 0.005, storage: 0.002 },
  },
};

export const MOCK_TRUST_SETTINGS = {
  settings_id: 'trust-set-7a8b9c0d',
  organization_id: 'org-acme-corp-7x2',
  organization_name: 'Acme Corporation',
  created_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
  updated_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  updated_by: {
    user_id: 'usr-m3k8n2p5',
    email: 'marcus.johnson@acme-corp.com',
    name: 'Marcus Johnson',
    role: 'Security Administrator',
  },
  version: 12,
  policy_preset: 'enterprise_secure',
  autonomy_level: 'critical_hitl',
  default_auto_approve: [
    ActionType.FILE_READ,
  ],
  auto_approve_conditions: {
    [ActionType.FILE_READ]: { max_file_size_mb: 10, excluded_paths: ['/secrets/', '/.env'] },
    [ActionType.DATABASE_QUERY]: { read_only: true, max_rows: 1000 },
  },
  always_require_approval: [
    ActionType.FILE_DELETE,
    ActionType.DATABASE_WRITE,
    ActionType.DEPLOYMENT,
    ActionType.CONFIGURATION_CHANGE,
    ActionType.SECRET_ACCESS,
  ],
  approval_requirements: {
    [ActionType.DEPLOYMENT]: { min_approvers: 2, required_roles: ['senior_engineer', 'team_lead'] },
    [ActionType.SECRET_ACCESS]: { min_approvers: 1, required_roles: ['security_admin'], mfa_required: true },
    [ActionType.DATABASE_WRITE]: { min_approvers: 1, required_roles: ['data_engineer', 'dba'] },
  },
  session_trusts: [
    {
      trust_id: 'trust-sess-a1b2c3d4',
      action_type: ActionType.FILE_READ,
      scope: TrustScope.THIS_SESSION,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      created_by: { user_id: 'usr-j3l8m1p4', email: 'david.kumar@acme-corp.com', name: 'David Kumar' },
      session_id: 'session-4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a',
      expires_at: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
    },
    {
      trust_id: 'trust-sess-b2c3d4e5',
      action_type: ActionType.FILE_WRITE,
      scope: TrustScope.THIS_ACTION_TYPE,
      created_at: new Date(Date.now() - 1800000).toISOString(),
      created_by: { user_id: 'usr-j3l8m1p4', email: 'david.kumar@acme-corp.com', name: 'David Kumar' },
      session_id: 'session-4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a',
      expires_at: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
      conditions: { paths: ['src/controllers/**', 'src/tests/**'] },
    },
  ],
  approval_timeout_seconds: 300,
  auto_deny_on_timeout: false,
  escalation_on_timeout: true,
  escalation_contacts: [
    { user_id: 'usr-m3k8n2p5', email: 'marcus.johnson@acme-corp.com', name: 'Marcus Johnson', method: 'slack' },
    { user_id: 'usr-k4m9n2p5', email: 'sarah.chen@acme-corp.com', name: 'Sarah Chen', method: 'email' },
  ],
  notification_settings: {
    slack_channel: '#aura-approvals',
    slack_mention_on_critical: true,
    email_digest_frequency: 'realtime',
    pagerduty_integration: true,
  },
  risk_thresholds: {
    auto_approve_max_risk_score: 0.20,
    require_senior_review_min_score: 0.70,
    require_multiple_approvers_min_score: 0.85,
  },
  audit_settings: {
    log_all_actions: true,
    log_retention_days: 365,
    compliance_frameworks: ['SOC2', 'NIST-800-53', 'PCI-DSS'],
    export_to_siem: true,
    siem_endpoint: 'https://siem.acme-corp.com/api/v1/events',
  },
  statistics_24h: {
    total_actions: 847,
    auto_approved: 623,
    human_approved: 198,
    denied: 14,
    timed_out: 12,
    approval_rate_percent: 97.1,
    avg_approval_time_seconds: 42,
  },
};

// =============================================================================
// MOCK API FUNCTIONS FOR DEVELOPMENT
// =============================================================================

/**
 * Simulate WebSocket events for development
 */
export function createMockWebSocket(_options = {}) {
  const listeners = new Map();
  let isConnected = false;
  let currentExecution = { ...MOCK_EXECUTION };

  const mockWs = {
    connect: () => {
      return new Promise((resolve) => {
        setTimeout(() => {
          isConnected = true;
          mockWs.emit('connected');
          resolve();
        }, 500);
      });
    },
    disconnect: () => {
      isConnected = false;
      mockWs.emit('disconnected', { code: 1000, reason: 'Client disconnect' });
    },
    subscribe: (executionId) => {
      if (isConnected) {
        setTimeout(() => {
          mockWs.emit(WSMessageType.EXECUTION_STARTED, {
            execution_id: executionId,
            execution: currentExecution,
          });
        }, 100);
      }
    },
    unsubscribe: () => {},
    sendApprove: (executionId, actionId, options) => {
      if (isConnected) {
        setTimeout(() => {
          // Find and update the action
          const actionIndex = currentExecution.actions.findIndex(a => a.action_id === actionId);
          if (actionIndex !== -1) {
            currentExecution.actions[actionIndex].status = ActionStatus.APPROVED;
            mockWs.emit(WSMessageType.ACTION_APPROVED, {
              execution_id: executionId,
              action_id: actionId,
              trust_scope: options?.trustScope || TrustScope.THIS_ACTION,
            });

            // Simulate execution
            setTimeout(() => {
              currentExecution.actions[actionIndex].status = ActionStatus.EXECUTING;
              mockWs.emit(WSMessageType.ACTION_EXECUTING, {
                execution_id: executionId,
                action_id: actionId,
              });

              setTimeout(() => {
                currentExecution.actions[actionIndex].status = ActionStatus.COMPLETED;
                mockWs.emit(WSMessageType.ACTION_COMPLETED, {
                  execution_id: executionId,
                  action_id: actionId,
                  result: { success: true },
                });

                // Move to next action
                const nextAction = currentExecution.actions.find(a => a.status === ActionStatus.PENDING);
                if (nextAction) {
                  nextAction.status = ActionStatus.AWAITING_APPROVAL;
                  nextAction.timeout_at = new Date(Date.now() + 300000).toISOString();
                  mockWs.emit(WSMessageType.ACTION_AWAITING_APPROVAL, {
                    execution_id: executionId,
                    action: nextAction,
                  });
                }
              }, 2000);
            }, 500);
          }
        }, 200);
      }
    },
    sendDeny: (executionId, actionId, reason) => {
      if (isConnected) {
        setTimeout(() => {
          const actionIndex = currentExecution.actions.findIndex(a => a.action_id === actionId);
          if (actionIndex !== -1) {
            currentExecution.actions[actionIndex].status = ActionStatus.DENIED;
            mockWs.emit(WSMessageType.ACTION_DENIED, {
              execution_id: executionId,
              action_id: actionId,
              reason,
            });

            // Move to next action
            const nextAction = currentExecution.actions.find(a => a.status === ActionStatus.PENDING);
            if (nextAction) {
              nextAction.status = ActionStatus.AWAITING_APPROVAL;
              nextAction.timeout_at = new Date(Date.now() + 300000).toISOString();
              mockWs.emit(WSMessageType.ACTION_AWAITING_APPROVAL, {
                execution_id: executionId,
                action: nextAction,
              });
            }
          }
        }, 200);
      }
    },
    sendModify: (executionId, actionId, modifiedParameters, trustScope) => {
      if (isConnected) {
        setTimeout(() => {
          const actionIndex = currentExecution.actions.findIndex(a => a.action_id === actionId);
          if (actionIndex !== -1) {
            currentExecution.actions[actionIndex].status = ActionStatus.MODIFIED;
            currentExecution.actions[actionIndex].parameters = {
              ...currentExecution.actions[actionIndex].parameters,
              ...modifiedParameters,
            };
            mockWs.emit(WSMessageType.ACTION_MODIFIED, {
              execution_id: executionId,
              action_id: actionId,
              modified_parameters: modifiedParameters,
              trust_scope: trustScope,
            });
          }
        }, 200);
      }
    },
    sendAbort: (executionId, reason) => {
      if (isConnected) {
        setTimeout(() => {
          mockWs.emit(WSMessageType.EXECUTION_ABORTED, {
            execution_id: executionId,
            reason,
          });
        }, 200);
      }
    },
    on: (event, callback) => {
      if (!listeners.has(event)) {
        listeners.set(event, new Set());
      }
      listeners.get(event).add(callback);
      return () => mockWs.off(event, callback);
    },
    off: (event, callback) => {
      const callbacks = listeners.get(event);
      if (callbacks) {
        callbacks.delete(callback);
      }
    },
    emit: (event, data) => {
      const callbacks = listeners.get(event);
      if (callbacks) {
        callbacks.forEach((callback) => callback(data));
      }
    },
    isConnected: () => isConnected,
  };

  return mockWs;
}

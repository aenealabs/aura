/**
 * Project Aura - Security Alerts API Service
 *
 * Client-side service for interacting with the Security Alerts API endpoints.
 * Provides methods for listing, viewing, acknowledging, and resolving security alerts.
 */

// API base URL - uses Vite's environment variable or defaults to relative path
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Alert priority levels (P1-P5)
 */
export const AlertPriority = {
  P1_CRITICAL: 'P1_CRITICAL',
  P2_HIGH: 'P2_HIGH',
  P3_MEDIUM: 'P3_MEDIUM',
  P4_LOW: 'P4_LOW',
  P5_INFO: 'P5_INFO',
};

/**
 * Alert status values
 */
export const AlertStatus = {
  NEW: 'NEW',
  ACKNOWLEDGED: 'ACKNOWLEDGED',
  INVESTIGATING: 'INVESTIGATING',
  RESOLVED: 'RESOLVED',
  FALSE_POSITIVE: 'FALSE_POSITIVE',
};

/**
 * Priority display configuration
 */
export const PRIORITY_CONFIG = {
  P1_CRITICAL: { label: 'P1 Critical', color: 'critical', bgClass: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' },
  P2_HIGH: { label: 'P2 High', color: 'warning', bgClass: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200' },
  P3_MEDIUM: { label: 'P3 Medium', color: 'olive', bgClass: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200' },
  P4_LOW: { label: 'P4 Low', color: 'aura', bgClass: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
  P5_INFO: { label: 'P5 Info', color: 'gray', bgClass: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200' },
};

/**
 * Status display configuration
 */
export const STATUS_CONFIG = {
  NEW: { label: 'New', color: 'critical', icon: 'ExclamationCircleIcon' },
  ACKNOWLEDGED: { label: 'Acknowledged', color: 'warning', icon: 'EyeIcon' },
  INVESTIGATING: { label: 'Investigating', color: 'aura', icon: 'MagnifyingGlassIcon' },
  RESOLVED: { label: 'Resolved', color: 'olive', icon: 'CheckCircleIcon' },
  FALSE_POSITIVE: { label: 'False Positive', color: 'gray', icon: 'XCircleIcon' },
};

/**
 * Custom error class for Security Alerts API errors
 */
export class SecurityAlertsApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'SecurityAlertsApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  // Add auth token if available
  const token = localStorage.getItem('authToken');
  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new SecurityAlertsApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  return response.json();
}

/**
 * List security alerts with optional filtering
 *
 * @param {Object} options - Query options
 * @param {string} [options.priority] - Filter by priority (P1_CRITICAL, P2_HIGH, etc.)
 * @param {string} [options.status] - Filter by status (NEW, ACKNOWLEDGED, etc.)
 * @param {string} [options.assignedTo] - Filter by assigned user
 * @param {string} [options.eventType] - Filter by security event type
 * @param {number} [options.limit=50] - Maximum results to return
 * @param {number} [options.offset=0] - Pagination offset
 * @returns {Promise<Object>} List of alerts with metadata
 */
export async function listSecurityAlerts({
  priority,
  status,
  assignedTo,
  eventType,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams();
  if (priority) params.append('priority', priority);
  if (status) params.append('status', status);
  if (assignedTo) params.append('assigned_to', assignedTo);
  if (eventType) params.append('event_type', eventType);
  if (limit) params.append('limit', limit.toString());
  if (offset) params.append('offset', offset.toString());

  const queryString = params.toString();
  const endpoint = `/alerts${queryString ? `?${queryString}` : ''}`;

  return fetchApi(endpoint);
}

/**
 * Get detailed information about a specific security alert
 *
 * @param {string} alertId - The alert ID
 * @returns {Promise<Object>} Full alert details including timeline
 */
export async function getSecurityAlertDetail(alertId) {
  return fetchApi(`/alerts/${alertId}`);
}

/**
 * Acknowledge a security alert
 *
 * @param {string} alertId - The alert ID
 * @param {string} userId - User acknowledging the alert
 * @param {string} [comment] - Optional acknowledgment comment
 * @returns {Promise<Object>} Updated alert
 */
export async function acknowledgeAlert(alertId, userId, comment = null) {
  const body = { user_id: userId };
  if (comment) body.comment = comment;

  return fetchApi(`/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Assign a security alert to a user
 *
 * @param {string} alertId - The alert ID
 * @param {string} assigneeId - User to assign the alert to
 * @param {string} [assignedBy] - User making the assignment
 * @returns {Promise<Object>} Updated alert
 */
export async function assignAlert(alertId, assigneeId, assignedBy = null) {
  return fetchApi(`/alerts/${alertId}/assign`, {
    method: 'POST',
    body: JSON.stringify({
      assignee_id: assigneeId,
      assigned_by: assignedBy,
    }),
  });
}

/**
 * Update alert status to investigating
 *
 * @param {string} alertId - The alert ID
 * @param {string} userId - User starting investigation
 * @param {string} [notes] - Investigation notes
 * @returns {Promise<Object>} Updated alert
 */
export async function startInvestigation(alertId, userId, notes = null) {
  const body = { user_id: userId, status: 'INVESTIGATING' };
  if (notes) body.notes = notes;

  return fetchApi(`/alerts/${alertId}/status`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

/**
 * Resolve a security alert
 *
 * @param {string} alertId - The alert ID
 * @param {string} userId - User resolving the alert
 * @param {string} resolution - Resolution description
 * @param {Array<string>} [actionsTaken] - List of actions taken
 * @returns {Promise<Object>} Updated alert
 */
export async function resolveAlert(alertId, userId, resolution, actionsTaken = []) {
  return fetchApi(`/alerts/${alertId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      resolution: resolution,
      actions_taken: actionsTaken,
    }),
  });
}

/**
 * Mark alert as false positive
 *
 * @param {string} alertId - The alert ID
 * @param {string} userId - User marking as false positive
 * @param {string} reason - Reason for marking as false positive
 * @returns {Promise<Object>} Updated alert
 */
export async function markFalsePositive(alertId, userId, reason) {
  return fetchApi(`/alerts/${alertId}/false-positive`, {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      reason: reason,
    }),
  });
}

/**
 * Add a comment to an alert
 *
 * @param {string} alertId - The alert ID
 * @param {string} userId - User adding the comment
 * @param {string} comment - Comment text
 * @returns {Promise<Object>} Updated alert with new comment
 */
export async function addAlertComment(alertId, userId, comment) {
  return fetchApi(`/alerts/${alertId}/comments`, {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      comment: comment,
    }),
  });
}

/**
 * Get security alert statistics
 *
 * @returns {Promise<Object>} Statistics including counts by priority and status
 */
export async function getAlertStats() {
  return fetchApi('/alerts/stats');
}

/**
 * Get alert timeline/history
 *
 * @param {string} alertId - The alert ID
 * @returns {Promise<Array>} List of timeline events
 */
export async function getAlertTimeline(alertId) {
  return fetchApi(`/alerts/${alertId}/timeline`);
}

/**
 * Get unacknowledged alert count (for badge display)
 *
 * @returns {Promise<Object>} Count of unacknowledged alerts by priority
 */
export async function getUnacknowledgedCount() {
  return fetchApi('/alerts/unacknowledged/count');
}

/**
 * Create a HITL approval request for an alert
 *
 * @param {string} alertId - The alert ID
 * @param {Object} approvalRequest - Approval request details
 * @returns {Promise<Object>} Created HITL approval request
 */
export async function createHITLRequest(alertId, approvalRequest) {
  return fetchApi(`/alerts/${alertId}/hitl-request`, {
    method: 'POST',
    body: JSON.stringify(approvalRequest),
  });
}

// Default export for convenience
export default {
  listSecurityAlerts,
  getSecurityAlertDetail,
  acknowledgeAlert,
  assignAlert,
  startInvestigation,
  resolveAlert,
  markFalsePositive,
  addAlertComment,
  getAlertStats,
  getAlertTimeline,
  getUnacknowledgedCount,
  createHITLRequest,
  AlertPriority,
  AlertStatus,
  PRIORITY_CONFIG,
  STATUS_CONFIG,
  SecurityAlertsApiError,
};

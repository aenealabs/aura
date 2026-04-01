/**
 * Project Aura - Approval API Service
 *
 * Client-side service for interacting with the HITL Approval API endpoints.
 * Provides methods for listing, viewing, approving, and rejecting patch approvals.
 */

// API base URL - uses Vite's environment variable or defaults to relative path
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for API errors
 */
export class ApprovalApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ApprovalApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Generic fetch wrapper with error handling
 * Returns null on network errors to allow graceful degradation
 */
async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApprovalApiError(
        errorData.detail || errorData.error || `API error: ${response.status}`,
        response.status,
        errorData
      );
    }

    return response.json();
  } catch (err) {
    // Network error or other fetch failure - allow graceful degradation
    if (err instanceof ApprovalApiError) {
      throw err;
    }
    console.warn('Approval API unavailable:', err.message);
    return null;
  }
}

/**
 * List approval requests with optional filtering
 *
 * @param {Object} options - Query options
 * @param {string} [options.status] - Filter by status (pending, approved, rejected)
 * @param {string} [options.severity] - Filter by severity (critical, high, medium, low)
 * @param {number} [options.limit=50] - Maximum results to return
 * @returns {Promise<Object>} List of approvals with counts
 */
export async function listApprovals({ status, severity, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (severity) params.append('severity', severity);
  if (limit) params.append('limit', limit.toString());

  const queryString = params.toString();
  const endpoint = `/approvals${queryString ? `?${queryString}` : ''}`;

  return fetchApi(endpoint);
}

/**
 * Get detailed information about a specific approval request
 *
 * @param {string} approvalId - The approval ID
 * @returns {Promise<Object>} Full approval details
 */
export async function getApprovalDetail(approvalId) {
  return fetchApi(`/approvals/${approvalId}`);
}

/**
 * Approve a pending approval request
 *
 * @param {string} approvalId - The approval ID
 * @param {string} reviewerEmail - Email of the reviewer approving
 * @param {string} [comment] - Optional approval comment
 * @returns {Promise<Object>} Approval action result
 */
export async function approveRequest(approvalId, reviewerEmail, comment = null) {
  const body = { reviewer_email: reviewerEmail };
  if (comment) body.comment = comment;

  return fetchApi(`/approvals/${approvalId}/approve`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Reject a pending approval request
 *
 * @param {string} approvalId - The approval ID
 * @param {string} reviewerEmail - Email of the reviewer rejecting
 * @param {string} reason - Reason for rejection (required)
 * @returns {Promise<Object>} Rejection action result
 */
export async function rejectRequest(approvalId, reviewerEmail, reason) {
  return fetchApi(`/approvals/${approvalId}/reject`, {
    method: 'POST',
    body: JSON.stringify({
      reviewer_email: reviewerEmail,
      reason: reason,
    }),
  });
}

/**
 * Cancel a pending approval request
 *
 * @param {string} approvalId - The approval ID
 * @returns {Promise<Object>} Cancellation action result
 */
export async function cancelRequest(approvalId) {
  return fetchApi(`/approvals/${approvalId}/cancel`, {
    method: 'POST',
  });
}

/**
 * Get approval statistics
 *
 * @returns {Promise<Object>} Statistics including counts by status and severity
 */
export async function getApprovalStats() {
  return fetchApi('/approvals/stats');
}

/**
 * Request changes on a pending approval
 *
 * @param {string} approvalId - The approval ID
 * @param {string} comment - Details of requested changes
 * @returns {Promise<Object>} Request changes action result
 */
export async function requestChanges(approvalId, comment) {
  return fetchApi(`/approvals/${approvalId}/request-changes`, {
    method: 'POST',
    body: JSON.stringify({
      comment: comment,
    }),
  });
}

// Alias exports for convenience
export const approveApproval = approveRequest;
export const rejectApproval = rejectRequest;

// Default export for convenience
export default {
  listApprovals,
  getApprovalDetail,
  approveRequest,
  rejectRequest,
  requestChanges,
  cancelRequest,
  getApprovalStats,
  ApprovalApiError,
  // Aliases
  approveApproval: approveRequest,
  rejectApproval: rejectRequest,
};

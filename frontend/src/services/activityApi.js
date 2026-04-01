/**
 * Project Aura - Activity API Service
 *
 * Client-side service for interacting with the Activity Feed API endpoints.
 * Provides methods for listing, viewing, marking as read, and dismissing activities.
 */

import { apiClient, ApiError } from './api';

/**
 * Activity types and their navigation targets
 */
export const ActivityType = {
  // Agent activities
  AGENT_STARTED: 'agent_started',
  AGENT_COMPLETED: 'agent_completed',
  AGENT_FAILED: 'agent_failed',

  // Scan activities
  SCAN_STARTED: 'scan_started',
  SCAN_COMPLETED: 'scan_completed',

  // Vulnerability activities
  VULNERABILITY_DETECTED: 'vulnerability_detected',

  // Patch activities
  PATCH_GENERATED: 'patch_generated',
  PATCH_APPROVED: 'patch_approved',
  PATCH_REJECTED: 'patch_rejected',
  PATCH_DEPLOYED: 'patch_deployed',

  // Approval activities
  APPROVAL_REQUESTED: 'approval_requested',
  APPROVAL_PENDING: 'pending',

  // Repository activities
  REPOSITORY_CONNECTED: 'repository_connected',
  REPOSITORY_SCAN_STARTED: 'repository_scan_started',
  REPOSITORY_UPDATED: 'repository_updated',

  // Alert activities
  ANOMALY_DETECTED: 'anomaly_detected',
  ALERT_TRIGGERED: 'alert_triggered',

  // Incident activities
  INCIDENT_OPENED: 'incident_opened',
  INCIDENT_RESOLVED: 'incident_resolved',

  // Generic
  IN_PROGRESS: 'in_progress',
};

/**
 * Navigation route mappings for activity types
 */
export const ACTIVITY_ROUTES = {
  // Agent activities -> Agent Mission Control
  [ActivityType.AGENT_STARTED]: (activity) => `/agents/mission-control/${activity.metadata?.agentId || activity.agentId || ''}`,
  [ActivityType.AGENT_COMPLETED]: (activity) => `/agents/mission-control/${activity.metadata?.agentId || activity.agentId || ''}`,
  [ActivityType.AGENT_FAILED]: (activity) => `/agents/mission-control/${activity.metadata?.agentId || activity.agentId || ''}`,

  // Scan activities -> Scan results or generic activity detail
  [ActivityType.SCAN_STARTED]: (activity) => `/activity/${activity.id}`,
  [ActivityType.SCAN_COMPLETED]: (activity) => `/activity/${activity.id}`,

  // Vulnerability activities -> Vulnerabilities or activity detail
  [ActivityType.VULNERABILITY_DETECTED]: (activity) => `/activity/${activity.id}`,

  // Patch activities -> Approvals dashboard
  [ActivityType.PATCH_GENERATED]: (_activity) => `/approvals`,
  [ActivityType.PATCH_APPROVED]: (_activity) => `/approvals`,
  [ActivityType.PATCH_REJECTED]: (_activity) => `/approvals`,
  [ActivityType.PATCH_DEPLOYED]: (activity) => `/activity/${activity.id}`,

  // Approval activities -> Approvals dashboard
  [ActivityType.APPROVAL_REQUESTED]: (_activity) => `/approvals`,
  [ActivityType.APPROVAL_PENDING]: (_activity) => `/approvals`,

  // Repository activities -> Repositories list
  [ActivityType.REPOSITORY_CONNECTED]: (_activity) => `/repositories`,
  [ActivityType.REPOSITORY_SCAN_STARTED]: (_activity) => `/repositories`,
  [ActivityType.REPOSITORY_UPDATED]: (_activity) => `/repositories`,

  // Alert activities -> Security alerts
  [ActivityType.ANOMALY_DETECTED]: (_activity) => `/security/alerts`,
  [ActivityType.ALERT_TRIGGERED]: (_activity) => `/security/alerts`,

  // Incident activities -> Incidents page
  [ActivityType.INCIDENT_OPENED]: (_activity) => `/incidents`,
  [ActivityType.INCIDENT_RESOLVED]: (_activity) => `/incidents`,

  // Generic fallback
  [ActivityType.IN_PROGRESS]: (activity) => `/activity/${activity.id}`,
};

/**
 * Get the navigation route for an activity based on its type
 *
 * @param {Object} activity - The activity object
 * @returns {string} The navigation route
 */
export function getActivityRoute(activity) {
  const routeGetter = ACTIVITY_ROUTES[activity.type];
  if (routeGetter) {
    return routeGetter(activity);
  }
  // Default fallback to activity detail page
  return `/activity/${activity.id}`;
}

/**
 * Activity status values
 */
export const ActivityStatus = {
  UNREAD: 'unread',
  READ: 'read',
  DISMISSED: 'dismissed',
};

/**
 * Custom error class for Activity API errors
 */
export class ActivityApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ActivityApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * List activities with optional filtering and pagination
 *
 * @param {Object} options - Query options
 * @param {string} [options.type] - Filter by activity type
 * @param {string} [options.status] - Filter by read status (unread, read, dismissed)
 * @param {string} [options.severity] - Filter by severity (critical, high, medium, low)
 * @param {string} [options.startDate] - Filter by start date (ISO string)
 * @param {string} [options.endDate] - Filter by end date (ISO string)
 * @param {number} [options.limit=50] - Maximum results to return
 * @param {number} [options.offset=0] - Pagination offset
 * @returns {Promise<Object>} List of activities with pagination metadata
 */
export async function getActivities({
  type,
  status,
  severity,
  startDate,
  endDate,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams();

  if (type) params.append('type', type);
  if (status) params.append('status', status);
  if (severity) params.append('severity', severity);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (limit) params.append('limit', limit.toString());
  if (offset) params.append('offset', offset.toString());

  const queryString = params.toString();
  const endpoint = `/activities${queryString ? `?${queryString}` : ''}`;

  try {
    const response = await apiClient.get(endpoint);
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Get detailed information about a specific activity
 *
 * @param {string} activityId - The activity ID
 * @returns {Promise<Object>} Full activity details including metadata and related entities
 */
export async function getActivity(activityId) {
  if (!activityId) {
    throw new ActivityApiError('Activity ID is required', 400);
  }

  try {
    const response = await apiClient.get(`/activities/${activityId}`);
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Mark an activity as read
 *
 * @param {string} activityId - The activity ID
 * @returns {Promise<Object>} Updated activity
 */
export async function markAsRead(activityId) {
  if (!activityId) {
    throw new ActivityApiError('Activity ID is required', 400);
  }

  try {
    const response = await apiClient.patch(`/activities/${activityId}`, {
      status: ActivityStatus.READ,
    });
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Mark multiple activities as read
 *
 * @param {string[]} activityIds - Array of activity IDs
 * @returns {Promise<Object>} Result with count of updated activities
 */
export async function markMultipleAsRead(activityIds) {
  if (!activityIds || activityIds.length === 0) {
    throw new ActivityApiError('At least one activity ID is required', 400);
  }

  try {
    const response = await apiClient.post('/activities/mark-read', {
      activity_ids: activityIds,
    });
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Mark all activities as read
 *
 * @returns {Promise<Object>} Result with count of updated activities
 */
export async function markAllAsRead() {
  try {
    const response = await apiClient.post('/activities/mark-all-read');
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Dismiss an activity (soft delete)
 *
 * @param {string} activityId - The activity ID
 * @returns {Promise<Object>} Dismissal confirmation
 */
export async function dismissActivity(activityId) {
  if (!activityId) {
    throw new ActivityApiError('Activity ID is required', 400);
  }

  try {
    const response = await apiClient.patch(`/activities/${activityId}`, {
      status: ActivityStatus.DISMISSED,
    });
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Dismiss multiple activities
 *
 * @param {string[]} activityIds - Array of activity IDs
 * @returns {Promise<Object>} Result with count of dismissed activities
 */
export async function dismissMultiple(activityIds) {
  if (!activityIds || activityIds.length === 0) {
    throw new ActivityApiError('At least one activity ID is required', 400);
  }

  try {
    const response = await apiClient.post('/activities/dismiss', {
      activity_ids: activityIds,
    });
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Get activity statistics
 *
 * @returns {Promise<Object>} Statistics including counts by type, severity, and status
 */
export async function getActivityStats() {
  try {
    const response = await apiClient.get('/activities/stats');
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Get unread activity count (for badge display)
 *
 * @returns {Promise<Object>} Count of unread activities by type
 */
export async function getUnreadCount() {
  try {
    const response = await apiClient.get('/activities/unread/count');
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

/**
 * Get related entities for an activity
 *
 * @param {string} activityId - The activity ID
 * @returns {Promise<Object>} Related entities (agents, scans, approvals, etc.)
 */
export async function getActivityRelatedEntities(activityId) {
  if (!activityId) {
    throw new ActivityApiError('Activity ID is required', 400);
  }

  try {
    const response = await apiClient.get(`/activities/${activityId}/related`);
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new ActivityApiError(error.message, error.status, error.details);
    }
    throw error;
  }
}

// Default export for convenience
export default {
  getActivities,
  getActivity,
  markAsRead,
  markMultipleAsRead,
  markAllAsRead,
  dismissActivity,
  dismissMultiple,
  getActivityStats,
  getUnreadCount,
  getActivityRelatedEntities,
  getActivityRoute,
  ActivityType,
  ActivityStatus,
  ACTIVITY_ROUTES,
  ActivityApiError,
};

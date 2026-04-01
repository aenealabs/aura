/**
 * Project Aura - Alignment API Service
 *
 * Client-side service for AI alignment monitoring and control.
 * Provides access to alignment health metrics, alerts, trends, and human overrides.
 *
 * Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
 */

// API base URL - uses Vite's environment variable or defaults to relative path
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Alignment API errors
 */
export class AlignmentApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'AlignmentApiError';
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

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new AlignmentApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  return response.json();
}

/**
 * Time range options for metrics
 */
export const TimeRanges = {
  HOUR: 1,
  DAY: 24,
  WEEK: 168,
  MONTH: 720,
};

/**
 * Alignment health status
 */
export const AlignmentStatus = {
  HEALTHY: 'healthy',
  WARNING: 'warning',
  CRITICAL: 'critical',
};

/**
 * Alert severity levels
 */
export const AlertSeverity = {
  INFO: 'info',
  WARNING: 'warning',
  CRITICAL: 'critical',
};

/**
 * Alert status values
 */
export const AlertStatus = {
  ACTIVE: 'active',
  ACKNOWLEDGED: 'acknowledged',
  RESOLVED: 'resolved',
  SUPPRESSED: 'suppressed',
};

/**
 * Trend direction values
 */
export const TrendDirection = {
  IMPROVING: 'improving',
  STABLE: 'stable',
  DEGRADING: 'degrading',
  UNKNOWN: 'unknown',
};

/**
 * Autonomy levels
 */
export const AutonomyLevel = {
  OBSERVE: 'observe',
  RECOMMEND: 'recommend',
  EXECUTE_REVIEW: 'execute_review',
  AUTONOMOUS: 'autonomous',
};

// =============================================================================
// Health API
// =============================================================================

/**
 * Get overall alignment health status
 * @returns {Promise<Object>} Alignment health data
 */
export async function getAlignmentHealth() {
  return fetchApi('/alignment/health');
}

// =============================================================================
// Metrics API
// =============================================================================

/**
 * Get time series data for a specific metric
 * @param {string} metricName - Name of the metric
 * @param {number} periodHours - Hours of history (default: 24)
 * @param {string} granularity - minute, hour, day, week (default: hour)
 * @param {string|null} agentId - Optional agent ID filter
 * @returns {Promise<Object>} Time series data
 */
export async function getMetricTimeSeries(
  metricName,
  periodHours = 24,
  granularity = 'hour',
  agentId = null
) {
  const params = new URLSearchParams({
    metric_name: metricName,
    period_hours: periodHours.toString(),
    granularity,
  });

  if (agentId) {
    params.append('agent_id', agentId);
  }

  return fetchApi(`/alignment/metrics?${params.toString()}`);
}

/**
 * Get trend analysis for all key metrics
 * @param {number} periodHours - Hours of history (default: 24)
 * @param {string|null} agentId - Optional agent ID filter
 * @returns {Promise<Array>} Array of trend analyses
 */
export async function getTrends(periodHours = 24, agentId = null) {
  const params = new URLSearchParams({
    period_hours: periodHours.toString(),
  });

  if (agentId) {
    params.append('agent_id', agentId);
  }

  return fetchApi(`/alignment/trends?${params.toString()}`);
}

// =============================================================================
// Alerts API
// =============================================================================

/**
 * Get alignment alerts
 * @param {Object} filters - Optional filters
 * @param {string|null} filters.status - Filter by status
 * @param {string|null} filters.severity - Filter by severity
 * @param {string|null} filters.agentId - Filter by agent ID
 * @returns {Promise<Array>} Array of alerts
 */
export async function getAlerts({ status = null, severity = null, agentId = null } = {}) {
  const params = new URLSearchParams();

  if (status) params.append('status', status);
  if (severity) params.append('severity', severity);
  if (agentId) params.append('agent_id', agentId);

  const queryString = params.toString();
  return fetchApi(`/alignment/alerts${queryString ? `?${queryString}` : ''}`);
}

/**
 * Acknowledge an alert
 * @param {string} alertId - Alert ID to acknowledge
 * @returns {Promise<Object>} Updated alert
 */
export async function acknowledgeAlert(alertId) {
  return fetchApi(`/alignment/alerts/${alertId}/acknowledge`, {
    method: 'POST',
  });
}

/**
 * Resolve an alert
 * @param {string} alertId - Alert ID to resolve
 * @returns {Promise<Object>} Updated alert
 */
export async function resolveAlert(alertId) {
  return fetchApi(`/alignment/alerts/${alertId}/resolve`, {
    method: 'POST',
  });
}

// =============================================================================
// Agent Comparison API
// =============================================================================

/**
 * Get alignment comparison across agents
 * @param {number} periodHours - Hours of history (default: 24)
 * @returns {Promise<Array>} Array of agent comparisons
 */
export async function getAgentComparisons(periodHours = 24) {
  return fetchApi(`/alignment/agents?period_hours=${periodHours}`);
}

// =============================================================================
// Reports API
// =============================================================================

/**
 * Generate a comprehensive alignment report
 * @param {number} periodHours - Hours of history (default: 24)
 * @param {boolean} includeComparisons - Include agent comparisons (default: true)
 * @returns {Promise<Object>} Alignment report
 */
export async function generateReport(periodHours = 24, includeComparisons = true) {
  const params = new URLSearchParams({
    period_hours: periodHours.toString(),
    include_comparisons: includeComparisons.toString(),
  });

  return fetchApi(`/alignment/reports?${params.toString()}`);
}

// =============================================================================
// Override API
// =============================================================================

/**
 * Grant temporary autonomy override to an agent
 * @param {string} agentId - Agent ID
 * @param {string} newLevel - New autonomy level
 * @param {string} reason - Justification for override
 * @param {number} durationHours - Duration in hours (default: 24)
 * @returns {Promise<Object>} Override result
 */
export async function grantOverride(agentId, newLevel, reason, durationHours = 24) {
  return fetchApi('/alignment/override', {
    method: 'POST',
    body: JSON.stringify({
      agent_id: agentId,
      new_level: newLevel,
      reason,
      duration_hours: durationHours,
    }),
  });
}

/**
 * Revoke temporary autonomy override from an agent
 * @param {string} agentId - Agent ID
 * @returns {Promise<Object>} Result
 */
export async function revokeOverride(agentId) {
  return fetchApi(`/alignment/override/${agentId}`, {
    method: 'DELETE',
  });
}

// =============================================================================
// Rollback API
// =============================================================================

/**
 * Check if an action can be rolled back
 * @param {string} actionId - Action ID
 * @returns {Promise<Object>} Rollback capability info
 */
export async function getRollbackCapability(actionId) {
  return fetchApi(`/alignment/rollback/${actionId}/capability`);
}

/**
 * Execute a rollback for a specific action
 * @param {string} actionId - Action ID to roll back
 * @param {string} reason - Reason for rollback (optional)
 * @returns {Promise<Object>} Rollback result
 */
export async function executeRollback(actionId, reason = '') {
  return fetchApi(`/alignment/rollback/${actionId}`, {
    method: 'POST',
    body: JSON.stringify({ action_id: actionId, reason }),
  });
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get status color class based on alignment status
 * @param {string} status - Alignment status
 * @returns {string} Tailwind color class
 */
export function getStatusColor(status) {
  switch (status) {
    case AlignmentStatus.HEALTHY:
      return 'text-olive-600 dark:text-olive-400';
    case AlignmentStatus.WARNING:
      return 'text-amber-600 dark:text-amber-400';
    case AlignmentStatus.CRITICAL:
      return 'text-critical-600 dark:text-critical-400';
    default:
      return 'text-surface-500 dark:text-surface-400';
  }
}

/**
 * Get status background color class based on alignment status
 * @param {string} status - Alignment status
 * @returns {string} Tailwind background color class
 */
export function getStatusBgColor(status) {
  switch (status) {
    case AlignmentStatus.HEALTHY:
      return 'bg-olive-100 dark:bg-olive-900/30';
    case AlignmentStatus.WARNING:
      return 'bg-amber-100 dark:bg-amber-900/30';
    case AlignmentStatus.CRITICAL:
      return 'bg-critical-100 dark:bg-critical-900/30';
    default:
      return 'bg-surface-100 dark:bg-surface-800';
  }
}

/**
 * Get severity color class
 * @param {string} severity - Alert severity
 * @returns {string} Tailwind color class
 */
export function getSeverityColor(severity) {
  switch (severity) {
    case AlertSeverity.CRITICAL:
      return 'text-critical-600 dark:text-critical-400';
    case AlertSeverity.WARNING:
      return 'text-amber-600 dark:text-amber-400';
    case AlertSeverity.INFO:
      return 'text-blue-600 dark:text-blue-400';
    default:
      return 'text-surface-500 dark:text-surface-400';
  }
}

/**
 * Get trend direction icon and color
 * @param {string} direction - Trend direction
 * @returns {Object} { icon, color, label }
 */
export function getTrendInfo(direction) {
  switch (direction) {
    case TrendDirection.IMPROVING:
      return {
        icon: 'ArrowTrendingUpIcon',
        color: 'text-olive-600 dark:text-olive-400',
        label: 'Improving',
      };
    case TrendDirection.STABLE:
      return {
        icon: 'MinusIcon',
        color: 'text-surface-500 dark:text-surface-400',
        label: 'Stable',
      };
    case TrendDirection.DEGRADING:
      return {
        icon: 'ArrowTrendingDownIcon',
        color: 'text-critical-600 dark:text-critical-400',
        label: 'Degrading',
      };
    default:
      return {
        icon: 'QuestionMarkCircleIcon',
        color: 'text-surface-400 dark:text-surface-500',
        label: 'Unknown',
      };
  }
}

/**
 * Format a percentage for display
 * @param {number} value - Value between 0 and 1
 * @param {number} decimals - Decimal places (default: 1)
 * @returns {string} Formatted percentage string
 */
export function formatPercent(value, decimals = 1) {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a score for display (0-100 scale)
 * @param {number} value - Value between 0 and 1
 * @returns {string} Formatted score string
 */
export function formatScore(value) {
  return Math.round(value * 100).toString();
}

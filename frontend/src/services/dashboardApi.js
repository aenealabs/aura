/**
 * Project Aura - Dashboard API Service
 *
 * Client-side service for fetching dashboard metrics, agent status,
 * scan results, security alerts, system health, and cost data.
 *
 * @module services/dashboardApi
 */

import { apiClient, ApiError } from './api';

// API endpoints for dashboard data
const ENDPOINTS = {
  SUMMARY: '/dashboard/summary',
  AGENTS: '/dashboard/agents',
  SCANS: '/dashboard/scans',
  ALERTS: '/dashboard/alerts',
  HEALTH: '/dashboard/health',
  COST: '/dashboard/cost',
};

/**
 * @typedef {Object} AgentMetrics
 * @property {number} active - Number of active agents
 * @property {number} idle - Number of idle agents
 * @property {number} total - Total agents
 * @property {number} trend - Percentage change from previous period
 * @property {number[]} sparkline - Historical data points for sparkline chart
 */

/**
 * @typedef {Object} ScanStats
 * @property {number} completed - Number of completed scans
 * @property {number} inProgress - Number of scans in progress
 * @property {number} failed - Number of failed scans
 * @property {number} vulnerabilitiesFound - Total vulnerabilities found
 * @property {number} trend - Percentage change from previous period
 */

/**
 * @typedef {Object} RepositoryHealth
 * @property {number} totalRepositories - Total number of repositories
 * @property {number} healthy - Repositories in healthy state
 * @property {number} warning - Repositories with warnings
 * @property {number} critical - Repositories in critical state
 * @property {number} healthScore - Overall health score (0-100)
 */

/**
 * @typedef {Object} MetricsSummary
 * @property {AgentMetrics} agents - Agent-related metrics
 * @property {ScanStats} scans - Scan statistics
 * @property {RepositoryHealth} repositories - Repository health metrics
 * @property {Object} vulnerabilities - Vulnerability metrics
 * @property {Object} patches - Patch deployment metrics
 * @property {Object} approvals - Pending approval metrics
 * @property {string} lastUpdated - ISO timestamp of last update
 */

/**
 * @typedef {Object} AgentStatus
 * @property {string} id - Unique agent identifier
 * @property {string} name - Agent display name (Coder, Reviewer, Validator)
 * @property {'active'|'idle'|'error'|'offline'} status - Current agent status
 * @property {string} task - Current task description
 * @property {number} progress - Task progress percentage (0-100)
 * @property {string} lastHeartbeat - ISO timestamp of last heartbeat
 * @property {Object} metrics - Agent-specific metrics
 */

/**
 * @typedef {Object} ScanResult
 * @property {string} id - Scan identifier
 * @property {string} repositoryName - Repository name
 * @property {'completed'|'in_progress'|'failed'|'queued'} status - Scan status
 * @property {number} vulnerabilities - Number of vulnerabilities found
 * @property {Object} severityBreakdown - Vulnerabilities by severity level
 * @property {string} startedAt - ISO timestamp when scan started
 * @property {string} completedAt - ISO timestamp when scan completed
 * @property {number} duration - Scan duration in seconds
 */

/**
 * @typedef {Object} SecurityAlert
 * @property {string} id - Alert identifier
 * @property {string} title - Alert title
 * @property {'P1_CRITICAL'|'P2_HIGH'|'P3_MEDIUM'|'P4_LOW'|'P5_INFO'} priority - Alert priority
 * @property {'NEW'|'ACKNOWLEDGED'|'INVESTIGATING'|'RESOLVED'} status - Alert status
 * @property {string} eventType - Type of security event
 * @property {string} createdAt - ISO timestamp when alert was created
 * @property {Object} metadata - Additional alert metadata
 */

/**
 * @typedef {Object} SystemHealthMetrics
 * @property {Object} api - API health metrics
 * @property {Object} graphRag - GraphRAG system health
 * @property {Object} llm - LLM quota and health
 * @property {Object} sandbox - Sandbox availability
 * @property {Object} database - Database health metrics
 * @property {string} overallStatus - Overall system status
 */

/**
 * @typedef {Object} CostMetrics
 * @property {number} currentPeriodCost - Cost for current billing period
 * @property {number} previousPeriodCost - Cost for previous billing period
 * @property {number} trend - Percentage change in cost
 * @property {Object} breakdown - Cost breakdown by service
 * @property {number} budgetUsed - Percentage of budget used
 * @property {number} projectedCost - Projected cost for current period
 */

/**
 * Fetches the dashboard metrics summary including agent counts,
 * scan statistics, and repository health.
 *
 * @returns {Promise<MetricsSummary>} Dashboard metrics summary
 * @throws {ApiError} When the request fails
 *
 * @example
 * const summary = await getMetricsSummary();
 * console.warn(`Active agents: ${summary.agents.active}`);
 */
export async function getMetricsSummary() {
  const { data } = await apiClient.get(ENDPOINTS.SUMMARY);
  return data;
}

/**
 * Fetches real-time agent status from the backend.
 * Returns the current state of all agents including their tasks and progress.
 *
 * @returns {Promise<AgentStatus[]>} Array of agent status objects
 * @throws {ApiError} When the request fails
 *
 * @example
 * const agents = await getAgentStatus();
 * const activeAgents = agents.filter(a => a.status === 'active');
 */
export async function getAgentStatus() {
  const { data } = await apiClient.get(ENDPOINTS.AGENTS);
  return data;
}

/**
 * Fetches recent scan results with optional filtering.
 *
 * @param {Object} [options] - Query options
 * @param {number} [options.limit=10] - Maximum number of results to return
 * @param {string} [options.status] - Filter by scan status
 * @param {string} [options.repository] - Filter by repository name
 * @returns {Promise<ScanResult[]>} Array of recent scan results
 * @throws {ApiError} When the request fails
 *
 * @example
 * const recentScans = await getRecentScans({ limit: 5 });
 * const completedScans = await getRecentScans({ status: 'completed' });
 */
export async function getRecentScans(options = {}) {
  const params = new URLSearchParams();

  if (options.limit) params.append('limit', options.limit.toString());
  if (options.status) params.append('status', options.status);
  if (options.repository) params.append('repository', options.repository);

  const queryString = params.toString();
  const endpoint = queryString ? `${ENDPOINTS.SCANS}?${queryString}` : ENDPOINTS.SCANS;

  const { data } = await apiClient.get(endpoint);
  return data;
}

/**
 * Fetches active security alerts for the dashboard.
 * Returns high-priority alerts that require attention.
 *
 * @param {Object} [options] - Query options
 * @param {number} [options.limit=10] - Maximum number of alerts to return
 * @param {string} [options.priority] - Filter by priority level
 * @param {boolean} [options.unacknowledgedOnly=false] - Only return unacknowledged alerts
 * @returns {Promise<{alerts: SecurityAlert[], total: number, unacknowledged: number}>}
 * @throws {ApiError} When the request fails
 *
 * @example
 * const { alerts, unacknowledged } = await getSecurityAlerts({ priority: 'P1_CRITICAL' });
 */
export async function getSecurityAlerts(options = {}) {
  const params = new URLSearchParams();

  if (options.limit) params.append('limit', options.limit.toString());
  if (options.priority) params.append('priority', options.priority);
  if (options.unacknowledgedOnly) params.append('unacknowledged_only', 'true');

  const queryString = params.toString();
  const endpoint = queryString ? `${ENDPOINTS.ALERTS}?${queryString}` : ENDPOINTS.ALERTS;

  const { data } = await apiClient.get(endpoint);
  return data;
}

/**
 * Fetches infrastructure health metrics.
 * Includes API health, GraphRAG status, LLM quota, and sandbox availability.
 *
 * @returns {Promise<SystemHealthMetrics>} System health metrics
 * @throws {ApiError} When the request fails
 *
 * @example
 * const health = await getSystemHealth();
 * if (health.overallStatus === 'degraded') {
 *   console.warn('System health is degraded');
 * }
 */
export async function getSystemHealth() {
  const { data } = await apiClient.get(ENDPOINTS.HEALTH);
  return data;
}

/**
 * Fetches usage and cost metrics for the dashboard.
 *
 * @param {Object} [options] - Query options
 * @param {string} [options.period='current'] - Billing period ('current' or 'previous')
 * @returns {Promise<CostMetrics>} Cost and usage metrics
 * @throws {ApiError} When the request fails
 *
 * @example
 * const cost = await getCostMetrics();
 * console.warn(`Budget used: ${cost.budgetUsed}%`);
 */
export async function getCostMetrics(options = {}) {
  const params = new URLSearchParams();

  if (options.period) params.append('period', options.period);

  const queryString = params.toString();
  const endpoint = queryString ? `${ENDPOINTS.COST}?${queryString}` : ENDPOINTS.COST;

  const { data } = await apiClient.get(endpoint);
  return data;
}

/**
 * Fetches all dashboard data in parallel for initial load.
 * More efficient than making individual requests.
 *
 * @returns {Promise<Object>} All dashboard data
 * @throws {ApiError} When any request fails
 *
 * @example
 * const { summary, agents, scans, alerts, health } = await getAllDashboardData();
 */
export async function getAllDashboardData() {
  const [summary, agents, scans, alerts, health] = await Promise.all([
    getMetricsSummary(),
    getAgentStatus(),
    getRecentScans({ limit: 10 }),
    getSecurityAlerts({ limit: 10 }),
    getSystemHealth(),
  ]);

  return {
    summary,
    agents,
    scans,
    alerts,
    health,
  };
}

/**
 * API error specific to dashboard operations
 */
export class DashboardApiError extends ApiError {
  constructor(message, status, details = null) {
    super(message, status, details);
    this.name = 'DashboardApiError';
  }
}

// Default export for convenience
export default {
  getMetricsSummary,
  getAgentStatus,
  getRecentScans,
  getSecurityAlerts,
  getSystemHealth,
  getCostMetrics,
  getAllDashboardData,
  DashboardApiError,
  ENDPOINTS,
};

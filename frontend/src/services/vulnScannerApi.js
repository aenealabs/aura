/**
 * Project Aura - Vulnerability Scanner API Service
 *
 * Client-side service for interacting with native vulnerability
 * scanning engine endpoints per ADR-084.
 *
 * @module services/vulnScannerApi
 */

import { apiClient } from './api';

// apiClient resolves to { data } and already prefixes /api/v1; callers here want the data itself
const get = async (url, config) => (await apiClient.get(url, config)).data;
const post = async (url, body) => (await apiClient.post(url, body)).data;

// API endpoints for Vulnerability Scanner
const ENDPOINTS = {
  // Scans
  SCANS: '/scanner/scans',
  SCAN_DETAIL: '/scanner/scans/:scanId',
  SCAN_LAUNCH: '/scanner/scans/launch',
  SCAN_CANCEL: '/scanner/scans/:scanId/cancel',

  // Findings
  FINDINGS: '/scanner/findings',
  FINDING_DETAIL: '/scanner/findings/:findingId',
  FINDING_ACTION: '/scanner/findings/:findingId/action',

  // Metrics
  FINDINGS_BY_SEVERITY: '/scanner/metrics/findings-by-severity',
  ACTIVE_SCANS: '/scanner/metrics/active-scans',
  TRUE_POSITIVE_RATE: '/scanner/metrics/true-positive-rate',
  LLM_TOKEN_SPEND: '/scanner/metrics/llm-token-spend',
  ALARM_STATUS: '/scanner/metrics/alarm-status',
  RECENT_ACTIVITY: '/scanner/metrics/recent-activity',
  FINDINGS_REQUIRING_APPROVAL: '/scanner/metrics/findings-requiring-approval',
  SCAN_DURATION_TREND: '/scanner/metrics/scan-duration-trend',
  STAGE_DURATION: '/scanner/metrics/stage-duration',
  FINDINGS_BY_CWE: '/scanner/metrics/findings-by-cwe',
  LLM_LATENCY: '/scanner/metrics/llm-latency',
  CONCURRENT_UTILIZATION: '/scanner/metrics/concurrent-utilization',
  CRITICAL_FINDINGS_TREND: '/scanner/metrics/critical-findings-trend',
  SCAN_QUEUE_DEPTH: '/scanner/metrics/scan-queue-depth',
  CANDIDATE_FUNNEL: '/scanner/metrics/candidate-funnel',
  FINDINGS_BY_LANGUAGE: '/scanner/metrics/findings-by-language',
  VERIFICATION_STATUS: '/scanner/metrics/verification-status',
  CLEANUP_ACTIVITY: '/scanner/metrics/cleanup-activity',
  SCAN_DEPTH_DISTRIBUTION: '/scanner/metrics/scan-depth-distribution',

  // Reports
  SARIF_DOWNLOAD: '/scanner/scans/:scanId/sarif',
};

/**
 * Get findings grouped by severity
 * @returns {Promise<Object>} severity counts and stacked bar data
 */
export async function getFindingsBySeverity() {
  return get(ENDPOINTS.FINDINGS_BY_SEVERITY);
}

/**
 * Get active scans with status
 * @returns {Promise<Object>} active scan count and details
 */
export async function getActiveScans() {
  return get(ENDPOINTS.ACTIVE_SCANS);
}

/**
 * Get true positive rate
 * @returns {Promise<Object>} rate percentage and trend
 */
export async function getTruePositiveRate() {
  return get(ENDPOINTS.TRUE_POSITIVE_RATE);
}

/**
 * Get LLM token spend metrics
 * @returns {Promise<Object>} daily and monthly token spend
 */
export async function getLLMTokenSpend() {
  return get(ENDPOINTS.LLM_TOKEN_SPEND);
}

/**
 * Get scanner alarm status
 * @returns {Promise<Object>} alarm status grid
 */
export async function getScannerAlarmStatus() {
  return get(ENDPOINTS.ALARM_STATUS);
}

/**
 * Get recent scan activity
 * @param {Object} params - Query parameters
 * @param {string} [params.sort_by] - Sort field
 * @param {string} [params.sort_order] - Sort direction
 * @param {string} [params.severity_filter] - Severity filter
 * @returns {Promise<Object>} activity feed data
 */
export async function getRecentScanActivity(params = {}) {
  // apiClient does not serialize params, so build the query string here
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null)
  ).toString();
  return get(query ? `${ENDPOINTS.RECENT_ACTIVITY}?${query}` : ENDPOINTS.RECENT_ACTIVITY);
}

/**
 * Get findings requiring HITL approval
 * @returns {Promise<Object>} count and finding list
 */
export async function getFindingsRequiringApproval() {
  return get(ENDPOINTS.FINDINGS_REQUIRING_APPROVAL);
}

/**
 * Get scan duration trend
 * @returns {Promise<Object>} time series duration data
 */
export async function getScanDurationTrend() {
  return get(ENDPOINTS.SCAN_DURATION_TREND);
}

/**
 * Get stage duration waterfall data
 * @returns {Promise<Object>} per-stage duration breakdown
 */
export async function getStageDuration() {
  return get(ENDPOINTS.STAGE_DURATION);
}

/**
 * Get findings by CWE category
 * @returns {Promise<Object>} CWE-grouped finding counts
 */
export async function getFindingsByCWE() {
  return get(ENDPOINTS.FINDINGS_BY_CWE);
}

/**
 * Get LLM latency percentiles
 * @returns {Promise<Object>} p50/p95/p99 latency data
 */
export async function getLLMLatency() {
  return get(ENDPOINTS.LLM_LATENCY);
}

/**
 * Get concurrent scan utilization
 * @returns {Promise<Object>} active vs max concurrent
 */
export async function getConcurrentUtilization() {
  return get(ENDPOINTS.CONCURRENT_UTILIZATION);
}

/**
 * Get 30-day critical findings trend
 * @returns {Promise<Object>} daily critical finding counts
 */
export async function getCriticalFindingsTrend() {
  return get(ENDPOINTS.CRITICAL_FINDINGS_TREND);
}

/**
 * Get scan queue depth
 * @returns {Promise<Object>} queued scan count
 */
export async function getScanQueueDepth() {
  return get(ENDPOINTS.SCAN_QUEUE_DEPTH);
}

/**
 * Get candidate filter funnel data
 * @returns {Promise<Object>} funnel stages and counts
 */
export async function getCandidateFunnel() {
  return get(ENDPOINTS.CANDIDATE_FUNNEL);
}

/**
 * Get findings by programming language
 * @returns {Promise<Object>} language distribution
 */
export async function getFindingsByLanguage() {
  return get(ENDPOINTS.FINDINGS_BY_LANGUAGE);
}

/**
 * Get verification status distribution
 * @returns {Promise<Object>} verification status counts
 */
export async function getVerificationStatus() {
  return get(ENDPOINTS.VERIFICATION_STATUS);
}

/**
 * Get cleanup activity data
 * @returns {Promise<Object>} cleanup bar chart data
 */
export async function getCleanupActivity() {
  return get(ENDPOINTS.CLEANUP_ACTIVITY);
}

/**
 * Get scan depth distribution
 * @returns {Promise<Object>} scan depth donut data
 */
export async function getScanDepthDistribution() {
  return get(ENDPOINTS.SCAN_DEPTH_DISTRIBUTION);
}

/**
 * Get scan detail
 * @param {string} scanId - Scan ID
 * @returns {Promise<Object>} full scan detail
 */
export async function getScanDetail(scanId) {
  return get(ENDPOINTS.SCAN_DETAIL.replace(':scanId', scanId));
}

/**
 * Get finding detail
 * @param {string} findingId - Finding ID
 * @returns {Promise<Object>} full finding detail
 */
export async function getFindingDetail(findingId) {
  return get(ENDPOINTS.FINDING_DETAIL.replace(':findingId', findingId));
}

/**
 * Launch a new scan
 * @param {Object} config - Scan configuration
 * @returns {Promise<Object>} created scan
 */
export async function launchScan(config) {
  return post(ENDPOINTS.SCAN_LAUNCH, config);
}

/**
 * Cancel a running scan
 * @param {string} scanId - Scan ID
 * @returns {Promise<Object>} cancellation result
 */
export async function cancelScan(scanId) {
  return post(ENDPOINTS.SCAN_CANCEL.replace(':scanId', scanId));
}

/**
 * Perform an action on a finding
 * @param {string} findingId - Finding ID
 * @param {Object} action - Action details (accept_fix, reject, false_positive, escalate)
 * @returns {Promise<Object>} action result
 */
export async function performFindingAction(findingId, action) {
  return post(
    ENDPOINTS.FINDING_ACTION.replace(':findingId', findingId),
    action
  );
}

/**
 * Download SARIF report for a scan
 * @param {string} scanId - Scan ID
 * @returns {Promise<Blob>} SARIF JSON file
 */
export async function downloadSARIF(scanId) {
  const sarif = await get(ENDPOINTS.SARIF_DOWNLOAD.replace(':scanId', scanId));
  const text = typeof sarif === 'string' ? sarif : JSON.stringify(sarif, null, 2);
  return new Blob([text], { type: 'application/sarif+json' });
}

// Re-export for convenience
export { ENDPOINTS as SCANNER_ENDPOINTS };

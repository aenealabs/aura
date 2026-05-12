/**
 * Project Aura - Top-Level Dashboard Metrics API Service.
 *
 * Backs the four top-level dashboard widgets (MTTR, AssetCriticality,
 * ComplianceDrift, InsiderRisk) that previously rendered inline mock
 * literals. Endpoint contracts are defined in
 * src/api/dashboard_metrics_endpoints.py.
 *
 * @module services/dashboardMetricsApi
 */

import { apiClient } from './api';

const ENDPOINTS = {
  MTTR: '/api/v1/dashboard/metrics/mttr',
  ASSET_CRITICALITY: '/api/v1/dashboard/metrics/asset-criticality',
  COMPLIANCE_DRIFT: '/api/v1/dashboard/metrics/compliance-drift',
  INSIDER_RISK: '/api/v1/dashboard/metrics/insider-risk',
  HEALTH: '/api/v1/dashboard/metrics/health',
};

/**
 * @typedef {Object} MTTRMetrics
 * @property {number} current_mttr_hours
 * @property {number} target_mttr_hours
 * @property {number} previous_mttr_hours
 * @property {number} critical_mttr_hours
 * @property {number} high_mttr_hours
 * @property {number} medium_mttr_hours
 * @property {number} open_count
 * @property {number} closed_last_7d
 */

/**
 * Get MTTR (mean time to remediate) rollup metrics.
 * @returns {Promise<MTTRMetrics>}
 */
export async function getMTTR() {
  return apiClient.get(ENDPOINTS.MTTR);
}

/**
 * @typedef {Object} AssetCriticalityEntry
 * @property {string} asset_id
 * @property {number} criticality_score 0-10
 * @property {string} data_classification 'Restricted'|'Confidential'|'Internal'|'Public'
 * @property {string} business_owner
 */

/**
 * Get top-N assets by criticality score.
 * @returns {Promise<{assets: AssetCriticalityEntry[]}>}
 */
export async function getAssetCriticality() {
  return apiClient.get(ENDPOINTS.ASSET_CRITICALITY);
}

/**
 * @typedef {Object} ComplianceFramework
 * @property {string} name
 * @property {number} passing
 * @property {number} failing
 * @property {number} total
 *
 * @typedef {Object} ComplianceControlFailure
 * @property {string} id
 * @property {string} control
 * @property {string} framework
 * @property {string} description
 * @property {number} daysOpen
 */

/**
 * Get per-framework compliance posture + recent control failures.
 * @returns {Promise<{frameworks: ComplianceFramework[], recentFailures: ComplianceControlFailure[]}>}
 */
export async function getComplianceDrift() {
  return apiClient.get(ENDPOINTS.COMPLIANCE_DRIFT);
}

/**
 * @typedef {Object} InsiderRiskMetrics
 * @property {number} elevated_count
 * @property {number} high_risk_count
 * @property {number} medium_risk_count
 * @property {number} total_monitored
 * @property {string} trend 'up'|'down'|'stable'
 * @property {number} trend_delta
 * @property {?string} last_escalation ISO 8601 or null
 */

/**
 * Get insider-risk rollup (tier counts + trend).
 * @returns {Promise<InsiderRiskMetrics>}
 */
export async function getInsiderRisk() {
  return apiClient.get(ENDPOINTS.INSIDER_RISK);
}

export { ENDPOINTS as DASHBOARD_METRICS_ENDPOINTS };

/**
 * Project Aura - Internal System Health API Service.
 *
 * Backs the HealthCheckModal. The endpoint contract lives in
 * src/api/system_health_endpoints.py and currently returns an honest
 * zero-state body until real per-service probes land.
 *
 * @module services/systemHealthApi
 */

import { apiClient } from './api';

const ENDPOINT = '/api/v1/system-health';

/**
 * @typedef {Object} ServiceMetric
 * @property {string} label
 * @property {string} value
 *
 * @typedef {Object} ServiceStatus
 * @property {string} name
 * @property {'healthy'|'degraded'|'unhealthy'|'unknown'} status
 * @property {ServiceMetric[]} metrics
 *
 * @typedef {Object} CategoryHealth
 * @property {'healthy'|'degraded'|'unhealthy'|'unknown'} status
 * @property {ServiceStatus[]} services
 *
 * @typedef {Object} SystemHealth
 * @property {'healthy'|'degraded'|'unhealthy'|'unknown'} overallStatus
 * @property {string} summary
 * @property {number} healthyServices
 * @property {number} degradedServices
 * @property {number} unhealthyServices
 * @property {string} lastUpdated ISO 8601
 * @property {Record<string, CategoryHealth>} categories
 */

/**
 * Get internal system services health rollup.
 * @returns {Promise<SystemHealth>}
 */
export async function getSystemHealth() {
  return apiClient.get(ENDPOINT);
}

export { ENDPOINT as SYSTEM_HEALTH_ENDPOINT };

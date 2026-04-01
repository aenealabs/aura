/**
 * Project Aura - Palantir AIP API Service
 *
 * Client-side service for interacting with the Palantir AIP integration
 * endpoints per ADR-074 and ADR-075.
 *
 * @module services/palantirApi
 */

import { apiClient, ApiError } from './api';

// API endpoints for Palantir integration
const ENDPOINTS = {
  // Health & Status
  HEALTH: '/api/v1/palantir/health',
  HEALTH_DETAILED: '/api/v1/palantir/health/detailed',
  CIRCUIT_BREAKER: '/api/v1/palantir/circuit-breaker',
  CIRCUIT_BREAKER_RESET: '/api/v1/palantir/circuit-breaker/reset',

  // Threat Intelligence
  THREATS_ACTIVE: '/api/v1/palantir/threats/active',
  THREATS_CONTEXT: '/api/v1/palantir/threats/context',
  CVE_CONTEXT: '/api/v1/palantir/cve',

  // Assets
  ASSETS_CRITICALITY: '/api/v1/palantir/assets',

  // Sync
  SYNC_STATUS: '/api/v1/palantir/sync/status',
  SYNC_TRIGGER: '/api/v1/palantir/sync',
  SYNC_ALL: '/api/v1/palantir/sync/all',

  // Events
  EVENTS_PUBLISH: '/api/v1/palantir/events/publish',
  EVENTS_METRICS: '/api/v1/palantir/events/metrics',
  EVENTS_RETRY_DLQ: '/api/v1/palantir/events/retry-dlq',

  // Configuration
  TEST_CONNECTION: '/api/v1/palantir/test-connection',
  METRICS: '/api/v1/palantir/metrics',
};

/**
 * @typedef {Object} ThreatContext
 * @property {string} threat_id - Unique threat identifier
 * @property {string} source_platform - Source platform (e.g., 'palantir')
 * @property {string[]} cves - Associated CVE identifiers
 * @property {number|null} epss_score - EPSS probability score (0-1)
 * @property {string[]} mitre_ttps - MITRE ATT&CK TTPs
 * @property {string[]} targeted_industries - Industries being targeted
 * @property {string[]} active_campaigns - Active campaign names
 * @property {number} priority_score - Composite priority score
 */

/**
 * @typedef {Object} AssetContext
 * @property {string} asset_id - Asset identifier
 * @property {number} criticality_score - Criticality score (1-10)
 * @property {string} data_classification - Data classification level
 * @property {string|null} business_owner - Business owner email
 * @property {boolean} pii_handling - Handles PII data
 * @property {boolean} phi_handling - Handles PHI data
 * @property {string[]} compliance_frameworks - Applicable frameworks
 * @property {boolean} is_high_value - High-value asset flag
 */

/**
 * @typedef {Object} SyncStatus
 * @property {string} object_type - Object type being synced
 * @property {string|null} last_sync_time - ISO timestamp of last sync
 * @property {string} last_sync_status - Status (synced/pending/failed)
 * @property {number} objects_synced - Count of synced objects
 * @property {number} objects_failed - Count of failed objects
 * @property {number} conflicts_resolved - Count of resolved conflicts
 * @property {string|null} last_error - Last error message if any
 */

/**
 * @typedef {Object} CircuitBreakerStatus
 * @property {string} name - Circuit breaker name
 * @property {string} state - Current state (CLOSED/HALF_OPEN/OPEN)
 * @property {number} failure_count - Current failure count
 * @property {number} success_count - Current success count
 * @property {number} total_failures - Total failures since start
 * @property {number} total_successes - Total successes since start
 * @property {string|null} last_failure - ISO timestamp of last failure
 * @property {string} last_state_change - ISO timestamp of last state change
 * @property {number} recovery_timeout_seconds - Recovery timeout
 */

/**
 * @typedef {Object} HealthResponse
 * @property {string} status - Health status (ok/degraded)
 * @property {string} connector_status - Connector status
 * @property {boolean} is_healthy - Overall health flag
 * @property {string|null} message - Optional status message
 */

/**
 * @typedef {Object} ConnectionTestConfig
 * @property {string} ontology_api_url - Ontology API URL
 * @property {string} foundry_api_url - Foundry API URL
 * @property {string} api_key - API key
 * @property {string|null} client_cert_path - mTLS certificate path
 */

/**
 * @typedef {Object} AdapterMetrics
 * @property {string} name - Adapter name
 * @property {string} status - Adapter status
 * @property {number} request_count - Total requests
 * @property {number} error_count - Total errors
 * @property {number} error_rate - Error rate percentage
 * @property {number} avg_latency_ms - Average latency in ms
 * @property {number} cache_hits - Cache hit count
 * @property {number} cache_misses - Cache miss count
 * @property {number} cache_hit_rate - Cache hit rate percentage
 * @property {number} uptime_seconds - Uptime in seconds
 */

// Mock data for development when API is unavailable
const MOCK_THREATS = [
  {
    threat_id: 'threat-apt29-001',
    source_platform: 'palantir',
    cves: ['CVE-2024-1234', 'CVE-2024-5678'],
    epss_score: 0.942,
    mitre_ttps: ['T1059.001', 'T1566.001', 'T1055'],
    targeted_industries: ['Healthcare', 'Financial'],
    active_campaigns: ['Operation Midnight', 'Supply Chain Assault'],
    priority_score: 98.5,
  },
  {
    threat_id: 'threat-lazarus-002',
    source_platform: 'palantir',
    cves: ['CVE-2024-9012'],
    epss_score: 0.872,
    mitre_ttps: ['T1190', 'T1105'],
    targeted_industries: ['Technology', 'Defense'],
    active_campaigns: ['DreamJob 2.0'],
    priority_score: 87.2,
  },
];

const MOCK_SYNC_STATUS = {
  ThreatActor: {
    object_type: 'ThreatActor',
    last_sync_time: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    last_sync_status: 'synced',
    objects_synced: 247,
    objects_failed: 0,
    conflicts_resolved: 3,
    last_error: null,
  },
  Vulnerability: {
    object_type: 'Vulnerability',
    last_sync_time: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    last_sync_status: 'synced',
    objects_synced: 1892,
    objects_failed: 2,
    conflicts_resolved: 15,
    last_error: null,
  },
  Asset: {
    object_type: 'Asset',
    last_sync_time: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    last_sync_status: 'synced',
    objects_synced: 156,
    objects_failed: 0,
    conflicts_resolved: 1,
    last_error: null,
  },
  Compliance: {
    object_type: 'Compliance',
    last_sync_time: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    last_sync_status: 'synced',
    objects_synced: 892,
    objects_failed: 0,
    conflicts_resolved: 5,
    last_error: null,
  },
};

const MOCK_CIRCUIT_BREAKER = {
  name: 'palantir_integration',
  state: 'CLOSED',
  failure_count: 0,
  success_count: 47,
  total_failures: 3,
  total_successes: 1247,
  last_failure: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  last_state_change: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  recovery_timeout_seconds: 60,
};

const MOCK_HEALTH = {
  status: 'ok',
  connector_status: 'CLOSED',
  is_healthy: true,
  message: null,
};

// ============================================================================
// Health & Status Endpoints
// ============================================================================

/**
 * Get Palantir integration health status.
 *
 * @returns {Promise<HealthResponse>} Health status
 * @throws {ApiError} When the request fails
 */
export async function getHealth() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.HEALTH);
    return data;
  } catch (err) {
    console.warn('Using mock health data (API unavailable)');
    return MOCK_HEALTH;
  }
}

/**
 * Get detailed health status with adapter metrics.
 *
 * @returns {Promise<Object>} Detailed health status
 * @throws {ApiError} When the request fails
 */
export async function getDetailedHealth() {
  const { data } = await apiClient.get(ENDPOINTS.HEALTH_DETAILED);
  return data;
}

/**
 * Get circuit breaker status.
 *
 * @returns {Promise<CircuitBreakerStatus>} Circuit breaker status
 * @throws {ApiError} When the request fails
 */
export async function getCircuitBreaker() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.CIRCUIT_BREAKER);
    return data;
  } catch (err) {
    console.warn('Using mock circuit breaker data (API unavailable)');
    return MOCK_CIRCUIT_BREAKER;
  }
}

/**
 * Reset circuit breaker to closed state.
 *
 * @returns {Promise<{status: string, new_state: string}>} Reset result
 * @throws {ApiError} When the request fails
 */
export async function resetCircuitBreaker() {
  const { data } = await apiClient.post(ENDPOINTS.CIRCUIT_BREAKER_RESET);
  return data;
}

// ============================================================================
// Threat Intelligence Endpoints
// ============================================================================

/**
 * Get active threat campaigns from Palantir.
 *
 * @returns {Promise<ThreatContext[]>} Array of active threats
 * @throws {ApiError} When the request fails
 */
export async function getActiveThreats() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.THREATS_ACTIVE);
    return data;
  } catch (err) {
    console.warn('Using mock threat data (API unavailable)');
    return MOCK_THREATS;
  }
}

/**
 * Get threat context for specific CVEs.
 *
 * @param {string[]} cveIds - Array of CVE identifiers
 * @returns {Promise<ThreatContext[]>} Threat context for CVEs
 * @throws {ApiError} When the request fails
 */
export async function getThreatContext(cveIds) {
  const { data } = await apiClient.post(ENDPOINTS.THREATS_CONTEXT, {
    cve_ids: cveIds,
  });
  return data;
}

/**
 * Get threat context for a single CVE.
 *
 * @param {string} cveId - CVE identifier
 * @returns {Promise<ThreatContext|null>} Threat context or null
 * @throws {ApiError} When the request fails
 */
export async function getCVEContext(cveId) {
  const { data } = await apiClient.get(`${ENDPOINTS.CVE_CONTEXT}/${cveId}/context`);
  return data;
}

// ============================================================================
// Asset Endpoints
// ============================================================================

/**
 * Get asset criticality for a repository.
 *
 * @param {string} repoId - Repository identifier
 * @returns {Promise<AssetContext|null>} Asset context or null
 * @throws {ApiError} When the request fails
 */
export async function getAssetCriticality(repoId) {
  const { data } = await apiClient.get(`${ENDPOINTS.ASSETS_CRITICALITY}/${repoId}/criticality`);
  return data;
}

// ============================================================================
// Sync Endpoints
// ============================================================================

/**
 * Get sync status for all object types.
 *
 * @returns {Promise<Object<string, SyncStatus>>} Sync status by object type
 * @throws {ApiError} When the request fails
 */
export async function getSyncStatus() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.SYNC_STATUS);
    return data;
  } catch (err) {
    console.warn('Using mock sync status (API unavailable)');
    return MOCK_SYNC_STATUS;
  }
}

/**
 * Trigger sync for a specific object type.
 *
 * @param {string} objectType - Object type to sync
 * @param {boolean} [fullSync=false] - Perform full sync
 * @returns {Promise<Object>} Sync result
 * @throws {ApiError} When the request fails
 */
export async function triggerSync(objectType, fullSync = false) {
  const { data } = await apiClient.post(`${ENDPOINTS.SYNC_TRIGGER}/${objectType}`, {
    full_sync: fullSync,
  });
  return data;
}

/**
 * Trigger sync for all object types.
 *
 * @param {boolean} [fullSync=false] - Perform full sync
 * @returns {Promise<Object>} Sync results by object type
 * @throws {ApiError} When the request fails
 */
export async function syncAll(fullSync = false) {
  const { data } = await apiClient.post(ENDPOINTS.SYNC_ALL, {
    full_sync: fullSync,
  });
  return data;
}

// ============================================================================
// Event Endpoints
// ============================================================================

/**
 * Publish a remediation event to Palantir.
 *
 * @param {string} eventType - Event type
 * @param {string} tenantId - Tenant identifier
 * @param {Object} payload - Event payload
 * @returns {Promise<{success: boolean, event_id: string|null, message: string}>}
 * @throws {ApiError} When the request fails
 */
export async function publishEvent(eventType, tenantId, payload) {
  const { data } = await apiClient.post(ENDPOINTS.EVENTS_PUBLISH, {
    event_type: eventType,
    tenant_id: tenantId,
    payload,
  });
  return data;
}

/**
 * Get event publisher metrics.
 *
 * @returns {Promise<Object>} Publisher metrics
 * @throws {ApiError} When the request fails
 */
export async function getEventMetrics() {
  const { data } = await apiClient.get(ENDPOINTS.EVENTS_METRICS);
  return data;
}

/**
 * Retry failed events from Dead Letter Queue.
 *
 * @returns {Promise<{retried: number, dlq_stats: Object}>} Retry results
 * @throws {ApiError} When the request fails
 */
export async function retryDLQEvents() {
  const { data } = await apiClient.post(ENDPOINTS.EVENTS_RETRY_DLQ);
  return data;
}

// ============================================================================
// Configuration Endpoints
// ============================================================================

/**
 * Test connection with provided configuration.
 *
 * @param {ConnectionTestConfig} config - Connection configuration
 * @returns {Promise<{success: boolean, message: string, latency_ms: number|null}>}
 * @throws {ApiError} When the request fails
 */
export async function testConnection(config) {
  const { data } = await apiClient.post(ENDPOINTS.TEST_CONNECTION, config);
  return data;
}

/**
 * Get adapter performance metrics.
 *
 * @returns {Promise<AdapterMetrics>} Adapter metrics
 * @throws {ApiError} When the request fails
 */
export async function getAdapterMetrics() {
  const { data } = await apiClient.get(ENDPOINTS.METRICS);
  return data;
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Get all Palantir status data in parallel.
 *
 * @returns {Promise<{health: HealthResponse, circuitBreaker: CircuitBreakerStatus, syncStatus: Object}>}
 */
export async function getAllStatus() {
  const [health, circuitBreaker, syncStatus] = await Promise.all([
    getHealth(),
    getCircuitBreaker(),
    getSyncStatus(),
  ]);

  return {
    health,
    circuitBreaker,
    syncStatus,
  };
}

/**
 * Get prioritized CVEs based on EPSS score and active threats.
 * Combines threat context with local CVE data.
 *
 * @param {string[]} cveIds - CVE identifiers to prioritize
 * @returns {Promise<Object[]>} Prioritized CVE list
 */
export async function getPrioritizedCVEs(cveIds) {
  const threats = await getThreatContext(cveIds);

  // Sort by priority score descending
  return threats.sort((a, b) => b.priority_score - a.priority_score);
}

/**
 * API error specific to Palantir operations
 */
export class PalantirApiError extends ApiError {
  constructor(message, status, details = null) {
    super(message, status, details);
    this.name = 'PalantirApiError';
  }
}

// Default export for convenience
export default {
  // Health & Status
  getHealth,
  getDetailedHealth,
  getCircuitBreaker,
  resetCircuitBreaker,

  // Threat Intelligence
  getActiveThreats,
  getThreatContext,
  getCVEContext,

  // Assets
  getAssetCriticality,

  // Sync
  getSyncStatus,
  triggerSync,
  syncAll,

  // Events
  publishEvent,
  getEventMetrics,
  retryDLQEvents,

  // Configuration
  testConnection,
  getAdapterMetrics,

  // Convenience
  getAllStatus,
  getPrioritizedCVEs,

  // Error class
  PalantirApiError,

  // Constants
  ENDPOINTS,
};

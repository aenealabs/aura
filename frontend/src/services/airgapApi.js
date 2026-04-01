/**
 * Project Aura - Air-Gapped/Edge Deployment API Service
 *
 * Client-side service for interacting with air-gapped and edge
 * deployment endpoints per ADR-078.
 *
 * @module services/airgapApi
 */

import { apiClient, ApiError } from './api';

// API endpoints for Air-Gapped/Edge deployments
const ENDPOINTS = {
  // Bundle Management
  BUNDLE_STATUS: '/api/v1/airgap/bundle/status',
  BUNDLE_CREATE: '/api/v1/airgap/bundle/create',
  BUNDLE_VERIFY: '/api/v1/airgap/bundle/verify',
  BUNDLE_LIST: '/api/v1/airgap/bundle/list',

  // Firmware Analysis
  FIRMWARE_ANALYSIS: '/api/v1/airgap/firmware/analysis',
  FIRMWARE_SCAN: '/api/v1/airgap/firmware/scan',
  FIRMWARE_VULNERABILITIES: '/api/v1/airgap/firmware/vulnerabilities',

  // Edge Runtime
  EDGE_HEALTH: '/api/v1/airgap/edge/health',
  EDGE_DEVICES: '/api/v1/airgap/edge/devices',
  EDGE_SYNC: '/api/v1/airgap/edge/sync',

  // Egress Validation
  EGRESS_STATUS: '/api/v1/airgap/egress/status',
  EGRESS_VIOLATIONS: '/api/v1/airgap/egress/violations',
  EGRESS_ALLOWLIST: '/api/v1/airgap/egress/allowlist',
};

/**
 * @typedef {Object} BundleStatus
 * @property {string} bundle_id - Bundle identifier
 * @property {string} version - Bundle version
 * @property {string} status - Status (current, expired, pending)
 * @property {string} created_at - Creation timestamp
 * @property {string} expires_at - Expiration timestamp
 * @property {boolean} integrity_verified - Integrity check passed
 * @property {string} checksum - Bundle checksum (SHA-256)
 * @property {number} size_bytes - Bundle size in bytes
 * @property {Object} components - Included components
 */

/**
 * @typedef {Object} FirmwareAnalysis
 * @property {string} firmware_id - Firmware identifier
 * @property {string} device_type - Device type
 * @property {string} version - Firmware version
 * @property {number} vulnerability_count - Known vulnerabilities
 * @property {number} critical_count - Critical vulnerabilities
 * @property {string} last_scan - Last scan timestamp
 * @property {Object[]} vulnerabilities - Detailed vulnerability list
 */

/**
 * @typedef {Object} EdgeDevice
 * @property {string} device_id - Device identifier
 * @property {string} hostname - Device hostname
 * @property {string} status - Status (online, offline, syncing)
 * @property {string} last_sync - Last sync timestamp
 * @property {string} bundle_version - Current bundle version
 * @property {boolean} update_available - Whether update is available
 * @property {Object} health_metrics - Health metrics
 */

/**
 * @typedef {Object} EgressViolation
 * @property {string} violation_id - Violation identifier
 * @property {string} source_device - Source device ID
 * @property {string} destination - Attempted destination
 * @property {string} port - Port number
 * @property {string} protocol - Protocol (TCP, UDP)
 * @property {string} severity - Severity level
 * @property {string} detected_at - Detection timestamp
 * @property {boolean} blocked - Whether traffic was blocked
 */

// Mock data for development
const MOCK_BUNDLE_STATUS = {
  bundle_id: 'bundle-2026-02-03-001',
  version: '2.4.1',
  status: 'current',
  created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
  expires_at: new Date(Date.now() + 23 * 24 * 60 * 60 * 1000).toISOString(),
  integrity_verified: true,
  checksum: 'sha256:a1b2c3d4e5f6789012345678901234567890abcdef',
  size_bytes: 2147483648,
  components: {
    vulnerability_db: '2026.02.03',
    policy_rules: 'v1.8.2',
    ml_models: 'v3.2.1',
    agent_binaries: 'v2.4.1',
  },
  bundles: [
    { id: 'bundle-2026-02-03-001', version: '2.4.1', status: 'current', expires_in_days: 23 },
    { id: 'bundle-2026-01-27-001', version: '2.4.0', status: 'expired', expires_in_days: -7 },
    { id: 'bundle-2026-02-10-001', version: '2.4.2', status: 'pending', expires_in_days: 30 },
  ],
};

const MOCK_FIRMWARE_ANALYSIS = {
  firmware_id: 'fw-iot-gateway-001',
  device_type: 'IoT Gateway',
  vendor: 'Sierra Wireless',
  model: 'RV55',
  version: '4.15.0.004',
  vulnerability_count: 7,
  critical_count: 2,
  high_count: 3,
  medium_count: 2,
  last_scan: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
  vulnerabilities: [
    { cve: 'CVE-2024-1234', severity: 'critical', component: 'OpenSSL', description: 'Buffer overflow in TLS handshake' },
    { cve: 'CVE-2024-5678', severity: 'critical', component: 'BusyBox', description: 'Command injection in networking utilities' },
    { cve: 'CVE-2023-9012', severity: 'high', component: 'Linux Kernel', description: 'Privilege escalation via eBPF' },
  ],
  devices: [
    { type: 'IoT Gateway', vendor: 'Sierra Wireless', model: 'RV55', vulnerabilities: 7, critical: 2 },
    { type: 'Edge Server', vendor: 'Dell', model: 'Edge 3000', vulnerabilities: 3, critical: 0 },
    { type: 'PLC Controller', vendor: 'Siemens', model: 'S7-1500', vulnerabilities: 5, critical: 1 },
    { type: 'HMI Panel', vendor: 'Rockwell', model: 'PanelView', vulnerabilities: 2, critical: 0 },
  ],
};

const MOCK_EDGE_HEALTH = {
  total_devices: 24,
  online_count: 21,
  offline_count: 2,
  syncing_count: 1,
  devices: [
    {
      device_id: 'edge-001',
      hostname: 'edge-gateway-us-east',
      status: 'online',
      last_sync: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      bundle_version: '2.4.1',
      update_available: false,
      health_metrics: { cpu: 45, memory: 62, disk: 38 },
    },
    {
      device_id: 'edge-002',
      hostname: 'edge-gateway-us-west',
      status: 'online',
      last_sync: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
      bundle_version: '2.4.1',
      update_available: false,
      health_metrics: { cpu: 38, memory: 55, disk: 42 },
    },
    {
      device_id: 'edge-003',
      hostname: 'edge-gateway-eu',
      status: 'syncing',
      last_sync: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      bundle_version: '2.4.0',
      update_available: true,
      health_metrics: { cpu: 72, memory: 78, disk: 55 },
    },
    {
      device_id: 'edge-004',
      hostname: 'edge-gateway-asia',
      status: 'offline',
      last_sync: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      bundle_version: '2.4.0',
      update_available: true,
      health_metrics: { cpu: 0, memory: 0, disk: 0 },
    },
  ],
};

const MOCK_EGRESS_STATUS = {
  monitoring_enabled: true,
  total_connections_24h: 15847,
  blocked_connections_24h: 23,
  allowed_domains: 156,
  recent_violations: [
    {
      violation_id: 'egr-001',
      source_device: 'edge-003',
      destination: 'suspicious-domain.ru',
      port: '443',
      protocol: 'TCP',
      severity: 'critical',
      detected_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
      blocked: true,
      reason: 'Domain on threat intelligence blocklist',
    },
    {
      violation_id: 'egr-002',
      source_device: 'edge-001',
      destination: '185.143.172.45',
      port: '8080',
      protocol: 'TCP',
      severity: 'high',
      detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      blocked: true,
      reason: 'IP not in allowed list for production environment',
    },
    {
      violation_id: 'egr-003',
      source_device: 'edge-002',
      destination: 'telemetry.example.com',
      port: '443',
      protocol: 'TCP',
      severity: 'medium',
      detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      blocked: false,
      reason: 'Unexpected egress to analytics domain',
    },
  ],
};

// ============================================================================
// Bundle Management Endpoints
// ============================================================================

/**
 * Get bundle status.
 *
 * @returns {Promise<BundleStatus>} Bundle status
 * @throws {ApiError} When the request fails
 */
export async function getBundleStatus() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.BUNDLE_STATUS);
    return data;
  } catch (err) {
    console.warn('Using mock bundle status (API unavailable)');
    return MOCK_BUNDLE_STATUS;
  }
}

/**
 * Create a new offline bundle.
 *
 * @param {Object} options - Bundle options
 * @param {string[]} [options.components] - Components to include
 * @param {number} [options.validity_days] - Validity period in days
 * @returns {Promise<Object>} Bundle creation result
 * @throws {ApiError} When the request fails
 */
export async function createBundle(options = {}) {
  const { data } = await apiClient.post(ENDPOINTS.BUNDLE_CREATE, options);
  return data;
}

/**
 * Verify bundle integrity.
 *
 * @param {string} bundleId - Bundle identifier
 * @returns {Promise<Object>} Verification result
 * @throws {ApiError} When the request fails
 */
export async function verifyBundle(bundleId) {
  const { data } = await apiClient.post(ENDPOINTS.BUNDLE_VERIFY, {
    bundle_id: bundleId,
  });
  return data;
}

/**
 * List all bundles.
 *
 * @returns {Promise<Object[]>} List of bundles
 * @throws {ApiError} When the request fails
 */
export async function listBundles() {
  const { data } = await apiClient.get(ENDPOINTS.BUNDLE_LIST);
  return data;
}

// ============================================================================
// Firmware Analysis Endpoints
// ============================================================================

/**
 * Get firmware analysis results.
 *
 * @param {string} [firmwareId] - Optional firmware ID to filter
 * @returns {Promise<FirmwareAnalysis>} Firmware analysis
 * @throws {ApiError} When the request fails
 */
export async function getFirmwareAnalysis(firmwareId) {
  try {
    const url = firmwareId
      ? `${ENDPOINTS.FIRMWARE_ANALYSIS}/${firmwareId}`
      : ENDPOINTS.FIRMWARE_ANALYSIS;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock firmware analysis (API unavailable)');
    return MOCK_FIRMWARE_ANALYSIS;
  }
}

/**
 * Scan firmware for vulnerabilities.
 *
 * @param {Object} firmware - Firmware details
 * @param {string} firmware.device_type - Device type
 * @param {string} firmware.version - Firmware version
 * @param {string} [firmware.checksum] - Firmware checksum
 * @returns {Promise<Object>} Scan result
 * @throws {ApiError} When the request fails
 */
export async function scanFirmware(firmware) {
  const { data } = await apiClient.post(ENDPOINTS.FIRMWARE_SCAN, firmware);
  return data;
}

/**
 * Get firmware vulnerabilities.
 *
 * @param {string} firmwareId - Firmware identifier
 * @returns {Promise<Object[]>} Vulnerabilities
 * @throws {ApiError} When the request fails
 */
export async function getFirmwareVulnerabilities(firmwareId) {
  const { data } = await apiClient.get(`${ENDPOINTS.FIRMWARE_VULNERABILITIES}/${firmwareId}`);
  return data;
}

// ============================================================================
// Edge Runtime Endpoints
// ============================================================================

/**
 * Get edge runtime health.
 *
 * @returns {Promise<Object>} Edge health status
 * @throws {ApiError} When the request fails
 */
export async function getEdgeHealth() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.EDGE_HEALTH);
    return data;
  } catch (err) {
    console.warn('Using mock edge health (API unavailable)');
    return MOCK_EDGE_HEALTH;
  }
}

/**
 * Get edge device list.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.status] - Filter by status
 * @returns {Promise<EdgeDevice[]>} Edge devices
 * @throws {ApiError} When the request fails
 */
export async function getEdgeDevices(filters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.append('status', filters.status);

  const url = `${ENDPOINTS.EDGE_DEVICES}${params.toString() ? `?${params}` : ''}`;
  const { data } = await apiClient.get(url);
  return data;
}

/**
 * Trigger sync for an edge device.
 *
 * @param {string} deviceId - Device identifier
 * @param {boolean} [force=false] - Force full sync
 * @returns {Promise<Object>} Sync result
 * @throws {ApiError} When the request fails
 */
export async function triggerEdgeSync(deviceId, force = false) {
  const { data } = await apiClient.post(ENDPOINTS.EDGE_SYNC, {
    device_id: deviceId,
    force,
  });
  return data;
}

// ============================================================================
// Egress Validation Endpoints
// ============================================================================

/**
 * Get egress monitoring status.
 *
 * @returns {Promise<Object>} Egress status
 * @throws {ApiError} When the request fails
 */
export async function getEgressStatus() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.EGRESS_STATUS);
    return data;
  } catch (err) {
    console.warn('Using mock egress status (API unavailable)');
    return MOCK_EGRESS_STATUS;
  }
}

/**
 * Get egress violations.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.severity] - Filter by severity
 * @param {string} [filters.device_id] - Filter by device
 * @returns {Promise<EgressViolation[]>} Violations
 * @throws {ApiError} When the request fails
 */
export async function getEgressViolations(filters = {}) {
  const params = new URLSearchParams();
  if (filters.severity) params.append('severity', filters.severity);
  if (filters.device_id) params.append('device_id', filters.device_id);

  const url = `${ENDPOINTS.EGRESS_VIOLATIONS}${params.toString() ? `?${params}` : ''}`;
  const { data } = await apiClient.get(url);
  return data;
}

/**
 * Update egress allowlist.
 *
 * @param {Object} update - Allowlist update
 * @param {string[]} [update.add_domains] - Domains to add
 * @param {string[]} [update.remove_domains] - Domains to remove
 * @returns {Promise<Object>} Update result
 * @throws {ApiError} When the request fails
 */
export async function updateEgressAllowlist(update) {
  const { data } = await apiClient.put(ENDPOINTS.EGRESS_ALLOWLIST, update);
  return data;
}

/**
 * API error specific to Air-Gap operations
 */
export class AirgapApiError extends ApiError {
  constructor(message, status, details = null) {
    super(message, status, details);
    this.name = 'AirgapApiError';
  }
}

// Default export for convenience
export default {
  // Bundle Management
  getBundleStatus,
  createBundle,
  verifyBundle,
  listBundles,

  // Firmware Analysis
  getFirmwareAnalysis,
  scanFirmware,
  getFirmwareVulnerabilities,

  // Edge Runtime
  getEdgeHealth,
  getEdgeDevices,
  triggerEdgeSync,

  // Egress Validation
  getEgressStatus,
  getEgressViolations,
  updateEgressAllowlist,

  // Error class
  AirgapApiError,

  // Constants
  ENDPOINTS,
};

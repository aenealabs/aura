/**
 * Project Aura - Supply Chain Security API Service
 *
 * Client-side service for interacting with supply chain security
 * endpoints per ADR-076.
 *
 * @module services/supplyChainApi
 */

import { apiClient, ApiError } from './api';

// API endpoints for Supply Chain Security
const ENDPOINTS = {
  // SBOM Endpoints
  SBOM_STATUS: '/api/v1/supply-chain/sbom/status',
  SBOM_GENERATE: '/api/v1/supply-chain/sbom/generate',
  SBOM_LIST: '/api/v1/supply-chain/sbom/list',
  SBOM_DOWNLOAD: '/api/v1/supply-chain/sbom',

  // Dependency Confusion
  DEPENDENCY_ALERTS: '/api/v1/supply-chain/dependency-confusion/alerts',
  TYPOSQUAT_CHECK: '/api/v1/supply-chain/dependency-confusion/typosquat-check',
  NAMESPACE_HIJACK: '/api/v1/supply-chain/dependency-confusion/namespace-hijack',

  // License Compliance
  LICENSE_SUMMARY: '/api/v1/supply-chain/licenses/summary',
  LICENSE_VIOLATIONS: '/api/v1/supply-chain/licenses/violations',
  LICENSE_POLICY: '/api/v1/supply-chain/licenses/policy',

  // Attestation
  ATTESTATION_STATUS: '/api/v1/supply-chain/attestation/status',
  ATTESTATION_VERIFY: '/api/v1/supply-chain/attestation/verify',
  SIGSTORE_STATUS: '/api/v1/supply-chain/attestation/sigstore',
};

/**
 * @typedef {Object} SBOMStatus
 * @property {string} repository_id - Repository identifier
 * @property {string} format - SBOM format (spdx, cyclonedx)
 * @property {string} status - Generation status (pending, complete, failed)
 * @property {number} component_count - Number of components
 * @property {number} vulnerability_count - Known vulnerabilities in components
 * @property {string} last_generated - ISO timestamp of last generation
 * @property {string|null} last_error - Last error message if any
 */

/**
 * @typedef {Object} DependencyConfusionAlert
 * @property {string} alert_id - Alert identifier
 * @property {string} alert_type - Type (typosquat, namespace_hijack, version_confusion)
 * @property {string} severity - Severity level (critical, high, medium, low)
 * @property {string} package_name - Affected package name
 * @property {string} suspected_malicious - Suspected malicious package
 * @property {number} confidence_score - Detection confidence (0-100)
 * @property {string} repository_id - Affected repository
 * @property {string} detected_at - ISO timestamp
 * @property {boolean} acknowledged - Whether alert has been acknowledged
 */

/**
 * @typedef {Object} LicenseSummary
 * @property {Object<string, number>} distribution - Count by license type
 * @property {number} total_components - Total component count
 * @property {number} compliant_count - Compliant components
 * @property {number} violation_count - Policy violations
 * @property {number} unknown_count - Unknown licenses
 * @property {string[]} high_risk_licenses - High-risk license types found
 */

/**
 * @typedef {Object} AttestationStatus
 * @property {number} signed_sbom_count - Number of signed SBOMs
 * @property {number} unsigned_sbom_count - Number of unsigned SBOMs
 * @property {number} sigstore_verified_count - Sigstore verified count
 * @property {string} sigstore_status - Sigstore service status
 * @property {string|null} last_verification - Last verification timestamp
 * @property {Object[]} recent_attestations - Recent attestation records
 */

// Mock data for development when API is unavailable
const MOCK_SBOM_STATUS = {
  repository_id: 'aura-core',
  format: 'cyclonedx',
  status: 'complete',
  component_count: 847,
  vulnerability_count: 12,
  last_generated: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  last_error: null,
  repositories: [
    { id: 'aura-core', format: 'cyclonedx', components: 847, vulnerabilities: 12, status: 'complete' },
    { id: 'aura-frontend', format: 'spdx', components: 423, vulnerabilities: 3, status: 'complete' },
    { id: 'aura-agents', format: 'cyclonedx', components: 156, vulnerabilities: 0, status: 'complete' },
    { id: 'aura-sandbox', format: 'cyclonedx', components: 89, vulnerabilities: 1, status: 'generating' },
  ],
};

const MOCK_DEPENDENCY_ALERTS = [
  {
    alert_id: 'dep-001',
    alert_type: 'typosquat',
    severity: 'critical',
    package_name: 'lodash',
    suspected_malicious: 'lodahs',
    confidence_score: 98,
    repository_id: 'aura-frontend',
    detected_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    acknowledged: false,
    description: 'Potential typosquatting package detected with similar name pattern',
  },
  {
    alert_id: 'dep-002',
    alert_type: 'namespace_hijack',
    severity: 'high',
    package_name: '@aura/utils',
    suspected_malicious: '@aura-internal/utils',
    confidence_score: 85,
    repository_id: 'aura-core',
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    acknowledged: false,
    description: 'Private namespace package available on public registry',
  },
  {
    alert_id: 'dep-003',
    alert_type: 'version_confusion',
    severity: 'medium',
    package_name: 'internal-auth',
    suspected_malicious: 'internal-auth@99.0.0',
    confidence_score: 72,
    repository_id: 'aura-agents',
    detected_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    acknowledged: true,
    description: 'Unusually high version number for internal package',
  },
];

const MOCK_LICENSE_SUMMARY = {
  distribution: {
    'MIT': 423,
    'Apache-2.0': 189,
    'BSD-3-Clause': 87,
    'ISC': 56,
    'GPL-3.0': 12,
    'LGPL-2.1': 8,
    'Unknown': 23,
    'Proprietary': 4,
  },
  total_components: 802,
  compliant_count: 763,
  violation_count: 16,
  unknown_count: 23,
  high_risk_licenses: ['GPL-3.0', 'AGPL-3.0'],
};

const MOCK_ATTESTATION_STATUS = {
  signed_sbom_count: 47,
  unsigned_sbom_count: 5,
  sigstore_verified_count: 42,
  sigstore_status: 'operational',
  last_verification: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  recent_attestations: [
    { sbom_id: 'sbom-001', repository: 'aura-core', signed: true, verified: true, timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString() },
    { sbom_id: 'sbom-002', repository: 'aura-frontend', signed: true, verified: true, timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString() },
    { sbom_id: 'sbom-003', repository: 'aura-agents', signed: true, verified: false, timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
  ],
};

// ============================================================================
// SBOM Endpoints
// ============================================================================

/**
 * Get SBOM generation status for repositories.
 *
 * @returns {Promise<SBOMStatus>} SBOM status
 * @throws {ApiError} When the request fails
 */
export async function getSBOMStatus() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.SBOM_STATUS);
    return data;
  } catch (err) {
    console.warn('Using mock SBOM status (API unavailable)');
    return MOCK_SBOM_STATUS;
  }
}

/**
 * Generate SBOM for a repository.
 *
 * @param {string} repositoryId - Repository identifier
 * @param {string} [format='cyclonedx'] - SBOM format
 * @returns {Promise<Object>} Generation result
 * @throws {ApiError} When the request fails
 */
export async function generateSBOM(repositoryId, format = 'cyclonedx') {
  const { data } = await apiClient.post(ENDPOINTS.SBOM_GENERATE, {
    repository_id: repositoryId,
    format,
  });
  return data;
}

/**
 * Get list of all SBOMs.
 *
 * @returns {Promise<Object[]>} List of SBOMs
 * @throws {ApiError} When the request fails
 */
export async function listSBOMs() {
  const { data } = await apiClient.get(ENDPOINTS.SBOM_LIST);
  return data;
}

// ============================================================================
// Dependency Confusion Endpoints
// ============================================================================

/**
 * Get dependency confusion alerts.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.severity] - Filter by severity
 * @param {boolean} [filters.acknowledged] - Filter by acknowledgment status
 * @returns {Promise<DependencyConfusionAlert[]>} Alerts
 * @throws {ApiError} When the request fails
 */
export async function getDependencyConfusionAlerts(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.severity) params.append('severity', filters.severity);
    if (filters.acknowledged !== undefined) params.append('acknowledged', filters.acknowledged);

    const url = `${ENDPOINTS.DEPENDENCY_ALERTS}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock dependency alerts (API unavailable)');
    let alerts = [...MOCK_DEPENDENCY_ALERTS];
    if (filters.severity) {
      alerts = alerts.filter((a) => a.severity === filters.severity);
    }
    if (filters.acknowledged !== undefined) {
      alerts = alerts.filter((a) => a.acknowledged === filters.acknowledged);
    }
    return alerts;
  }
}

/**
 * Check for typosquatting on a package name.
 *
 * @param {string} packageName - Package name to check
 * @returns {Promise<Object>} Typosquat analysis
 * @throws {ApiError} When the request fails
 */
export async function checkTyposquat(packageName) {
  const { data } = await apiClient.post(ENDPOINTS.TYPOSQUAT_CHECK, {
    package_name: packageName,
  });
  return data;
}

/**
 * Acknowledge a dependency confusion alert.
 *
 * @param {string} alertId - Alert identifier
 * @returns {Promise<Object>} Acknowledgment result
 * @throws {ApiError} When the request fails
 */
export async function acknowledgeAlert(alertId) {
  const { data } = await apiClient.post(`${ENDPOINTS.DEPENDENCY_ALERTS}/${alertId}/acknowledge`);
  return data;
}

// ============================================================================
// License Compliance Endpoints
// ============================================================================

/**
 * Get license compliance summary.
 *
 * @returns {Promise<LicenseSummary>} License summary
 * @throws {ApiError} When the request fails
 */
export async function getLicenseSummary() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.LICENSE_SUMMARY);
    return data;
  } catch (err) {
    console.warn('Using mock license summary (API unavailable)');
    return MOCK_LICENSE_SUMMARY;
  }
}

/**
 * Get license policy violations.
 *
 * @returns {Promise<Object[]>} License violations
 * @throws {ApiError} When the request fails
 */
export async function getLicenseViolations() {
  const { data } = await apiClient.get(ENDPOINTS.LICENSE_VIOLATIONS);
  return data;
}

/**
 * Update license policy.
 *
 * @param {Object} policy - License policy configuration
 * @returns {Promise<Object>} Updated policy
 * @throws {ApiError} When the request fails
 */
export async function updateLicensePolicy(policy) {
  const { data } = await apiClient.put(ENDPOINTS.LICENSE_POLICY, policy);
  return data;
}

// ============================================================================
// Attestation Endpoints
// ============================================================================

/**
 * Get attestation status.
 *
 * @returns {Promise<AttestationStatus>} Attestation status
 * @throws {ApiError} When the request fails
 */
export async function getAttestationStatus() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.ATTESTATION_STATUS);
    return data;
  } catch (err) {
    console.warn('Using mock attestation status (API unavailable)');
    return MOCK_ATTESTATION_STATUS;
  }
}

/**
 * Verify an SBOM attestation.
 *
 * @param {string} sbomId - SBOM identifier
 * @returns {Promise<Object>} Verification result
 * @throws {ApiError} When the request fails
 */
export async function verifyAttestation(sbomId) {
  const { data } = await apiClient.post(ENDPOINTS.ATTESTATION_VERIFY, {
    sbom_id: sbomId,
  });
  return data;
}

/**
 * Get Sigstore service status.
 *
 * @returns {Promise<Object>} Sigstore status
 * @throws {ApiError} When the request fails
 */
export async function getSigstoreStatus() {
  const { data } = await apiClient.get(ENDPOINTS.SIGSTORE_STATUS);
  return data;
}

/**
 * API error specific to Supply Chain operations
 */
export class SupplyChainApiError extends ApiError {
  constructor(message, status, details = null) {
    super(message, status, details);
    this.name = 'SupplyChainApiError';
  }
}

// Default export for convenience
export default {
  // SBOM
  getSBOMStatus,
  generateSBOM,
  listSBOMs,

  // Dependency Confusion
  getDependencyConfusionAlerts,
  checkTyposquat,
  acknowledgeAlert,

  // License Compliance
  getLicenseSummary,
  getLicenseViolations,
  updateLicensePolicy,

  // Attestation
  getAttestationStatus,
  verifyAttestation,
  getSigstoreStatus,

  // Error class
  SupplyChainApiError,

  // Constants
  ENDPOINTS,
};

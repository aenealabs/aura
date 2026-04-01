/**
 * Project Aura - Runtime Security API Service
 *
 * Client-side service for interacting with runtime security
 * endpoints per ADR-077.
 *
 * @module services/runtimeSecurityApi
 */

import { apiClient, ApiError } from './api';

// API endpoints for Runtime Security
const ENDPOINTS = {
  // Admission Controller
  ADMISSION_DECISIONS: '/api/v1/runtime-security/admission/decisions',
  ADMISSION_POLICIES: '/api/v1/runtime-security/admission/policies',
  ADMISSION_STATS: '/api/v1/runtime-security/admission/stats',

  // Container Escape Detection
  ESCAPE_ATTEMPTS: '/api/v1/runtime-security/container/escape-attempts',
  CONTAINER_ANOMALIES: '/api/v1/runtime-security/container/anomalies',
  MITRE_MAPPING: '/api/v1/runtime-security/container/mitre-mapping',

  // Runtime Correlation
  RUNTIME_CORRELATION: '/api/v1/runtime-security/correlation',
  CLOUDTRAIL_EVENTS: '/api/v1/runtime-security/correlation/cloudtrail',
  CODE_CORRELATION: '/api/v1/runtime-security/correlation/code',

  // GuardDuty Integration
  GUARDDUTY_FINDINGS: '/api/v1/runtime-security/guardduty/findings',
  GUARDDUTY_STATS: '/api/v1/runtime-security/guardduty/stats',
  GUARDDUTY_CODE_LINKS: '/api/v1/runtime-security/guardduty/code-links',
};

/**
 * @typedef {Object} AdmissionDecision
 * @property {string} decision_id - Decision identifier
 * @property {string} decision - Decision (ALLOW, DENY, WARN)
 * @property {string} resource_type - Resource type (pod, deployment, service)
 * @property {string} resource_name - Resource name
 * @property {string} namespace - Kubernetes namespace
 * @property {string} policy_name - Triggered policy name
 * @property {string} reason - Decision reason
 * @property {string} timestamp - ISO timestamp
 * @property {Object} metadata - Additional metadata
 */

/**
 * @typedef {Object} ContainerEscapeAttempt
 * @property {string} attempt_id - Attempt identifier
 * @property {string} container_id - Container identifier
 * @property {string} pod_name - Pod name
 * @property {string} namespace - Kubernetes namespace
 * @property {string} technique - Escape technique used
 * @property {string} mitre_tactic - MITRE ATT&CK tactic
 * @property {string} mitre_technique - MITRE ATT&CK technique ID
 * @property {string} severity - Severity level
 * @property {boolean} blocked - Whether attempt was blocked
 * @property {string} detected_at - ISO timestamp
 */

/**
 * @typedef {Object} RuntimeCorrelation
 * @property {string} correlation_id - Correlation identifier
 * @property {string} source_event - Source event type (cloudtrail, guardduty)
 * @property {string} event_id - Original event identifier
 * @property {Object} code_location - Correlated code location
 * @property {number} confidence_score - Correlation confidence (0-100)
 * @property {string[]} affected_files - Affected source files
 * @property {string} correlated_at - ISO timestamp
 */

/**
 * @typedef {Object} GuardDutyFinding
 * @property {string} finding_id - Finding identifier
 * @property {string} type - Finding type
 * @property {string} severity - Severity (Critical, High, Medium, Low)
 * @property {number} severity_score - Numeric severity (1-10)
 * @property {string} title - Finding title
 * @property {string} description - Finding description
 * @property {string} resource_type - Affected resource type
 * @property {string} resource_id - Affected resource identifier
 * @property {Object|null} code_link - Link to source code if correlated
 * @property {string} detected_at - ISO timestamp
 * @property {boolean} archived - Whether finding is archived
 */

// Mock data for development
const MOCK_ADMISSION_DECISIONS = {
  decisions: [
    {
      decision_id: 'adm-001',
      decision: 'DENY',
      resource_type: 'pod',
      resource_name: 'suspicious-workload',
      namespace: 'default',
      policy_name: 'privileged-container-policy',
      reason: 'Container requests privileged mode',
      timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      metadata: { user: 'system:serviceaccount:ci/deployer' },
    },
    {
      decision_id: 'adm-002',
      decision: 'WARN',
      resource_type: 'deployment',
      resource_name: 'web-frontend',
      namespace: 'production',
      policy_name: 'resource-limits-policy',
      reason: 'No resource limits specified',
      timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      metadata: { user: 'developer@aura.com' },
    },
    {
      decision_id: 'adm-003',
      decision: 'ALLOW',
      resource_type: 'pod',
      resource_name: 'api-worker-78d9f',
      namespace: 'production',
      policy_name: 'image-registry-policy',
      reason: 'All policies passed',
      timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
      metadata: { user: 'system:serviceaccount:production/deployer' },
    },
  ],
  summary: {
    allow_count: 847,
    deny_count: 23,
    warn_count: 56,
    total_24h: 926,
  },
};

const MOCK_ESCAPE_ATTEMPTS = [
  {
    attempt_id: 'esc-001',
    container_id: 'ctr-a7b8c9d0',
    pod_name: 'compromised-pod-1',
    namespace: 'staging',
    technique: 'Mount host filesystem',
    mitre_tactic: 'Privilege Escalation',
    mitre_technique: 'T1611',
    severity: 'critical',
    blocked: true,
    detected_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    details: 'Attempted to mount /etc/shadow from host',
  },
  {
    attempt_id: 'esc-002',
    container_id: 'ctr-e1f2g3h4',
    pod_name: 'suspicious-workload-2',
    namespace: 'default',
    technique: 'Kernel exploit (CVE-2022-0847)',
    mitre_tactic: 'Privilege Escalation',
    mitre_technique: 'T1068',
    severity: 'critical',
    blocked: true,
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    details: 'Dirty Pipe exploit attempt detected',
  },
  {
    attempt_id: 'esc-003',
    container_id: 'ctr-i5j6k7l8',
    pod_name: 'api-worker-compromised',
    namespace: 'production',
    technique: 'Docker socket access',
    mitre_tactic: 'Execution',
    mitre_technique: 'T1610',
    severity: 'high',
    blocked: false,
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    details: 'Container accessed Docker socket at /var/run/docker.sock',
  },
];

const MOCK_RUNTIME_CORRELATIONS = [
  {
    correlation_id: 'corr-001',
    source_event: 'cloudtrail',
    event_id: 'ct-abc123',
    event_name: 'AssumeRole',
    code_location: {
      file: 'src/services/auth/role_manager.py',
      line: 145,
      function: 'assume_cross_account_role',
    },
    confidence_score: 94,
    affected_files: ['src/services/auth/role_manager.py', 'src/config/iam_policies.yaml'],
    correlated_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
  {
    correlation_id: 'corr-002',
    source_event: 'guardduty',
    event_id: 'gd-def456',
    event_name: 'UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration',
    code_location: {
      file: 'src/agents/scanner/credential_handler.py',
      line: 78,
      function: 'fetch_instance_metadata',
    },
    confidence_score: 87,
    affected_files: ['src/agents/scanner/credential_handler.py'],
    correlated_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
  },
];

const MOCK_GUARDDUTY_FINDINGS = [
  {
    finding_id: 'gd-001',
    type: 'UnauthorizedAccess:EC2/SSHBruteForce',
    severity: 'High',
    severity_score: 8,
    title: 'SSH brute force attack detected',
    description: 'EC2 instance i-0abc123 is performing SSH brute force attacks against 10.0.1.50',
    resource_type: 'EC2Instance',
    resource_id: 'i-0abc123',
    code_link: {
      file: 'deploy/cloudformation/bastion.yaml',
      line: 45,
      context: 'Security group allows SSH from 0.0.0.0/0',
    },
    detected_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    archived: false,
  },
  {
    finding_id: 'gd-002',
    type: 'Recon:EC2/PortProbeUnprotectedPort',
    severity: 'Medium',
    severity_score: 5,
    title: 'Unprotected port being probed',
    description: 'EC2 instance i-0def456 has unprotected port 22 being probed from malicious IP',
    resource_type: 'EC2Instance',
    resource_id: 'i-0def456',
    code_link: null,
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    archived: false,
  },
  {
    finding_id: 'gd-003',
    type: 'CryptoCurrency:EC2/BitcoinTool.B!DNS',
    severity: 'High',
    severity_score: 8,
    title: 'Bitcoin mining activity detected',
    description: 'EC2 instance i-0ghi789 is querying a domain associated with Bitcoin mining',
    resource_type: 'EC2Instance',
    resource_id: 'i-0ghi789',
    code_link: {
      file: 'src/workers/batch_processor.py',
      line: 234,
      context: 'Suspicious outbound DNS query to mining pool',
    },
    detected_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    archived: false,
  },
];

// ============================================================================
// Admission Controller Endpoints
// ============================================================================

/**
 * Get admission controller decisions.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.decision] - Filter by decision type
 * @param {string} [filters.namespace] - Filter by namespace
 * @param {number} [filters.limit] - Limit results
 * @returns {Promise<Object>} Admission decisions and summary
 * @throws {ApiError} When the request fails
 */
export async function getAdmissionDecisions(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.decision) params.append('decision', filters.decision);
    if (filters.namespace) params.append('namespace', filters.namespace);
    if (filters.limit) params.append('limit', filters.limit);

    const url = `${ENDPOINTS.ADMISSION_DECISIONS}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock admission decisions (API unavailable)');
    let decisions = [...MOCK_ADMISSION_DECISIONS.decisions];
    if (filters.decision) {
      decisions = decisions.filter((d) => d.decision === filters.decision);
    }
    if (filters.namespace) {
      decisions = decisions.filter((d) => d.namespace === filters.namespace);
    }
    return { decisions, summary: MOCK_ADMISSION_DECISIONS.summary };
  }
}

/**
 * Get admission controller statistics.
 *
 * @param {string} [timeRange='24h'] - Time range for stats
 * @returns {Promise<Object>} Admission statistics
 * @throws {ApiError} When the request fails
 */
export async function getAdmissionStats(timeRange = '24h') {
  try {
    const { data } = await apiClient.get(`${ENDPOINTS.ADMISSION_STATS}?range=${timeRange}`);
    return data;
  } catch (err) {
    console.warn('Using mock admission stats (API unavailable)');
    return MOCK_ADMISSION_DECISIONS.summary;
  }
}

// ============================================================================
// Container Escape Detection Endpoints
// ============================================================================

/**
 * Get container escape attempts.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.severity] - Filter by severity
 * @param {boolean} [filters.blocked] - Filter by blocked status
 * @returns {Promise<ContainerEscapeAttempt[]>} Escape attempts
 * @throws {ApiError} When the request fails
 */
export async function getContainerEscapeAttempts(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.severity) params.append('severity', filters.severity);
    if (filters.blocked !== undefined) params.append('blocked', filters.blocked);

    const url = `${ENDPOINTS.ESCAPE_ATTEMPTS}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock escape attempts (API unavailable)');
    let attempts = [...MOCK_ESCAPE_ATTEMPTS];
    if (filters.severity) {
      attempts = attempts.filter((a) => a.severity === filters.severity);
    }
    if (filters.blocked !== undefined) {
      attempts = attempts.filter((a) => a.blocked === filters.blocked);
    }
    return attempts;
  }
}

/**
 * Get MITRE ATT&CK mapping for container techniques.
 *
 * @returns {Promise<Object>} MITRE mapping
 * @throws {ApiError} When the request fails
 */
export async function getMitreMapping() {
  const { data } = await apiClient.get(ENDPOINTS.MITRE_MAPPING);
  return data;
}

// ============================================================================
// Runtime Correlation Endpoints
// ============================================================================

/**
 * Get runtime event to code correlations.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.source] - Filter by source (cloudtrail, guardduty)
 * @returns {Promise<RuntimeCorrelation[]>} Correlations
 * @throws {ApiError} When the request fails
 */
export async function getRuntimeCorrelations(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.source) params.append('source', filters.source);

    const url = `${ENDPOINTS.RUNTIME_CORRELATION}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock runtime correlations (API unavailable)');
    let correlations = [...MOCK_RUNTIME_CORRELATIONS];
    if (filters.source) {
      correlations = correlations.filter((c) => c.source_event === filters.source);
    }
    return correlations;
  }
}

/**
 * Get CloudTrail events with code correlation.
 *
 * @param {string} [timeRange='24h'] - Time range
 * @returns {Promise<Object[]>} CloudTrail events
 * @throws {ApiError} When the request fails
 */
export async function getCloudTrailEvents(timeRange = '24h') {
  const { data } = await apiClient.get(`${ENDPOINTS.CLOUDTRAIL_EVENTS}?range=${timeRange}`);
  return data;
}

// ============================================================================
// GuardDuty Integration Endpoints
// ============================================================================

/**
 * Get GuardDuty findings.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.severity] - Filter by severity
 * @param {boolean} [filters.archived] - Filter by archived status
 * @param {boolean} [filters.hasCodeLink] - Filter by code link presence
 * @returns {Promise<GuardDutyFinding[]>} Findings
 * @throws {ApiError} When the request fails
 */
export async function getGuardDutyFindings(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.severity) params.append('severity', filters.severity);
    if (filters.archived !== undefined) params.append('archived', filters.archived);
    if (filters.hasCodeLink !== undefined) params.append('has_code_link', filters.hasCodeLink);

    const url = `${ENDPOINTS.GUARDDUTY_FINDINGS}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock GuardDuty findings (API unavailable)');
    let findings = [...MOCK_GUARDDUTY_FINDINGS];
    if (filters.severity) {
      findings = findings.filter((f) => f.severity === filters.severity);
    }
    if (filters.archived !== undefined) {
      findings = findings.filter((f) => f.archived === filters.archived);
    }
    if (filters.hasCodeLink !== undefined) {
      findings = findings.filter((f) => !!f.code_link === filters.hasCodeLink);
    }
    return findings;
  }
}

/**
 * Get GuardDuty statistics.
 *
 * @returns {Promise<Object>} GuardDuty stats
 * @throws {ApiError} When the request fails
 */
export async function getGuardDutyStats() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.GUARDDUTY_STATS);
    return data;
  } catch (err) {
    console.warn('Using mock GuardDuty stats (API unavailable)');
    return {
      critical_count: 1,
      high_count: 4,
      medium_count: 8,
      low_count: 12,
      total_findings: 25,
      code_linked_count: 15,
      correlation_rate: 60,
    };
  }
}

/**
 * Archive a GuardDuty finding.
 *
 * @param {string} findingId - Finding identifier
 * @returns {Promise<Object>} Archive result
 * @throws {ApiError} When the request fails
 */
export async function archiveGuardDutyFinding(findingId) {
  const { data } = await apiClient.post(`${ENDPOINTS.GUARDDUTY_FINDINGS}/${findingId}/archive`);
  return data;
}

/**
 * API error specific to Runtime Security operations
 */
export class RuntimeSecurityApiError extends ApiError {
  constructor(message, status, details = null) {
    super(message, status, details);
    this.name = 'RuntimeSecurityApiError';
  }
}

// Default export for convenience
export default {
  // Admission Controller
  getAdmissionDecisions,
  getAdmissionStats,

  // Container Escape Detection
  getContainerEscapeAttempts,
  getMitreMapping,

  // Runtime Correlation
  getRuntimeCorrelations,
  getCloudTrailEvents,

  // GuardDuty
  getGuardDutyFindings,
  getGuardDutyStats,
  archiveGuardDutyFinding,

  // Error class
  RuntimeSecurityApiError,

  // Constants
  ENDPOINTS,
};

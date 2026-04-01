/**
 * Guardrails API Service
 *
 * Provides API client functions for the Guardrail Settings page (ADR-069).
 * Endpoints:
 * - GET  /api/v1/guardrails/config      - Get current configuration
 * - PUT  /api/v1/guardrails/config      - Update configuration
 * - GET  /api/v1/guardrails/metrics     - Get activity metrics
 * - POST /api/v1/guardrails/impact      - Get impact preview for changes
 * - GET  /api/v1/guardrails/profiles    - List compliance profiles
 * - GET  /api/v1/guardrails/history     - Get change history
 *
 * In development mode, falls back to mock data when the backend is unavailable.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';
const IS_DEV = import.meta.env.DEV;

/**
 * Get auth headers for API requests
 */
function getAuthHeaders() {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Handle API response and parse JSON
 */
async function handleResponse(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Mock data for development when backend is unavailable
 */
const MOCK_DATA = {
  config: {
    profile: 'balanced',
    complianceProfile: null,
    advanced: {
      hitlSensitivity: 1,
      trustLevel: 'medium',
      verbosity: 'standard',
      reviewerType: 'team_lead',
      enableAnomalyAlerts: true,
      auditAllDecisions: false,
      enableContradictionDetection: true,
    },
    version: 3,
    lastModifiedBy: 'admin@aenealabs.com',
    lastModifiedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
  metrics: {
    '7d': {
      totalDecisions: 1247,
      autoApproved: 1189,
      hitlRequired: 58,
      hitlApproved: 51,
      hitlRejected: 7,
      avgResponseTimeMs: 342,
      anomaliesDetected: 3,
      contradictionsFound: 2,
      byAgent: {
        CoderAgent: { decisions: 523, hitl: 18, avgLatency: 312 },
        ReviewerAgent: { decisions: 298, hitl: 15, avgLatency: 287 },
        ValidatorAgent: { decisions: 245, hitl: 12, avgLatency: 198 },
        PatcherAgent: { decisions: 181, hitl: 13, avgLatency: 456 },
      },
      byDay: [
        { date: '2026-01-21', decisions: 187, hitl: 8 },
        { date: '2026-01-22', decisions: 203, hitl: 12 },
        { date: '2026-01-23', decisions: 178, hitl: 7 },
        { date: '2026-01-24', decisions: 156, hitl: 9 },
        { date: '2026-01-25', decisions: 189, hitl: 11 },
        { date: '2026-01-26', decisions: 167, hitl: 6 },
        { date: '2026-01-27', decisions: 167, hitl: 5 },
      ],
    },
    '24h': {
      totalDecisions: 167,
      autoApproved: 162,
      hitlRequired: 5,
      hitlApproved: 4,
      hitlRejected: 1,
      avgResponseTimeMs: 298,
      anomaliesDetected: 0,
      contradictionsFound: 1,
      byAgent: {
        CoderAgent: { decisions: 78, hitl: 2, avgLatency: 301 },
        ReviewerAgent: { decisions: 42, hitl: 1, avgLatency: 265 },
        ValidatorAgent: { decisions: 32, hitl: 1, avgLatency: 187 },
        PatcherAgent: { decisions: 15, hitl: 1, avgLatency: 423 },
      },
      byHour: Array.from({ length: 24 }, (_, i) => ({
        hour: i,
        decisions: Math.floor(Math.random() * 15) + 3,
        hitl: Math.floor(Math.random() * 2),
      })),
    },
    '30d': {
      totalDecisions: 4892,
      autoApproved: 4651,
      hitlRequired: 241,
      hitlApproved: 218,
      hitlRejected: 23,
      avgResponseTimeMs: 367,
      anomaliesDetected: 12,
      contradictionsFound: 8,
      byAgent: {
        CoderAgent: { decisions: 2034, hitl: 92, avgLatency: 328 },
        ReviewerAgent: { decisions: 1156, hitl: 67, avgLatency: 298 },
        ValidatorAgent: { decisions: 978, hitl: 48, avgLatency: 212 },
        PatcherAgent: { decisions: 724, hitl: 34, avgLatency: 478 },
      },
      byWeek: [
        { week: '2025-W52', decisions: 1023, hitl: 52 },
        { week: '2026-W01', decisions: 1287, hitl: 61 },
        { week: '2026-W02', decisions: 1198, hitl: 58 },
        { week: '2026-W03', decisions: 1247, hitl: 58 },
        { week: '2026-W04', decisions: 137, hitl: 12 },
      ],
    },
  },
  impactPreview: {
    metrics: [
      { label: 'Daily HITL prompts', before: 12, after: 5, inverted: true },
      { label: 'Auto-approved operations', before: 847, after: 891 },
      { label: 'Quarantined items', before: 3, after: 8 },
      { label: 'Avg decision latency', before: 2.3, after: 1.1, inverted: true, format: 'time' },
    ],
    warnings: [],
  },
  profiles: [
    {
      id: 'cmmc_l2',
      name: 'CMMC Level 2',
      description: 'Cybersecurity Maturity Model Certification Level 2 requirements',
      lockedSettings: ['auditAllDecisions'],
    },
    {
      id: 'cmmc_l3',
      name: 'CMMC Level 3',
      description: 'Cybersecurity Maturity Model Certification Level 3 requirements',
      lockedSettings: ['auditAllDecisions', 'enableContradictionDetection'],
    },
    {
      id: 'fedramp_high',
      name: 'FedRAMP High',
      description: 'Federal Risk and Authorization Management Program High baseline',
      lockedSettings: ['hitlSensitivity', 'trustLevel', 'auditAllDecisions'],
    },
    {
      id: 'sox',
      name: 'SOX Compliance',
      description: 'Sarbanes-Oxley Act compliance requirements',
      lockedSettings: ['auditAllDecisions'],
    },
  ],
  history: [
    {
      id: 'chg-001',
      timestamp: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      userId: 'admin@aenealabs.com',
      settingPath: 'profile',
      previousValue: 'conservative',
      newValue: 'balanced',
      justification: 'Reducing HITL friction after initial deployment stabilization',
    },
    {
      id: 'chg-002',
      timestamp: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
      userId: 'security@aenealabs.com',
      settingPath: 'enableAnomalyAlerts',
      previousValue: false,
      newValue: true,
      justification: 'Enabling anomaly detection per security team recommendation',
    },
    {
      id: 'chg-003',
      timestamp: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      userId: 'admin@aenealabs.com',
      settingPath: '*',
      previousValue: null,
      newValue: 'initial',
      justification: 'Initial configuration',
      changeType: 'create',
    },
  ],
};

/**
 * Wrapper to fall back to mock data in development mode
 */
async function withMockFallback(apiCall, mockData, label) {
  try {
    return await apiCall();
  } catch (error) {
    if (IS_DEV) {
      console.warn(`[Guardrails] ${label} API unavailable, using mock data:`, error.message);
      return mockData;
    }
    throw error;
  }
}

/**
 * Get current guardrail configuration
 * @returns {Promise<Object>} Current configuration
 */
export async function getGuardrailConfig() {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/guardrails/config`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.config,
    'Config'
  );
}

/**
 * Update guardrail configuration
 * @param {Object} config - New configuration
 * @param {string} [justification] - Reason for change
 * @returns {Promise<Object>} Updated configuration
 */
export async function updateGuardrailConfig(config, justification = '') {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/guardrails/config`, {
        method: 'PUT',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...config, justification }),
      });
      return handleResponse(response);
    },
    { ...MOCK_DATA.config, ...config },
    'Update Config'
  );
}

/**
 * Get guardrail activity metrics
 * @param {string} [timeRange='7d'] - Time range: '24h', '7d', or '30d'
 * @returns {Promise<Object>} Activity metrics
 */
export async function getGuardrailMetrics(timeRange = '7d') {
  return withMockFallback(
    async () => {
      const response = await fetch(
        `${API_BASE}/api/v1/guardrails/metrics?time_range=${timeRange}`,
        {
          method: 'GET',
          headers: getAuthHeaders(),
        }
      );
      return handleResponse(response);
    },
    MOCK_DATA.metrics[timeRange] || MOCK_DATA.metrics['7d'],
    'Metrics'
  );
}

/**
 * Get impact preview for configuration changes
 * @param {Object} proposedChanges - Proposed configuration changes
 * @returns {Promise<Object>} Impact preview with projected metrics and warnings
 */
export async function getImpactPreview(proposedChanges) {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/guardrails/impact`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(proposedChanges),
      });
      return handleResponse(response);
    },
    MOCK_DATA.impactPreview,
    'Impact Preview'
  );
}

/**
 * Get available compliance profiles
 * @returns {Promise<Array>} List of compliance profiles
 */
export async function getComplianceProfiles() {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/guardrails/profiles`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.profiles,
    'Profiles'
  );
}

/**
 * Get configuration change history
 * @param {number} [limit=100] - Maximum records to return
 * @returns {Promise<Array>} Change history records
 */
export async function getChangeHistory(limit = 100) {
  return withMockFallback(
    async () => {
      const response = await fetch(
        `${API_BASE}/api/v1/guardrails/history?limit=${limit}`,
        {
          method: 'GET',
          headers: getAuthHeaders(),
        }
      );
      return handleResponse(response);
    },
    MOCK_DATA.history,
    'History'
  );
}

/**
 * Reset configuration to defaults
 * @param {string} [justification] - Reason for reset
 * @returns {Promise<Object>} Default configuration
 */
export async function resetToDefaults(justification = 'Reset to defaults') {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/guardrails/config/reset`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ justification }),
      });
      return handleResponse(response);
    },
    {
      profile: 'balanced',
      complianceProfile: null,
      advanced: {
        hitlSensitivity: 1,
        trustLevel: 'medium',
        verbosity: 'standard',
        reviewerType: 'team_lead',
        enableAnomalyAlerts: true,
        auditAllDecisions: false,
        enableContradictionDetection: true,
      },
    },
    'Reset'
  );
}

export default {
  getGuardrailConfig,
  updateGuardrailConfig,
  getGuardrailMetrics,
  getImpactPreview,
  getComplianceProfiles,
  getChangeHistory,
  resetToDefaults,
};

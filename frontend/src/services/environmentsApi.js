/**
 * Project Aura - Environments API Service
 *
 * Client-side service for managing test environments and admin settings.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Check if running in dev mode
const IS_DEV = import.meta.env.DEV || !import.meta.env.VITE_API_URL;

// ============================================================================
// Mock Data for Development/Demo
// ============================================================================

const MOCK_ENVIRONMENTS = [
  {
    environment_id: 'env-a1b2c3d4-api-tests',
    display_name: 'API Integration Tests',
    status: 'active',
    environment_type: 'standard',
    template_id: 'development',
    cost_estimate_daily: 10.80,
    dns_name: 'api-tests.sandbox.aura.local',
    expires_at: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(), // 6 hours from now
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    created_by: 'dev@aenealabs.com',
    description: 'Testing REST API endpoints for user authentication service',
  },
  {
    environment_id: 'env-e5f6g7h8-security-scan',
    display_name: 'Security Vulnerability Scan',
    status: 'active',
    environment_type: 'compliance',
    template_id: 'security-testing',
    cost_estimate_daily: 15.60,
    dns_name: 'sec-scan.sandbox.aura.local',
    expires_at: new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString(), // 3 hours from now
    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(), // 5 hours ago
    created_by: 'dev@aenealabs.com',
    description: 'SAST/DAST scanning for CVE-2024-1234 remediation validation',
  },
  {
    environment_id: 'env-i9j0k1l2-patch-validation',
    display_name: 'SQL Injection Patch Test',
    status: 'expiring',
    environment_type: 'quick',
    template_id: 'basic-sandbox',
    cost_estimate_daily: 3.60,
    dns_name: 'patch-test.sandbox.aura.local',
    expires_at: new Date(Date.now() + 45 * 60 * 1000).toISOString(), // 45 minutes from now
    created_at: new Date(Date.now() - 3.25 * 60 * 60 * 1000).toISOString(), // 3.25 hours ago
    created_by: 'dev@aenealabs.com',
    description: 'Validating SQL injection fix in user search endpoint',
  },
  {
    environment_id: 'env-m3n4o5p6-e2e-suite',
    display_name: 'E2E Test Suite - Sprint 47',
    status: 'pending_approval',
    environment_type: 'extended',
    template_id: 'integration-testing',
    cost_estimate_daily: 20.40,
    dns_name: 'e2e-s47.sandbox.aura.local',
    expires_at: new Date(Date.now() + 72 * 60 * 60 * 1000).toISOString(), // 72 hours from now
    created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 minutes ago
    created_by: 'dev@aenealabs.com',
    description: 'Full E2E test suite for Sprint 47 release validation',
  },
  {
    environment_id: 'env-q7r8s9t0-graphrag-perf',
    display_name: 'GraphRAG Performance Benchmark',
    status: 'provisioning',
    environment_type: 'standard',
    template_id: 'development',
    cost_estimate_daily: 10.80,
    dns_name: 'graphrag-perf.sandbox.aura.local',
    expires_at: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(), // 8 hours from now
    created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
    created_by: 'dev@aenealabs.com',
    description: 'Benchmarking Neptune query performance with 100K nodes',
  },
];

const MOCK_QUOTA = {
  user_id: 'dev@aenealabs.com',
  concurrent_limit: 3,
  active_count: 2,
  available: 1,
  monthly_budget: 500.0,
  monthly_spent: 127.40,
  monthly_remaining: 372.60,
};

/**
 * Custom error class for Environments API errors
 */
export class EnvironmentsApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'EnvironmentsApiError';
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
    throw new EnvironmentsApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * Environment types
 */
export const EnvironmentTypes = {
  QUICK: 'quick',
  STANDARD: 'standard',
  EXTENDED: 'extended',
  COMPLIANCE: 'compliance',
};

/**
 * Environment type display configuration
 */
export const ENVIRONMENT_TYPE_CONFIG = {
  quick: {
    label: 'Quick',
    description: 'EKS Namespace (4h)',
    color: 'aura',
    defaultTtl: 4,
    maxTtl: 8,
    requiresApproval: false,
  },
  standard: {
    label: 'Standard',
    description: 'Service Catalog (24h)',
    color: 'olive',
    defaultTtl: 24,
    maxTtl: 72,
    requiresApproval: false,
  },
  extended: {
    label: 'Extended',
    description: 'Service Catalog (7d)',
    color: 'warning',
    defaultTtl: 168,
    maxTtl: 336,
    requiresApproval: true,
  },
  compliance: {
    label: 'Compliance',
    description: 'Dedicated VPC (24h)',
    color: 'critical',
    defaultTtl: 24,
    maxTtl: 72,
    requiresApproval: true,
  },
};

/**
 * Isolation levels
 */
export const IsolationLevels = {
  NAMESPACE: 'namespace',
  CONTAINER: 'container',
  VPC: 'vpc',
  ACCOUNT: 'account',
};

/**
 * Isolation level display configuration
 */
export const ISOLATION_LEVEL_CONFIG = {
  namespace: {
    label: 'Namespace',
    description: 'Kubernetes namespace isolation with network policies',
    color: 'aura',
    securityLevel: 'standard',
    features: ['Network policies', 'Resource quotas', 'Shared cluster'],
  },
  container: {
    label: 'Container',
    description: 'Dedicated container with enhanced isolation',
    color: 'olive',
    securityLevel: 'enhanced',
    features: ['Seccomp profiles', 'AppArmor', 'Read-only filesystem'],
  },
  vpc: {
    label: 'VPC',
    description: 'Dedicated VPC with private subnets',
    color: 'warning',
    securityLevel: 'high',
    features: ['Private subnets', 'NAT gateway', 'VPC flow logs'],
  },
  account: {
    label: 'Account',
    description: 'Dedicated AWS account (GovCloud compatible)',
    color: 'critical',
    securityLevel: 'maximum',
    features: ['Account boundary', 'SCPs', 'Full isolation'],
  },
};

/**
 * Default admin settings
 */
export const DEFAULT_ADMIN_SETTINGS = {
  templates: [],
  quotas: {
    default_concurrent_limit: 3,
    default_monthly_budget: 500,
    allow_extended_ttl: true,
    require_approval_for_extended: true,
  },
  defaults: {
    default_ttl_hours: 24,
    max_ttl_hours: 168,
    default_isolation_level: 'namespace',
    auto_terminate_on_inactivity: true,
    inactivity_timeout_hours: 4,
  },
  cleanup: {
    enabled: true,
    grace_period_minutes: 30,
    send_expiry_warning: true,
    warning_before_minutes: 60,
  },
};

/**
 * Get environment templates (admin)
 *
 * @returns {Promise<Array>} List of templates
 */
export async function getEnvironmentTemplates() {
  try {
    return await fetchApi('/environments/admin/templates');
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Create environment template (admin)
 *
 * @param {Object} templateData - Template configuration
 * @returns {Promise<Object>} Created template
 */
export async function createEnvironmentTemplate(templateData) {
  return fetchApi('/environments/admin/templates', {
    method: 'POST',
    body: JSON.stringify(templateData),
  });
}

/**
 * Update environment template (admin)
 *
 * @param {string} templateId - Template identifier
 * @param {Object} updates - Template updates
 * @returns {Promise<Object>} Updated template
 */
export async function updateEnvironmentTemplate(templateId, updates) {
  return fetchApi(`/environments/admin/templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

/**
 * Delete environment template (admin)
 *
 * @param {string} templateId - Template identifier
 * @returns {Promise<null>} No content
 */
export async function deleteEnvironmentTemplate(templateId) {
  return fetchApi(`/environments/admin/templates/${templateId}`, {
    method: 'DELETE',
  });
}

/**
 * Get quota configuration (admin)
 *
 * @param {string} userId - User ID (optional, for user-specific quota)
 * @param {string} teamId - Team ID (optional, for team-specific quota)
 * @returns {Promise<Object>} Quota configuration
 */
export async function getQuotaConfig(userId = null, teamId = null) {
  try {
    const params = new URLSearchParams();
    if (userId) params.append('user_id', userId);
    if (teamId) params.append('team_id', teamId);
    const queryString = params.toString() ? `?${params}` : '';
    return await fetchApi(`/environments/admin/quotas${queryString}`);
  } catch (error) {
    if (error.status === 404) {
      return DEFAULT_ADMIN_SETTINGS.quotas;
    }
    throw error;
  }
}

/**
 * Update quota configuration (admin)
 *
 * @param {Object} quotaConfig - Quota updates
 * @param {string} userId - User ID (optional)
 * @param {string} teamId - Team ID (optional)
 * @returns {Promise<Object>} Updated quota
 */
export async function updateQuotaConfig(quotaConfig, userId = null, teamId = null) {
  const params = new URLSearchParams();
  if (userId) params.append('user_id', userId);
  if (teamId) params.append('team_id', teamId);
  const queryString = params.toString() ? `?${params}` : '';
  return fetchApi(`/environments/admin/quotas${queryString}`, {
    method: 'PUT',
    body: JSON.stringify(quotaConfig),
  });
}

/**
 * Get default TTL settings (admin)
 *
 * @returns {Promise<Object>} Default settings
 */
export async function getDefaultSettings() {
  try {
    return await fetchApi('/environments/admin/defaults');
  } catch (error) {
    if (error.status === 404) {
      return DEFAULT_ADMIN_SETTINGS.defaults;
    }
    throw error;
  }
}

/**
 * Update default TTL settings (admin)
 *
 * @param {Object} settings - Default settings
 * @returns {Promise<Object>} Updated settings
 */
export async function updateDefaultSettings(settings) {
  return fetchApi('/environments/admin/defaults', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

/**
 * Get cleanup settings (admin)
 *
 * @returns {Promise<Object>} Cleanup settings
 */
export async function getCleanupSettings() {
  try {
    return await fetchApi('/environments/admin/cleanup');
  } catch (error) {
    if (error.status === 404) {
      return DEFAULT_ADMIN_SETTINGS.cleanup;
    }
    throw error;
  }
}

/**
 * Update cleanup settings (admin)
 *
 * @param {Object} settings - Cleanup settings
 * @returns {Promise<Object>} Updated settings
 */
export async function updateCleanupSettings(settings) {
  return fetchApi('/environments/admin/cleanup', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

/**
 * Get environment isolation level
 *
 * @param {string} environmentId - Environment identifier
 * @returns {Promise<Object>} Isolation configuration
 */
export async function getEnvironmentIsolation(environmentId) {
  try {
    return await fetchApi(`/environments/${environmentId}/isolation`);
  } catch (error) {
    if (error.status === 404) {
      return { level: 'namespace', features: [] };
    }
    throw error;
  }
}

/**
 * Update environment isolation level
 *
 * @param {string} environmentId - Environment identifier
 * @param {string} isolationLevel - New isolation level
 * @returns {Promise<Object>} Updated isolation
 */
export async function updateEnvironmentIsolation(environmentId, isolationLevel) {
  return fetchApi(`/environments/${environmentId}/isolation`, {
    method: 'PUT',
    body: JSON.stringify({ level: isolationLevel }),
  });
}

/**
 * Get environment usage statistics (admin)
 *
 * @param {string} period - Time period (7d, 30d, 90d)
 * @returns {Promise<Object>} Usage statistics
 */
export async function getEnvironmentUsageStats(period = '30d') {
  try {
    return await fetchApi(`/environments/admin/stats?period=${period}`);
  } catch (error) {
    if (error.status === 404) {
      return {
        total_created: 0,
        total_active: 0,
        avg_lifetime_hours: 0,
        total_cost: 0,
        by_type: {},
        by_user: {},
      };
    }
    throw error;
  }
}

// ============================================================================
// Core User API Functions
// ============================================================================

/**
 * List user's environments
 *
 * @param {Object} options - Query options
 * @param {string} options.status - Filter by status (optional)
 * @param {string} options.environment_type - Filter by type (optional)
 * @param {number} options.limit - Max results (default 50)
 * @returns {Promise<Object>} Environment list with total count
 */
export async function listEnvironments(options = {}) {
  try {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.environment_type) params.append('environment_type', options.environment_type);
    if (options.limit) params.append('limit', options.limit.toString());
    const queryString = params.toString() ? `?${params}` : '';
    return await fetchApi(`/environments${queryString}`);
  } catch (error) {
    // Return mock data in dev mode when API is unavailable
    if (IS_DEV) {
      console.warn('Using mock environment data (API unavailable)');
      let environments = [...MOCK_ENVIRONMENTS];
      // Apply filters
      if (options.status) {
        environments = environments.filter(e => e.status === options.status);
      }
      if (options.environment_type) {
        environments = environments.filter(e => e.environment_type === options.environment_type);
      }
      return { environments, total: environments.length };
    }
    throw error;
  }
}

/**
 * Create a new test environment
 *
 * @param {Object} config - Environment configuration
 * @param {string} config.template_id - Template ID to use
 * @param {string} config.display_name - Human-readable name
 * @param {string} config.description - Optional description
 * @param {number} config.ttl_hours - Custom TTL in hours (optional)
 * @param {Object} config.metadata - Custom metadata tags (optional)
 * @returns {Promise<Object>} Created environment
 */
export async function createEnvironment(config) {
  return fetchApi('/environments', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

/**
 * Get environment details
 *
 * @param {string} environmentId - Environment ID
 * @returns {Promise<Object>} Environment details
 */
export async function getEnvironment(environmentId) {
  return fetchApi(`/environments/${environmentId}`);
}

/**
 * Terminate an environment
 *
 * @param {string} environmentId - Environment ID
 * @returns {Promise<null>} No content on success
 */
export async function terminateEnvironment(environmentId) {
  return fetchApi(`/environments/${environmentId}`, {
    method: 'DELETE',
  });
}

/**
 * Extend environment TTL
 *
 * @param {string} environmentId - Environment ID
 * @param {number} additionalHours - Hours to extend
 * @param {string} reason - Reason for extension (optional)
 * @returns {Promise<Object>} Updated environment
 */
export async function extendEnvironmentTTL(environmentId, additionalHours, reason = '') {
  return fetchApi(`/environments/${environmentId}/extend`, {
    method: 'POST',
    body: JSON.stringify({
      additional_hours: additionalHours,
      reason: reason,
    }),
  });
}

/**
 * Get available environment templates
 *
 * @returns {Promise<Array>} List of templates
 */
export async function getTemplates() {
  return fetchApi('/environments/templates');
}

/**
 * Get user's quota status
 *
 * @returns {Promise<Object>} Quota information
 */
export async function getUserQuota() {
  try {
    return await fetchApi('/environments/quota');
  } catch (error) {
    // Return mock quota in dev mode when API is unavailable
    if (IS_DEV) {
      console.warn('Using mock quota data (API unavailable)');
      return MOCK_QUOTA;
    }
    throw error;
  }
}

/**
 * Health check for environment service
 *
 * @returns {Promise<Object>} Service health status
 */
export async function getEnvironmentHealth() {
  return fetchApi('/environments/health');
}

/**
 * Get environment metrics for dashboard
 *
 * @returns {Promise<Object>} Environment metrics
 */
export async function getEnvironmentMetrics() {
  try {
    return await fetchApi('/environments/metrics');
  } catch (error) {
    // Return default metrics if endpoint not available
    if (error.status === 404) {
      return {
        active_environments: 0,
        pending_approvals: 0,
        total_patches: 0,
        security_score: 0,
      };
    }
    throw error;
  }
}

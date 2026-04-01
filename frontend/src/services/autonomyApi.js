/**
 * Project Aura - Autonomy Policy API Service
 *
 * Client-side service for managing autonomy policies and HITL controls.
 * Connects to /api/v1/autonomy endpoints.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Autonomy API errors
 */
export class AutonomyApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'AutonomyApiError';
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
    throw new AutonomyApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * Autonomy level options
 */
export const AutonomyLevels = {
  FULL_HITL: 'full_hitl',
  CRITICAL_HITL: 'critical_hitl',
  AUDIT_ONLY: 'audit_only',
  FULL_AUTONOMOUS: 'full_autonomous',
};

/**
 * Autonomy level display configuration
 */
export const AUTONOMY_LEVEL_CONFIG = {
  full_hitl: {
    label: 'Full HITL',
    description: 'All actions require human approval',
    color: 'critical',
    icon: 'ShieldExclamationIcon',
  },
  critical_hitl: {
    label: 'Critical HITL',
    description: 'Critical and high severity require approval',
    color: 'warning',
    icon: 'ShieldCheckIcon',
  },
  audit_only: {
    label: 'Audit Only',
    description: 'Actions are logged but auto-approved',
    color: 'aura',
    icon: 'DocumentMagnifyingGlassIcon',
  },
  full_autonomous: {
    label: 'Full Autonomous',
    description: 'Maximum autonomy, guardrails only',
    color: 'olive',
    icon: 'BoltIcon',
  },
};

/**
 * Policy presets with display information
 */
export const POLICY_PRESETS = {
  maximum_oversight: {
    name: 'Maximum Oversight',
    description: 'All actions require human approval. For highest security environments.',
    defaultLevel: 'full_hitl',
    hitlEnabled: true,
    icon: 'ShieldExclamationIcon',
    color: 'critical',
    useCase: 'Defense contractors, classified systems',
  },
  high_oversight: {
    name: 'High Oversight',
    description: 'Critical and high severity require approval. Standard for regulated industries.',
    defaultLevel: 'critical_hitl',
    hitlEnabled: true,
    icon: 'ShieldCheckIcon',
    color: 'orange',
    useCase: 'Financial services, healthcare',
  },
  balanced: {
    name: 'Balanced',
    description: 'Critical actions require approval, others are audited.',
    defaultLevel: 'critical_hitl',
    hitlEnabled: true,
    icon: 'ScaleIcon',
    color: 'aura',
    useCase: 'Enterprise standard',
  },
  efficiency_focused: {
    name: 'Efficiency Focused',
    description: 'Most actions are auto-approved with audit trail.',
    defaultLevel: 'audit_only',
    hitlEnabled: true,
    icon: 'ChartBarIcon',
    color: 'olive',
    useCase: 'Startups, rapid development',
  },
  maximum_autonomy: {
    name: 'Maximum Autonomy',
    description: 'Full autonomous operation, guardrails only.',
    defaultLevel: 'full_autonomous',
    hitlEnabled: false,
    icon: 'BoltIcon',
    color: 'olive',
    useCase: 'Internal tools, low-risk systems',
  },
  emergency_response: {
    name: 'Emergency Response',
    description: 'Temporary high-speed mode for incident response.',
    defaultLevel: 'audit_only',
    hitlEnabled: false,
    icon: 'ExclamationTriangleIcon',
    color: 'warning',
    useCase: 'Active incident response',
  },
  maintenance_mode: {
    name: 'Maintenance Mode',
    description: 'All automation paused, manual operations only.',
    defaultLevel: 'full_hitl',
    hitlEnabled: true,
    icon: 'WrenchScrewdriverIcon',
    color: 'surface',
    useCase: 'Scheduled maintenance windows',
  },
};

/**
 * Default mock policy for development
 */
export const DEFAULT_POLICY = {
  policy_id: 'pol-default-001',
  organization_id: 'org-aura-001',
  name: 'Default Policy',
  description: 'Standard autonomy policy for the organization',
  hitl_enabled: true,
  default_level: 'critical_hitl',
  severity_overrides: {},
  operation_overrides: {},
  repository_overrides: {},
  guardrails: ['production_deployment', 'credential_modification', 'database_schema_change'],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  created_by: 'admin@aura.local',
  updated_by: null,
  is_active: true,
  preset_name: 'balanced',
};

/**
 * Get policies for an organization
 *
 * @param {string} organizationId - Organization identifier
 * @param {boolean} includeInactive - Include inactive policies
 * @returns {Promise<Array>} List of policies
 */
export async function getPolicies(organizationId, includeInactive = false) {
  try {
    const params = new URLSearchParams({
      organization_id: organizationId,
      include_inactive: includeInactive.toString(),
    });
    return await fetchApi(`/autonomy/policies?${params}`);
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Autonomy policies API not available, using defaults');
      return [DEFAULT_POLICY];
    }
    throw error;
  }
}

/**
 * Get a single policy by ID
 *
 * @param {string} policyId - Policy identifier
 * @returns {Promise<Object>} Policy details
 */
export async function getPolicy(policyId) {
  try {
    return await fetchApi(`/autonomy/policies/${policyId}`);
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Autonomy policy API not available, using defaults');
      return DEFAULT_POLICY;
    }
    throw error;
  }
}

/**
 * Create a new policy
 *
 * @param {Object} policyData - Policy creation data
 * @returns {Promise<Object>} Created policy
 */
export async function createPolicy(policyData) {
  try {
    return await fetchApi('/autonomy/policies', {
      method: 'POST',
      body: JSON.stringify(policyData),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, using local state');
      return {
        ...DEFAULT_POLICY,
        ...policyData,
        policy_id: `pol-local-${Date.now()}`,
        created_at: new Date().toISOString(),
      };
    }
    throw error;
  }
}

/**
 * Create a policy from a preset
 *
 * @param {string} organizationId - Organization identifier
 * @param {string} presetName - Preset name
 * @returns {Promise<Object>} Created policy
 */
export async function createPolicyFromPreset(organizationId, presetName) {
  try {
    return await fetchApi('/autonomy/policies', {
      method: 'POST',
      body: JSON.stringify({
        organization_id: organizationId,
        preset_name: presetName,
      }),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, using local state');
      const preset = POLICY_PRESETS[presetName] || POLICY_PRESETS.balanced;
      return {
        ...DEFAULT_POLICY,
        policy_id: `pol-local-${Date.now()}`,
        organization_id: organizationId,
        preset_name: presetName,
        name: preset.name,
        description: preset.description,
        default_level: preset.defaultLevel,
        hitl_enabled: preset.hitlEnabled,
        created_at: new Date().toISOString(),
      };
    }
    throw error;
  }
}

/**
 * Update a policy
 *
 * @param {string} policyId - Policy identifier
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated policy
 */
export async function updatePolicy(policyId, updates) {
  try {
    return await fetchApi(`/autonomy/policies/${policyId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, using local state');
      return { ...DEFAULT_POLICY, ...updates, policy_id: policyId, updated_at: new Date().toISOString() };
    }
    throw error;
  }
}

/**
 * Delete (deactivate) a policy
 *
 * @param {string} policyId - Policy identifier
 * @param {string} reason - Reason for deletion
 * @returns {Promise<null>} No content
 */
export async function deletePolicy(policyId, reason = null) {
  try {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return await fetchApi(`/autonomy/policies/${policyId}${params}`, {
      method: 'DELETE',
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, simulating deletion');
      return null;
    }
    throw error;
  }
}

/**
 * Toggle HITL on/off for a policy
 *
 * @param {string} policyId - Policy identifier
 * @param {boolean} hitlEnabled - New HITL state
 * @param {string} reason - Reason for change
 * @returns {Promise<Object>} Updated policy
 */
export async function toggleHITL(policyId, hitlEnabled, reason = null) {
  try {
    return await fetchApi(`/autonomy/policies/${policyId}/toggle`, {
      method: 'PUT',
      body: JSON.stringify({
        hitl_enabled: hitlEnabled,
        reason: reason,
      }),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, using local state');
      return { ...DEFAULT_POLICY, policy_id: policyId, hitl_enabled: hitlEnabled, updated_at: new Date().toISOString() };
    }
    throw error;
  }
}

/**
 * Add an override to a policy
 *
 * @param {string} policyId - Policy identifier
 * @param {string} overrideType - Type: 'severity', 'operation', or 'repository'
 * @param {string} contextValue - Value to match
 * @param {string} autonomyLevel - Autonomy level for this context
 * @param {string} reason - Reason for override
 * @returns {Promise<Object>} Updated policy
 */
export async function addOverride(policyId, overrideType, contextValue, autonomyLevel, reason = null) {
  try {
    return await fetchApi(`/autonomy/policies/${policyId}/override`, {
      method: 'POST',
      body: JSON.stringify({
        override_type: overrideType,
        context_value: contextValue,
        autonomy_level: autonomyLevel,
        reason: reason,
      }),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, using local state');
      return { ...DEFAULT_POLICY, policy_id: policyId, updated_at: new Date().toISOString() };
    }
    throw error;
  }
}

/**
 * Remove an override from a policy
 *
 * @param {string} policyId - Policy identifier
 * @param {string} overrideType - Type: 'severity', 'operation', or 'repository'
 * @param {string} contextValue - Value to remove
 * @returns {Promise<Object>} Updated policy
 */
export async function removeOverride(policyId, overrideType, contextValue) {
  try {
    return await fetchApi(`/autonomy/policies/${policyId}/override`, {
      method: 'DELETE',
      body: JSON.stringify({
        override_type: overrideType,
        context_value: contextValue,
      }),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, using local state');
      return { ...DEFAULT_POLICY, policy_id: policyId, updated_at: new Date().toISOString() };
    }
    throw error;
  }
}

/**
 * Get available policy presets
 *
 * @returns {Promise<Array>} List of presets
 */
export async function getPresets() {
  try {
    return await fetchApi('/autonomy/presets');
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Autonomy presets API not available, using defaults');
      return Object.entries(POLICY_PRESETS).map(([key, preset]) => ({
        name: key,
        display_name: preset.name,
        description: preset.description,
        default_level: preset.defaultLevel,
        hitl_enabled: preset.hitlEnabled,
      }));
    }
    throw error;
  }
}

/**
 * Check if HITL is required for an action
 *
 * @param {string} policyId - Policy identifier
 * @param {string} severity - Action severity
 * @param {string} operation - Operation type
 * @param {string} repository - Repository name (optional)
 * @returns {Promise<Object>} HITL check result
 */
export async function checkHITL(policyId, severity, operation, repository = '') {
  try {
    return await fetchApi('/autonomy/check', {
      method: 'POST',
      body: JSON.stringify({
        policy_id: policyId,
        severity: severity,
        operation: operation,
        repository: repository,
      }),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, returning default HITL check');
      return {
        hitl_required: severity === 'critical' || severity === 'high',
        autonomy_level: 'critical_hitl',
        reason: 'Default policy (API unavailable)',
      };
    }
    throw error;
  }
}

/**
 * Get autonomy decisions history
 *
 * @param {string} organizationId - Organization identifier
 * @param {number} limit - Maximum results
 * @param {string} executionId - Filter by execution ID (optional)
 * @returns {Promise<Array>} List of decisions
 */
export async function getDecisions(organizationId, limit = 100, executionId = null) {
  try {
    const params = new URLSearchParams({
      organization_id: organizationId,
      limit: limit.toString(),
    });
    if (executionId) {
      params.append('execution_id', executionId);
    }
    return await fetchApi(`/autonomy/decisions?${params}`);
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Autonomy API not available, returning empty decisions');
      return [];
    }
    throw error;
  }
}

/**
 * Get autonomy service health
 *
 * @returns {Promise<Object>} Health status
 */
export async function getAutonomyHealth() {
  try {
    return await fetchApi('/autonomy/health');
  } catch (error) {
    return { status: 'unknown', service: 'autonomy_policy_service' };
  }
}

/**
 * Project Aura - Agent Configuration API Service
 *
 * Client-side service for managing agent configurations.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Agent API errors
 */
export class AgentApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'AgentApiError';
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
    throw new AgentApiError(
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
 * Agent type configuration
 */
export const AGENT_TYPES = {
  orchestrator: {
    label: 'Orchestrator',
    description: 'Coordinates multi-agent workflows',
    color: 'olive',
    capabilities: ['workflow_orchestration', 'agent_coordination', 'priority_management'],
  },
  coder: {
    label: 'Coder',
    description: 'Generates and modifies code',
    color: 'aura',
    capabilities: ['code_generation', 'patch_creation', 'refactoring'],
  },
  reviewer: {
    label: 'Reviewer',
    description: 'Reviews code for quality and security',
    color: 'warning',
    capabilities: ['security_review', 'owasp_analysis', 'compliance_check'],
  },
  validator: {
    label: 'Validator',
    description: 'Validates patches in sandbox',
    color: 'olive',
    capabilities: ['sandbox_testing', 'integration_testing', 'regression_testing'],
  },
  scanner: {
    label: 'Scanner',
    description: 'Scans for vulnerabilities',
    color: 'aura',
    capabilities: ['vulnerability_detection', 'cve_matching', 'threat_assessment'],
  },
  external: {
    label: 'External',
    description: 'External A2A agent',
    color: 'warning',
    capabilities: ['static_analysis', 'dependency_check'],
  },
};

/**
 * Default agent configuration template
 */
export const DEFAULT_AGENT_CONFIG = {
  enabled: true,
  max_concurrent_tasks: 5,
  timeout_seconds: 300,
  retry_attempts: 3,
  retry_delay_seconds: 30,
  resource_limits: {
    cpu_millicores: 1000,
    memory_mb: 2048,
    max_tokens_per_request: 16000,
  },
  rate_limits: {
    requests_per_minute: 30,
    requests_per_hour: 500,
  },
  logging: {
    level: 'info',
    include_prompts: false,
    include_responses: false,
  },
  capabilities_enabled: [],
};

/**
 * Get agent configuration
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Agent configuration
 */
export async function getAgentConfig(agentId) {
  try {
    return await fetchApi(`/agents/${agentId}/config`);
  } catch (error) {
    if (error.status === 404) {
      return { ...DEFAULT_AGENT_CONFIG, agent_id: agentId };
    }
    throw error;
  }
}

/**
 * Update agent configuration
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} config - Configuration updates
 * @returns {Promise<Object>} Updated configuration
 */
export async function updateAgentConfig(agentId, config) {
  return fetchApi(`/agents/${agentId}/config`, {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

/**
 * Enable an agent
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Updated agent
 */
export async function enableAgent(agentId) {
  return fetchApi(`/agents/${agentId}/enable`, {
    method: 'POST',
  });
}

/**
 * Disable an agent
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Updated agent
 */
export async function disableAgent(agentId) {
  return fetchApi(`/agents/${agentId}/disable`, {
    method: 'POST',
  });
}

/**
 * Restart an agent
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Restart result
 */
export async function restartAgent(agentId) {
  return fetchApi(`/agents/${agentId}/restart`, {
    method: 'POST',
  });
}

/**
 * Get agent metrics
 *
 * @param {string} agentId - Agent identifier
 * @param {string} period - Time period (1h, 24h, 7d)
 * @returns {Promise<Object>} Agent metrics
 */
export async function getAgentMetrics(agentId, period = '24h') {
  try {
    return await fetchApi(`/agents/${agentId}/metrics?period=${period}`);
  } catch (error) {
    if (error.status === 404) {
      return {
        tasks_completed: 0,
        success_rate: 0,
        avg_execution_time: 0,
        tokens_used: 0,
        errors: 0,
      };
    }
    throw error;
  }
}

/**
 * Get all agents
 *
 * @returns {Promise<Array>} List of agents
 */
export async function getAgents() {
  try {
    return await fetchApi('/agents');
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Get agent health status
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Health status
 */
export async function getAgentHealth(agentId) {
  try {
    return await fetchApi(`/agents/${agentId}/health`);
  } catch (error) {
    return { status: 'unknown', agent_id: agentId };
  }
}

/**
 * Deploy a new agent
 *
 * @param {Object} agentConfig - Agent deployment configuration
 * @param {string} agentConfig.name - Agent name
 * @param {string} agentConfig.type - Agent type (orchestrator, coder, reviewer, etc.)
 * @param {string} agentConfig.description - Agent description
 * @param {Array} agentConfig.capabilities - Enabled capabilities
 * @param {Object} agentConfig.resource_limits - Resource limits configuration
 * @returns {Promise<Object>} Deployed agent
 */
export async function deployAgent(agentConfig) {
  return fetchApi('/agents', {
    method: 'POST',
    body: JSON.stringify({
      ...DEFAULT_AGENT_CONFIG,
      ...agentConfig,
      capabilities_enabled: agentConfig.capabilities || [],
    }),
  });
}

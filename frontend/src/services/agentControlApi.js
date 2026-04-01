/**
 * Project Aura - Agent Control API Service
 *
 * Client-side service for managing agent lifecycle operations:
 * start, stop, pause, resume, delete, and status updates.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Agent Control API errors
 */
export class AgentControlError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'AgentControlError';
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
    throw new AgentControlError(
      errorData.detail || errorData.error || errorData.message || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

// =============================================================================
// Agent Status Constants
// =============================================================================

export const AGENT_STATUS = {
  ACTIVE: 'active',
  IDLE: 'idle',
  BUSY: 'busy',
  PAUSED: 'paused',
  STOPPED: 'stopped',
  DEGRADED: 'degraded',
  ERROR: 'error',
  PENDING: 'pending',
  STARTING: 'starting',
  STOPPING: 'stopping',
};

export const AGENT_ACTIONS = {
  START: 'start',
  STOP: 'stop',
  PAUSE: 'pause',
  RESUME: 'resume',
  RESTART: 'restart',
  DELETE: 'delete',
  CONFIGURE: 'configure',
};

// =============================================================================
// Agent Control Operations
// =============================================================================

/**
 * Start an agent
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Start options (optional)
 * @returns {Promise<Object>} Updated agent status
 */
export async function startAgent(agentId, options = {}) {
  return fetchApi(`/agents/${agentId}/start`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
}

/**
 * Stop an agent
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Stop options (graceful, force, timeout)
 * @returns {Promise<Object>} Updated agent status
 */
export async function stopAgent(agentId, options = { graceful: true, timeout: 30 }) {
  return fetchApi(`/agents/${agentId}/stop`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
}

/**
 * Pause an agent (suspends task processing without stopping)
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Pause options
 * @returns {Promise<Object>} Updated agent status
 */
export async function pauseAgent(agentId, options = {}) {
  return fetchApi(`/agents/${agentId}/pause`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
}

/**
 * Resume a paused agent
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Resume options
 * @returns {Promise<Object>} Updated agent status
 */
export async function resumeAgent(agentId, options = {}) {
  return fetchApi(`/agents/${agentId}/resume`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
}

/**
 * Restart an agent
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Restart options
 * @returns {Promise<Object>} Updated agent status
 */
export async function restartAgent(agentId, options = {}) {
  return fetchApi(`/agents/${agentId}/restart`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
}

/**
 * Delete an agent
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Delete options (force, cleanup)
 * @returns {Promise<Object>} Deletion result
 */
export async function deleteAgent(agentId, options = { force: false, cleanup: true }) {
  return fetchApi(`/agents/${agentId}`, {
    method: 'DELETE',
    body: JSON.stringify(options),
  });
}

// =============================================================================
// Agent Status Operations
// =============================================================================

/**
 * Get agent status
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Agent status
 */
export async function getAgentStatus(agentId) {
  try {
    return await fetchApi(`/agents/${agentId}/status`);
  } catch (error) {
    if (error.status === 404) {
      return {
        agent_id: agentId,
        status: AGENT_STATUS.ERROR,
        message: 'Agent not found',
      };
    }
    throw error;
  }
}

/**
 * Get all agents with status
 *
 * @param {Object} filters - Optional filters (status, type)
 * @returns {Promise<Array>} List of agents with status
 */
export async function getAgentsWithStatus(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.status) params.append('status', filters.status);
    if (filters.type) params.append('type', filters.type);

    const queryString = params.toString();
    const endpoint = queryString ? `/agents?${queryString}` : '/agents';
    return await fetchApi(endpoint);
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Get agent task history
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} options - Query options (limit, offset, status)
 * @returns {Promise<Array>} Task history
 */
export async function getAgentTaskHistory(agentId, options = { limit: 20 }) {
  try {
    const params = new URLSearchParams();
    if (options.limit) params.append('limit', options.limit);
    if (options.offset) params.append('offset', options.offset);
    if (options.status) params.append('status', options.status);

    const queryString = params.toString();
    return await fetchApi(`/agents/${agentId}/tasks?${queryString}`);
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}

// =============================================================================
// Agent Configuration Operations
// =============================================================================

/**
 * Get agent configuration
 *
 * @param {string} agentId - Agent identifier
 * @returns {Promise<Object>} Agent configuration
 */
export async function getAgentConfig(agentId) {
  return fetchApi(`/agents/${agentId}/config`);
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
 * Validate agent configuration
 *
 * @param {string} agentId - Agent identifier
 * @param {Object} config - Configuration to validate
 * @returns {Promise<Object>} Validation result with errors if any
 */
export async function validateAgentConfig(agentId, config) {
  try {
    return await fetchApi(`/agents/${agentId}/config/validate`, {
      method: 'POST',
      body: JSON.stringify(config),
    });
  } catch (error) {
    // Return validation errors as result instead of throwing
    if (error.status === 400 && error.details?.validation_errors) {
      return {
        valid: false,
        errors: error.details.validation_errors,
      };
    }
    throw error;
  }
}

/**
 * Get configuration version history
 *
 * @param {string} agentId - Agent identifier
 * @param {number} limit - Number of versions to return
 * @returns {Promise<Array>} Configuration version history
 */
export async function getConfigVersions(agentId, limit = 10) {
  try {
    return await fetchApi(`/agents/${agentId}/config/versions?limit=${limit}`);
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Restore configuration to a specific version
 *
 * @param {string} agentId - Agent identifier
 * @param {string} versionId - Version ID to restore
 * @returns {Promise<Object>} Restored configuration
 */
export async function restoreConfigVersion(agentId, versionId) {
  return fetchApi(`/agents/${agentId}/config/restore/${versionId}`, {
    method: 'POST',
  });
}

// =============================================================================
// Batch Operations
// =============================================================================

/**
 * Perform batch action on multiple agents
 *
 * @param {Array<string>} agentIds - List of agent IDs
 * @param {string} action - Action to perform (start, stop, pause, resume)
 * @param {Object} options - Action options
 * @returns {Promise<Object>} Batch operation result
 */
export async function batchAgentAction(agentIds, action, options = {}) {
  return fetchApi('/agents/batch', {
    method: 'POST',
    body: JSON.stringify({
      agent_ids: agentIds,
      action,
      options,
    }),
  });
}

// =============================================================================
// Config Validation Helpers
// =============================================================================

/**
 * Validate configuration before saving
 *
 * @param {Object} config - Configuration to validate
 * @returns {Object} Validation result { valid: boolean, errors: Array }
 */
export function validateConfigLocally(config) {
  const errors = [];

  // Validate max concurrent tasks
  if (config.max_concurrent_tasks !== undefined) {
    if (config.max_concurrent_tasks < 1 || config.max_concurrent_tasks > 50) {
      errors.push({
        field: 'max_concurrent_tasks',
        message: 'Must be between 1 and 50',
      });
    }
  }

  // Validate timeout
  if (config.timeout_seconds !== undefined) {
    if (config.timeout_seconds < 10 || config.timeout_seconds > 3600) {
      errors.push({
        field: 'timeout_seconds',
        message: 'Must be between 10 and 3600 seconds',
      });
    }
  }

  // Validate retry attempts
  if (config.retry_attempts !== undefined) {
    if (config.retry_attempts < 0 || config.retry_attempts > 10) {
      errors.push({
        field: 'retry_attempts',
        message: 'Must be between 0 and 10',
      });
    }
  }

  // Validate resource limits
  if (config.resource_limits) {
    const { cpu_millicores, memory_mb, max_tokens_per_request } = config.resource_limits;

    if (cpu_millicores !== undefined && (cpu_millicores < 100 || cpu_millicores > 8000)) {
      errors.push({
        field: 'resource_limits.cpu_millicores',
        message: 'CPU must be between 100 and 8000 millicores',
      });
    }

    if (memory_mb !== undefined && (memory_mb < 256 || memory_mb > 32768)) {
      errors.push({
        field: 'resource_limits.memory_mb',
        message: 'Memory must be between 256 MB and 32 GB',
      });
    }

    if (max_tokens_per_request !== undefined && (max_tokens_per_request < 100 || max_tokens_per_request > 200000)) {
      errors.push({
        field: 'resource_limits.max_tokens_per_request',
        message: 'Max tokens must be between 100 and 200,000',
      });
    }
  }

  // Validate rate limits
  if (config.rate_limits) {
    const { requests_per_minute, requests_per_hour } = config.rate_limits;

    if (requests_per_minute !== undefined && (requests_per_minute < 1 || requests_per_minute > 200)) {
      errors.push({
        field: 'rate_limits.requests_per_minute',
        message: 'Must be between 1 and 200 requests per minute',
      });
    }

    if (requests_per_hour !== undefined && (requests_per_hour < 1 || requests_per_hour > 10000)) {
      errors.push({
        field: 'rate_limits.requests_per_hour',
        message: 'Must be between 1 and 10,000 requests per hour',
      });
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export default {
  // Control operations
  startAgent,
  stopAgent,
  pauseAgent,
  resumeAgent,
  restartAgent,
  deleteAgent,

  // Status operations
  getAgentStatus,
  getAgentsWithStatus,
  getAgentTaskHistory,

  // Config operations
  getAgentConfig,
  updateAgentConfig,
  validateAgentConfig,
  getConfigVersions,
  restoreConfigVersion,

  // Batch operations
  batchAgentAction,

  // Helpers
  validateConfigLocally,

  // Constants
  AGENT_STATUS,
  AGENT_ACTIONS,
};

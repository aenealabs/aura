/**
 * Project Aura - Model Router API Service
 *
 * Client-side service for LLM model routing configuration and analytics.
 * Provides visibility into model selection decisions, cost savings, and routing rules.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Model Router API errors
 */
export class ModelRouterApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ModelRouterApiError';
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
    throw new ModelRouterApiError(
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
 * Model tier options
 */
export const ModelTiers = {
  FAST: 'fast',
  ACCURATE: 'accurate',
  MAXIMUM: 'maximum',
};

/**
 * Task complexity options
 */
export const TaskComplexity = {
  SIMPLE: 'simple',
  MEDIUM: 'medium',
  COMPLEX: 'complex',
};

/**
 * Model display information
 */
export const MODEL_INFO = {
  fast: {
    name: 'Claude Haiku',
    description: 'Fast, cost-effective for simple tasks',
    color: '#3B82F6',
    costPer1k: 0.00025,
  },
  accurate: {
    name: 'Claude Sonnet',
    description: 'Balanced performance for standard tasks',
    color: '#7C9A3E',
    costPer1k: 0.003,
  },
  maximum: {
    name: 'Claude Opus',
    description: 'Maximum capability for complex tasks',
    color: '#EA580C',
    costPer1k: 0.015,
  },
};

/**
 * Complexity badge styles
 */
export const COMPLEXITY_STYLES = {
  simple: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-700 dark:text-olive-400',
    label: 'Simple',
  },
  medium: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-700 dark:text-warning-400',
    label: 'Medium',
  },
  complex: {
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    text: 'text-critical-700 dark:text-critical-400',
    label: 'Complex',
  },
};

/**
 * Default stats data for development/fallback
 */
export const DEFAULT_STATS = {
  costSavings: {
    percentage: 42,
    amount: 1247.50,
    trend: [35, 38, 40, 37, 42, 45, 43, 48, 44, 42],
    baseline_cost: 2150.00,
    optimized_cost: 902.50,
    period: '30d',
  },
  distribution: {
    distribution: [
      { model: 'Claude Haiku', tier: 'fast', percentage: 68, count: 6800, color: '#3B82F6' },
      { model: 'Claude Sonnet', tier: 'accurate', percentage: 28, count: 2800, color: '#7C9A3E' },
      { model: 'Claude Opus', tier: 'maximum', percentage: 4, count: 400, color: '#EA580C' },
    ],
    total_requests: 10000,
    period: '30d',
  },
  abTest: {
    enabled: false,
    experiment_id: '',
    experiment_name: '',
    control_tier: 'accurate',
    treatment_tier: 'fast',
    traffic_split: 0.5,
    task_types: [],
    status: 'inactive',
  },
  total_decisions: 10000,
};

/**
 * Default routing rules for development/fallback
 */
export const DEFAULT_RULES = [
  { id: 'rule-0', task_type: 'query_intent_analysis', complexity: 'simple', tier: 'fast', model: 'Claude Haiku', cost_per_1k: 0.00025, description: 'Classify query intent', enabled: true },
  { id: 'rule-1', task_type: 'query_expansion', complexity: 'simple', tier: 'fast', model: 'Claude Haiku', cost_per_1k: 0.00025, description: 'Expand search queries', enabled: true },
  { id: 'rule-2', task_type: 'patch_generation', complexity: 'medium', tier: 'accurate', model: 'Claude Sonnet', cost_per_1k: 0.003, description: 'Generate patches', enabled: true },
  { id: 'rule-3', task_type: 'code_review', complexity: 'medium', tier: 'accurate', model: 'Claude Sonnet', cost_per_1k: 0.003, description: 'Review code', enabled: true },
  { id: 'rule-4', task_type: 'cross_codebase_correlation', complexity: 'complex', tier: 'maximum', model: 'Claude Opus', cost_per_1k: 0.015, description: 'Cross-codebase analysis', enabled: true },
];

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get comprehensive router statistics
 *
 * @param {string} period - Time period: 7d, 30d, 90d
 * @returns {Promise<Object>} Router stats including cost savings and distribution
 */
export async function getRouterStats(period = '30d') {
  try {
    return await fetchApi(`/model-router/stats?period=${period}`);
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model router stats endpoint not available, using defaults');
      return DEFAULT_STATS;
    }
    throw error;
  }
}

/**
 * Get model distribution data
 *
 * @param {string} period - Time period
 * @returns {Promise<Object>} Model distribution data
 */
export async function getModelDistribution(period = '30d') {
  try {
    return await fetchApi(`/model-router/distribution?period=${period}`);
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model distribution endpoint not available, using defaults');
      return DEFAULT_STATS.distribution;
    }
    throw error;
  }
}

/**
 * Get all routing rules
 *
 * @returns {Promise<Array>} List of routing rules
 */
export async function getRoutingRules() {
  try {
    return await fetchApi('/model-router/rules');
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Routing rules endpoint not available, using defaults');
      return DEFAULT_RULES;
    }
    throw error;
  }
}

/**
 * Create a new routing rule
 *
 * @param {Object} rule - Rule data
 * @returns {Promise<Object>} Created rule
 */
export async function createRoutingRule(rule) {
  try {
    return await fetchApi('/model-router/rules', {
      method: 'POST',
      body: JSON.stringify(rule),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model router API not available, using local state');
      return { ...rule, id: `rule-${Date.now()}`, created: true };
    }
    throw error;
  }
}

/**
 * Update an existing routing rule
 *
 * @param {string} ruleId - Rule ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated rule
 */
export async function updateRoutingRule(ruleId, updates) {
  try {
    return await fetchApi(`/model-router/rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model router API not available, using local state');
      return { id: ruleId, ...updates, updated: true };
    }
    throw error;
  }
}

/**
 * Delete a routing rule
 *
 * @param {string} ruleId - Rule ID
 * @returns {Promise<null>}
 */
export async function deleteRoutingRule(ruleId) {
  try {
    return await fetchApi(`/model-router/rules/${ruleId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model router API not available, simulating deletion');
      return null;
    }
    throw error;
  }
}

/**
 * Get A/B test configuration
 *
 * @returns {Promise<Object>} A/B test config
 */
export async function getABTestConfig() {
  try {
    return await fetchApi('/model-router/ab-test');
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('A/B test config endpoint not available, using defaults');
      return DEFAULT_STATS.abTest;
    }
    throw error;
  }
}

/**
 * Update A/B test configuration
 *
 * @param {Object} config - A/B test configuration
 * @returns {Promise<Object>} Updated config
 */
export async function updateABTestConfig(config) {
  try {
    return await fetchApi('/model-router/ab-test', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model router API not available, using local state');
      return { ...DEFAULT_STATS.abTest, ...config, updated: true };
    }
    throw error;
  }
}

/**
 * Get per-investigation cost breakdown
 *
 * @param {string} period - Time period
 * @param {number} limit - Max results
 * @returns {Promise<Object>} Investigation costs
 */
export async function getInvestigationCosts(period = '7d', limit = 20) {
  try {
    return await fetchApi(`/model-router/costs?period=${period}&limit=${limit}`);
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Investigation costs endpoint not available, using defaults');
      return { investigations: [], total_cost: 0, period };
    }
    throw error;
  }
}

/**
 * Refresh router configuration
 *
 * @returns {Promise<Object>} Status message
 */
export async function refreshRouterConfig() {
  try {
    return await fetchApi('/model-router/refresh', {
      method: 'POST',
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Model router API not available, simulating refresh');
      return { status: 'refreshed', message: 'Configuration refreshed (dev mode)' };
    }
    throw error;
  }
}

/**
 * Format cost for display
 *
 * @param {number} cost - Cost in USD
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted cost string
 */
export function formatCost(cost, decimals = 2) {
  if (cost < 0.01) {
    return `$${cost.toFixed(5)}`;
  }
  return `$${cost.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

/**
 * Format large numbers with K/M suffixes
 *
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
export function formatNumber(num) {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toLocaleString();
}

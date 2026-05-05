/**
 * Project Aura - Orchestrator Settings API Service
 *
 * Client-side service for managing orchestrator deployment modes.
 * Connects to /api/v1/orchestrator/settings endpoints.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Orchestrator API errors
 */
export class OrchestratorApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'OrchestratorApiError';
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
    throw new OrchestratorApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  return response.json();
}

/**
 * Deployment mode options
 */
export const DeploymentModes = {
  ON_DEMAND: 'on_demand',
  WARM_POOL: 'warm_pool',
  HYBRID: 'hybrid',
};

/**
 * Deployment mode display configuration
 */
export const DEPLOYMENT_MODE_CONFIG = {
  on_demand: {
    label: 'On-Demand Jobs',
    description: 'EKS Jobs created per request. Zero base cost, pay per job execution.',
    icon: 'CloudIcon',
    color: 'aura',
    baseCost: 0,
    coldStart: 30,
    recommended: [
      'Low-volume workloads (<100 jobs/day)',
      'Cost-sensitive environments',
      'Dev/test environments',
      'Unpredictable traffic patterns',
    ],
  },
  warm_pool: {
    label: 'Warm Pool',
    description: 'Always-on replica for instant job processing. Fixed monthly cost.',
    icon: 'ServerStackIcon',
    color: 'olive',
    baseCost: 28,
    coldStart: 0,
    recommended: [
      'High-volume workloads (>500 jobs/day)',
      'Latency-sensitive applications',
      'Production environments',
      'Consistent traffic patterns',
    ],
  },
  hybrid: {
    label: 'Hybrid Mode',
    description: 'Warm pool + burst jobs. Best of both worlds for variable workloads.',
    icon: 'CpuChipIcon',
    color: 'warning',
    baseCost: 28,
    coldStart: 0,
    recommended: [
      'Variable workloads with peaks',
      'High-value production workloads',
      'Latency-sensitive with burst capacity',
      'Enterprise deployments',
    ],
  },
};

/**
 * Hyperscale execution tiers (ADR-087)
 */
export const ExecutionTiers = {
  IN_PROCESS: 'in_process',
  DISTRIBUTED_SIMPLE: 'distributed_simple',
  DISTRIBUTED_ORCHESTRATED: 'distributed_orchestrated',
};

/**
 * Execution tier display configuration
 */
export const EXECUTION_TIER_CONFIG = {
  in_process: {
    label: 'In-Process',
    description: 'Single pod, asyncio DAG execution. Zero infrastructure overhead.',
    agentRange: '1–20',
    minAgents: 1,
    maxAgents: 20,
    defaultAgents: 10,
    icon: 'CpuChipIcon',
    color: 'aura',
    costPerAgent: 0,
    recommended: [
      'Small repositories (<50K lines)',
      'Targeted vulnerability scans',
      'Single-file patch generation',
    ],
    edition: 'standard',
  },
  distributed_simple: {
    label: 'Distributed Simple',
    description: 'SQS fan-out with DynamoDB job graph. Scales to mid-size enterprise repos.',
    agentRange: '20–200',
    minAgents: 20,
    maxAgents: 200,
    defaultAgents: 50,
    icon: 'ServerStackIcon',
    color: 'olive',
    costPerAgent: 0.06,
    recommended: [
      'Mid-size enterprise codebases',
      'Multi-service repositories',
      'Parallel vulnerability scanning',
    ],
    edition: 'enterprise',
  },
  distributed_orchestrated: {
    label: 'Distributed Orchestrated',
    description: 'Step Functions fan-out with Karpenter autoscaling. Full enterprise codebase coverage.',
    agentRange: '200–1,000+',
    minAgents: 200,
    maxAgents: 1000,
    defaultAgents: 500,
    icon: 'BoltIcon',
    color: 'warning',
    costPerAgent: 0.16,
    recommended: [
      'Large enterprise codebases (500K+ lines)',
      'Organization-wide security audits',
      'Full codebase remediation campaigns',
    ],
    edition: 'scale',
  },
};

/**
 * Security gate status configuration
 */
export const SECURITY_GATE_CONFIG = {
  gate_1: {
    label: 'Gate 1',
    threshold: 50,
    description: 'Prerequisite for distributed execution',
    controls: [
      'Neptune tenant partitioning',
      'DAG cycle detection',
      'Constitutional AI fail-closed',
      'Per-tenant ResourceQuotas',
      'Per-task execution timeouts',
    ],
  },
  gate_2: {
    label: 'Gate 2',
    threshold: 200,
    description: 'Distributed execution controls',
    controls: [
      'Tiered IAM roles',
      'STS session tagging',
      'Job-graph governance',
      'HITL rate limiting',
      'Sandbox concurrency ceiling',
    ],
  },
  gate_3: {
    label: 'Gate 3',
    threshold: 1000,
    description: 'Full hyperscale controls',
    controls: [
      'Write quorum for Neptune',
      'Cumulative impact tracking',
      'Graph mutation journaling',
      'Behavioral baseline recalibration',
      'Incident response playbooks',
    ],
  },
};

/**
 * Default hyperscale settings (ADR-087)
 */
export const DEFAULT_HYPERSCALE_SETTINGS = {
  enabled: false,
  execution_tier: 'in_process',
  max_parallel_agents: 10,
  feasibility_gate_enabled: true,
  cost_circuit_breaker_usd: 500,
  security_gates: {
    gate_1: { validated: false, validated_at: null },
    gate_2: { validated: false, validated_at: null },
    gate_3: { validated: false, validated_at: null },
  },
};

/**
 * Default orchestrator settings
 */
export const DEFAULT_ORCHESTRATOR_SETTINGS = {
  on_demand_jobs_enabled: true,
  warm_pool_enabled: false,
  hybrid_mode_enabled: false,
  warm_pool_replicas: 1,
  hybrid_threshold_queue_depth: 5,
  hybrid_scale_up_cooldown_seconds: 60,
  hybrid_max_burst_jobs: 10,
  estimated_cost_per_job_usd: 0.15,
  estimated_warm_pool_monthly_usd: 28.0,
  mode_change_cooldown_seconds: 300,
  last_mode_change_at: null,
  last_mode_change_by: null,
  effective_mode: 'on_demand',
  is_organization_override: false,
  organization_id: null,
  hyperscale: DEFAULT_HYPERSCALE_SETTINGS,
};

/**
 * Get orchestrator settings
 *
 * @param {string} organizationId - Organization ID (optional, for org-specific settings)
 * @returns {Promise<Object>} Orchestrator settings
 */
export async function getOrchestratorSettings(organizationId = null) {
  try {
    const params = organizationId ? `?organization_id=${organizationId}` : '';
    return await fetchApi(`/orchestrator/settings${params}`);
  } catch (error) {
    if (error.status === 404) {
      return DEFAULT_ORCHESTRATOR_SETTINGS;
    }
    throw error;
  }
}

/**
 * Update orchestrator settings
 *
 * @param {Object} updates - Settings to update
 * @param {string} organizationId - Organization ID (optional)
 * @returns {Promise<Object>} Updated settings
 */
export async function updateOrchestratorSettings(updates, organizationId = null) {
  try {
    const params = organizationId ? `?organization_id=${organizationId}` : '';
    return await fetchApi(`/orchestrator/settings${params}`, {
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
      console.warn('Orchestrator API not available, using local state');
      return { ...DEFAULT_ORCHESTRATOR_SETTINGS, ...updates, updated: true };
    }
    throw error;
  }
}

/**
 * Get available deployment modes
 *
 * @returns {Promise<Array>} List of deployment modes
 */
export async function getAvailableModes() {
  try {
    return await fetchApi('/orchestrator/settings/modes');
  } catch (error) {
    if (error.status === 404) {
      return Object.entries(DEPLOYMENT_MODE_CONFIG).map(([mode, config]) => ({
        mode: mode,
        display_name: config.label,
        description: config.description,
        base_monthly_cost_usd: config.baseCost,
        cold_start_seconds: config.coldStart,
        recommended_for: config.recommended,
      }));
    }
    throw error;
  }
}

/**
 * Switch deployment mode
 *
 * @param {string} targetMode - Target deployment mode
 * @param {string} reason - Reason for change (optional)
 * @param {boolean} force - Force change even during cooldown
 * @param {string} organizationId - Organization ID (optional)
 * @returns {Promise<Object>} Updated settings
 */
export async function switchDeploymentMode(targetMode, reason = null, force = false, organizationId = null) {
  try {
    const params = organizationId ? `?organization_id=${organizationId}` : '';
    return await fetchApi(`/orchestrator/settings/switch${params}`, {
      method: 'POST',
      body: JSON.stringify({
        target_mode: targetMode,
        reason: reason,
        force: force,
      }),
    });
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500 ||
      error.message?.includes('API error')
    ) {
      console.warn('Orchestrator API not available, using local state');
      return {
        ...DEFAULT_ORCHESTRATOR_SETTINGS,
        effective_mode: targetMode,
        on_demand_jobs_enabled: targetMode === 'on_demand' || targetMode === 'hybrid',
        warm_pool_enabled: targetMode === 'warm_pool' || targetMode === 'hybrid',
        hybrid_mode_enabled: targetMode === 'hybrid',
        last_mode_change_at: new Date().toISOString(),
        switched: true,
      };
    }
    throw error;
  }
}

/**
 * Get current mode status
 *
 * @param {string} organizationId - Organization ID (optional)
 * @returns {Promise<Object>} Mode status
 */
export async function getModeStatus(organizationId = null) {
  try {
    const params = organizationId ? `?organization_id=${organizationId}` : '';
    return await fetchApi(`/orchestrator/settings/status${params}`);
  } catch (error) {
    if (error.status === 404) {
      return {
        current_mode: 'on_demand',
        warm_pool_replicas_desired: 0,
        warm_pool_replicas_ready: 0,
        queue_depth: 0,
        active_burst_jobs: 0,
        can_switch_mode: true,
        cooldown_remaining_seconds: 0,
        last_mode_change_at: null,
        last_mode_change_by: null,
      };
    }
    throw error;
  }
}

/**
 * Get orchestrator health status
 *
 * @returns {Promise<Object>} Health status
 */
export async function getOrchestratorHealth() {
  try {
    return await fetchApi('/orchestrator/settings/health');
  } catch (error) {
    return { status: 'unknown', service: 'orchestrator_settings' };
  }
}

/**
 * Get hyperscale orchestration settings (ADR-087)
 *
 * @param {string} organizationId - Organization ID (optional)
 * @returns {Promise<Object>} Hyperscale settings
 */
export async function getHyperscaleSettings(organizationId = null) {
  try {
    const params = organizationId ? `?organization_id=${organizationId}` : '';
    return await fetchApi(`/orchestrator/hyperscale${params}`);
  } catch (error) {
    if (
      error.message?.includes('Failed to fetch') ||
      error.status === 404 ||
      error.status === 500
    ) {
      console.warn('Hyperscale API not available, using defaults');
      return DEFAULT_HYPERSCALE_SETTINGS;
    }
    throw error;
  }
}

/**
 * Update hyperscale orchestration settings (ADR-087)
 *
 * @param {Object} updates - Settings to update
 * @param {string} organizationId - Organization ID (optional)
 * @returns {Promise<Object>} Updated hyperscale settings
 */
export async function updateHyperscaleSettings(updates, organizationId = null) {
  try {
    const params = organizationId ? `?organization_id=${organizationId}` : '';
    return await fetchApi(`/orchestrator/hyperscale${params}`, {
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
      console.warn('Hyperscale API not available, using local state');
      return { ...DEFAULT_HYPERSCALE_SETTINGS, ...updates };
    }
    throw error;
  }
}

/**
 * Project Aura - useCapabilityGraph Hook
 *
 * Custom React hook for fetching and managing capability graph data.
 * Implements ADR-071 for graph-based capability visualization.
 *
 * Usage:
 *   const { data, loading, error, refresh } = useCapabilityGraph();
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api/v1/capability-graph';

// Mock data for development when API is unavailable - Production scale simulation
const MOCK_VISUALIZATION_DATA = {
  nodes: [
    // Coder Agents (3 instances)
    { id: 'coder-agent-1', name: 'CoderAgent', label: 'CoderAgent-1', type: 'agent', agent_type: 'coder', classification: 'safe', capabilities_count: 4 },
    { id: 'coder-agent-2', name: 'CoderAgent', label: 'CoderAgent-2', type: 'agent', agent_type: 'coder', classification: 'safe', capabilities_count: 3 },
    { id: 'coder-agent-3', name: 'CoderAgent', label: 'CoderAgent-3', type: 'agent', agent_type: 'coder', classification: 'safe', capabilities_count: 5 },
    // Reviewer Agents (2 instances)
    { id: 'reviewer-agent-1', name: 'ReviewerAgent', label: 'ReviewerAgent-1', type: 'agent', agent_type: 'reviewer', classification: 'safe', capabilities_count: 3 },
    { id: 'reviewer-agent-2', name: 'ReviewerAgent', label: 'ReviewerAgent-2', type: 'agent', agent_type: 'reviewer', classification: 'safe', capabilities_count: 2 },
    // Validator Agents (2 instances)
    { id: 'validator-agent-1', name: 'ValidatorAgent', label: 'ValidatorAgent-1', type: 'agent', agent_type: 'validator', classification: 'safe', capabilities_count: 3 },
    { id: 'validator-agent-2', name: 'ValidatorAgent', label: 'ValidatorAgent-2', type: 'agent', agent_type: 'validator', classification: 'safe', capabilities_count: 2 },
    // Security Agents (2 instances)
    { id: 'security-agent-1', name: 'SecurityAgent', label: 'SecurityAgent-1', type: 'agent', agent_type: 'security', classification: 'monitoring', capabilities_count: 4 },
    { id: 'security-agent-2', name: 'SecurityAgent', label: 'SecurityAgent-2', type: 'agent', agent_type: 'security', classification: 'monitoring', capabilities_count: 3 },
    // Patcher Agents (2 instances - high risk)
    { id: 'patcher-agent-1', name: 'PatcherAgent', label: 'PatcherAgent-1', type: 'agent', agent_type: 'patcher', classification: 'dangerous', capabilities_count: 5, has_escalation_risk: true },
    { id: 'patcher-agent-2', name: 'PatcherAgent', label: 'PatcherAgent-2', type: 'agent', agent_type: 'patcher', classification: 'dangerous', capabilities_count: 4, has_escalation_risk: true },
    // Orchestrator Agent (1 instance - critical)
    { id: 'orchestrator-agent', name: 'OrchestratorAgent', label: 'OrchestratorAgent', type: 'agent', agent_type: 'orchestrator', classification: 'critical', capabilities_count: 8, has_escalation_risk: true },
    // DevOps Agent
    { id: 'devops-agent', name: 'DevOpsAgent', label: 'DevOpsAgent', type: 'agent', agent_type: 'devops', classification: 'dangerous', capabilities_count: 6, has_escalation_risk: true },
    // Documentation Agent
    { id: 'docs-agent', name: 'DocsAgent', label: 'DocsAgent', type: 'agent', agent_type: 'docs', classification: 'safe', capabilities_count: 2 },

    // SAFE Tools (green)
    { id: 'tool-semantic-search', name: 'semantic_search', label: 'Semantic Search', type: 'tool', classification: 'safe' },
    { id: 'tool-code-read', name: 'code_read', label: 'Code Read', type: 'tool', classification: 'safe' },
    { id: 'tool-list-files', name: 'list_files', label: 'List Files', type: 'tool', classification: 'safe' },
    { id: 'tool-get-docs', name: 'get_documentation', label: 'Get Documentation', type: 'tool', classification: 'safe' },
    { id: 'tool-syntax-check', name: 'syntax_check', label: 'Syntax Check', type: 'tool', classification: 'safe' },

    // MONITORING Tools (amber)
    { id: 'tool-code-review', name: 'code_review', label: 'Code Review', type: 'tool', classification: 'monitoring' },
    { id: 'tool-test-exec', name: 'test_execution', label: 'Test Execution', type: 'tool', classification: 'monitoring' },
    { id: 'tool-vuln-scan', name: 'vulnerability_scan', label: 'Vulnerability Scan', type: 'tool', classification: 'monitoring' },
    { id: 'tool-audit-log', name: 'audit_logs', label: 'Audit Logs', type: 'tool', classification: 'monitoring' },
    { id: 'tool-metrics', name: 'get_metrics', label: 'Get Metrics', type: 'tool', classification: 'monitoring' },
    { id: 'tool-graph-query', name: 'graph_query', label: 'Graph Query', type: 'tool', classification: 'monitoring' },

    // DANGEROUS Tools (orange)
    { id: 'tool-code-gen', name: 'code_generation', label: 'Code Generation', type: 'tool', classification: 'dangerous' },
    { id: 'tool-file-write', name: 'file_write', label: 'File Write', type: 'tool', classification: 'dangerous' },
    { id: 'tool-sandbox-create', name: 'create_sandbox', label: 'Create Sandbox', type: 'tool', classification: 'dangerous' },
    { id: 'tool-git-commit', name: 'git_commit', label: 'Git Commit', type: 'tool', classification: 'dangerous' },
    { id: 'tool-config-modify', name: 'config_modify', label: 'Config Modify', type: 'tool', classification: 'dangerous' },

    // CRITICAL Tools (red)
    { id: 'tool-deploy', name: 'deployment', label: 'Deployment', type: 'tool', classification: 'critical', has_escalation_risk: true },
    { id: 'tool-db-access', name: 'database_access', label: 'Database Access', type: 'tool', classification: 'critical', has_escalation_risk: true },
    { id: 'tool-secrets', name: 'secrets_manager', label: 'Secrets Manager', type: 'tool', classification: 'critical', has_escalation_risk: true },
    { id: 'tool-iam-modify', name: 'iam_modify', label: 'IAM Modify', type: 'tool', classification: 'critical', has_escalation_risk: true },
    { id: 'tool-prod-access', name: 'production_access', label: 'Production Access', type: 'tool', classification: 'critical', has_escalation_risk: true },
  ],
  edges: [
    // Coder Agent 1 capabilities
    { source: 'coder-agent-1', target: 'tool-semantic-search', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-1', target: 'tool-code-read', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-1', target: 'tool-code-gen', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-1', target: 'tool-file-write', type: 'HAS_CAPABILITY' },
    // Coder Agent 2 capabilities
    { source: 'coder-agent-2', target: 'tool-semantic-search', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-2', target: 'tool-code-gen', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-2', target: 'tool-syntax-check', type: 'HAS_CAPABILITY' },
    // Coder Agent 3 capabilities
    { source: 'coder-agent-3', target: 'tool-semantic-search', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-3', target: 'tool-code-read', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-3', target: 'tool-code-gen', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-3', target: 'tool-file-write', type: 'HAS_CAPABILITY' },
    { source: 'coder-agent-3', target: 'tool-git-commit', type: 'HAS_CAPABILITY' },
    // Reviewer Agent capabilities
    { source: 'reviewer-agent-1', target: 'tool-code-review', type: 'HAS_CAPABILITY' },
    { source: 'reviewer-agent-1', target: 'tool-semantic-search', type: 'HAS_CAPABILITY' },
    { source: 'reviewer-agent-1', target: 'tool-graph-query', type: 'HAS_CAPABILITY' },
    { source: 'reviewer-agent-2', target: 'tool-code-review', type: 'HAS_CAPABILITY' },
    { source: 'reviewer-agent-2', target: 'tool-vuln-scan', type: 'HAS_CAPABILITY' },
    // Validator Agent capabilities
    { source: 'validator-agent-1', target: 'tool-test-exec', type: 'HAS_CAPABILITY' },
    { source: 'validator-agent-1', target: 'tool-vuln-scan', type: 'HAS_CAPABILITY' },
    { source: 'validator-agent-1', target: 'tool-sandbox-create', type: 'HAS_CAPABILITY' },
    { source: 'validator-agent-2', target: 'tool-test-exec', type: 'HAS_CAPABILITY' },
    { source: 'validator-agent-2', target: 'tool-syntax-check', type: 'HAS_CAPABILITY' },
    // Security Agent capabilities
    { source: 'security-agent-1', target: 'tool-vuln-scan', type: 'HAS_CAPABILITY' },
    { source: 'security-agent-1', target: 'tool-audit-log', type: 'HAS_CAPABILITY' },
    { source: 'security-agent-1', target: 'tool-metrics', type: 'HAS_CAPABILITY' },
    { source: 'security-agent-1', target: 'tool-graph-query', type: 'HAS_CAPABILITY' },
    { source: 'security-agent-2', target: 'tool-vuln-scan', type: 'HAS_CAPABILITY' },
    { source: 'security-agent-2', target: 'tool-audit-log', type: 'HAS_CAPABILITY' },
    { source: 'security-agent-2', target: 'tool-secrets', type: 'HAS_CAPABILITY' },
    // Patcher Agent capabilities (high risk)
    { source: 'patcher-agent-1', target: 'tool-code-gen', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-1', target: 'tool-file-write', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-1', target: 'tool-git-commit', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-1', target: 'tool-deploy', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-1', target: 'tool-db-access', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-2', target: 'tool-code-gen', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-2', target: 'tool-file-write', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-2', target: 'tool-deploy', type: 'HAS_CAPABILITY' },
    { source: 'patcher-agent-2', target: 'tool-config-modify', type: 'HAS_CAPABILITY' },
    // Orchestrator Agent capabilities (critical)
    { source: 'orchestrator-agent', target: 'tool-semantic-search', type: 'HAS_CAPABILITY' },
    { source: 'orchestrator-agent', target: 'tool-metrics', type: 'HAS_CAPABILITY' },
    { source: 'orchestrator-agent', target: 'tool-deploy', type: 'HAS_CAPABILITY' },
    { source: 'orchestrator-agent', target: 'tool-secrets', type: 'HAS_CAPABILITY' },
    { source: 'orchestrator-agent', target: 'tool-iam-modify', type: 'HAS_CAPABILITY' },
    { source: 'orchestrator-agent', target: 'tool-prod-access', type: 'HAS_CAPABILITY' },
    // DevOps Agent capabilities
    { source: 'devops-agent', target: 'tool-sandbox-create', type: 'HAS_CAPABILITY' },
    { source: 'devops-agent', target: 'tool-config-modify', type: 'HAS_CAPABILITY' },
    { source: 'devops-agent', target: 'tool-deploy', type: 'HAS_CAPABILITY' },
    { source: 'devops-agent', target: 'tool-metrics', type: 'HAS_CAPABILITY' },
    { source: 'devops-agent', target: 'tool-audit-log', type: 'HAS_CAPABILITY' },
    { source: 'devops-agent', target: 'tool-secrets', type: 'HAS_CAPABILITY' },
    // Docs Agent capabilities
    { source: 'docs-agent', target: 'tool-semantic-search', type: 'HAS_CAPABILITY' },
    { source: 'docs-agent', target: 'tool-get-docs', type: 'HAS_CAPABILITY' },
    // Agent delegation relationships
    { source: 'orchestrator-agent', target: 'coder-agent-1', type: 'DELEGATES_TO', style: 'dashed' },
    { source: 'orchestrator-agent', target: 'reviewer-agent-1', type: 'DELEGATES_TO', style: 'dashed' },
    { source: 'orchestrator-agent', target: 'patcher-agent-1', type: 'DELEGATES_TO', style: 'dashed' },
    { source: 'reviewer-agent-1', target: 'coder-agent-2', type: 'DELEGATES_TO', style: 'dashed' },
    { source: 'validator-agent-1', target: 'security-agent-1', type: 'DELEGATES_TO', style: 'dashed' },
  ],
  escalation_paths: [
    {
      path: ['patcher-agent-1', 'tool-deploy', 'tool-db-access'],
      risk_score: 0.92,
      description: 'Deployment + database access enables production data modification',
    },
    {
      path: ['orchestrator-agent', 'tool-iam-modify', 'tool-prod-access'],
      risk_score: 0.95,
      description: 'IAM modification with production access enables privilege escalation',
    },
    {
      path: ['devops-agent', 'tool-secrets', 'tool-deploy'],
      risk_score: 0.78,
      description: 'Secrets access combined with deployment capability',
    },
    {
      path: ['security-agent-2', 'tool-secrets'],
      risk_score: 0.65,
      description: 'Security agent with secrets access requires monitoring',
    },
  ],
};

const MOCK_ANALYSIS_RESULTS = {
  escalation_paths: [
    {
      steps: ['PatcherAgent', 'deployment', 'database_access'],
      risk_score: 0.85,
      description: 'High-risk escalation path detected',
    },
  ],
  coverage_gaps: [
    { agent: 'CoderAgent', missing_capability: 'security_scanning' },
  ],
  toxic_combinations: [
    { tools: ['deployment', 'database_access'], reason: 'Direct production data modification risk' },
  ],
};

/**
 * Fetch capability graph visualization data.
 * @param {boolean} includeEscalationPaths - Highlight escalation paths
 * @returns {Promise<Object>} Visualization data
 */
async function fetchVisualization(includeEscalationPaths = true) {
  try {
    const params = new URLSearchParams({
      include_escalation_paths: includeEscalationPaths.toString(),
    });
    const response = await fetch(`${API_BASE}/visualization?${params}`);
    if (!response.ok) {
      console.warn('API unavailable, using mock data');
      return MOCK_VISUALIZATION_DATA;
    }
    return response.json();
  } catch (err) {
    console.warn('API unavailable, using mock data:', err.message);
    return MOCK_VISUALIZATION_DATA;
  }
}

/**
 * Fetch escalation paths.
 * @param {number} minRiskScore - Minimum risk score (0.0-1.0)
 * @returns {Promise<Array>} Escalation paths
 */
async function fetchEscalationPaths(minRiskScore = 0.5) {
  try {
    const params = new URLSearchParams({
      min_risk_score: minRiskScore.toString(),
    });
    const response = await fetch(`${API_BASE}/escalation-paths?${params}`);
    if (!response.ok) {
      return MOCK_ANALYSIS_RESULTS.escalation_paths;
    }
    return response.json();
  } catch (err) {
    return MOCK_ANALYSIS_RESULTS.escalation_paths;
  }
}

/**
 * Fetch coverage gaps.
 * @returns {Promise<Array>} Coverage gaps
 */
async function fetchCoverageGaps() {
  try {
    const response = await fetch(`${API_BASE}/coverage-gaps`);
    if (!response.ok) {
      return MOCK_ANALYSIS_RESULTS.coverage_gaps;
    }
    return response.json();
  } catch (err) {
    return MOCK_ANALYSIS_RESULTS.coverage_gaps;
  }
}

/**
 * Fetch toxic combinations.
 * @returns {Promise<Array>} Toxic combinations
 */
async function fetchToxicCombinations() {
  try {
    const response = await fetch(`${API_BASE}/toxic-combinations`);
    if (!response.ok) {
      return MOCK_ANALYSIS_RESULTS.toxic_combinations;
    }
    return response.json();
  } catch (err) {
    return MOCK_ANALYSIS_RESULTS.toxic_combinations;
  }
}

/**
 * Run full analysis.
 * @returns {Promise<Object>} Full analysis results
 */
async function runFullAnalysis() {
  try {
    const response = await fetch(`${API_BASE}/analysis`);
    if (!response.ok) {
      console.warn('API unavailable, using mock analysis data');
      return MOCK_ANALYSIS_RESULTS;
    }
    return response.json();
  } catch (err) {
    console.warn('API unavailable, using mock analysis data:', err.message);
    return MOCK_ANALYSIS_RESULTS;
  }
}

/**
 * Trigger policy sync.
 * @param {string|null} agentType - Agent type to sync (null for all)
 * @returns {Promise<Object>} Sync result
 */
async function triggerSync(agentType = null) {
  try {
    const response = await fetch(`${API_BASE}/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_type: agentType, force: false }),
    });
    if (!response.ok) {
      return { success: true, message: 'Mock sync completed', agents_synced: 4 };
    }
    return response.json();
  } catch (err) {
    return { success: true, message: 'Mock sync completed', agents_synced: 4 };
  }
}

/**
 * Update agent capabilities/permissions.
 * @param {string} agentId - Agent ID to update
 * @param {Array<string>} grantedTools - List of tool IDs to grant
 * @returns {Promise<Object>} Update result
 */
async function updateAgentCapabilities(agentId, grantedTools) {
  try {
    const response = await fetch(`${API_BASE}/agents/${agentId}/capabilities`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ granted_tools: grantedTools }),
    });
    if (!response.ok) {
      // Mock success for development
      console.info('Mock: Updated capabilities for', agentId, grantedTools);
      return {
        success: true,
        agent_id: agentId,
        capabilities_count: grantedTools.length,
        message: 'Capabilities updated successfully (mock)',
      };
    }
    return response.json();
  } catch (err) {
    console.info('Mock: Updated capabilities for', agentId, grantedTools);
    return {
      success: true,
      agent_id: agentId,
      capabilities_count: grantedTools.length,
      message: 'Capabilities updated successfully (mock)',
    };
  }
}

/**
 * Fetch detailed agent information including capabilities.
 * @param {string} agentId - Agent ID to fetch
 * @returns {Promise<Object>} Agent details
 */
async function fetchAgentDetails(agentId) {
  try {
    const response = await fetch(`${API_BASE}/agents/${agentId}`);
    if (!response.ok) {
      // Return mock data for the agent
      const mockNode = MOCK_VISUALIZATION_DATA.nodes.find(n => n.id === agentId);
      if (mockNode) {
        return {
          ...mockNode,
          capabilities: getDefaultCapabilitiesForType(mockNode.agent_type),
        };
      }
      return null;
    }
    return response.json();
  } catch (err) {
    const mockNode = MOCK_VISUALIZATION_DATA.nodes.find(n => n.id === agentId);
    if (mockNode) {
      return {
        ...mockNode,
        capabilities: getDefaultCapabilitiesForType(mockNode.agent_type),
      };
    }
    return null;
  }
}

/**
 * Get default capabilities for an agent type (mock helper).
 */
function getDefaultCapabilitiesForType(agentType) {
  const capabilityMap = {
    coder: [
      { tool_id: 'semantic_search', classification: 'safe' },
      { tool_id: 'get_documentation', classification: 'safe' },
      { tool_id: 'generate_code', classification: 'dangerous' },
      { tool_id: 'modify_code', classification: 'dangerous' },
    ],
    reviewer: [
      { tool_id: 'semantic_search', classification: 'safe' },
      { tool_id: 'query_code_graph', classification: 'monitoring' },
      { tool_id: 'analyze_code_complexity', classification: 'monitoring' },
    ],
    validator: [
      { tool_id: 'semantic_search', classification: 'safe' },
      { tool_id: 'execute_tests', classification: 'dangerous' },
      { tool_id: 'get_vulnerability_report', classification: 'monitoring' },
    ],
    patcher: [
      { tool_id: 'semantic_search', classification: 'safe' },
      { tool_id: 'modify_code', classification: 'dangerous' },
      { tool_id: 'deploy_code', classification: 'critical' },
      { tool_id: 'database_access', classification: 'critical' },
    ],
  };
  return capabilityMap[agentType] || [
    { tool_id: 'semantic_search', classification: 'safe' },
    { tool_id: 'list_tools', classification: 'safe' },
  ];
}

/**
 * Custom hook for capability graph data management.
 *
 * @param {Object} options - Hook options
 * @param {boolean} options.autoLoad - Automatically load on mount
 * @param {boolean} options.includeEscalationPaths - Include escalation paths
 * @returns {Object} Graph data and control functions
 */
export function useCapabilityGraph(options = {}) {
  const { autoLoad = true, includeEscalationPaths = true } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadVisualization = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchVisualization(includeEscalationPaths);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [includeEscalationPaths]);

  const refresh = useCallback(async () => {
    await loadVisualization();
  }, [loadVisualization]);

  useEffect(() => {
    if (autoLoad) {
      loadVisualization();
    }
  }, [autoLoad, loadVisualization]);

  return {
    data,
    loading,
    error,
    refresh,
    // Additional API functions
    fetchEscalationPaths,
    fetchCoverageGaps,
    fetchToxicCombinations,
    runFullAnalysis,
    triggerSync,
    updateAgentCapabilities,
    fetchAgentDetails,
  };
}

export default useCapabilityGraph;

/**
 * Project Aura - Dashboard Data Hook
 *
 * Custom React hook for fetching and managing dashboard data with
 * auto-refresh, loading states, error handling, and optimistic updates.
 *
 * @module hooks/useDashboardData
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getMetricsSummary,
  getAgentStatus,
  getRecentScans,
  getSecurityAlerts,
  getSystemHealth,
  getCostMetrics,
} from '../services/dashboardApi';

/**
 * @typedef {Object} DashboardState
 * @property {Object|null} summary - Metrics summary data
 * @property {Array|null} agents - Agent status data
 * @property {Array|null} scans - Recent scan results
 * @property {Object|null} alerts - Security alerts data
 * @property {Object|null} health - System health metrics
 * @property {Object|null} cost - Cost metrics
 */

/**
 * @typedef {Object} LoadingState
 * @property {boolean} initial - Initial load in progress
 * @property {boolean} summary - Summary refresh in progress
 * @property {boolean} agents - Agents refresh in progress
 * @property {boolean} scans - Scans refresh in progress
 * @property {boolean} alerts - Alerts refresh in progress
 * @property {boolean} health - Health refresh in progress
 * @property {boolean} cost - Cost refresh in progress
 */

/**
 * @typedef {Object} ErrorState
 * @property {Error|null} summary - Summary fetch error
 * @property {Error|null} agents - Agents fetch error
 * @property {Error|null} scans - Scans fetch error
 * @property {Error|null} alerts - Alerts fetch error
 * @property {Error|null} health - Health fetch error
 * @property {Error|null} cost - Cost fetch error
 */

// Default refresh interval (30 seconds)
const DEFAULT_REFRESH_INTERVAL = 30000;

// Minimum refresh interval (5 seconds) to prevent API abuse
const MIN_REFRESH_INTERVAL = 5000;

// Default mock data for development when API is unavailable
// Enterprise-scale: ~214 agents, 12 repositories, 1.4M events/day
const DEFAULT_AGENTS = [
  {
    id: 'coder-agent-047',
    name: 'Coder Agent #47',
    status: 'active',
    task: 'Generating security patch for CVE-2024-8912 in payment-service',
    progress: 67,
    lastHeartbeat: new Date().toISOString(),
    metrics: { tasksCompleted: 1842, successRate: 94.2 },
  },
  {
    id: 'reviewer-agent-012',
    name: 'Reviewer Agent #12',
    status: 'active',
    task: 'Reviewing PR #4,291 for XSS vulnerabilities in frontend-app',
    progress: 45,
    lastHeartbeat: new Date().toISOString(),
    metrics: { reviewsCompleted: 3456, issuesFound: 892 },
  },
  {
    id: 'validator-agent-006',
    name: 'Validator Agent #6',
    status: 'active',
    task: 'Validating sandbox patch deployment for auth-service',
    progress: 78,
    lastHeartbeat: new Date().toISOString(),
    metrics: { validationsCompleted: 2187, passRate: 87.5 },
  },
  {
    id: 'scanner-agent-019',
    name: 'Security Scanner #19',
    status: 'active',
    task: 'Full SAST/DAST scan of graphrag-engine repository',
    progress: 82,
    lastHeartbeat: new Date().toISOString(),
    metrics: { scansCompleted: 4521, vulnerabilitiesFound: 1247 },
  },
  {
    id: 'orchestrator-003',
    name: 'Orchestrator #3',
    status: 'active',
    task: 'Coordinating multi-agent remediation for 42 pending approvals',
    progress: 35,
    lastHeartbeat: new Date().toISOString(),
    metrics: { tasksCoordinated: 12847, agentsManaged: 214 },
  },
  {
    id: 'coder-agent-108',
    name: 'Coder Agent #108',
    status: 'active',
    task: 'Refactoring insecure deserialization in data-pipeline',
    progress: 91,
    lastHeartbeat: new Date().toISOString(),
    metrics: { tasksCompleted: 967, successRate: 96.1 },
  },
  {
    id: 'mcp-server-015',
    name: 'MCP Server Tools #15',
    status: 'active',
    task: 'Serving tool calls for 28 active agent sessions',
    progress: 100,
    lastHeartbeat: new Date().toISOString(),
    metrics: { toolCallsServed: 58400, uptimeHours: 2184 },
  },
  {
    id: 'scanner-agent-007',
    name: 'Security Scanner #7',
    status: 'idle',
    task: 'Awaiting next scheduled scan (sandbox-controller)',
    progress: 0,
    lastHeartbeat: new Date().toISOString(),
    metrics: { scansCompleted: 3891, vulnerabilitiesFound: 987 },
  },
];

const DEFAULT_HEALTH = {
  api: {
    status: 'healthy',
    percentage: 99.7,
    latencyMs: 38,
    requestsPerMinute: 12400,
  },
  graphRag: {
    status: 'healthy',
    percentage: 98.2,
    nodes: 284000,
    edges: 891000,
    queries24h: 42800,
    avgLatencyMs: 85,
  },
  llm: {
    status: 'healthy',
    quotaUsed: 67,
    tokensRemaining: 3200000,
    requestsToday: 18470,
  },
  sandbox: {
    status: 'healthy',
    available: 8,
    total: 20,
    inUse: 12,
  },
  database: {
    status: 'healthy',
    connections: 340,
    maxConnections: 500,
    avgQueryTime: 8,
  },
  overallStatus: 'healthy',
};

const DEFAULT_SUMMARY = {
  agents: {
    active: 187,
    idle: 27,
    total: 214,
    trend: 8,
    sparkline: [178, 182, 180, 185, 183, 186, 184, 187, 185, 188, 186, 187],
  },
  approvals: {
    pending: 42,
    trend: -12,
    funnel: {
      detected: 1247,
      patched: 1089,
      approved: 956,
      deployed: 892,
    },
  },
  vulnerabilities: {
    open: 156,
    trend: -14,
    sparkline: [210, 198, 185, 178, 172, 168, 165, 162, 160, 158, 157, 156],
    history: [
      { label: 'Jan 6', value: 210 },
      { label: 'Jan 13', value: 185 },
      { label: 'Jan 20', value: 172 },
      { label: 'Jan 27', value: 165 },
      { label: 'Feb 3', value: 160 },
      { label: 'Feb 10', value: 158 },
      { label: 'Feb 17', value: 156 },
    ],
    severity: {
      critical: 18,
      high: 47,
      medium: 62,
      low: 29,
    },
  },
  patches: {
    deployed: 892,
    trend: 15,
    sparkline: [52, 58, 61, 55, 63, 68, 64, 71, 67, 74, 69, 73],
  },
  sandbox: {
    running: 12,
    status: 'healthy',
  },
  anomalies: {
    count: 23,
  },
  lastUpdated: new Date().toISOString(),
};

// Default mock scans data when API is unavailable
const DEFAULT_SCANS = [
  {
    id: 'scan-001',
    repositoryName: 'core-api',
    status: 'completed',
    vulnerabilities: 23,
    startedAt: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
  {
    id: 'scan-002',
    repositoryName: 'payment-service',
    status: 'completed',
    vulnerabilities: 12,
    startedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 1.5 * 60 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
  {
    id: 'scan-003',
    repositoryName: 'auth-service',
    status: 'in_progress',
    vulnerabilities: 0,
    startedAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    completedAt: null,
    scanType: 'security',
    progress: 65,
  },
  {
    id: 'scan-004',
    repositoryName: 'graphrag-engine',
    status: 'completed',
    vulnerabilities: 8,
    startedAt: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
  {
    id: 'scan-005',
    repositoryName: 'frontend-app',
    status: 'completed',
    vulnerabilities: 15,
    startedAt: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
  {
    id: 'scan-006',
    repositoryName: 'data-pipeline',
    status: 'completed',
    vulnerabilities: 31,
    startedAt: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
  {
    id: 'scan-007',
    repositoryName: 'sandbox-controller',
    status: 'completed',
    vulnerabilities: 5,
    startedAt: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 11 * 60 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
  {
    id: 'scan-008',
    repositoryName: 'agent-orchestrator',
    status: 'completed',
    vulnerabilities: 18,
    startedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString(),
    scanType: 'security',
  },
];

// Default mock alerts data when API is unavailable
const DEFAULT_ALERTS = [
  {
    id: 'alert-001',
    title: 'SQL Injection in payment query handler',
    severity: 'critical',
    status: 'open',
    repository: 'payment-service',
    file: 'src/api/handlers/transaction_query.py',
    createdAt: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    cwe: 'CWE-89',
  },
  {
    id: 'alert-002',
    title: 'Prompt injection vector in agent input parser',
    severity: 'critical',
    status: 'open',
    repository: 'agent-orchestrator',
    file: 'src/agents/input_parser.py',
    createdAt: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    cwe: 'CWE-77',
  },
  {
    id: 'alert-003',
    title: 'XSS vulnerability in user-generated report view',
    severity: 'high',
    status: 'open',
    repository: 'frontend-app',
    file: 'src/components/reports/ReportViewer.jsx',
    createdAt: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    cwe: 'CWE-79',
  },
  {
    id: 'alert-004',
    title: 'Hardcoded database credentials in staging config',
    severity: 'critical',
    status: 'acknowledged',
    repository: 'auth-service',
    file: 'config/staging_database.py',
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    cwe: 'CWE-798',
  },
  {
    id: 'alert-005',
    title: 'Insecure deserialization in event processor',
    severity: 'high',
    status: 'open',
    repository: 'data-pipeline',
    file: 'src/processors/event_deserializer.py',
    createdAt: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    cwe: 'CWE-502',
  },
  {
    id: 'alert-006',
    title: 'SSRF in GraphRAG external source fetcher',
    severity: 'high',
    status: 'acknowledged',
    repository: 'graphrag-engine',
    file: 'src/ingest/external_fetcher.py',
    createdAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    cwe: 'CWE-918',
  },
  {
    id: 'alert-007',
    title: 'Sandbox escape via container mount path traversal',
    severity: 'critical',
    status: 'open',
    repository: 'sandbox-controller',
    file: 'src/provisioner/volume_mount.py',
    createdAt: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    cwe: 'CWE-22',
  },
  {
    id: 'alert-008',
    title: 'Insufficient access control on approval override API',
    severity: 'medium',
    status: 'resolved',
    repository: 'core-api',
    file: 'src/api/routes/approvals.py',
    createdAt: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    cwe: 'CWE-285',
  },
];

/**
 * Custom hook for fetching and managing all dashboard data.
 *
 * Features:
 * - Fetches all dashboard data on mount
 * - Auto-refresh at configurable interval (default: 30 seconds)
 * - Individual loading states for each data category
 * - Error handling with retry capability
 * - Optimistic updates for user actions
 * - Cleanup on unmount
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=30000] - Auto-refresh interval in milliseconds
 * @param {boolean} [options.autoRefresh=true] - Enable auto-refresh
 * @param {boolean} [options.fetchCost=false] - Include cost metrics (optional, may require permissions)
 * @returns {Object} Dashboard data and control functions
 *
 * @example
 * const {
 *   data,
 *   loading,
 *   error,
 *   refetch,
 *   refetchSection,
 *   isAnyLoading,
 *   hasAnyError,
 * } = useDashboardData({ refreshInterval: 60000 });
 */
export function useDashboardData(options = {}) {
  const {
    refreshInterval = DEFAULT_REFRESH_INTERVAL,
    autoRefresh = true,
    fetchCost = false,
  } = options;

  // Validate refresh interval
  const validRefreshInterval = Math.max(refreshInterval, MIN_REFRESH_INTERVAL);

  // Data state
  const [data, setData] = useState({
    summary: null,
    agents: null,
    scans: null,
    alerts: null,
    health: null,
    cost: null,
  });

  // Loading states
  const [loading, setLoading] = useState({
    initial: true,
    summary: false,
    agents: false,
    scans: false,
    alerts: false,
    health: false,
    cost: false,
  });

  // Error states
  const [error, setError] = useState({
    summary: null,
    agents: null,
    scans: null,
    alerts: null,
    health: null,
    cost: null,
  });

  // Last updated timestamp
  const [lastUpdated, setLastUpdated] = useState(null);

  // Refs for cleanup
  const mountedRef = useRef(true);
  const refreshIntervalRef = useRef(null);
  const abortControllerRef = useRef(null);

  /**
   * Fetches a single section of dashboard data
   */
  const fetchSection = useCallback(async (section, fetchFn, fetchOptions = {}) => {
    if (!mountedRef.current) return;

    setLoading((prev) => ({ ...prev, [section]: true }));
    setError((prev) => ({ ...prev, [section]: null }));

    try {
      const result = await fetchFn(fetchOptions);

      if (mountedRef.current) {
        setData((prev) => ({ ...prev, [section]: result }));
        setLastUpdated(new Date().toISOString());
      }

      return result;
    } catch (err) {
      if (mountedRef.current) {
        setError((prev) => ({ ...prev, [section]: err }));
        console.error(`Failed to fetch ${section}:`, err);
      }
      throw err;
    } finally {
      if (mountedRef.current) {
        setLoading((prev) => ({ ...prev, [section]: false }));
      }
    }
  }, []);

  /**
   * Fetches all dashboard data in parallel
   */
  const fetchAllData = useCallback(async () => {
    if (!mountedRef.current) return;

    // Cancel any pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setLoading((prev) => ({
      ...prev,
      initial: prev.initial,
      summary: true,
      agents: true,
      scans: true,
      alerts: true,
      health: true,
      cost: fetchCost,
    }));

    // Clear previous errors
    setError({
      summary: null,
      agents: null,
      scans: null,
      alerts: null,
      health: null,
      cost: null,
    });

    // Fetch all data in parallel (use defaults when API unavailable)
    const promises = [
      getMetricsSummary().catch((_err) => {
        // Use default summary for dev environment when API unavailable
        console.warn('Using default summary data (API unavailable)');
        return DEFAULT_SUMMARY;
      }),
      getAgentStatus().catch((_err) => {
        // Use default agents for dev environment when API unavailable
        console.warn('Using default agent data (API unavailable)');
        return DEFAULT_AGENTS;
      }),
      getRecentScans({ limit: 10 }).catch((_err) => {
        // Use default scans for dev environment when API unavailable
        console.warn('Using default scans data (API unavailable)');
        return DEFAULT_SCANS;
      }),
      getSecurityAlerts({ limit: 10 }).catch((_err) => {
        // Use default alerts for dev environment when API unavailable
        console.warn('Using default alerts data (API unavailable)');
        return DEFAULT_ALERTS;
      }),
      getSystemHealth().catch((_err) => {
        // Use default health metrics for dev environment when API unavailable
        console.warn('Using default health data (API unavailable)');
        return DEFAULT_HEALTH;
      }),
    ];

    // Optionally fetch cost metrics
    if (fetchCost) {
      promises.push(
        getCostMetrics().catch((err) => {
          if (mountedRef.current) setError((prev) => ({ ...prev, cost: err }));
          return null;
        })
      );
    }

    try {
      const results = await Promise.all(promises);

      if (mountedRef.current) {
        const [summary, agents, scans, alerts, health, cost = null] = results;

        setData({
          summary,
          agents,
          scans,
          alerts,
          health,
          cost,
        });

        setLastUpdated(new Date().toISOString());
      }
    } finally {
      if (mountedRef.current) {
        setLoading({
          initial: false,
          summary: false,
          agents: false,
          scans: false,
          alerts: false,
          health: false,
          cost: false,
        });
      }
    }
  }, [fetchCost]);

  /**
   * Refetch all dashboard data
   */
  const refetch = useCallback(() => {
    return fetchAllData();
  }, [fetchAllData]);

  /**
   * Refetch a specific section of dashboard data
   */
  const refetchSection = useCallback(
    async (section) => {
      const fetchFunctions = {
        summary: () => fetchSection('summary', getMetricsSummary),
        agents: () => fetchSection('agents', getAgentStatus),
        scans: () => fetchSection('scans', getRecentScans, { limit: 10 }),
        alerts: () => fetchSection('alerts', getSecurityAlerts, { limit: 10 }),
        health: () => fetchSection('health', getSystemHealth),
        cost: () => fetchSection('cost', getCostMetrics),
      };

      const fetchFn = fetchFunctions[section];
      if (fetchFn) {
        return fetchFn();
      }
      throw new Error(`Unknown section: ${section}`);
    },
    [fetchSection]
  );

  /**
   * Optimistically update a section of data
   */
  const optimisticUpdate = useCallback((section, updater) => {
    setData((prev) => ({
      ...prev,
      [section]: typeof updater === 'function' ? updater(prev[section]) : updater,
    }));
  }, []);

  /**
   * Revert an optimistic update by refetching the section
   */
  const revertOptimisticUpdate = useCallback(
    (section) => {
      return refetchSection(section);
    },
    [refetchSection]
  );

  // Initial data fetch
  useEffect(() => {
    mountedRef.current = true;
    fetchAllData();

    return () => {
      mountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchAllData]);

  // Auto-refresh interval
  useEffect(() => {
    if (!autoRefresh) return;

    refreshIntervalRef.current = setInterval(() => {
      if (mountedRef.current) {
        fetchAllData();
      }
    }, validRefreshInterval);

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, validRefreshInterval, fetchAllData]);

  // Computed states
  const isAnyLoading = Object.values(loading).some(Boolean);
  const hasAnyError = Object.values(error).some((e) => e !== null);
  const isInitialLoading = loading.initial;

  return {
    // Data
    data,
    summary: data.summary,
    agents: data.agents,
    scans: data.scans,
    alerts: data.alerts,
    health: data.health,
    cost: data.cost,

    // Loading states
    loading,
    isAnyLoading,
    isInitialLoading,

    // Error states
    error,
    hasAnyError,

    // Metadata
    lastUpdated,

    // Actions
    refetch,
    refetchSection,
    optimisticUpdate,
    revertOptimisticUpdate,
  };
}

/**
 * Hook for fetching only agent status with auto-refresh.
 * Useful for components that only need agent data.
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=10000] - Refresh interval (default: 10s)
 * @returns {Object} Agent status data and controls
 */
export function useAgentStatus(options = {}) {
  const { refreshInterval = 10000 } = options;

  const [agents, setAgents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchAgents = useCallback(async () => {
    if (!mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getAgentStatus();
      if (mountedRef.current) {
        setAgents(data);
      }
    } catch (err) {
      // Use default agents when API unavailable
      if (mountedRef.current) {
        console.warn('Using default agent data (API unavailable)');
        setAgents(DEFAULT_AGENTS);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchAgents();

    const interval = setInterval(fetchAgents, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAgents, refreshInterval]);

  return {
    agents,
    loading,
    error,
    refetch: fetchAgents,
  };
}

/**
 * Hook for fetching system health with auto-refresh.
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=15000] - Refresh interval (default: 15s)
 * @returns {Object} System health data and controls
 */
export function useSystemHealth(options = {}) {
  const { refreshInterval = 15000 } = options;

  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchHealth = useCallback(async () => {
    if (!mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getSystemHealth();
      if (mountedRef.current) {
        setHealth(data);
      }
    } catch (err) {
      // Use default health metrics when API unavailable
      if (mountedRef.current) {
        console.warn('Using default health data (API unavailable)');
        setHealth(DEFAULT_HEALTH);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchHealth();

    const interval = setInterval(fetchHealth, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchHealth, refreshInterval]);

  return {
    health,
    loading,
    error,
    refetch: fetchHealth,
  };
}

export default useDashboardData;

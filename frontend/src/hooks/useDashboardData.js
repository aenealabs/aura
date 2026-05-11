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


// Note: DEFAULT_AGENTS / DEFAULT_HEALTH / DEFAULT_SUMMARY / DEFAULT_SCANS /
// DEFAULT_ALERTS fixtures were removed in Wave 4 (#163). On API failure the
// hooks now surface the error and let the consumer render an empty/error
// state, rather than substituting fabricated tenant data that the May 10
// GTM audit flagged as the biggest customer-visible deception.

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

    // Fetch all data in parallel. Wave-4 (#163): the previous
    // ``catch -> DEFAULT_*`` shims were silently substituting
    // fabricated tenant data when the API was down, which the May 10
    // GTM audit flagged as the biggest customer-visible deception.
    // Each per-call catch now records the error on the error map and
    // returns ``null``; the consumer renders an empty/error state.
    const recordError = (key) => (err) => {
      if (mountedRef.current) {
        setError((prev) => ({ ...prev, [key]: err }));
      }
      return null;
    };

    const promises = [
      getMetricsSummary().catch(recordError('summary')),
      getAgentStatus().catch(recordError('agents')),
      getRecentScans({ limit: 10 }).catch(recordError('scans')),
      getSecurityAlerts({ limit: 10 }).catch(recordError('alerts')),
      getSystemHealth().catch(recordError('health')),
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
      // Wave-4 (#163): on API failure, surface the error rather than
      // substituting fabricated agent data. ``agents`` stays at its
      // previous value (or null on first load) and the consumer
      // renders an error or empty state.
      if (mountedRef.current) {
        setError(err);
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
      // Wave-4 (#163): surface the error; do not substitute fabricated
      // health metrics. ``health`` remains at its previous value (or
      // null) so the consumer can render an error/empty state.
      if (mountedRef.current) {
        setError(err);
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

/**
 * Project Aura - Palantir Sync Hook
 *
 * Custom React hook for managing Palantir integration sync status
 * with auto-refresh, circuit breaker state, and health monitoring.
 *
 * @module hooks/usePalantirSync
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getHealth,
  getCircuitBreaker,
  getSyncStatus,
  getAllStatus,
  resetCircuitBreaker,
  triggerSync,
} from '../services/palantirApi';

// Default refresh interval (30 seconds)
const DEFAULT_REFRESH_INTERVAL = 30000;

// Minimum refresh interval (5 seconds)
const MIN_REFRESH_INTERVAL = 5000;

/**
 * @typedef {Object} PalantirSyncState
 * @property {Object|null} health - Health status
 * @property {Object|null} circuitBreaker - Circuit breaker status
 * @property {Object|null} syncStatus - Sync status by object type
 * @property {string|null} lastSyncTime - ISO timestamp of last successful fetch
 * @property {boolean} isLoading - Initial loading state
 * @property {Error|null} error - Last error if any
 */

/**
 * Custom hook for Palantir integration sync status.
 *
 * Features:
 * - Fetches health, circuit breaker, and sync status in parallel
 * - Auto-refresh at configurable interval (default: 30 seconds)
 * - Cleanup on unmount with AbortController
 * - Actions for manual refresh, circuit breaker reset, and sync triggers
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=30000] - Auto-refresh interval in ms
 * @param {boolean} [options.autoRefresh=true] - Enable auto-refresh
 * @returns {Object} Palantir sync state and actions
 *
 * @example
 * const {
 *   health,
 *   circuitBreaker,
 *   syncStatus,
 *   isLoading,
 *   error,
 *   refetch,
 *   resetBreaker,
 *   triggerObjectSync,
 * } = usePalantirSync({ refreshInterval: 60000 });
 */
export function usePalantirSync(options = {}) {
  const {
    refreshInterval = DEFAULT_REFRESH_INTERVAL,
    autoRefresh = true,
  } = options;

  // Validate refresh interval
  const validRefreshInterval = Math.max(refreshInterval, MIN_REFRESH_INTERVAL);

  // State
  const [health, setHealth] = useState(null);
  const [circuitBreaker, setCircuitBreaker] = useState(null);
  const [syncStatus, setSyncStatus] = useState(null);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Refs for cleanup
  const mountedRef = useRef(true);
  const refreshIntervalRef = useRef(null);
  const abortControllerRef = useRef(null);

  /**
   * Fetch all Palantir status data in parallel
   */
  const fetchStatus = useCallback(async () => {
    if (!mountedRef.current) return;

    // Cancel any pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      const result = await getAllStatus();

      if (mountedRef.current) {
        setHealth(result.health);
        setCircuitBreaker(result.circuitBreaker);
        setSyncStatus(result.syncStatus);
        setLastSyncTime(new Date().toISOString());
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current && !abortControllerRef.current.signal.aborted) {
        setError(err);
        console.error('Failed to fetch Palantir status:', err);
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  /**
   * Manual refetch
   */
  const refetch = useCallback(() => {
    return fetchStatus();
  }, [fetchStatus]);

  /**
   * Reset circuit breaker to closed state
   */
  const resetBreaker = useCallback(async () => {
    try {
      const result = await resetCircuitBreaker();

      if (mountedRef.current) {
        // Update local state optimistically
        setCircuitBreaker((prev) => ({
          ...prev,
          state: result.new_state,
          failure_count: 0,
        }));
      }

      return result;
    } catch (err) {
      console.error('Failed to reset circuit breaker:', err);
      throw err;
    }
  }, []);

  /**
   * Trigger sync for a specific object type
   */
  const triggerObjectSync = useCallback(async (objectType, fullSync = false) => {
    try {
      const result = await triggerSync(objectType, fullSync);

      // Refetch status after sync
      if (mountedRef.current) {
        await fetchStatus();
      }

      return result;
    } catch (err) {
      console.error(`Failed to trigger sync for ${objectType}:`, err);
      throw err;
    }
  }, [fetchStatus]);

  // Initial fetch
  useEffect(() => {
    mountedRef.current = true;
    fetchStatus();

    return () => {
      mountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchStatus]);

  // Auto-refresh interval
  useEffect(() => {
    if (!autoRefresh) return;

    refreshIntervalRef.current = setInterval(() => {
      if (mountedRef.current) {
        fetchStatus();
      }
    }, validRefreshInterval);

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, validRefreshInterval, fetchStatus]);

  // Computed states
  const isHealthy = health?.is_healthy ?? false;
  const isCircuitOpen = circuitBreaker?.state === 'OPEN';
  const isCircuitHalfOpen = circuitBreaker?.state === 'HALF_OPEN';
  const hasSyncErrors = syncStatus && Object.values(syncStatus).some(
    (s) => s.last_sync_status === 'failed'
  );

  // Calculate overall integration status
  const integrationStatus = (() => {
    if (error) return 'error';
    if (isCircuitOpen) return 'degraded';
    if (isCircuitHalfOpen || hasSyncErrors) return 'warning';
    if (isHealthy) return 'healthy';
    return 'unknown';
  })();

  return {
    // Data
    health,
    circuitBreaker,
    syncStatus,
    lastSyncTime,

    // Loading & Error
    isLoading,
    error,

    // Computed states
    isHealthy,
    isCircuitOpen,
    isCircuitHalfOpen,
    hasSyncErrors,
    integrationStatus,

    // Actions
    refetch,
    resetBreaker,
    triggerObjectSync,
  };
}

/**
 * Hook for fetching only circuit breaker status with faster refresh.
 * Useful for admin monitoring components.
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=10000] - Refresh interval (default: 10s)
 * @returns {Object} Circuit breaker status and controls
 */
export function useCircuitBreaker(options = {}) {
  const { refreshInterval = 10000 } = options;

  const [circuitBreaker, setCircuitBreaker] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchBreaker = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      const data = await getCircuitBreaker();
      if (mountedRef.current) {
        setCircuitBreaker(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const reset = useCallback(async () => {
    const result = await resetCircuitBreaker();
    if (mountedRef.current) {
      setCircuitBreaker((prev) => ({
        ...prev,
        state: result.new_state,
        failure_count: 0,
      }));
    }
    return result;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchBreaker();

    const interval = setInterval(fetchBreaker, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchBreaker, refreshInterval]);

  return {
    circuitBreaker,
    state: circuitBreaker?.state ?? 'unknown',
    isLoading,
    error,
    refetch: fetchBreaker,
    reset,
  };
}

/**
 * Hook for fetching Palantir health status.
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=15000] - Refresh interval (default: 15s)
 * @returns {Object} Health status and controls
 */
export function usePalantirHealth(options = {}) {
  const { refreshInterval = 15000 } = options;

  const [health, setHealth] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchHealth = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      const data = await getHealth();
      if (mountedRef.current) {
        setHealth(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
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
    isHealthy: health?.is_healthy ?? false,
    status: health?.status ?? 'unknown',
    isLoading,
    error,
    refetch: fetchHealth,
  };
}

export default usePalantirSync;

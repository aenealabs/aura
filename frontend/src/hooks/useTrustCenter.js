/**
 * useTrustCenter Hook
 *
 * Provides data management for the AI Trust Center dashboard.
 * Features:
 * - Status, principles, autonomy, metrics, and decisions data
 * - Auto-refresh every 60 seconds
 * - Period selection for metrics
 * - Export functionality
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  getTrustCenterStatus,
  getPrinciples,
  getAutonomyConfig,
  getSafetyMetrics,
  getAuditDecisions,
  exportTrustCenterData,
  MetricPeriods,
} from '../services/trustCenterApi';

// Default refresh interval (60 seconds)
const DEFAULT_REFRESH_INTERVAL = 60000;

/**
 * Main Trust Center hook
 * @param {Object} options - Hook options
 * @param {boolean} [options.autoRefresh=true] - Enable auto-refresh
 * @param {number} [options.refreshInterval=60000] - Refresh interval in ms
 * @param {string} [options.initialPeriod='24h'] - Initial metrics period
 */
export function useTrustCenter(options = {}) {
  const {
    autoRefresh = true,
    refreshInterval = DEFAULT_REFRESH_INTERVAL,
    initialPeriod = MetricPeriods.DAY,
  } = options;

  // State
  const [status, setStatus] = useState(null);
  const [principles, setPrinciples] = useState([]);
  const [autonomy, setAutonomy] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [decisions, setDecisions] = useState({ decisions: [], total_count: 0, has_more: false });

  // Filter state
  const [metricsPeriod, setMetricsPeriod] = useState(initialPeriod);
  const [principlesFilter, setPrinciplesFilter] = useState({ category: null, severity: null });
  const [decisionsPage, setDecisionsPage] = useState(0);
  const [decisionsFilter, setDecisionsFilter] = useState({ agentName: null });

  // Loading states
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingPrinciples, setLoadingPrinciples] = useState(true);
  const [loadingAutonomy, setLoadingAutonomy] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [loadingDecisions, setLoadingDecisions] = useState(true);
  const [loadingExport, setLoadingExport] = useState(false);

  // Error state
  const [error, setError] = useState(null);

  // Refs for cleanup
  const mountedRef = useRef(true);
  const refreshIntervalRef = useRef(null);

  /**
   * Fetch system status
   */
  const fetchStatus = useCallback(async () => {
    try {
      setLoadingStatus(true);
      const data = await getTrustCenterStatus();
      if (mountedRef.current) {
        setStatus(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to load Trust Center status');
        console.error('Failed to fetch Trust Center status:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingStatus(false);
      }
    }
  }, []);

  /**
   * Fetch principles with filters
   */
  const fetchPrinciples = useCallback(async (filters = principlesFilter) => {
    try {
      setLoadingPrinciples(true);
      const data = await getPrinciples({
        category: filters.category,
        severity: filters.severity,
        includeMetrics: true,
      });
      if (mountedRef.current) {
        setPrinciples(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch principles:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingPrinciples(false);
      }
    }
  }, [principlesFilter]);

  /**
   * Fetch autonomy configuration
   */
  const fetchAutonomy = useCallback(async () => {
    try {
      setLoadingAutonomy(true);
      const data = await getAutonomyConfig();
      if (mountedRef.current) {
        setAutonomy(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch autonomy config:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingAutonomy(false);
      }
    }
  }, []);

  /**
   * Fetch safety metrics for period
   */
  const fetchMetrics = useCallback(async (period = metricsPeriod) => {
    try {
      setLoadingMetrics(true);
      const data = await getSafetyMetrics(period);
      if (mountedRef.current) {
        setMetrics(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch metrics:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingMetrics(false);
      }
    }
  }, [metricsPeriod]);

  /**
   * Fetch audit decisions with pagination
   */
  const fetchDecisions = useCallback(async (page = decisionsPage, filters = decisionsFilter) => {
    try {
      setLoadingDecisions(true);
      const data = await getAuditDecisions({
        limit: 20,
        offset: page * 20,
        agentName: filters.agentName,
      });
      if (mountedRef.current) {
        setDecisions(data);
        setDecisionsPage(page);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch decisions:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingDecisions(false);
      }
    }
  }, [decisionsPage, decisionsFilter]);

  /**
   * Refresh all data
   */
  const refreshData = useCallback(async () => {
    await Promise.all([
      fetchStatus(),
      fetchPrinciples(),
      fetchAutonomy(),
      fetchMetrics(),
      fetchDecisions(),
    ]);
  }, [fetchStatus, fetchPrinciples, fetchAutonomy, fetchMetrics, fetchDecisions]);

  /**
   * Handle metrics period change
   */
  const handlePeriodChange = useCallback((period) => {
    setMetricsPeriod(period);
    fetchMetrics(period);
  }, [fetchMetrics]);

  /**
   * Handle principles filter change
   */
  const handlePrinciplesFilterChange = useCallback((filters) => {
    setPrinciplesFilter(prev => ({ ...prev, ...filters }));
  }, []);

  /**
   * Handle decisions filter change
   */
  const handleDecisionsFilterChange = useCallback((filters) => {
    setDecisionsFilter(prev => ({ ...prev, ...filters }));
    setDecisionsPage(0);
  }, []);

  /**
   * Load next page of decisions
   */
  const loadMoreDecisions = useCallback(() => {
    if (decisions.has_more) {
      fetchDecisions(decisionsPage + 1, decisionsFilter);
    }
  }, [decisions.has_more, fetchDecisions, decisionsPage, decisionsFilter]);

  /**
   * Load previous page of decisions
   */
  const loadPreviousDecisions = useCallback(() => {
    if (decisionsPage > 0) {
      fetchDecisions(decisionsPage - 1, decisionsFilter);
    }
  }, [decisionsPage, fetchDecisions, decisionsFilter]);

  /**
   * Export data
   */
  const handleExport = useCallback(async (format = 'json', period = metricsPeriod) => {
    try {
      setLoadingExport(true);
      const result = await exportTrustCenterData({ format, period });

      if (format === 'json') {
        // Download JSON file
        const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trust-center-export-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }

      return { success: true, data: result };
    } catch (err) {
      console.error('Failed to export data:', err);
      return { success: false, error: err.message };
    } finally {
      setLoadingExport(false);
    }
  }, [metricsPeriod]);

  // Initial data fetch
  useEffect(() => {
    mountedRef.current = true;
    refreshData();

    return () => {
      mountedRef.current = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch principles when filter changes
  useEffect(() => {
    fetchPrinciples(principlesFilter);
  }, [principlesFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch decisions when filter changes
  useEffect(() => {
    fetchDecisions(0, decisionsFilter);
  }, [decisionsFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Set up auto-refresh
  useEffect(() => {
    if (autoRefresh && refreshInterval > 0) {
      refreshIntervalRef.current = setInterval(() => {
        refreshData();
      }, refreshInterval);
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, refreshInterval, refreshData]);

  // Computed values
  const isLoading = useMemo(() => (
    loadingStatus || loadingPrinciples || loadingAutonomy || loadingMetrics || loadingDecisions
  ), [loadingStatus, loadingPrinciples, loadingAutonomy, loadingMetrics, loadingDecisions]);

  const overallStatus = useMemo(() => (
    status?.overall_status || 'unknown'
  ), [status]);

  const complianceScore = useMemo(() => (
    status?.compliance_score ? Math.round(status.compliance_score * 100) : 0
  ), [status]);

  const criticalPrinciples = useMemo(() => (
    principles.filter(p => p.severity === 'critical')
  ), [principles]);

  const principlesByCategory = useMemo(() => {
    const grouped = {};
    principles.forEach(p => {
      const cat = p.category || 'unknown';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(p);
    });
    return grouped;
  }, [principles]);

  const metricsSummary = useMemo(() => {
    if (!metrics) return null;
    return {
      critiqueAccuracy: metrics.critique_accuracy,
      revisionConvergence: metrics.revision_convergence_rate,
      cacheHitRate: metrics.cache_hit_rate,
      nonEvasiveRate: metrics.non_evasive_rate,
      latencyP95: metrics.critique_latency_p95,
      goldenSetPass: metrics.golden_set_pass_rate,
    };
  }, [metrics]);

  const chartData = useMemo(() => {
    if (!metricsSummary) return {};

    const formatTimeSeries = (metric) => {
      if (!metric?.time_series?.length) return { data: [], labels: [] };
      return {
        data: metric.time_series.map(d => d.value),
        labels: metric.time_series.map(d => {
          const date = new Date(d.timestamp);
          return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }),
      };
    };

    return {
      critiqueAccuracy: formatTimeSeries(metricsSummary.critiqueAccuracy),
      revisionConvergence: formatTimeSeries(metricsSummary.revisionConvergence),
      cacheHitRate: formatTimeSeries(metricsSummary.cacheHitRate),
      latencyP95: formatTimeSeries(metricsSummary.latencyP95),
    };
  }, [metricsSummary]);

  return {
    // Data
    status,
    principles,
    autonomy,
    metrics,
    decisions,

    // Computed values
    overallStatus,
    complianceScore,
    criticalPrinciples,
    principlesByCategory,
    metricsSummary,
    chartData,

    // Loading states
    isLoading,
    loadingStatus,
    loadingPrinciples,
    loadingAutonomy,
    loadingMetrics,
    loadingDecisions,
    loadingExport,

    // Error state
    error,

    // Filters and pagination
    metricsPeriod,
    principlesFilter,
    decisionsPage,
    decisionsFilter,

    // Actions
    setPeriod: handlePeriodChange,
    setPrinciplesFilter: handlePrinciplesFilterChange,
    setDecisionsFilter: handleDecisionsFilterChange,
    refreshData,
    loadMoreDecisions,
    loadPreviousDecisions,
    exportData: handleExport,
  };
}

export default useTrustCenter;

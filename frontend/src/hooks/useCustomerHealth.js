import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  getHealthOverview,
  getComponentHealth,
  getHealthHistory,
  getIncidents,
  getRecommendations,
  acknowledgeIncident,
  resolveIncident,
  dismissRecommendation,
  exportHealthReport,
  TimeRanges,
} from '../services/customerHealthApi';

/**
 * useCustomerHealth Hook
 *
 * Comprehensive hook for managing customer health dashboard state.
 * Features:
 * - Automatic data fetching and caching
 * - Auto-refresh every 60 seconds (configurable)
 * - Date range filtering
 * - Component drill-down support
 * - Incident management actions
 * - Export functionality
 *
 * Usage:
 *   const {
 *     overview,
 *     incidents,
 *     recommendations,
 *     loading,
 *     error,
 *     timeRange,
 *     setTimeRange,
 *     refreshData,
 *   } = useCustomerHealth();
 */

// Default refresh interval (60 seconds)
const DEFAULT_REFRESH_INTERVAL = 60000;

// Cache duration for component health data (5 minutes)
const COMPONENT_CACHE_DURATION = 5 * 60 * 1000;

/**
 * Simple in-memory cache for component health data
 */
const componentCache = new Map();

function getCachedComponent(componentId, timeRange) {
  const key = `${componentId}-${timeRange}`;
  const cached = componentCache.get(key);
  if (cached && Date.now() - cached.timestamp < COMPONENT_CACHE_DURATION) {
    return cached.data;
  }
  return null;
}

function setCachedComponent(componentId, timeRange, data) {
  const key = `${componentId}-${timeRange}`;
  componentCache.set(key, { data, timestamp: Date.now() });
}

export function useCustomerHealth(options = {}) {
  const {
    autoRefresh = true,
    refreshInterval = DEFAULT_REFRESH_INTERVAL,
    initialTimeRange = TimeRanges.DAY,
  } = options;

  // State
  const [timeRange, setTimeRange] = useState(initialTimeRange);
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState(null);
  const [incidents, setIncidents] = useState({ incidents: [], total: 0, has_more: false });
  const [recommendations, setRecommendations] = useState([]);
  const [selectedComponent, setSelectedComponent] = useState(null);
  const [componentDetails, setComponentDetails] = useState(null);

  // Loading states
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingIncidents, setLoadingIncidents] = useState(true);
  const [loadingRecommendations, setLoadingRecommendations] = useState(true);
  const [loadingComponent, setLoadingComponent] = useState(false);
  const [loadingExport, setLoadingExport] = useState(false);

  // Error states
  const [error, setError] = useState(null);
  const [componentError, setComponentError] = useState(null);

  // Refs for cleanup
  const refreshIntervalRef = useRef(null);
  const mountedRef = useRef(true);

  // Incident pagination state
  const [incidentPage, setIncidentPage] = useState(0);
  const [incidentFilter, setIncidentFilter] = useState({ status: null, severity: null });

  // History date range
  const [historyDays, setHistoryDays] = useState(30);

  /**
   * Fetch health overview
   */
  const fetchOverview = useCallback(async () => {
    try {
      setLoadingOverview(true);
      setError(null);
      const data = await getHealthOverview(timeRange);
      if (mountedRef.current) {
        setOverview(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to load health overview');
        console.error('Failed to fetch health overview:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingOverview(false);
      }
    }
  }, [timeRange]);

  /**
   * Fetch health history for charts
   */
  const fetchHistory = useCallback(async (days = historyDays, resolution = 'daily') => {
    try {
      setLoadingHistory(true);
      const data = await getHealthHistory(days, resolution);
      if (mountedRef.current) {
        setHistory(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch health history:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingHistory(false);
      }
    }
  }, [historyDays]);

  /**
   * Fetch incidents with pagination and filters
   */
  const fetchIncidents = useCallback(async (page = 0, filters = incidentFilter) => {
    try {
      setLoadingIncidents(true);
      const data = await getIncidents({
        status: filters.status,
        severity: filters.severity,
        limit: 10,
        offset: page * 10,
      });
      if (mountedRef.current) {
        setIncidents(data);
        setIncidentPage(page);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch incidents:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingIncidents(false);
      }
    }
  }, [incidentFilter]);

  /**
   * Fetch recommendations
   */
  const fetchRecommendations = useCallback(async (category = null) => {
    try {
      setLoadingRecommendations(true);
      const data = await getRecommendations(category);
      if (mountedRef.current) {
        setRecommendations(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch recommendations:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingRecommendations(false);
      }
    }
  }, []);

  /**
   * Fetch component details with caching
   */
  const fetchComponentDetails = useCallback(async (componentId) => {
    if (!componentId) {
      setComponentDetails(null);
      return;
    }

    // Check cache first
    const cached = getCachedComponent(componentId, timeRange);
    if (cached) {
      setComponentDetails(cached);
      return;
    }

    try {
      setLoadingComponent(true);
      setComponentError(null);
      const data = await getComponentHealth(componentId, timeRange);
      if (mountedRef.current) {
        setCachedComponent(componentId, timeRange, data);
        setComponentDetails(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setComponentError(err.message || 'Failed to load component details');
        console.error('Failed to fetch component details:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoadingComponent(false);
      }
    }
  }, [timeRange]);

  /**
   * Refresh all data
   */
  const refreshData = useCallback(async () => {
    await Promise.all([
      fetchOverview(),
      fetchIncidents(incidentPage, incidentFilter),
      fetchRecommendations(),
    ]);
    if (selectedComponent) {
      await fetchComponentDetails(selectedComponent);
    }
  }, [fetchOverview, fetchIncidents, fetchRecommendations, fetchComponentDetails, incidentPage, incidentFilter, selectedComponent]);

  /**
   * Handle incident acknowledgement
   */
  const handleAcknowledgeIncident = useCallback(async (incidentId, notes = '') => {
    try {
      await acknowledgeIncident(incidentId, notes);
      // Refresh incidents to get updated status
      await fetchIncidents(incidentPage, incidentFilter);
      return { success: true };
    } catch (err) {
      console.error('Failed to acknowledge incident:', err);
      return { success: false, error: err.message };
    }
  }, [fetchIncidents, incidentPage, incidentFilter]);

  /**
   * Handle incident resolution
   */
  const handleResolveIncident = useCallback(async (incidentId, resolution = '') => {
    try {
      await resolveIncident(incidentId, resolution);
      await fetchIncidents(incidentPage, incidentFilter);
      return { success: true };
    } catch (err) {
      console.error('Failed to resolve incident:', err);
      return { success: false, error: err.message };
    }
  }, [fetchIncidents, incidentPage, incidentFilter]);

  /**
   * Handle recommendation dismissal
   */
  const handleDismissRecommendation = useCallback(async (recommendationId, reason = '') => {
    try {
      await dismissRecommendation(recommendationId, reason);
      // Remove from local state
      setRecommendations(prev => prev.filter(r => r.id !== recommendationId));
      return { success: true };
    } catch (err) {
      console.error('Failed to dismiss recommendation:', err);
      return { success: false, error: err.message };
    }
  }, []);

  /**
   * Handle report export
   */
  const handleExportReport = useCallback(async (format = 'pdf', dateFrom = null, dateTo = null) => {
    try {
      setLoadingExport(true);
      const blob = await exportHealthReport({
        format,
        dateFrom,
        dateTo,
        sections: ['overview', 'incidents', 'recommendations'],
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `health-report-${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      return { success: true };
    } catch (err) {
      console.error('Failed to export report:', err);
      return { success: false, error: err.message };
    } finally {
      setLoadingExport(false);
    }
  }, []);

  /**
   * Handle time range change
   */
  const handleTimeRangeChange = useCallback((newRange) => {
    setTimeRange(newRange);
    // Clear component cache when time range changes
    componentCache.clear();
  }, []);

  /**
   * Handle incident filter change
   */
  const handleIncidentFilterChange = useCallback((filters) => {
    setIncidentFilter(prev => ({ ...prev, ...filters }));
    setIncidentPage(0);
  }, []);

  /**
   * Select a component for drill-down
   */
  const selectComponent = useCallback((componentId) => {
    setSelectedComponent(componentId);
    if (componentId) {
      fetchComponentDetails(componentId);
    } else {
      setComponentDetails(null);
    }
  }, [fetchComponentDetails]);

  /**
   * Load next page of incidents
   */
  const loadMoreIncidents = useCallback(() => {
    if (incidents.has_more) {
      fetchIncidents(incidentPage + 1, incidentFilter);
    }
  }, [incidents.has_more, fetchIncidents, incidentPage, incidentFilter]);

  /**
   * Load previous page of incidents
   */
  const loadPreviousIncidents = useCallback(() => {
    if (incidentPage > 0) {
      fetchIncidents(incidentPage - 1, incidentFilter);
    }
  }, [incidentPage, fetchIncidents, incidentFilter]);

  // Initial data fetch
  useEffect(() => {
    mountedRef.current = true;
    fetchOverview();
    fetchHistory();
    fetchIncidents();
    fetchRecommendations();

    return () => {
      mountedRef.current = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch overview when time range changes
  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  // Re-fetch history when days change
  useEffect(() => {
    fetchHistory(historyDays);
  }, [fetchHistory, historyDays]);

  // Re-fetch incidents when filter changes
  useEffect(() => {
    fetchIncidents(0, incidentFilter);
  }, [incidentFilter]); // eslint-disable-line react-hooks/exhaustive-deps

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
    loadingOverview || loadingIncidents || loadingRecommendations
  ), [loadingOverview, loadingIncidents, loadingRecommendations]);

  const activeIncidentsCount = useMemo(() => (
    incidents.incidents?.filter(i => i.status === 'active').length || 0
  ), [incidents]);

  const healthScore = useMemo(() => (
    overview?.score || 0
  ), [overview]);

  const healthStatus = useMemo(() => (
    overview?.status || 'unknown'
  ), [overview]);

  // Chart data formatted for components
  const trendChartData = useMemo(() => {
    if (!overview?.trend?.data) return { data: [], labels: [] };

    return {
      data: overview.trend.data.map(d => Math.round(d.score)),
      labels: overview.trend.data.map(d => {
        const date = new Date(d.timestamp);
        if (timeRange === '1h') {
          return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        if (timeRange === '24h') {
          return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }),
    };
  }, [overview, timeRange]);

  const historyChartData = useMemo(() => {
    if (!history?.data) return { data: [], labels: [] };

    return {
      data: history.data.map(d => d.score),
      labels: history.data.map(d => {
        const date = new Date(d.timestamp);
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }),
    };
  }, [history]);

  return {
    // Data
    overview,
    history,
    incidents,
    recommendations,
    componentDetails,
    selectedComponent,

    // Computed values
    healthScore,
    healthStatus,
    activeIncidentsCount,
    trendChartData,
    historyChartData,

    // Loading states
    isLoading,
    loadingOverview,
    loadingHistory,
    loadingIncidents,
    loadingRecommendations,
    loadingComponent,
    loadingExport,

    // Error states
    error,
    componentError,

    // Filters and pagination
    timeRange,
    incidentPage,
    incidentFilter,
    historyDays,

    // Actions
    setTimeRange: handleTimeRangeChange,
    setIncidentFilter: handleIncidentFilterChange,
    setHistoryDays,
    selectComponent,
    refreshData,
    loadMoreIncidents,
    loadPreviousIncidents,

    // Mutations
    acknowledgeIncident: handleAcknowledgeIncident,
    resolveIncident: handleResolveIncident,
    dismissRecommendation: handleDismissRecommendation,
    exportReport: handleExportReport,
  };
}

/**
 * useHealthOverview Hook
 *
 * Simplified hook for just the health overview data.
 * Useful for dashboard widgets that only need the score.
 */
export function useHealthOverview(timeRange = TimeRanges.DAY) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        const data = await getHealthOverview(timeRange);
        if (mounted) {
          setOverview(data);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err.message);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    // Refresh every 60 seconds
    const interval = setInterval(fetchData, 60000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [timeRange]);

  return { overview, loading, error };
}

/**
 * useIncidents Hook
 *
 * Focused hook for incident management.
 */
export function useIncidents(options = {}) {
  const { status = null, severity = null, limit = 10 } = options;
  const [incidents, setIncidents] = useState({ incidents: [], total: 0, has_more: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);

  const fetchData = useCallback(async (pageNum = page) => {
    try {
      setLoading(true);
      const data = await getIncidents({
        status,
        severity,
        limit,
        offset: pageNum * limit,
      });
      setIncidents(data);
      setPage(pageNum);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [status, severity, limit, page]);

  useEffect(() => {
    fetchData(0);
  }, [status, severity]); // eslint-disable-line react-hooks/exhaustive-deps

  const nextPage = useCallback(() => {
    if (incidents.has_more) {
      fetchData(page + 1);
    }
  }, [incidents.has_more, fetchData, page]);

  const prevPage = useCallback(() => {
    if (page > 0) {
      fetchData(page - 1);
    }
  }, [page, fetchData]);

  const acknowledge = useCallback(async (incidentId, notes = '') => {
    const result = await acknowledgeIncident(incidentId, notes);
    await fetchData(page);
    return result;
  }, [fetchData, page]);

  const resolve = useCallback(async (incidentId, resolution = '') => {
    const result = await resolveIncident(incidentId, resolution);
    await fetchData(page);
    return result;
  }, [fetchData, page]);

  return {
    incidents: incidents.incidents,
    total: incidents.total,
    hasMore: incidents.has_more,
    page,
    loading,
    error,
    refresh: () => fetchData(page),
    nextPage,
    prevPage,
    acknowledge,
    resolve,
  };
}

export default useCustomerHealth;

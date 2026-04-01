/**
 * Project Aura - Dashboard Configuration Hook
 *
 * Custom React hook for managing dashboard layout configurations
 * with persistence, role-based defaults, and optimistic updates.
 *
 * Implements ADR-064 customizable dashboard widgets.
 *
 * @module hooks/useDashboardConfig
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ROLE_DEFAULT_CONFIGS, getWidgetById, UserRole } from '../components/dashboard';

// API base URL - uses environment variable or defaults to localhost for dev
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Local storage key for dashboard config cache
const STORAGE_KEY = 'aura-dashboard-config';

// Default config for new users
const DEFAULT_CONFIG = ROLE_DEFAULT_CONFIGS[UserRole.SECURITY_ENGINEER];

/**
 * Convert role default config to layout/widgets format
 */
function roleConfigToLayout(roleConfig) {
  const layout = [];
  const widgets = [];

  roleConfig.widgets.forEach((w, index) => {
    const definition = getWidgetById(w.id);
    if (!definition) return;

    const widgetId = `widget-${w.id}-${index}`;

    layout.push({
      i: widgetId,
      x: w.x,
      y: w.y,
      w: w.w,
      h: w.h,
      minW: definition.minWidth,
      minH: definition.minHeight,
    });

    widgets.push({
      i: widgetId,
      definitionId: w.id,
      color: definition.defaultColor,
      dataSource: definition.dataSource,
      refreshSeconds: definition.defaultRefreshSeconds,
    });
  });

  return { layout, widgets };
}

/**
 * Custom hook for managing dashboard configurations.
 *
 * Features:
 * - Fetch user's dashboard configuration from API
 * - Save configuration changes with optimistic updates
 * - Load role-based default configurations
 * - Local storage cache for offline support
 * - Auto-save on layout changes (debounced)
 *
 * @param {Object} [options] - Hook options
 * @param {string} [options.userId] - User ID for personalization
 * @param {string} [options.userRole] - User role for defaults
 * @param {string} [options.dashboardId] - Specific dashboard ID to load
 * @param {boolean} [options.autoSave=true] - Enable auto-save on changes
 * @param {number} [options.autoSaveDelay=2000] - Auto-save debounce delay in ms
 * @returns {Object} Dashboard configuration and controls
 *
 * @example
 * const {
 *   layout,
 *   widgets,
 *   loading,
 *   error,
 *   saveConfig,
 *   loadRoleDefault,
 *   updateLayout,
 *   addWidget,
 *   removeWidget,
 *   resetToDefault,
 * } = useDashboardConfig({ userId: 'user-123', userRole: 'security-engineer' });
 */
export function useDashboardConfig(options = {}) {
  const {
    userId = null,
    userRole = UserRole.SECURITY_ENGINEER,
    dashboardId = null,
    autoSave = true,
    autoSaveDelay = 2000,
  } = options;

  // State
  const [layout, setLayout] = useState([]);
  const [widgets, setWidgets] = useState([]);
  const [dashboardMeta, setDashboardMeta] = useState({
    id: null,
    name: 'My Dashboard',
    description: '',
    isDefault: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Refs
  const mountedRef = useRef(true);
  const autoSaveTimerRef = useRef(null);
  const previousConfigRef = useRef(null);

  /**
   * Load configuration from local storage cache
   */
  const loadFromCache = useCallback(() => {
    try {
      const cached = localStorage.getItem(STORAGE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed.userId === userId) {
          return parsed;
        }
      }
    } catch (err) {
      console.warn('Failed to load dashboard config from cache:', err);
    }
    return null;
  }, [userId]);

  /**
   * Save configuration to local storage cache
   */
  const saveToCache = useCallback((config) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        ...config,
        userId,
        cachedAt: new Date().toISOString(),
      }));
    } catch (err) {
      console.warn('Failed to cache dashboard config:', err);
    }
  }, [userId]);

  /**
   * Fetch dashboard configuration from API
   */
  const fetchConfig = useCallback(async () => {
    if (!mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      // Try to load from API
      const endpoint = dashboardId
        ? `${API_BASE_URL}/dashboards/${dashboardId}`
        : `${API_BASE_URL}/dashboards/me`;

      const response = await fetch(endpoint, {
        headers: {
          'Content-Type': 'application/json',
          // Auth header would be added by interceptor in real app
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (mountedRef.current) {
          setLayout(data.layout || []);
          setWidgets(data.widgets || []);
          setDashboardMeta({
            id: data.id,
            name: data.name,
            description: data.description,
            isDefault: data.isDefault || false,
          });
          saveToCache({ layout: data.layout, widgets: data.widgets });
        }
        return;
      }

      // If 404, user doesn't have a saved dashboard - load role default
      if (response.status === 404) {
        const defaultConfig = roleConfigToLayout(
          ROLE_DEFAULT_CONFIGS[userRole] || DEFAULT_CONFIG
        );
        if (mountedRef.current) {
          setLayout(defaultConfig.layout);
          setWidgets(defaultConfig.widgets);
          setDashboardMeta({
            id: null,
            name: 'My Dashboard',
            description: '',
            isDefault: true,
          });
        }
        return;
      }

      throw new Error(`Failed to fetch dashboard: ${response.statusText}`);
    } catch (err) {
      // Try cache on network error
      const cached = loadFromCache();
      if (cached && mountedRef.current) {
        setLayout(cached.layout || []);
        setWidgets(cached.widgets || []);
        console.warn('Loaded dashboard config from cache (API unavailable)');
        return;
      }

      // Fall back to role default
      const defaultConfig = roleConfigToLayout(
        ROLE_DEFAULT_CONFIGS[userRole] || DEFAULT_CONFIG
      );
      if (mountedRef.current) {
        setLayout(defaultConfig.layout);
        setWidgets(defaultConfig.widgets);
        setDashboardMeta({
          id: null,
          name: 'My Dashboard',
          description: '',
          isDefault: true,
        });
        // Don't show error for expected dev scenario
        if (err.message !== 'Failed to fetch') {
          setError(err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [dashboardId, userRole, loadFromCache, saveToCache]);

  /**
   * Save dashboard configuration to API
   */
  const saveConfig = useCallback(async (configOverride = null) => {
    if (!mountedRef.current) return;

    const configToSave = configOverride || { layout, widgets };
    setSaving(true);
    setError(null);

    // Store previous config for rollback
    previousConfigRef.current = { layout, widgets };

    try {
      const endpoint = dashboardMeta.id
        ? `${API_BASE_URL}/dashboards/${dashboardMeta.id}`
        : `${API_BASE_URL}/dashboards`;

      const method = dashboardMeta.id ? 'PUT' : 'POST';

      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: dashboardMeta.name,
          description: dashboardMeta.description,
          layout: configToSave.layout,
          widgets: configToSave.widgets,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to save dashboard: ${response.statusText}`);
      }

      const saved = await response.json();
      if (mountedRef.current) {
        setDashboardMeta((prev) => ({
          ...prev,
          id: saved.id,
          isDefault: false,
        }));
        setHasUnsavedChanges(false);
        saveToCache(configToSave);
      }

      return saved;
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        // Save to cache even on API failure
        saveToCache(configToSave);
      }
      throw err;
    } finally {
      if (mountedRef.current) {
        setSaving(false);
      }
    }
  }, [layout, widgets, dashboardMeta, saveToCache]);

  /**
   * Update layout (from react-grid-layout)
   */
  const updateLayout = useCallback((newLayout) => {
    setLayout(newLayout);
    setHasUnsavedChanges(true);

    // Auto-save with debounce
    if (autoSave) {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
      autoSaveTimerRef.current = setTimeout(() => {
        saveConfig({ layout: newLayout, widgets });
      }, autoSaveDelay);
    }
  }, [autoSave, autoSaveDelay, saveConfig, widgets]);

  /**
   * Add a widget to the dashboard
   */
  const addWidget = useCallback((widgetDefinition) => {
    const widgetId = `widget-${widgetDefinition.id}-${Date.now()}`;

    // Find first available position
    const maxY = layout.reduce((max, item) => Math.max(max, item.y + item.h), 0);

    const newLayoutItem = {
      i: widgetId,
      x: 0,
      y: maxY,
      w: widgetDefinition.defaultWidth,
      h: widgetDefinition.defaultHeight,
      minW: widgetDefinition.minWidth,
      minH: widgetDefinition.minHeight,
    };

    const newWidget = {
      i: widgetId,
      definitionId: widgetDefinition.id,
      color: widgetDefinition.defaultColor,
      dataSource: widgetDefinition.dataSource,
      refreshSeconds: widgetDefinition.defaultRefreshSeconds,
    };

    setLayout((prev) => [...prev, newLayoutItem]);
    setWidgets((prev) => [...prev, newWidget]);
    setHasUnsavedChanges(true);

    return widgetId;
  }, [layout]);

  /**
   * Remove a widget from the dashboard
   */
  const removeWidget = useCallback((widgetId) => {
    setLayout((prev) => prev.filter((item) => item.i !== widgetId));
    setWidgets((prev) => prev.filter((w) => w.i !== widgetId));
    setHasUnsavedChanges(true);
  }, []);

  /**
   * Update widget configuration
   */
  const updateWidget = useCallback((widgetId, updates) => {
    setWidgets((prev) =>
      prev.map((w) => (w.i === widgetId ? { ...w, ...updates } : w))
    );
    setHasUnsavedChanges(true);
  }, []);

  /**
   * Load a role-based default configuration
   */
  const loadRoleDefault = useCallback((role) => {
    const roleConfig = ROLE_DEFAULT_CONFIGS[role];
    if (!roleConfig) {
      console.warn(`No default config for role: ${role}`);
      return;
    }

    const { layout: newLayout, widgets: newWidgets } = roleConfigToLayout(roleConfig);
    setLayout(newLayout);
    setWidgets(newWidgets);
    setDashboardMeta({
      id: null,
      name: roleConfig.name,
      description: roleConfig.description,
      isDefault: true,
    });
    setHasUnsavedChanges(true);
  }, []);

  /**
   * Reset to default configuration
   */
  const resetToDefault = useCallback(() => {
    loadRoleDefault(userRole);
  }, [loadRoleDefault, userRole]);

  /**
   * Revert to last saved configuration
   */
  const revertChanges = useCallback(() => {
    if (previousConfigRef.current) {
      setLayout(previousConfigRef.current.layout);
      setWidgets(previousConfigRef.current.widgets);
      setHasUnsavedChanges(false);
    }
  }, []);

  /**
   * Update dashboard metadata (name, description)
   */
  const updateMeta = useCallback((updates) => {
    setDashboardMeta((prev) => ({ ...prev, ...updates }));
    setHasUnsavedChanges(true);
  }, []);

  /**
   * Share dashboard with a user or organization
   */
  const shareDashboard = useCallback(async ({ userId: shareUserId, orgId, permission = 'view' }) => {
    if (!dashboardMeta.id) {
      throw new Error('Dashboard must be saved before sharing');
    }

    const response = await fetch(`${API_BASE_URL}/dashboards/${dashboardMeta.id}/share`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: shareUserId,
        org_id: orgId,
        permission,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to share dashboard');
    }

    return response.json();
  }, [dashboardMeta.id]);

  /**
   * Revoke share access for a user
   */
  const revokeShare = useCallback(async ({ userId: revokeUserId }) => {
    if (!dashboardMeta.id) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardMeta.id}/shares/${revokeUserId}`,
      {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to revoke share');
    }
  }, [dashboardMeta.id]);

  /**
   * Clone dashboard
   */
  const cloneDashboard = useCallback(async (dashboardId, newName = null) => {
    const response = await fetch(`${API_BASE_URL}/dashboards/${dashboardId}/clone`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: newName,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to clone dashboard');
    }

    return response.json();
  }, []);

  /**
   * Fetch shares for current dashboard
   */
  const fetchShares = useCallback(async () => {
    if (!dashboardMeta.id) return [];

    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/${dashboardMeta.id}/shares`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) return [];

      const data = await response.json();
      return data.shares || [];
    } catch {
      return [];
    }
  }, [dashboardMeta.id]);

  // ==========================================================================
  // Phase 3: Custom Widget Builder Functions
  // ==========================================================================

  /**
   * Fetch available data sources for custom widgets
   */
  const fetchDataSources = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/widgets/custom/data-sources`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) return { data_sources: [], query_types: [] };

      return response.json();
    } catch {
      return { data_sources: [], query_types: [] };
    }
  }, []);

  /**
   * List custom widgets
   */
  const listCustomWidgets = useCallback(async (includePublished = true) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/widgets/custom?include_published=${includePublished}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) return [];

      const data = await response.json();
      return data.widgets || [];
    } catch {
      return [];
    }
  }, []);

  /**
   * Create a custom widget
   */
  const createCustomWidget = useCallback(async (widgetData) => {
    const response = await fetch(`${API_BASE_URL}/widgets/custom`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(widgetData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to create custom widget');
    }

    return response.json();
  }, []);

  /**
   * Update a custom widget
   */
  const updateCustomWidget = useCallback(async (widgetId, widgetData) => {
    const response = await fetch(`${API_BASE_URL}/widgets/custom/${widgetId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(widgetData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to update custom widget');
    }

    return response.json();
  }, []);

  /**
   * Delete a custom widget
   */
  const deleteCustomWidget = useCallback(async (widgetId) => {
    const response = await fetch(`${API_BASE_URL}/widgets/custom/${widgetId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to delete custom widget');
    }
  }, []);

  /**
   * Preview a custom widget query
   */
  const previewCustomQuery = useCallback(async (query) => {
    const response = await fetch(`${API_BASE_URL}/widgets/custom/preview`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(query),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to preview query');
    }

    return response.json();
  }, []);

  /**
   * Execute a custom widget's query
   */
  const executeCustomWidgetQuery = useCallback(async (widgetId) => {
    const response = await fetch(`${API_BASE_URL}/widgets/custom/${widgetId}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to execute query');
    }

    return response.json();
  }, []);

  // Initial load
  useEffect(() => {
    mountedRef.current = true;
    fetchConfig();

    return () => {
      mountedRef.current = false;
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [fetchConfig]);

  // Warn on unsaved changes before unload
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  return {
    // Data
    layout,
    widgets,
    dashboardMeta,

    // States
    loading,
    saving,
    error,
    hasUnsavedChanges,

    // Actions
    saveConfig,
    updateLayout,
    addWidget,
    removeWidget,
    updateWidget,
    loadRoleDefault,
    resetToDefault,
    revertChanges,
    updateMeta,
    refetch: fetchConfig,

    // Phase 2: Sharing & Collaboration
    shareDashboard,
    revokeShare,
    cloneDashboard,
    fetchShares,

    // Phase 3: Custom Widget Builder
    fetchDataSources,
    listCustomWidgets,
    createCustomWidget,
    updateCustomWidget,
    deleteCustomWidget,
    previewCustomQuery,
    executeCustomWidgetQuery,
  };
}

/**
 * Hook for fetching available dashboards (for dashboard switcher)
 */
export function useDashboardList(options = {}) {
  const { userId = null } = options;

  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchDashboards = useCallback(async () => {
    if (!mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/dashboards`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch dashboards: ${response.statusText}`);
      }

      const data = await response.json();
      if (mountedRef.current) {
        setDashboards(data.dashboards || []);
      }
    } catch (err) {
      if (mountedRef.current) {
        // Return empty list on error (expected in dev)
        setDashboards([]);
        if (err.message !== 'Failed to fetch') {
          setError(err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchDashboards();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchDashboards]);

  return {
    dashboards,
    loading,
    error,
    refetch: fetchDashboards,
  };
}

// =============================================================================
// Scheduled Reports Hook (Phase 3)
// =============================================================================

/**
 * Hook for managing scheduled reports for a dashboard.
 *
 * @param {string} dashboardId - Dashboard ID to manage schedules for
 * @returns {Object} Schedule management functions and state
 */
export function useScheduledReports(dashboardId) {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  /**
   * Fetch schedules for the dashboard
   */
  const fetchSchedules = useCallback(async () => {
    if (!dashboardId) {
      setSchedules([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/dashboards/${dashboardId}/schedules`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch schedules: ${response.statusText}`);
      }

      const data = await response.json();
      if (mountedRef.current) {
        setSchedules(data.schedules || []);
      }
    } catch (err) {
      if (mountedRef.current) {
        setSchedules([]);
        if (err.message !== 'Failed to fetch') {
          setError(err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [dashboardId]);

  /**
   * Create a new scheduled report
   */
  const createSchedule = useCallback(async (scheduleData) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/schedules`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(scheduleData),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to create schedule');
    }

    const newSchedule = await response.json();

    if (mountedRef.current) {
      setSchedules((prev) => [...prev, newSchedule]);
    }

    return newSchedule;
  }, [dashboardId]);

  /**
   * Update an existing scheduled report
   */
  const updateSchedule = useCallback(async (reportId, scheduleData) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/schedules/${reportId}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(scheduleData),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to update schedule');
    }

    const updatedSchedule = await response.json();

    if (mountedRef.current) {
      setSchedules((prev) =>
        prev.map((s) => (s.report_id === reportId ? updatedSchedule : s))
      );
    }

    return updatedSchedule;
  }, [dashboardId]);

  /**
   * Delete a scheduled report
   */
  const deleteSchedule = useCallback(async (reportId) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/schedules/${reportId}`,
      {
        method: 'DELETE',
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to delete schedule');
    }

    if (mountedRef.current) {
      setSchedules((prev) => prev.filter((s) => s.report_id !== reportId));
    }
  }, [dashboardId]);

  /**
   * Manually trigger report delivery
   */
  const sendReportNow = useCallback(async (reportId) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/schedules/${reportId}/send`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to send report');
    }

    const result = await response.json();

    // Refresh schedules to get updated stats
    fetchSchedules();

    return result;
  }, [dashboardId, fetchSchedules]);

  useEffect(() => {
    mountedRef.current = true;
    fetchSchedules();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchSchedules]);

  return {
    schedules,
    loading,
    error,
    fetchSchedules,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    sendReportNow,
  };
}

/**
 * Hook for fetching all user's scheduled reports across dashboards.
 *
 * @returns {Object} User schedules and state
 */
export function useUserScheduledReports() {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchSchedules = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/dashboards/user/schedules`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch schedules: ${response.statusText}`);
      }

      const data = await response.json();
      if (mountedRef.current) {
        setSchedules(data.schedules || []);
      }
    } catch (err) {
      if (mountedRef.current) {
        setSchedules([]);
        if (err.message !== 'Failed to fetch') {
          setError(err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchSchedules();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchSchedules]);

  return {
    schedules,
    loading,
    error,
    refetch: fetchSchedules,
  };
}

// =============================================================================
// Dashboard Embedding Hook (Phase 3)
// =============================================================================

/**
 * Hook for managing embed tokens for a dashboard.
 *
 * @param {string} dashboardId - Dashboard ID to manage embed tokens for
 * @returns {Object} Embed token management functions and state
 */
export function useEmbedTokens(dashboardId) {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  /**
   * Fetch embed tokens for the dashboard
   */
  const fetchTokens = useCallback(async () => {
    if (!dashboardId) {
      setTokens([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/dashboards/${dashboardId}/embed`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch embed tokens: ${response.statusText}`);
      }

      const data = await response.json();
      if (mountedRef.current) {
        setTokens(data.tokens || []);
      }
    } catch (err) {
      if (mountedRef.current) {
        setTokens([]);
        if (err.message !== 'Failed to fetch') {
          setError(err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [dashboardId]);

  /**
   * Create a new embed token
   */
  const createToken = useCallback(async (tokenData) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/embed`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(tokenData),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to create embed token');
    }

    const newToken = await response.json();

    if (mountedRef.current) {
      setTokens((prev) => [...prev, newToken]);
    }

    return newToken;
  }, [dashboardId]);

  /**
   * Update an existing embed token
   */
  const updateToken = useCallback(async (tokenId, tokenData) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/embed/${tokenId}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(tokenData),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to update embed token');
    }

    const updatedToken = await response.json();

    if (mountedRef.current) {
      setTokens((prev) =>
        prev.map((t) => (t.token_id === tokenId ? updatedToken : t))
      );
    }

    return updatedToken;
  }, [dashboardId]);

  /**
   * Revoke an embed token (deactivate without deleting)
   */
  const revokeToken = useCallback(async (tokenId) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/embed/${tokenId}/revoke`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to revoke embed token');
    }

    // Refresh tokens to get updated status
    fetchTokens();
  }, [dashboardId, fetchTokens]);

  /**
   * Delete an embed token permanently
   */
  const deleteToken = useCallback(async (tokenId) => {
    if (!dashboardId) {
      throw new Error('Dashboard ID is required');
    }

    const response = await fetch(
      `${API_BASE_URL}/dashboards/${dashboardId}/embed/${tokenId}`,
      {
        method: 'DELETE',
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to delete embed token');
    }

    if (mountedRef.current) {
      setTokens((prev) => prev.filter((t) => t.token_id !== tokenId));
    }
  }, [dashboardId]);

  useEffect(() => {
    mountedRef.current = true;
    fetchTokens();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchTokens]);

  return {
    tokens,
    loading,
    error,
    fetchTokens,
    createToken,
    updateToken,
    revokeToken,
    deleteToken,
  };
}

/**
 * Hook for fetching all user's embed tokens across dashboards.
 *
 * @returns {Object} User embed tokens and state
 */
export function useUserEmbedTokens() {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchTokens = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/dashboards/user/embed-tokens`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch embed tokens: ${response.statusText}`);
      }

      const data = await response.json();
      if (mountedRef.current) {
        setTokens(data.tokens || []);
      }
    } catch (err) {
      if (mountedRef.current) {
        setTokens([]);
        if (err.message !== 'Failed to fetch') {
          setError(err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchTokens();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchTokens]);

  return {
    tokens,
    loading,
    error,
    refetch: fetchTokens,
  };
}

export default useDashboardConfig;

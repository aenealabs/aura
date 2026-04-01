/**
 * Developer Mode Context
 *
 * Provides global state management for developer/debug mode features.
 * Controls performance bar, API inspector, log levels, and other dev tools.
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

// Log levels from least to most verbose
export const LOG_LEVELS = {
  ERROR: 'error',
  WARN: 'warn',
  INFO: 'info',
  DEBUG: 'debug',
  VERBOSE: 'verbose',
};

// Network throttling presets
export const NETWORK_PRESETS = {
  NONE: { id: 'none', label: 'No Throttling', latency: 0, downloadSpeed: Infinity },
  FAST_3G: { id: 'fast_3g', label: 'Fast 3G', latency: 150, downloadSpeed: 1.5 },
  SLOW_3G: { id: 'slow_3g', label: 'Slow 3G', latency: 400, downloadSpeed: 0.4 },
  OFFLINE: { id: 'offline', label: 'Offline', latency: Infinity, downloadSpeed: 0 },
};

// Session timeout options (in minutes)
export const SESSION_TIMEOUTS = [
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
  { value: 240, label: '4 hours' },
  { value: null, label: 'Never' },
];

// Feature flags available for override
export const FEATURE_FLAGS = [
  { id: 'experimental_graph_viz', label: 'Experimental Graph Visualization', description: 'New 3D graph rendering engine' },
  { id: 'ai_suggestions_v2', label: 'AI Suggestions v2', description: 'Next-gen code suggestion algorithm' },
  { id: 'realtime_collaboration', label: 'Real-time Collaboration', description: 'Live cursor and editing sync' },
  { id: 'advanced_security_scan', label: 'Advanced Security Scanning', description: 'Deep vulnerability analysis' },
  { id: 'agent_autonomy_v2', label: 'Agent Autonomy v2', description: 'Enhanced autonomous decision making' },
];

const STORAGE_KEY = 'aura_developer_mode';

const defaultState = {
  enabled: false,
  sessionTimeout: 60, // minutes
  sessionExpiresAt: null,
  performanceBar: {
    enabled: false,
    position: 'bottom', // 'top' | 'bottom'
  },
  logLevel: LOG_LEVELS.ERROR,
  apiInspector: {
    enabled: false,
    capturePayloads: true,
    maxRequests: 100,
  },
  featureFlags: {},
  graphRAGDebug: false,
  agentTraceViewer: false,
  mockDataMode: false,
  networkThrottling: 'none',
};

const DeveloperModeContext = createContext(null);

export function DeveloperModeProvider({ children }) {
  const [state, setState] = useState(() => {
    // Load from localStorage on init
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Check if session has expired
        if (parsed.sessionExpiresAt && new Date(parsed.sessionExpiresAt) < new Date()) {
          return defaultState;
        }
        return { ...defaultState, ...parsed };
      }
    } catch (e) {
      console.warn('Failed to load developer mode state:', e);
    }
    return defaultState;
  });

  const [apiRequests, setApiRequests] = useState([]);
  const [performanceMetrics, setPerformanceMetrics] = useState({
    apiCalls: 0,
    apiTime: 0,
    dbQueries: 0,
    dbTime: 0,
    cacheHits: 0,
    cacheMisses: 0,
    memoryUsage: 0,
  });

  const timeoutRef = useRef(null);

  // Persist state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn('Failed to save developer mode state:', e);
    }
  }, [state]);

  // Handle session timeout
  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    if (state.enabled && state.sessionTimeout && state.sessionExpiresAt) {
      const remaining = new Date(state.sessionExpiresAt) - new Date();
      if (remaining > 0) {
        timeoutRef.current = setTimeout(() => {
          setState((prev) => ({ ...prev, enabled: false, sessionExpiresAt: null }));
        }, remaining);
      }
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [state.enabled, state.sessionTimeout, state.sessionExpiresAt]);

  // Enable developer mode
  const enableDevMode = useCallback((timeout = state.sessionTimeout) => {
    const expiresAt = timeout ? new Date(Date.now() + timeout * 60 * 1000).toISOString() : null;
    setState((prev) => ({
      ...prev,
      enabled: true,
      sessionTimeout: timeout,
      sessionExpiresAt: expiresAt,
    }));
  }, [state.sessionTimeout]);

  // Disable developer mode
  const disableDevMode = useCallback(() => {
    setState((prev) => ({
      ...prev,
      enabled: false,
      sessionExpiresAt: null,
      performanceBar: { ...prev.performanceBar, enabled: false },
      apiInspector: { ...prev.apiInspector, enabled: false },
    }));
    setApiRequests([]);
  }, []);

  // Toggle performance bar
  const togglePerformanceBar = useCallback(() => {
    setState((prev) => ({
      ...prev,
      performanceBar: {
        ...prev.performanceBar,
        enabled: !prev.performanceBar.enabled,
      },
    }));
  }, []);

  // Set log level
  const setLogLevel = useCallback((level) => {
    setState((prev) => ({ ...prev, logLevel: level }));
  }, []);

  // Toggle API inspector
  const toggleApiInspector = useCallback(() => {
    setState((prev) => ({
      ...prev,
      apiInspector: {
        ...prev.apiInspector,
        enabled: !prev.apiInspector.enabled,
      },
    }));
  }, []);

  // Toggle feature flag
  const toggleFeatureFlag = useCallback((flagId) => {
    setState((prev) => ({
      ...prev,
      featureFlags: {
        ...prev.featureFlags,
        [flagId]: !prev.featureFlags[flagId],
      },
    }));
  }, []);

  // Toggle GraphRAG debug
  const toggleGraphRAGDebug = useCallback(() => {
    setState((prev) => ({ ...prev, graphRAGDebug: !prev.graphRAGDebug }));
  }, []);

  // Toggle agent trace viewer
  const toggleAgentTraceViewer = useCallback(() => {
    setState((prev) => ({ ...prev, agentTraceViewer: !prev.agentTraceViewer }));
  }, []);

  // Toggle mock data mode
  const toggleMockDataMode = useCallback(() => {
    setState((prev) => ({ ...prev, mockDataMode: !prev.mockDataMode }));
  }, []);

  // Set network throttling
  const setNetworkThrottling = useCallback((preset) => {
    setState((prev) => ({ ...prev, networkThrottling: preset }));
  }, []);

  // Record API request (for API Inspector)
  const recordApiRequest = useCallback((request) => {
    if (!state.apiInspector.enabled) return;

    setApiRequests((prev) => {
      const newRequests = [
        {
          id: Date.now(),
          timestamp: new Date().toISOString(),
          ...request,
        },
        ...prev,
      ].slice(0, state.apiInspector.maxRequests);
      return newRequests;
    });
  }, [state.apiInspector.enabled, state.apiInspector.maxRequests]);

  // Update performance metrics
  const updatePerformanceMetrics = useCallback((metrics) => {
    setPerformanceMetrics((prev) => ({
      ...prev,
      ...metrics,
    }));
  }, []);

  // Clear API requests
  const clearApiRequests = useCallback(() => {
    setApiRequests([]);
  }, []);

  // Get time remaining in session
  const getSessionTimeRemaining = useCallback(() => {
    if (!state.sessionExpiresAt) return null;
    const remaining = new Date(state.sessionExpiresAt) - new Date();
    return Math.max(0, Math.floor(remaining / 1000));
  }, [state.sessionExpiresAt]);

  // Console logging helper that respects log level
  const devLog = useCallback((level, ...args) => {
    if (!state.enabled) return;

    const levelOrder = [LOG_LEVELS.ERROR, LOG_LEVELS.WARN, LOG_LEVELS.INFO, LOG_LEVELS.DEBUG, LOG_LEVELS.VERBOSE];
    const currentLevelIndex = levelOrder.indexOf(state.logLevel);
    const messageLevelIndex = levelOrder.indexOf(level);

    if (messageLevelIndex <= currentLevelIndex) {
      const prefix = `[Aura Dev ${level.toUpperCase()}]`;
      switch (level) {
        case LOG_LEVELS.ERROR:
          console.error(prefix, ...args);
          break;
        case LOG_LEVELS.WARN:
          console.warn(prefix, ...args);
          break;
        case LOG_LEVELS.INFO:
          // eslint-disable-next-line no-console -- Intentional dev mode logging
          console.info(prefix, ...args);
          break;
        case LOG_LEVELS.DEBUG:
        case LOG_LEVELS.VERBOSE:
          // eslint-disable-next-line no-console -- Intentional dev mode logging
          console.log(prefix, ...args);
          break;
        default:
          // eslint-disable-next-line no-console -- Intentional dev mode logging
          console.log(prefix, ...args);
      }
    }
  }, [state.enabled, state.logLevel]);

  const value = {
    // State
    ...state,
    apiRequests,
    performanceMetrics,

    // Actions
    enableDevMode,
    disableDevMode,
    togglePerformanceBar,
    setLogLevel,
    toggleApiInspector,
    toggleFeatureFlag,
    toggleGraphRAGDebug,
    toggleAgentTraceViewer,
    toggleMockDataMode,
    setNetworkThrottling,
    recordApiRequest,
    updatePerformanceMetrics,
    clearApiRequests,
    getSessionTimeRemaining,
    devLog,

    // Constants
    LOG_LEVELS,
    NETWORK_PRESETS,
    SESSION_TIMEOUTS,
    FEATURE_FLAGS,
  };

  return (
    <DeveloperModeContext.Provider value={value}>
      {children}
    </DeveloperModeContext.Provider>
  );
}

export function useDeveloperMode() {
  const context = useContext(DeveloperModeContext);
  if (!context) {
    throw new Error('useDeveloperMode must be used within a DeveloperModeProvider');
  }
  return context;
}

// Hook for checking if a feature flag is enabled
export function useFeatureFlag(flagId) {
  const { enabled, featureFlags } = useDeveloperMode();
  return enabled && featureFlags[flagId];
}

// Hook for dev logging
export function useDevLog() {
  const { devLog } = useDeveloperMode();
  return devLog;
}

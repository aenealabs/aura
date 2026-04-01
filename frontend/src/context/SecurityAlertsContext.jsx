/**
 * Project Aura - Security Alerts Context Provider
 *
 * Provides global state management for security alerts with real-time updates,
 * filtering, and notification support.
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  listSecurityAlerts,
  getSecurityAlertDetail,
  acknowledgeAlert,
  resolveAlert,
  getUnacknowledgedCount,
  AlertPriority,
  AlertStatus,
} from '../services/securityAlertsApi';

// Create context
const SecurityAlertsContext = createContext(null);

// Polling interval for real-time updates (30 seconds)
const POLLING_INTERVAL = 30000;

// Local storage keys
const STORAGE_KEYS = {
  FILTERS: 'aura_security_alerts_filters',
  DISMISSED: 'aura_security_alerts_dismissed',
};

/**
 * Security Alerts Provider Component
 */
export function SecurityAlertsProvider({ children }) {
  // Alert list state
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Filter state
  const [filters, setFilters] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.FILTERS);
    return saved ? JSON.parse(saved) : {
      priority: null,
      status: null,
      assignedTo: null,
    };
  });

  // Statistics
  const [stats, setStats] = useState({
    total: 0,
    byPriority: {},
    byStatus: {},
    unacknowledged: 0,
  });

  // Unacknowledged count for badge
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0);

  // Polling ref
  const pollingRef = useRef(null);
  const isPollingEnabled = useRef(true);

  /**
   * Fetch alerts with current filters
   */
  const fetchAlerts = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);

    try {
      const response = await listSecurityAlerts({
        priority: filters.priority,
        status: filters.status,
        assignedTo: filters.assignedTo,
        limit: 100,
      });

      setAlerts(response.alerts || response.data || []);

      // Update stats if included in response
      if (response.stats) {
        setStats(response.stats);
      }
    } catch (err) {
      console.error('Failed to fetch security alerts:', err);

      // Use mock data in dev mode (don't show error)
      if (import.meta.env.DEV) {
        setAlerts(MOCK_ALERTS);
        setError(null);
      } else {
        setError(err.message || 'Failed to fetch alerts');
      }
    } finally {
      setLoading(false);
    }
  }, [filters]);

  /**
   * Fetch unacknowledged count
   */
  const fetchUnacknowledgedCount = useCallback(async () => {
    try {
      const response = await getUnacknowledgedCount();
      const count = response.total || response.count || 0;
      setUnacknowledgedCount(count);

      // Show browser notification for critical alerts
      if (count > 0 && response.p1_count > 0) {
        showNotification(`${response.p1_count} Critical Security Alert(s)`, {
          body: 'Immediate attention required',
          tag: 'security-alert-critical',
        });
      }
    } catch (err) {
      console.error('Failed to fetch unacknowledged count:', err);
      // Use mock count in dev mode
      if (import.meta.env.DEV) {
        setUnacknowledgedCount(3);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Fetch alert details
   */
  const fetchAlertDetail = useCallback(async (alertId) => {
    try {
      const detail = await getSecurityAlertDetail(alertId);
      setSelectedAlert(detail);
      return detail;
    } catch (err) {
      console.error('Failed to fetch alert detail:', err);

      // Find in existing alerts for dev mode (don't show error)
      if (import.meta.env.DEV) {
        const existing = alerts.find(a => a.alert_id === alertId);
        if (existing) {
          setSelectedAlert(existing);
          return existing;
        }
      }
      setError(err.message);
      return null;
    }
  }, [alerts]);

  /**
   * Acknowledge an alert
   */
  const handleAcknowledge = useCallback(async (alertId, userId, comment) => {
    try {
      const updated = await acknowledgeAlert(alertId, userId, comment);

      // Update local state
      setAlerts(prev => prev.map(a =>
        a.alert_id === alertId ? { ...a, status: AlertStatus.ACKNOWLEDGED } : a
      ));

      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(prev => ({ ...prev, status: AlertStatus.ACKNOWLEDGED }));
      }

      // Refresh counts
      fetchUnacknowledgedCount();

      return updated;
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
      throw err;
    }
  }, [selectedAlert, fetchUnacknowledgedCount]);

  /**
   * Resolve an alert
   */
  const handleResolve = useCallback(async (alertId, userId, resolution, actionsTaken) => {
    try {
      const updated = await resolveAlert(alertId, userId, resolution, actionsTaken);

      // Update local state
      setAlerts(prev => prev.map(a =>
        a.alert_id === alertId ? { ...a, status: AlertStatus.RESOLVED } : a
      ));

      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(prev => ({ ...prev, status: AlertStatus.RESOLVED }));
      }

      // Refresh counts
      fetchUnacknowledgedCount();

      return updated;
    } catch (err) {
      console.error('Failed to resolve alert:', err);
      throw err;
    }
  }, [selectedAlert, fetchUnacknowledgedCount]);

  /**
   * Update filters
   */
  const updateFilters = useCallback((newFilters) => {
    setFilters(prev => {
      const updated = { ...prev, ...newFilters };
      localStorage.setItem(STORAGE_KEYS.FILTERS, JSON.stringify(updated));
      return updated;
    });
  }, []);

  /**
   * Clear all filters
   */
  const clearFilters = useCallback(() => {
    const cleared = { priority: null, status: null, assignedTo: null };
    setFilters(cleared);
    localStorage.setItem(STORAGE_KEYS.FILTERS, JSON.stringify(cleared));
  }, []);

  /**
   * Show browser notification
   */
  const showNotification = useCallback((title, options = {}) => {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, {
        icon: '/favicon.ico',
        ...options,
      });
    }
  }, []);

  /**
   * Request notification permission
   */
  const requestNotificationPermission = useCallback(async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission();
    }
  }, []);

  /**
   * Start polling for updates
   */
  const startPolling = useCallback(() => {
    isPollingEnabled.current = true;

    const poll = async () => {
      if (!isPollingEnabled.current) return;

      await fetchAlerts(false);
      await fetchUnacknowledgedCount();

      if (isPollingEnabled.current) {
        pollingRef.current = setTimeout(poll, POLLING_INTERVAL);
      }
    };

    poll();
  }, [fetchAlerts, fetchUnacknowledgedCount]);

  /**
   * Stop polling
   */
  const stopPolling = useCallback(() => {
    isPollingEnabled.current = false;
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  /**
   * Refresh data manually
   */
  const refresh = useCallback(async () => {
    await Promise.all([
      fetchAlerts(true),
      fetchUnacknowledgedCount(),
    ]);
  }, [fetchAlerts, fetchUnacknowledgedCount]);

  // Initial fetch and start polling
  useEffect(() => {
    fetchAlerts();
    fetchUnacknowledgedCount();
    requestNotificationPermission();

    // Start polling
    startPolling();

    // Cleanup on unmount
    return () => {
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refetch when filters change
  useEffect(() => {
    fetchAlerts();
  }, [filters, fetchAlerts]);

  // Context value
  const value = {
    // State
    alerts,
    selectedAlert,
    loading,
    error,
    filters,
    stats,
    unacknowledgedCount,

    // Actions
    fetchAlerts,
    fetchAlertDetail,
    handleAcknowledge,
    handleResolve,
    updateFilters,
    clearFilters,
    setSelectedAlert,
    refresh,
    startPolling,
    stopPolling,

    // Constants
    AlertPriority,
    AlertStatus,
  };

  return (
    <SecurityAlertsContext.Provider value={value}>
      {children}
    </SecurityAlertsContext.Provider>
  );
}

/**
 * Hook to use security alerts context
 */
export function useSecurityAlerts() {
  const context = useContext(SecurityAlertsContext);
  if (!context) {
    throw new Error('useSecurityAlerts must be used within a SecurityAlertsProvider');
  }
  return context;
}

// Mock data for development
const MOCK_ALERTS = [
  {
    alert_id: 'alert-001',
    title: 'SQL Injection Attempt Detected',
    description: 'Malicious SQL pattern detected in user input on /api/v1/query endpoint',
    priority: 'P1_CRITICAL',
    status: 'NEW',
    event_type: 'security.injection.sql',
    severity: 'CRITICAL',
    source_ip: '192.168.1.105',
    user_id: 'user-12345',
    created_at: new Date(Date.now() - 300000).toISOString(),
    remediation_steps: [
      'Block source IP address',
      'Review query logs for data exfiltration',
      'Audit database for unauthorized changes',
    ],
  },
  {
    alert_id: 'alert-002',
    title: 'API Key Exposed in Code',
    description: 'AWS access key detected in committed code file',
    priority: 'P1_CRITICAL',
    status: 'ACKNOWLEDGED',
    event_type: 'security.secrets.exposure',
    severity: 'CRITICAL',
    source_ip: null,
    user_id: 'dev-user-001',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    acknowledged_at: new Date(Date.now() - 3000000).toISOString(),
    remediation_steps: [
      'Rotate exposed credentials immediately',
      'Revoke compromised API key',
      'Scan for unauthorized usage',
    ],
  },
  {
    alert_id: 'alert-003',
    title: 'Prompt Injection Attempt',
    description: 'LLM manipulation pattern detected in chat input',
    priority: 'P2_HIGH',
    status: 'INVESTIGATING',
    event_type: 'security.injection.prompt',
    severity: 'HIGH',
    source_ip: '10.0.1.50',
    user_id: 'user-67890',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    remediation_steps: [
      'Review conversation history',
      'Add input to blocklist patterns',
      'Monitor for follow-up attempts',
    ],
  },
  {
    alert_id: 'alert-004',
    title: 'Rate Limit Exceeded',
    description: 'API rate limit breached from single IP address',
    priority: 'P3_MEDIUM',
    status: 'RESOLVED',
    event_type: 'security.rate_limit',
    severity: 'MEDIUM',
    source_ip: '203.0.113.42',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    resolved_at: new Date(Date.now() - 82800000).toISOString(),
    resolution: 'IP temporarily blocked, legitimate traffic confirmed',
  },
];

export default SecurityAlertsContext;

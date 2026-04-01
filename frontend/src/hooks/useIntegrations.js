/**
 * Project Aura - useIntegrations Hook
 *
 * Custom hook for managing integration states, OAuth flows, and sync operations.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getIntegrations,
  getAvailableIntegrations,
  getIntegrationConfig,
  saveIntegrationConfig,
  updateIntegration,
  deleteIntegration,
  testConnection,
  syncNow,
  getIntegrationLogs,
  toggleIntegration,
  getOAuthUrl,
  completeOAuth,
  validateConfig,
  INTEGRATION_PROVIDERS,
} from '../services/integrationApi';

/**
 * Main hook for managing integrations
 */
export function useIntegrations(options = {}) {
  const {
    autoLoad = true,
    category = null,
    pollInterval = 30000, // 30 seconds for status polling
  } = options;

  const [integrations, setIntegrations] = useState([]);
  const [availableProviders, setAvailableProviders] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState({});

  const pollIntervalRef = useRef(null);
  const mountedRef = useRef(true);

  // Load integrations data
  const loadIntegrations = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      const [integrationsData, availableData] = await Promise.all([
        getIntegrations({ category }),
        getAvailableIntegrations(category),
      ]);

      if (mountedRef.current) {
        setIntegrations(integrationsData.integrations || []);
        setAvailableProviders(availableData.integrations || []);
        setCategories(availableData.categories || []);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to load integrations');
        // Fall back to local provider definitions
        setAvailableProviders(Object.values(INTEGRATION_PROVIDERS));
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [category]);

  // Initial load
  useEffect(() => {
    mountedRef.current = true;

    if (autoLoad) {
      loadIntegrations();
    }

    return () => {
      mountedRef.current = false;
    };
  }, [autoLoad, loadIntegrations]);

  // Status polling for connected integrations
  useEffect(() => {
    if (pollInterval && integrations.length > 0) {
      pollIntervalRef.current = setInterval(() => {
        // Only poll for connected integrations
        const connectedIntegrations = integrations.filter(
          (i) => i.status === 'connected' || i.status === 'syncing'
        );
        if (connectedIntegrations.length > 0) {
          loadIntegrations();
        }
      }, pollInterval);
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollInterval, integrations.length, loadIntegrations]);

  // Create new integration
  const createIntegration = useCallback(async (provider, config) => {
    const validation = validateConfig(provider, config);
    if (!validation.valid) {
      throw new Error(validation.errors.join(', '));
    }

    const result = await saveIntegrationConfig(provider, config);
    await loadIntegrations();
    return result;
  }, [loadIntegrations]);

  // Update existing integration
  const updateIntegrationConfig = useCallback(async (integrationId, updates) => {
    const result = await updateIntegration(integrationId, updates);
    setIntegrations((prev) =>
      prev.map((i) => (i.id === integrationId ? { ...i, ...result } : i))
    );
    return result;
  }, []);

  // Delete integration
  const removeIntegration = useCallback(async (integrationId) => {
    await deleteIntegration(integrationId);
    setIntegrations((prev) => prev.filter((i) => i.id !== integrationId));
  }, []);

  // Test connection
  const testIntegrationConnection = useCallback(async (provider, config = null) => {
    return await testConnection(provider, config);
  }, []);

  // Trigger sync
  const triggerSync = useCallback(async (provider) => {
    setSyncing((prev) => ({ ...prev, [provider]: true }));
    try {
      const result = await syncNow(provider);
      await loadIntegrations();
      return result;
    } finally {
      setSyncing((prev) => ({ ...prev, [provider]: false }));
    }
  }, [loadIntegrations]);

  // Toggle integration enabled/disabled
  const toggleIntegrationEnabled = useCallback(async (provider, enabled) => {
    const result = await toggleIntegration(provider, enabled);
    setIntegrations((prev) =>
      prev.map((i) => (i.provider === provider ? { ...i, enabled } : i))
    );
    return result;
  }, []);

  // Get integration by provider
  const getIntegration = useCallback((provider) => {
    return integrations.find((i) => i.provider === provider);
  }, [integrations]);

  // Check if provider is connected
  const isConnected = useCallback((provider) => {
    const integration = integrations.find((i) => i.provider === provider);
    return integration?.status === 'connected';
  }, [integrations]);

  return {
    integrations,
    availableProviders,
    categories,
    loading,
    error,
    syncing,
    refresh: loadIntegrations,
    createIntegration,
    updateIntegration: updateIntegrationConfig,
    deleteIntegration: removeIntegration,
    testConnection: testIntegrationConnection,
    triggerSync,
    toggleEnabled: toggleIntegrationEnabled,
    getIntegration,
    isConnected,
  };
}

/**
 * Hook for managing OAuth flows
 */
export function useOAuthFlow(provider) {
  const [authUrl, setAuthUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [completed, setCompleted] = useState(false);

  const initiateOAuth = useCallback(async (redirectUri) => {
    setLoading(true);
    setError(null);

    try {
      const result = await getOAuthUrl(provider, redirectUri);
      setAuthUrl(result.auth_url);

      // Store state for verification
      sessionStorage.setItem(`oauth_state_${provider}`, result.state);

      return result.auth_url;
    } catch (err) {
      setError(err.message || 'Failed to initiate OAuth');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [provider]);

  const completeOAuthFlow = useCallback(async (code, state) => {
    setLoading(true);
    setError(null);

    try {
      // Verify state matches
      const storedState = sessionStorage.getItem(`oauth_state_${provider}`);
      if (storedState !== state) {
        throw new Error('OAuth state mismatch - possible CSRF attack');
      }

      const result = await completeOAuth(provider, code, state);
      sessionStorage.removeItem(`oauth_state_${provider}`);
      setCompleted(true);

      return result;
    } catch (err) {
      setError(err.message || 'Failed to complete OAuth');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [provider]);

  const reset = useCallback(() => {
    setAuthUrl(null);
    setError(null);
    setCompleted(false);
    sessionStorage.removeItem(`oauth_state_${provider}`);
  }, [provider]);

  return {
    authUrl,
    loading,
    error,
    completed,
    initiateOAuth,
    completeOAuth: completeOAuthFlow,
    reset,
  };
}

/**
 * Hook for integration logs
 */
export function useIntegrationLogs(provider, options = {}) {
  const { limit = 50, autoLoad = true, pollInterval = 0 } = options;

  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);

  const pollIntervalRef = useRef(null);
  const mountedRef = useRef(true);

  const loadLogs = useCallback(async (reset = false) => {
    if (!provider || !mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const currentOffset = reset ? 0 : offset;
      const result = await getIntegrationLogs(provider, {
        limit,
        offset: currentOffset,
      });

      if (mountedRef.current) {
        if (reset) {
          setLogs(result.logs || []);
          setOffset(limit);
        } else {
          setLogs((prev) => [...prev, ...(result.logs || [])]);
          setOffset((prev) => prev + limit);
        }
        setHasMore(result.has_more || false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to load logs');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [provider, limit, offset]);

  useEffect(() => {
    mountedRef.current = true;

    if (autoLoad && provider) {
      loadLogs(true);
    }

    return () => {
      mountedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, autoLoad]);

  // Polling for new logs
  useEffect(() => {
    if (pollInterval > 0 && provider) {
      pollIntervalRef.current = setInterval(() => {
        loadLogs(true);
      }, pollInterval);
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollInterval, provider]);

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      loadLogs(false);
    }
  }, [loading, hasMore, loadLogs]);

  const refresh = useCallback(() => {
    setOffset(0);
    loadLogs(true);
  }, [loadLogs]);

  return {
    logs,
    loading,
    error,
    hasMore,
    loadMore,
    refresh,
  };
}

/**
 * Hook for integration configuration form
 */
export function useIntegrationConfig(provider) {
  const providerDef = INTEGRATION_PROVIDERS[provider];
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState(null);
  const [isDirty, setIsDirty] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});

  // Load existing config
  useEffect(() => {
    if (!provider) return;

    const loadConfig = async () => {
      setLoading(true);
      try {
        const data = await getIntegrationConfig(provider);
        setConfig(data.config || {});
        setError(null);
      } catch (err) {
        // New integration, start with empty config
        setConfig({});
      } finally {
        setLoading(false);
      }
    };

    loadConfig();
  }, [provider]);

  // Update field
  const updateField = useCallback((field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
    setIsDirty(true);
    setTestResult(null);

    // Clear validation error for this field
    setValidationErrors((prev) => {
      const { [field]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  // Validate config
  const validate = useCallback(() => {
    if (!providerDef) return false;

    const errors = {};
    for (const field of providerDef.configFields) {
      if (field.required && !config[field.name]) {
        errors[field.name] = `${field.label} is required`;
      }
      if (field.type === 'email' && config[field.name]) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(config[field.name])) {
          errors[field.name] = 'Invalid email address';
        }
      }
      if (field.type === 'url' && config[field.name]) {
        try {
          new URL(config[field.name]);
        } catch {
          errors[field.name] = 'Invalid URL';
        }
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [config, providerDef]);

  // Test connection
  const testConnectionHandler = useCallback(async () => {
    if (!validate()) return { success: false, message: 'Please fix validation errors' };

    setTesting(true);
    setTestResult(null);

    try {
      const result = await testConnection(provider, config);
      setTestResult(result);
      return result;
    } catch (err) {
      const result = { success: false, message: err.message || 'Connection test failed' };
      setTestResult(result);
      return result;
    } finally {
      setTesting(false);
    }
  }, [provider, config, validate]);

  // Save config
  const saveConfig = useCallback(async (additionalData = {}) => {
    if (!validate()) {
      throw new Error('Please fix validation errors before saving');
    }

    setSaving(true);
    setError(null);

    try {
      const result = await saveIntegrationConfig(provider, {
        ...config,
        ...additionalData,
      });
      setIsDirty(false);
      return result;
    } catch (err) {
      setError(err.message || 'Failed to save configuration');
      throw err;
    } finally {
      setSaving(false);
    }
  }, [provider, config, validate]);

  // Reset to saved state
  const reset = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getIntegrationConfig(provider);
      setConfig(data.config || {});
      setIsDirty(false);
      setValidationErrors({});
      setTestResult(null);
    } catch {
      setConfig({});
    } finally {
      setLoading(false);
    }
  }, [provider]);

  return {
    config,
    loading,
    saving,
    testing,
    testResult,
    error,
    isDirty,
    validationErrors,
    providerDef,
    updateField,
    validate,
    testConnection: testConnectionHandler,
    saveConfig,
    reset,
  };
}

export default useIntegrations;

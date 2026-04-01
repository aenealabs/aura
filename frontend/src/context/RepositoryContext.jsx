/**
 * Project Aura - Repository Context
 *
 * State management for repository onboarding wizard and repository operations.
 * Provides centralized state and actions for the repository onboarding flow.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import * as repositoryApi from '../services/repositoryApi';

// Repository Context
const RepositoryContext = createContext(null);

// Storage keys
const WIZARD_STATE_KEY = 'aura_wizard_state';
const OAUTH_STATE_KEY = 'aura_oauth_state';

// Wizard steps
export const WizardSteps = {
  CONNECT_PROVIDER: 1,
  SELECT_REPOSITORIES: 2,
  CONFIGURE_ANALYSIS: 3,
  REVIEW: 4,
  COMPLETION: 5,
};

// Repository Provider Component
export const RepositoryProvider = ({ children }) => {
  // ============================================================================
  // Repository List State
  // ============================================================================
  const [repositories, setRepositories] = useState([]);
  const [connections, setConnections] = useState([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);
  const [error, setError] = useState(null);

  // ============================================================================
  // Wizard State
  // ============================================================================
  const [wizardState, setWizardState] = useState({
    isOpen: false,
    currentStep: WizardSteps.CONNECT_PROVIDER,
    provider: null, // 'github', 'gitlab', 'manual'
    connection: null, // OAuth connection object
    availableRepos: [], // Repos from provider
    selectedRepos: [], // Selected repo IDs
    repoConfigs: {}, // Map of repoId -> config overrides
    ingestionJobs: [], // Active ingestion jobs
    isLoading: false,
    wizardError: null,
  });

  // Polling reference for ingestion status
  const pollingRef = useRef(null);

  // ============================================================================
  // Load Initial Data
  // ============================================================================
  useEffect(() => {
    loadRepositories();
    loadConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadRepositories = useCallback(async () => {
    setIsLoadingRepositories(true);
    setError(null);
    try {
      const repos = await repositoryApi.listRepositories();
      setRepositories(repos);
    } catch (err) {
      console.error('Failed to load repositories:', err);
      // Don't set error for 404 (no repositories yet)
      if (err.status !== 404) {
        setError(err.message);
      }
    } finally {
      setIsLoadingRepositories(false);
    }
  }, []);

  const loadConnections = useCallback(async () => {
    setIsLoadingConnections(true);
    try {
      const conns = await repositoryApi.listOAuthConnections();
      setConnections(conns);
    } catch (err) {
      console.error('Failed to load connections:', err);
      // Don't set error for 404 (no connections yet)
    } finally {
      setIsLoadingConnections(false);
    }
  }, []);

  // ============================================================================
  // Wizard Actions
  // ============================================================================

  const openWizard = useCallback((initialProvider = null) => {
    setWizardState((prev) => ({
      ...prev,
      isOpen: true,
      currentStep: WizardSteps.CONNECT_PROVIDER,
      provider: initialProvider,
      connection: null,
      availableRepos: [],
      selectedRepos: [],
      repoConfigs: {},
      ingestionJobs: [],
      isLoading: false,
      wizardError: null,
    }));
  }, []);

  const closeWizard = useCallback(() => {
    // Stop any polling
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    setWizardState((prev) => ({
      ...prev,
      isOpen: false,
    }));
  }, []);

  const resetWizard = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    setWizardState({
      isOpen: false,
      currentStep: WizardSteps.CONNECT_PROVIDER,
      provider: null,
      connection: null,
      availableRepos: [],
      selectedRepos: [],
      repoConfigs: {},
      ingestionJobs: [],
      isLoading: false,
      wizardError: null,
    });

    // Clear session storage
    sessionStorage.removeItem(OAUTH_STATE_KEY);
    sessionStorage.removeItem(WIZARD_STATE_KEY);
  }, []);

  const setStep = useCallback((step) => {
    setWizardState((prev) => ({
      ...prev,
      currentStep: step,
      wizardError: null,
    }));
  }, []);

  const nextStep = useCallback(() => {
    setWizardState((prev) => ({
      ...prev,
      currentStep: Math.min(prev.currentStep + 1, WizardSteps.COMPLETION),
      wizardError: null,
    }));
  }, []);

  const prevStep = useCallback(() => {
    setWizardState((prev) => ({
      ...prev,
      currentStep: Math.max(prev.currentStep - 1, WizardSteps.CONNECT_PROVIDER),
      wizardError: null,
    }));
  }, []);

  // ============================================================================
  // Provider Connection
  // ============================================================================

  const selectProvider = useCallback((provider) => {
    setWizardState((prev) => ({
      ...prev,
      provider,
      wizardError: null,
    }));
  }, []);

  const initiateOAuth = useCallback(async (provider) => {
    setWizardState((prev) => ({ ...prev, isLoading: true, wizardError: null }));

    try {
      const result = await repositoryApi.initiateOAuth(provider);

      // Store state in session for callback validation
      sessionStorage.setItem(OAUTH_STATE_KEY, result.state);

      // Store wizard state to restore after callback
      sessionStorage.setItem(WIZARD_STATE_KEY, JSON.stringify({
        provider,
        step: WizardSteps.CONNECT_PROVIDER,
      }));

      // Redirect to OAuth provider
      window.location.href = result.authorization_url;
    } catch (err) {
      console.error('OAuth initiation failed:', err);
      setWizardState((prev) => ({
        ...prev,
        isLoading: false,
        wizardError: `Failed to connect to ${provider}: ${err.message}`,
      }));
    }
  }, []);

  const handleOAuthCallback = useCallback(async (provider, code, state) => {
    // Validate state
    const storedState = sessionStorage.getItem(OAUTH_STATE_KEY);
    if (storedState && storedState !== state) {
      setWizardState((prev) => ({
        ...prev,
        wizardError: 'OAuth state mismatch. Please try again.',
      }));
      return null;
    }

    setWizardState((prev) => ({ ...prev, isLoading: true, wizardError: null }));

    try {
      const result = await repositoryApi.completeOAuth(provider, code, state);

      // Clear stored state
      sessionStorage.removeItem(OAUTH_STATE_KEY);
      sessionStorage.removeItem(WIZARD_STATE_KEY);

      // Refresh connections list
      await loadConnections();

      // Find the new connection
      const newConnection = connections.find((c) => c.connection_id === result.connection_id) || {
        connection_id: result.connection_id,
        provider: result.provider,
        provider_username: result.provider_username,
        status: 'connected',
      };

      setWizardState((prev) => ({
        ...prev,
        isOpen: true,
        provider: result.provider,
        connection: newConnection,
        currentStep: WizardSteps.SELECT_REPOSITORIES,
        isLoading: false,
      }));

      return result;
    } catch (err) {
      console.error('OAuth callback failed:', err);
      setWizardState((prev) => ({
        ...prev,
        isLoading: false,
        wizardError: `Failed to complete OAuth: ${err.message}`,
      }));
      return null;
    }
  }, [loadConnections, connections]);

  const setConnection = useCallback((connection) => {
    setWizardState((prev) => ({
      ...prev,
      connection,
      wizardError: null,
    }));
  }, []);

  // ============================================================================
  // Repository Selection
  // ============================================================================

  const loadAvailableRepos = useCallback(async (connectionId) => {
    setWizardState((prev) => ({ ...prev, isLoading: true, wizardError: null }));

    try {
      const result = await repositoryApi.listAvailableRepositories(connectionId);
      setWizardState((prev) => ({
        ...prev,
        availableRepos: result.repositories || [],
        isLoading: false,
      }));
    } catch (err) {
      console.error('Failed to load available repos:', err);
      setWizardState((prev) => ({
        ...prev,
        isLoading: false,
        wizardError: `Failed to load repositories: ${err.message}`,
      }));
    }
  }, []);

  const toggleRepoSelection = useCallback((repoId) => {
    setWizardState((prev) => {
      const isSelected = prev.selectedRepos.includes(repoId);
      const selectedRepos = isSelected
        ? prev.selectedRepos.filter((id) => id !== repoId)
        : [...prev.selectedRepos, repoId];

      // Initialize default config if newly selected
      let repoConfigs = prev.repoConfigs;
      if (!isSelected && !prev.repoConfigs[repoId]) {
        const repo = prev.availableRepos.find((r) => r.id === repoId);
        repoConfigs = {
          ...prev.repoConfigs,
          [repoId]: {
            ...repositoryApi.DEFAULT_REPOSITORY_CONFIG,
            branch: repo?.default_branch || 'main',
            name: repo?.name || '',
          },
        };
      }

      return {
        ...prev,
        selectedRepos,
        repoConfigs,
        wizardError: null,
      };
    });
  }, []);

  const selectAllRepos = useCallback(() => {
    setWizardState((prev) => {
      const allIds = prev.availableRepos
        .filter((r) => !r.already_connected)
        .map((r) => r.id);

      const repoConfigs = { ...prev.repoConfigs };
      allIds.forEach((id) => {
        if (!repoConfigs[id]) {
          const repo = prev.availableRepos.find((r) => r.id === id);
          repoConfigs[id] = {
            ...repositoryApi.DEFAULT_REPOSITORY_CONFIG,
            branch: repo?.default_branch || 'main',
            name: repo?.name || '',
          };
        }
      });

      return {
        ...prev,
        selectedRepos: allIds,
        repoConfigs,
      };
    });
  }, []);

  const clearSelection = useCallback(() => {
    setWizardState((prev) => ({
      ...prev,
      selectedRepos: [],
    }));
  }, []);

  // ============================================================================
  // Repository Configuration
  // ============================================================================

  const updateRepoConfig = useCallback((repoId, config) => {
    setWizardState((prev) => ({
      ...prev,
      repoConfigs: {
        ...prev.repoConfigs,
        [repoId]: {
          ...prev.repoConfigs[repoId],
          ...config,
        },
      },
    }));
  }, []);

  const applyConfigToAll = useCallback((config) => {
    setWizardState((prev) => {
      const repoConfigs = { ...prev.repoConfigs };
      prev.selectedRepos.forEach((repoId) => {
        repoConfigs[repoId] = {
          ...repoConfigs[repoId],
          ...config,
        };
      });
      return { ...prev, repoConfigs };
    });
  }, []);

  // ============================================================================
  // Ingestion
  // ============================================================================

  const startIngestion = useCallback(async () => {
    setWizardState((prev) => ({ ...prev, isLoading: true, wizardError: null }));

    try {
      // Build repository configs for ingestion
      const configs = wizardState.selectedRepos.map((repoId) => {
        const repo = wizardState.availableRepos.find((r) => r.id === repoId);
        const config = wizardState.repoConfigs[repoId] || repositoryApi.DEFAULT_REPOSITORY_CONFIG;

        return {
          connectionId: wizardState.connection?.connection_id,
          providerRepoId: repoId,
          cloneUrl: repo?.clone_url,
          name: repo?.name || config.name,
          branch: config.branch,
          languages: config.languages,
          scanFrequency: config.scanFrequency,
          excludePatterns: config.excludePatterns,
          enableWebhook: config.enableWebhook,
        };
      });

      const result = await repositoryApi.startIngestion(configs);

      setWizardState((prev) => ({
        ...prev,
        ingestionJobs: result.jobs || [],
        currentStep: WizardSteps.COMPLETION,
        isLoading: false,
      }));

      // Start polling for status updates
      startStatusPolling(result.jobs.map((j) => j.job_id));

      return result;
    } catch (err) {
      console.error('Failed to start ingestion:', err);
      setWizardState((prev) => ({
        ...prev,
        isLoading: false,
        wizardError: `Failed to start ingestion: ${err.message}`,
      }));
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wizardState.selectedRepos, wizardState.availableRepos, wizardState.repoConfigs, wizardState.connection]);

  const startStatusPolling = useCallback((jobIds) => {
    // Clear any existing polling
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    const poll = async () => {
      try {
        const statuses = await repositoryApi.getIngestionStatus(jobIds);

        setWizardState((prev) => ({
          ...prev,
          ingestionJobs: statuses,
        }));

        // Stop polling if all jobs are complete
        const allComplete = statuses.every(
          (s) => s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled'
        );

        if (allComplete) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;

          // Refresh repositories list
          loadRepositories();
        }
      } catch (err) {
        console.error('Failed to poll ingestion status:', err);
      }
    };

    // Poll every 2 seconds
    pollingRef.current = setInterval(poll, 2000);

    // Initial poll
    poll();
  }, [loadRepositories]);

  const cancelIngestionJob = useCallback(async (jobId) => {
    try {
      await repositoryApi.cancelIngestion(jobId);

      // Update local state
      setWizardState((prev) => ({
        ...prev,
        ingestionJobs: prev.ingestionJobs.map((job) =>
          job.job_id === jobId ? { ...job, status: 'cancelled' } : job
        ),
      }));
    } catch (err) {
      console.error('Failed to cancel ingestion:', err);
    }
  }, []);

  // ============================================================================
  // Repository Management Actions
  // ============================================================================

  const deleteRepositoryAction = useCallback(async (repositoryId, deleteData = true) => {
    try {
      await repositoryApi.deleteRepository(repositoryId, deleteData);
      setRepositories((prev) => prev.filter((r) => r.repository_id !== repositoryId));
      return true;
    } catch (err) {
      console.error('Failed to delete repository:', err);
      setError(`Failed to delete repository: ${err.message}`);
      return false;
    }
  }, []);

  const triggerSyncAction = useCallback(async (repositoryId) => {
    try {
      const result = await repositoryApi.triggerSync(repositoryId);

      // Update repository status
      setRepositories((prev) =>
        prev.map((r) =>
          r.repository_id === repositoryId ? { ...r, status: 'syncing' } : r
        )
      );

      return result;
    } catch (err) {
      console.error('Failed to trigger sync:', err);
      setError(`Failed to trigger sync: ${err.message}`);
      return null;
    }
  }, []);

  const revokeConnectionAction = useCallback(async (connectionId) => {
    try {
      await repositoryApi.revokeOAuthConnection(connectionId);
      setConnections((prev) => prev.filter((c) => c.connection_id !== connectionId));
      return true;
    } catch (err) {
      console.error('Failed to revoke connection:', err);
      setError(`Failed to revoke connection: ${err.message}`);
      return false;
    }
  }, []);

  // ============================================================================
  // Context Value
  // ============================================================================

  const value = {
    // Repository list state
    repositories,
    connections,
    isLoadingRepositories,
    isLoadingConnections,
    error,
    loadRepositories,
    loadConnections,

    // Wizard state
    wizardState,
    isWizardOpen: wizardState.isOpen,
    currentStep: wizardState.currentStep,
    provider: wizardState.provider,
    connection: wizardState.connection,
    availableRepos: wizardState.availableRepos,
    selectedRepos: wizardState.selectedRepos,
    repoConfigs: wizardState.repoConfigs,
    ingestionJobs: wizardState.ingestionJobs,
    isWizardLoading: wizardState.isLoading,
    wizardError: wizardState.wizardError,

    // Wizard actions
    openWizard,
    closeWizard,
    resetWizard,
    setStep,
    nextStep,
    prevStep,

    // Provider actions
    selectProvider,
    initiateOAuth,
    handleOAuthCallback,
    setConnection,

    // Repository selection
    loadAvailableRepos,
    toggleRepoSelection,
    selectAllRepos,
    clearSelection,

    // Configuration
    updateRepoConfig,
    applyConfigToAll,

    // Ingestion
    startIngestion,
    cancelIngestionJob,

    // Repository management
    deleteRepository: deleteRepositoryAction,
    triggerSync: triggerSyncAction,
    revokeConnection: revokeConnectionAction,

    // Constants
    WizardSteps,
  };

  return <RepositoryContext.Provider value={value}>{children}</RepositoryContext.Provider>;
};

// Custom hook to use repository context
export const useRepositories = () => {
  const context = useContext(RepositoryContext);
  if (!context) {
    throw new Error('useRepositories must be used within a RepositoryProvider');
  }
  return context;
};

export default RepositoryContext;

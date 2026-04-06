/**
 * Aura TypeScript SDK - React Hooks
 *
 * React hooks for integrating Aura functionality into React applications.
 *
 * @example
 * ```tsx
 * import { AuraProvider, useApprovals, useVulnerabilities } from '@aenealabs/aura-sdk/react';
 *
 * function App() {
 *   return (
 *     <AuraProvider baseUrl="https://api.aura.example.com" apiKey="...">
 *       <Dashboard />
 *     </AuraProvider>
 *   );
 * }
 *
 * function Dashboard() {
 *   const { approvals, stats, loading } = useApprovals();
 *   const { findings, scanFile } = useVulnerabilities();
 *   // ...
 * }
 * ```
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';

import { AuraClient, type AuraClientConfig } from '../client/AuraClient';
import type {
  Finding,
  FindingsListResponse,
  ScanRequest,
  ScanResponse,
  Patch,
  PatchRequest,
  PatchResponse,
  ApprovalSummary,
  ApprovalDetail,
  ApprovalListResponse,
  ApprovalStats,
  ApprovalActionResponse,
  IncidentSummary,
  IncidentDetail,
  IncidentListResponse,
  PlatformSettings,
  HITLSettings,
  MCPSettings,
  Severity,
  ApprovalStatus,
  FindingsFilterParams,
  ApprovalsFilterParams,
  IncidentsFilterParams,
} from '../types';

// ============================================================================
// Context
// ============================================================================

/**
 * Context value for the Aura provider
 */
interface AuraContextValue {
  client: AuraClient;
  isConnected: boolean;
}

const AuraContext = createContext<AuraContextValue | null>(null);

/**
 * Props for the AuraProvider component
 */
export interface AuraProviderProps extends AuraClientConfig {
  children: ReactNode;
}

/**
 * Provider component for Aura SDK
 *
 * @example
 * ```tsx
 * <AuraProvider baseUrl="https://api.aura.example.com" apiKey="...">
 *   <App />
 * </AuraProvider>
 * ```
 */
export function AuraProvider({ children, ...config }: AuraProviderProps) {
  const [isConnected, setIsConnected] = useState(false);
  const clientRef = useRef<AuraClient | null>(null);

  // Create client only once
  if (!clientRef.current) {
    clientRef.current = new AuraClient(config);
  }

  const client = clientRef.current;

  // Check connection on mount
  useEffect(() => {
    client.healthCheck().then(setIsConnected);
  }, [client]);

  const value = useMemo(
    () => ({ client, isConnected }),
    [client, isConnected]
  );

  return (
    <AuraContext.Provider value={value}>
      {children}
    </AuraContext.Provider>
  );
}

/**
 * Hook to access the Aura client
 */
export function useAuraClient(): AuraClient {
  const context = useContext(AuraContext);
  if (!context) {
    throw new Error('useAuraClient must be used within an AuraProvider');
  }
  return context.client;
}

/**
 * Hook to check connection status
 */
export function useAuraConnection(): boolean {
  const context = useContext(AuraContext);
  return context?.isConnected ?? false;
}

// ============================================================================
// Generic Async State Hook
// ============================================================================

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

function useAsyncState<T>(initialData: T | null = null): [
  AsyncState<T>,
  {
    setData: (data: T) => void;
    setLoading: (loading: boolean) => void;
    setError: (error: Error | null) => void;
    reset: () => void;
  }
] {
  const [state, setState] = useState<AsyncState<T>>({
    data: initialData,
    loading: false,
    error: null,
  });

  const setData = useCallback((data: T) => {
    setState({ data, loading: false, error: null });
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, loading }));
  }, []);

  const setError = useCallback((error: Error | null) => {
    setState(prev => ({ ...prev, loading: false, error }));
  }, []);

  const reset = useCallback(() => {
    setState({ data: initialData, loading: false, error: null });
  }, [initialData]);

  return [state, { setData, setLoading, setError, reset }];
}

// ============================================================================
// Vulnerabilities Hooks
// ============================================================================

/**
 * Return type for useVulnerabilities hook
 */
export interface UseVulnerabilitiesResult {
  findings: Finding[];
  total: number;
  loading: boolean;
  error: Error | null;
  scanFile: (request: ScanRequest) => Promise<ScanResponse>;
  refresh: () => Promise<void>;
  filter: (params: FindingsFilterParams) => void;
  currentFilters: FindingsFilterParams;
}

/**
 * Hook for managing vulnerability findings
 *
 * @example
 * ```tsx
 * function VulnerabilityList() {
 *   const { findings, loading, scanFile, filter } = useVulnerabilities();
 *
 *   return (
 *     <div>
 *       {loading && <Spinner />}
 *       {findings.map(f => (
 *         <VulnerabilityCard key={f.id} finding={f} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useVulnerabilities(
  initialFilters?: FindingsFilterParams
): UseVulnerabilitiesResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<FindingsListResponse>(null);
  const [filters, setFilters] = useState<FindingsFilterParams>(
    initialFilters ?? {}
  );

  const fetchFindings = useCallback(async () => {
    actions.setLoading(true);
    try {
      const response = await client.extension.listFindings(filters);
      actions.setData(response);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, filters, actions]);

  useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  const scanFile = useCallback(
    async (request: ScanRequest): Promise<ScanResponse> => {
      const response = await client.extension.scanFile(request);
      // Refresh findings after scan
      await fetchFindings();
      return response;
    },
    [client, fetchFindings]
  );

  const filter = useCallback((params: FindingsFilterParams) => {
    setFilters(prev => ({ ...prev, ...params }));
  }, []);

  return {
    findings: state.data?.findings ?? [],
    total: state.data?.total ?? 0,
    loading: state.loading,
    error: state.error,
    scanFile,
    refresh: fetchFindings,
    filter,
    currentFilters: filters,
  };
}

/**
 * Return type for useFinding hook
 */
export interface UseFindingResult {
  finding: Finding | null;
  loading: boolean;
  error: Error | null;
  generatePatch: () => Promise<PatchResponse>;
}

/**
 * Hook for a single finding with patch generation
 */
export function useFinding(findingId: string, filePath: string): UseFindingResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<Finding>(null);

  useEffect(() => {
    const fetchFinding = async () => {
      actions.setLoading(true);
      try {
        const response = await client.extension.getFindings(filePath);
        const finding = response.findings.find(f => f.id === findingId);
        if (finding) {
          actions.setData(finding);
        } else {
          actions.setError(new Error(`Finding ${findingId} not found`));
        }
      } catch (error) {
        actions.setError(error instanceof Error ? error : new Error(String(error)));
      }
    };

    fetchFinding();
  }, [client, findingId, filePath, actions]);

  const generatePatch = useCallback(async (): Promise<PatchResponse> => {
    if (!state.data) {
      throw new Error('No finding loaded');
    }

    return client.extension.generatePatch({
      finding_id: findingId,
      file_path: filePath,
      file_content: '', // Would need to be provided by the caller
      context_lines: 10,
    });
  }, [client, findingId, filePath, state.data]);

  return {
    finding: state.data,
    loading: state.loading,
    error: state.error,
    generatePatch,
  };
}

// ============================================================================
// Patches Hooks
// ============================================================================

/**
 * Return type for usePatch hook
 */
export interface UsePatchResult {
  patch: Patch | null;
  loading: boolean;
  error: Error | null;
  apply: () => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * Hook for managing a single patch
 */
export function usePatch(patchId: string): UsePatchResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<Patch>(null);

  const fetchPatch = useCallback(async () => {
    actions.setLoading(true);
    try {
      const patch = await client.extension.getPatch(patchId);
      actions.setData(patch);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, patchId, actions]);

  useEffect(() => {
    fetchPatch();
  }, [fetchPatch]);

  const apply = useCallback(async () => {
    await client.extension.applyPatch(patchId, true);
    await fetchPatch();
  }, [client, patchId, fetchPatch]);

  return {
    patch: state.data,
    loading: state.loading,
    error: state.error,
    apply,
    refresh: fetchPatch,
  };
}

// ============================================================================
// Approvals Hooks
// ============================================================================

/**
 * Return type for useApprovals hook
 */
export interface UseApprovalsResult {
  approvals: ApprovalSummary[];
  total: number;
  hasMore: boolean;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  loadMore: () => Promise<void>;
  filter: (params: ApprovalsFilterParams) => void;
  currentFilters: ApprovalsFilterParams;
}

/**
 * Hook for managing approval requests
 *
 * @example
 * ```tsx
 * function ApprovalList() {
 *   const { approvals, loading, filter } = useApprovals({ status: 'pending' });
 *
 *   return (
 *     <div>
 *       <FilterBar onFilter={filter} />
 *       {approvals.map(a => (
 *         <ApprovalCard key={a.id} approval={a} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useApprovals(
  initialFilters?: ApprovalsFilterParams
): UseApprovalsResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<ApprovalListResponse>(null);
  const [filters, setFilters] = useState<ApprovalsFilterParams>(
    initialFilters ?? { page: 1, page_size: 20 }
  );

  const fetchApprovals = useCallback(async () => {
    actions.setLoading(true);
    try {
      const response = await client.approvals.list(filters);
      actions.setData(response);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, filters, actions]);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const loadMore = useCallback(async () => {
    if (!state.data?.has_more) return;

    const nextPage = (filters.page ?? 1) + 1;
    try {
      const response = await client.approvals.list({ ...filters, page: nextPage });
      actions.setData({
        ...response,
        approvals: [...(state.data?.approvals ?? []), ...response.approvals],
      });
      setFilters(prev => ({ ...prev, page: nextPage }));
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, filters, state.data, actions]);

  const filter = useCallback((params: ApprovalsFilterParams) => {
    setFilters({ ...params, page: 1, page_size: filters.page_size ?? 20 });
  }, [filters.page_size]);

  return {
    approvals: state.data?.approvals ?? [],
    total: state.data?.total ?? 0,
    hasMore: state.data?.has_more ?? false,
    loading: state.loading,
    error: state.error,
    refresh: fetchApprovals,
    loadMore,
    filter,
    currentFilters: filters,
  };
}

/**
 * Return type for useApproval hook
 */
export interface UseApprovalResult {
  approval: ApprovalDetail | null;
  loading: boolean;
  error: Error | null;
  approve: (comments?: string) => Promise<ApprovalActionResponse>;
  reject: (reason: string) => Promise<ApprovalActionResponse>;
  cancel: (reason?: string) => Promise<ApprovalActionResponse>;
  refresh: () => Promise<void>;
}

/**
 * Hook for managing a single approval
 */
export function useApproval(approvalId: string): UseApprovalResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<ApprovalDetail>(null);

  const fetchApproval = useCallback(async () => {
    actions.setLoading(true);
    try {
      const approval = await client.approvals.get(approvalId);
      actions.setData(approval);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, approvalId, actions]);

  useEffect(() => {
    fetchApproval();
  }, [fetchApproval]);

  const approve = useCallback(
    async (comments?: string): Promise<ApprovalActionResponse> => {
      const response = await client.approvals.approve(approvalId, comments);
      await fetchApproval();
      return response;
    },
    [client, approvalId, fetchApproval]
  );

  const reject = useCallback(
    async (reason: string): Promise<ApprovalActionResponse> => {
      const response = await client.approvals.reject(approvalId, reason);
      await fetchApproval();
      return response;
    },
    [client, approvalId, fetchApproval]
  );

  const cancel = useCallback(
    async (reason?: string): Promise<ApprovalActionResponse> => {
      const response = await client.approvals.cancel(approvalId, reason);
      await fetchApproval();
      return response;
    },
    [client, approvalId, fetchApproval]
  );

  return {
    approval: state.data,
    loading: state.loading,
    error: state.error,
    approve,
    reject,
    cancel,
    refresh: fetchApproval,
  };
}

/**
 * Return type for useApprovalStats hook
 */
export interface UseApprovalStatsResult {
  stats: ApprovalStats | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for approval statistics
 */
export function useApprovalStats(): UseApprovalStatsResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<ApprovalStats>(null);

  const fetchStats = useCallback(async () => {
    actions.setLoading(true);
    try {
      const stats = await client.approvals.getStats();
      actions.setData(stats);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, actions]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats: state.data,
    loading: state.loading,
    error: state.error,
    refresh: fetchStats,
  };
}

// ============================================================================
// Incidents Hooks
// ============================================================================

/**
 * Return type for useIncidents hook
 */
export interface UseIncidentsResult {
  incidents: IncidentSummary[];
  total: number;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  filter: (params: IncidentsFilterParams) => void;
  currentFilters: IncidentsFilterParams;
}

/**
 * Hook for managing incidents
 */
export function useIncidents(
  initialFilters?: IncidentsFilterParams
): UseIncidentsResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<IncidentListResponse>(null);
  const [filters, setFilters] = useState<IncidentsFilterParams>(
    initialFilters ?? {}
  );

  const fetchIncidents = useCallback(async () => {
    actions.setLoading(true);
    try {
      const response = await client.incidents.list(filters);
      actions.setData(response);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, filters, actions]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  const filter = useCallback((params: IncidentsFilterParams) => {
    setFilters(prev => ({ ...prev, ...params }));
  }, []);

  return {
    incidents: state.data?.incidents ?? [],
    total: state.data?.total ?? 0,
    loading: state.loading,
    error: state.error,
    refresh: fetchIncidents,
    filter,
    currentFilters: filters,
  };
}

/**
 * Return type for useIncident hook
 */
export interface UseIncidentResult {
  incident: IncidentDetail | null;
  loading: boolean;
  error: Error | null;
  acknowledge: () => Promise<void>;
  resolve: (rootCause: string, remediation: string[]) => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * Hook for managing a single incident
 */
export function useIncident(incidentId: string): UseIncidentResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<IncidentDetail>(null);

  const fetchIncident = useCallback(async () => {
    actions.setLoading(true);
    try {
      const incident = await client.incidents.get(incidentId);
      actions.setData(incident);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, incidentId, actions]);

  useEffect(() => {
    fetchIncident();
  }, [fetchIncident]);

  const acknowledge = useCallback(async () => {
    await client.incidents.acknowledge(incidentId);
    await fetchIncident();
  }, [client, incidentId, fetchIncident]);

  const resolve = useCallback(
    async (rootCause: string, remediation: string[]) => {
      await client.incidents.resolve(incidentId, rootCause, remediation);
      await fetchIncident();
    },
    [client, incidentId, fetchIncident]
  );

  return {
    incident: state.data,
    loading: state.loading,
    error: state.error,
    acknowledge,
    resolve,
    refresh: fetchIncident,
  };
}

// ============================================================================
// Settings Hooks
// ============================================================================

/**
 * Return type for useSettings hook
 */
export interface UseSettingsResult {
  settings: PlatformSettings | null;
  loading: boolean;
  error: Error | null;
  update: (settings: Partial<PlatformSettings>) => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * Hook for managing platform settings
 */
export function useSettings(): UseSettingsResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<PlatformSettings>(null);

  const fetchSettings = useCallback(async () => {
    actions.setLoading(true);
    try {
      const settings = await client.settings.get();
      actions.setData(settings);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, actions]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const update = useCallback(
    async (settings: Partial<PlatformSettings>) => {
      const updated = await client.settings.update(settings);
      actions.setData(updated);
    },
    [client, actions]
  );

  return {
    settings: state.data,
    loading: state.loading,
    error: state.error,
    update,
    refresh: fetchSettings,
  };
}

/**
 * Return type for useHITLSettings hook
 */
export interface UseHITLSettingsResult {
  settings: HITLSettings | null;
  loading: boolean;
  error: Error | null;
  update: (settings: Partial<HITLSettings>) => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * Hook for managing HITL settings
 */
export function useHITLSettings(): UseHITLSettingsResult {
  const client = useAuraClient();
  const [state, actions] = useAsyncState<HITLSettings>(null);

  const fetchSettings = useCallback(async () => {
    actions.setLoading(true);
    try {
      const settings = await client.settings.getHITLSettings();
      actions.setData(settings);
    } catch (error) {
      actions.setError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [client, actions]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const update = useCallback(
    async (settings: Partial<HITLSettings>) => {
      const updated = await client.settings.updateHITLSettings(settings);
      actions.setData(updated);
    },
    [client, actions]
  );

  return {
    settings: state.data,
    loading: state.loading,
    error: state.error,
    update,
    refresh: fetchSettings,
  };
}

// ============================================================================
// Utility Hooks
// ============================================================================

/**
 * Hook for polling approval status
 */
export function useApprovalPolling(
  approvalId: string | null,
  intervalMs: number = 5000
): ApprovalDetail | null {
  const client = useAuraClient();
  const [approval, setApproval] = useState<ApprovalDetail | null>(null);

  useEffect(() => {
    if (!approvalId) return;

    const poll = async () => {
      try {
        const data = await client.approvals.get(approvalId);
        setApproval(data);
      } catch {
        // Ignore errors during polling
      }
    };

    // Initial fetch
    poll();

    // Set up polling interval
    const intervalId = setInterval(poll, intervalMs);

    return () => clearInterval(intervalId);
  }, [client, approvalId, intervalMs]);

  return approval;
}

/**
 * Hook for real-time vulnerability count
 */
export function useVulnerabilityCount(severity?: Severity): number {
  const { total } = useVulnerabilities(severity ? { severity } : undefined);
  return total;
}

/**
 * Hook for pending approval count
 */
export function usePendingApprovalCount(): number {
  const { total } = useApprovals({ status: 'pending' as ApprovalStatus });
  return total;
}

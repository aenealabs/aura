/**
 * Aura TypeScript SDK - React Integration
 *
 * React hooks and components for integrating Aura into React applications.
 *
 * @packageDocumentation
 * @module @aenealabs/aura-sdk/react
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
 *   const { approvals, stats, approve, reject } = useApprovals({ status: 'pending' });
 *   const { findings, scanFile } = useVulnerabilities();
 *
 *   return (
 *     <div>
 *       <h2>Pending Approvals: {approvals.length}</h2>
 *       <h2>Vulnerabilities: {findings.length}</h2>
 *     </div>
 *   );
 * }
 * ```
 */

// Re-export everything from hooks
export {
  // Provider
  AuraProvider,
  type AuraProviderProps,

  // Core hooks
  useAuraClient,
  useAuraConnection,

  // Vulnerability hooks
  useVulnerabilities,
  useFinding,
  type UseVulnerabilitiesResult,
  type UseFindingResult,

  // Patch hooks
  usePatch,
  type UsePatchResult,

  // Approval hooks
  useApprovals,
  useApproval,
  useApprovalStats,
  type UseApprovalsResult,
  type UseApprovalResult,
  type UseApprovalStatsResult,

  // Incident hooks
  useIncidents,
  useIncident,
  type UseIncidentsResult,
  type UseIncidentResult,

  // Settings hooks
  useSettings,
  useHITLSettings,
  type UseSettingsResult,
  type UseHITLSettingsResult,

  // Utility hooks
  useApprovalPolling,
  useVulnerabilityCount,
  usePendingApprovalCount,
} from './hooks';

// Also export types for convenience
export * from './types';

// Export utilities
export * from './utils';

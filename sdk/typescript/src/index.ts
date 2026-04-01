/**
 * Aura TypeScript SDK
 *
 * TypeScript/JavaScript SDK for integrating with the Aura Code Intelligence Platform.
 *
 * @packageDocumentation
 * @module @aenealabs/aura-sdk
 *
 * @example
 * Basic usage:
 * ```typescript
 * import { AuraClient } from '@aenealabs/aura-sdk';
 *
 * const client = new AuraClient({
 *   baseUrl: 'https://api.aura.example.com',
 *   apiKey: 'your-api-key',
 * });
 *
 * // Scan a file for vulnerabilities
 * const result = await client.extension.scanFile({
 *   file_path: 'src/app.ts',
 *   file_content: sourceCode,
 *   language: 'typescript',
 * });
 *
 * // List pending approvals
 * const approvals = await client.approvals.list({ status: 'pending' });
 * ```
 *
 * @example
 * React usage:
 * ```tsx
 * import { AuraProvider, useApprovals } from '@aenealabs/aura-sdk/react';
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
 *   const { approvals, loading, error } = useApprovals({ status: 'pending' });
 *   // Render approvals...
 * }
 * ```
 */

// Client exports
export {
  AuraClient,
  type AuraClientConfig,
  type RequestOptions,
  AuraAPIError,
  AuthenticationError,
  NotFoundError,
  ValidationError,
  ExtensionAPI,
  ApprovalsAPI,
  IncidentsAPI,
  SettingsAPI,
} from './client';

// Type exports
export * from './types';

// Utility exports
export * from './utils';

// Default export
export { default } from './client';

# @aenealabs/aura-sdk

TypeScript SDK for the Aura Code Intelligence Platform.

## Installation

```bash
npm install @aenealabs/aura-sdk
# or
yarn add @aenealabs/aura-sdk
# or
pnpm add @aenealabs/aura-sdk
```

## Quick Start

### Basic Usage

```typescript
import { AuraClient } from '@aenealabs/aura-sdk';

const client = new AuraClient({
  baseUrl: 'https://api.aura.example.com',
  apiKey: 'your-api-key',
});

// Scan a file for vulnerabilities
const result = await client.extension.scanFile({
  file_path: 'src/app.ts',
  file_content: sourceCode,
  language: 'typescript',
});

console.log(`Found ${result.findings_count} issues`);

// Get findings
const findings = await client.extension.listFindings({ severity: 'critical' });
findings.findings.forEach((f) => {
  console.log(`${f.severity}: ${f.title} in ${f.file_path}:${f.line_start}`);
});
```

### React Integration

```tsx
import { AuraProvider, useApprovals, useVulnerabilities } from '@aenealabs/aura-sdk/react';

function App() {
  return (
    <AuraProvider baseUrl="https://api.aura.example.com" apiKey="...">
      <Dashboard />
    </AuraProvider>
  );
}

function Dashboard() {
  const { approvals, loading, error, approve, reject } = useApprovals({
    status: 'pending',
  });
  const { findings, scanFile } = useVulnerabilities();

  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;

  return (
    <div>
      <h2>Pending Approvals: {approvals.length}</h2>
      {approvals.map((approval) => (
        <ApprovalCard
          key={approval.id}
          approval={approval}
          onApprove={() => approve(approval.id)}
          onReject={(reason) => reject(approval.id, reason)}
        />
      ))}

      <h2>Vulnerabilities: {findings.length}</h2>
      {findings.map((finding) => (
        <FindingCard key={finding.id} finding={finding} />
      ))}
    </div>
  );
}
```

## API Reference

### Client APIs

#### ExtensionAPI

- `getConfig()` - Get extension configuration
- `scanFile(request)` - Scan a file for vulnerabilities
- `getFindings(filePath)` - Get findings for a file
- `listFindings(params?)` - List all findings with filters
- `generatePatch(request)` - Generate a patch for a finding
- `getPatch(patchId)` - Get patch details
- `applyPatch(patchId, confirm)` - Apply an approved patch
- `getApprovalStatus(approvalId)` - Get approval status

#### ApprovalsAPI

- `list(params?)` - List approval requests
- `getStats()` - Get approval statistics
- `get(approvalId)` - Get approval details
- `approve(approvalId, comments?)` - Approve a request
- `reject(approvalId, reason)` - Reject a request
- `cancel(approvalId, reason?)` - Cancel a request

#### IncidentsAPI

- `list(params?)` - List incidents
- `get(incidentId)` - Get incident details
- `acknowledge(incidentId)` - Acknowledge an incident
- `resolve(incidentId, rootCause, remediation)` - Resolve an incident

#### SettingsAPI

- `get()` - Get platform settings
- `update(settings)` - Update platform settings
- `getIntegrationMode()` - Get integration mode
- `setIntegrationMode(mode)` - Set integration mode
- `getHITLSettings()` - Get HITL settings
- `updateHITLSettings(settings)` - Update HITL settings
- `getMCPSettings()` - Get MCP settings
- `updateMCPSettings(settings)` - Update MCP settings
- `getMCPTools()` - Get available MCP tools
- `testMCPConnection(gatewayUrl)` - Test MCP connection
- `getMCPUsage()` - Get MCP usage statistics

### React Hooks

#### Core Hooks

- `useAuraClient()` - Access the Aura client
- `useAuraConnection()` - Check connection status

#### Vulnerability Hooks

- `useVulnerabilities(filters?)` - Manage vulnerability findings
- `useFinding(findingId, filePath)` - Get a single finding

#### Patch Hooks

- `usePatch(patchId)` - Manage a single patch

#### Approval Hooks

- `useApprovals(filters?)` - Manage approval requests
- `useApproval(approvalId)` - Manage a single approval
- `useApprovalStats()` - Get approval statistics

#### Incident Hooks

- `useIncidents(filters?)` - Manage incidents
- `useIncident(incidentId)` - Manage a single incident

#### Settings Hooks

- `useSettings()` - Manage platform settings
- `useHITLSettings()` - Manage HITL settings

#### Utility Hooks

- `useApprovalPolling(approvalId, interval?)` - Poll for approval updates
- `useVulnerabilityCount(severity?)` - Get vulnerability count
- `usePendingApprovalCount()` - Get pending approval count

### Utilities

```typescript
import {
  compareSeverity,
  meetsSeverityThreshold,
  getSeverityColor,
  groupFindingsByFile,
  sortFindingsBySeverity,
  getCWEUrl,
  getOWASPUrl,
  getRelativeTime,
  parseDiff,
} from '@aenealabs/aura-sdk';
```

## Types

All API types are exported from the main package:

```typescript
import type {
  Finding,
  Patch,
  ApprovalSummary,
  IncidentSummary,
  Severity,
  PatchStatus,
  ApprovalStatus,
} from '@aenealabs/aura-sdk';
```

## Error Handling

```typescript
import {
  AuraAPIError,
  AuthenticationError,
  NotFoundError,
  ValidationError,
} from '@aenealabs/aura-sdk';

try {
  await client.extension.scanFile(request);
} catch (error) {
  if (error instanceof AuthenticationError) {
    // Handle authentication failure
  } else if (error instanceof NotFoundError) {
    // Handle resource not found
  } else if (error instanceof ValidationError) {
    // Handle validation errors
    console.log(error.errors);
  } else if (error instanceof AuraAPIError) {
    // Handle other API errors
    console.log(error.statusCode, error.message);
  }
}
```

## Configuration

```typescript
const client = new AuraClient({
  // Required: Base URL of the Aura API
  baseUrl: 'https://api.aura.example.com',

  // Authentication (choose one)
  apiKey: 'your-api-key',
  jwtToken: 'your-jwt-token',

  // Optional: Request timeout (default: 30000ms)
  timeout: 60000,

  // Optional: Custom headers
  headers: {
    'X-Custom-Header': 'value',
  },

  // Optional: Enable debug logging
  debug: true,
});
```

## License

MIT

# GraphQL API Reference

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

Project Aura provides a GraphQL API alongside the REST API, enabling flexible queries and efficient data fetching. GraphQL is particularly useful when you need to fetch related data in a single request or when building complex dashboards.

**Endpoint:** `https://api.aenealabs.com/v1/graphql`

---

## Quick Start

### Authentication

GraphQL requests require the same JWT authentication as REST:

```bash
curl -X POST https://api.aenealabs.com/v1/graphql \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ me { id email name } }"
  }'
```

### GraphQL Playground

An interactive GraphQL IDE is available at:

- Production: `https://api.aenealabs.com/v1/graphql/playground`
- Staging: `https://api.staging.aenealabs.com/v1/graphql/playground`

---

## Schema Overview

```graphql
type Query {
  # User and Organization
  me: User!
  organization: Organization!
  users(filter: UserFilter, pagination: Pagination): UserConnection!

  # Repositories
  repositories(filter: RepositoryFilter, pagination: Pagination): RepositoryConnection!
  repository(id: ID!): Repository

  # Vulnerabilities
  vulnerabilities(filter: VulnerabilityFilter, pagination: Pagination): VulnerabilityConnection!
  vulnerability(id: ID!): Vulnerability

  # Patches
  patches(filter: PatchFilter, pagination: Pagination): PatchConnection!
  patch(id: ID!): Patch

  # Approvals
  approvals(filter: ApprovalFilter, pagination: Pagination): ApprovalConnection!
  approval(id: ID!): Approval

  # Agents
  agentStatus: AgentStatusSummary!
  agentExecutions(filter: ExecutionFilter, pagination: Pagination): ExecutionConnection!

  # System
  systemHealth: SystemHealth!
  systemMetrics: SystemMetrics!
}

type Mutation {
  # Repository Operations
  createRepository(input: CreateRepositoryInput!): Repository!
  updateRepository(id: ID!, input: UpdateRepositoryInput!): Repository!
  deleteRepository(id: ID!): Boolean!
  triggerScan(repositoryId: ID!, input: ScanInput): Scan!

  # Vulnerability Operations
  updateVulnerability(id: ID!, input: UpdateVulnerabilityInput!): Vulnerability!
  bulkUpdateVulnerabilities(ids: [ID!]!, input: UpdateVulnerabilityInput!): [Vulnerability!]!

  # Patch Operations
  approvePatch(id: ID!, input: ApproveInput!): Patch!
  rejectPatch(id: ID!, input: RejectInput!): Patch!
  deployPatch(id: ID!, input: DeployInput!): Deployment!
  regeneratePatch(vulnerabilityId: ID!): Patch!

  # Settings
  updateHITLSettings(input: HITLSettingsInput!): HITLSettings!

  # Webhooks
  createWebhook(input: CreateWebhookInput!): Webhook!
  updateWebhook(id: ID!, input: UpdateWebhookInput!): Webhook!
  deleteWebhook(id: ID!): Boolean!
}

type Subscription {
  vulnerabilityDetected(repositoryId: ID): Vulnerability!
  patchGenerated(repositoryId: ID): Patch!
  approvalRequested(repositoryId: ID): Approval!
  patchDeployed(repositoryId: ID): Deployment!
  agentStatusChanged: AgentStatusChange!
}
```

---

## Core Types

### User

```graphql
type User {
  id: ID!
  email: String!
  name: String!
  roles: [Role!]!
  permissions: [Permission!]!
  teams: [Team!]!
  organization: Organization!
  lastLoginAt: DateTime
  mfaEnabled: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!
}

enum Role {
  ORG_ADMIN
  SECURITY_ADMIN
  DEVELOPER
  VIEWER
}
```

### Repository

```graphql
type Repository {
  id: ID!
  name: String!
  url: String!
  provider: GitProvider!
  defaultBranch: String!
  status: RepositoryStatus!
  scanConfig: ScanConfig!
  team: Team

  # Related data
  vulnerabilities(filter: VulnerabilityFilter, pagination: Pagination): VulnerabilityConnection!
  patches(filter: PatchFilter, pagination: Pagination): PatchConnection!
  scans(pagination: Pagination): ScanConnection!

  # Statistics
  vulnerabilityCounts: VulnerabilityCounts!
  statistics: RepositoryStatistics!

  lastScanAt: DateTime
  createdAt: DateTime!
  updatedAt: DateTime!
}

enum GitProvider {
  GITHUB
  GITLAB
  BITBUCKET
  AZURE_DEVOPS
}

enum RepositoryStatus {
  ACTIVE
  INACTIVE
  SCANNING
  ERROR
}

type VulnerabilityCounts {
  critical: Int!
  high: Int!
  medium: Int!
  low: Int!
  total: Int!
}

type RepositoryStatistics {
  totalLinesOfCode: Int!
  totalFiles: Int!
  lastCommit: DateTime
  languages: [LanguageBreakdown!]!
}
```

### Vulnerability

```graphql
type Vulnerability {
  id: ID!
  title: String!
  description: String!
  severity: Severity!
  status: VulnerabilityStatus!
  cveId: String
  cwes: [String!]!
  cvssScore: Float
  cvssVector: String

  # Location
  repository: Repository!
  location: CodeLocation!

  # Remediation
  remediation: Remediation!
  patch: Patch

  # Metadata
  scan: Scan!
  history: [VulnerabilityEvent!]!

  detectedAt: DateTime!
  createdAt: DateTime!
  updatedAt: DateTime!
}

enum Severity {
  CRITICAL
  HIGH
  MEDIUM
  LOW
  INFO
}

enum VulnerabilityStatus {
  OPEN
  IN_PROGRESS
  RESOLVED
  IGNORED
}

type CodeLocation {
  file: String!
  lineStart: Int!
  lineEnd: Int!
  function: String
  codeSnippet: String!
}

type Remediation {
  recommendation: String!
  references: [String!]!
  estimatedEffort: String
}
```

### Patch

```graphql
type Patch {
  id: ID!
  vulnerability: Vulnerability!
  repository: Repository!
  status: PatchStatus!
  confidenceScore: Float!

  # Changes
  filesChanged: [FileChange!]!
  diffSummary: DiffSummary!

  # Validation
  sandboxResults: SandboxResults!

  # AI Metadata
  agentReasoning: String!
  generatedBy: AgentInfo!

  # Approval
  approval: Approval

  generatedAt: DateTime!
  createdAt: DateTime!
  updatedAt: DateTime!
}

enum PatchStatus {
  PENDING_APPROVAL
  APPROVED
  REJECTED
  DEPLOYED
  FAILED
}

type FileChange {
  path: String!
  additions: Int!
  deletions: Int!
  diff: String!
}

type DiffSummary {
  totalAdditions: Int!
  totalDeletions: Int!
  filesChanged: Int!
}

type SandboxResults {
  allPassed: Boolean!
  syntaxCheck: TestResult!
  unitTests: UnitTestResult!
  securityScan: TestResult!
  performance: PerformanceResult!
}

type TestResult {
  status: TestStatus!
  details: String
}

enum TestStatus {
  PASSED
  FAILED
  SKIPPED
  ERROR
}

type UnitTestResult {
  status: TestStatus!
  passed: Int!
  failed: Int!
  skipped: Int!
  coverage: Float
}

type PerformanceResult {
  status: TestStatus!
  latencyChangePercent: Float
  memoryChangePercent: Float
}
```

### Approval

```graphql
type Approval {
  id: ID!
  type: ApprovalType!
  patch: Patch!
  repository: Repository!
  status: ApprovalStatus!
  requiredRole: Role!
  policy: HITLPolicy!

  # Approval details
  approvedBy: User
  approvedAt: DateTime
  comment: String

  # Notifications
  notificationsSent: [NotificationRecord!]!

  expiresAt: DateTime!
  createdAt: DateTime!
}

enum ApprovalType {
  PATCH_APPROVAL
  DEPLOYMENT_APPROVAL
  CONFIG_CHANGE
}

enum ApprovalStatus {
  PENDING
  APPROVED
  REJECTED
  EXPIRED
}
```

---

## Queries

### Fetch Repositories with Vulnerabilities

```graphql
query GetRepositoriesWithVulns($filter: RepositoryFilter, $first: Int) {
  repositories(filter: $filter, pagination: { first: $first }) {
    edges {
      node {
        id
        name
        url
        status
        vulnerabilityCounts {
          critical
          high
          medium
          low
          total
        }
        vulnerabilities(filter: { status: OPEN }, pagination: { first: 5 }) {
          edges {
            node {
              id
              title
              severity
              detectedAt
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

**Variables:**

```json
{
  "filter": { "status": "ACTIVE" },
  "first": 10
}
```

---

### Fetch Vulnerability Details

```graphql
query GetVulnerability($id: ID!) {
  vulnerability(id: $id) {
    id
    title
    description
    severity
    status
    cveId
    cwes
    cvssScore
    cvssVector
    repository {
      id
      name
      url
    }
    location {
      file
      lineStart
      lineEnd
      function
      codeSnippet
    }
    remediation {
      recommendation
      references
    }
    patch {
      id
      status
      confidenceScore
      sandboxResults {
        allPassed
        unitTests {
          passed
          failed
        }
      }
    }
    history {
      timestamp
      action
      actor {
        id
        name
      }
    }
  }
}
```

---

### Fetch Patch with Full Diff

```graphql
query GetPatchDetails($id: ID!) {
  patch(id: $id) {
    id
    status
    confidenceScore
    vulnerability {
      id
      title
      severity
    }
    repository {
      id
      name
    }
    filesChanged {
      path
      additions
      deletions
      diff
    }
    sandboxResults {
      allPassed
      syntaxCheck {
        status
        details
      }
      unitTests {
        status
        passed
        failed
        skipped
        coverage
      }
      securityScan {
        status
        details
      }
      performance {
        status
        latencyChangePercent
      }
    }
    agentReasoning
    generatedBy {
      agent
      model
      contextTokensUsed
    }
    approval {
      status
      approvedBy {
        name
      }
      approvedAt
      comment
    }
  }
}
```

---

### Dashboard Summary Query

```graphql
query DashboardSummary {
  me {
    name
    organization {
      name
    }
  }

  systemHealth {
    status
    components {
      name
      status
    }
  }

  # Repository overview
  repositories(pagination: { first: 100 }) {
    totalCount
    edges {
      node {
        id
        name
        vulnerabilityCounts {
          critical
          high
          medium
          low
        }
      }
    }
  }

  # Open vulnerabilities
  vulnerabilities(filter: { status: OPEN }) {
    totalCount
  }

  # Pending approvals
  approvals(filter: { status: PENDING }) {
    totalCount
    edges {
      node {
        id
        patch {
          vulnerability {
            title
            severity
          }
        }
        expiresAt
      }
    }
  }

  # Recent patches
  patches(pagination: { first: 5 }) {
    edges {
      node {
        id
        status
        vulnerability {
          title
        }
        generatedAt
      }
    }
  }

  # System metrics
  systemMetrics {
    api {
      requestsPerMinute
      errorRatePercent
    }
    vulnerabilities {
      totalResolved
      mttrHours
    }
  }
}
```

---

## Mutations

### Approve a Patch

```graphql
mutation ApprovePatch($id: ID!, $input: ApproveInput!) {
  approvePatch(id: $id, input: $input) {
    id
    status
    approval {
      status
      approvedBy {
        name
      }
      approvedAt
      comment
    }
  }
}
```

**Variables:**

```json
{
  "id": "patch-67890",
  "input": {
    "comment": "Reviewed and approved. Implementation is correct.",
    "deployImmediately": false
  }
}
```

---

### Reject a Patch

```graphql
mutation RejectPatch($id: ID!, $input: RejectInput!) {
  rejectPatch(id: $id, input: $input) {
    id
    status
    approval {
      status
      comment
    }
  }
}
```

**Variables:**

```json
{
  "id": "patch-67890",
  "input": {
    "reason": "INCOMPLETE_FIX",
    "comment": "Need to also fix the query on line 78."
  }
}
```

---

### Deploy a Patch

```graphql
mutation DeployPatch($id: ID!, $input: DeployInput!) {
  deployPatch(id: $id, input: $input) {
    id
    status
    pullRequest {
      url
      number
    }
  }
}
```

**Variables:**

```json
{
  "id": "patch-67890",
  "input": {
    "targetBranch": "main",
    "createPullRequest": true,
    "reviewers": ["user-23456"]
  }
}
```

---

### Update Vulnerability Status

```graphql
mutation UpdateVulnerability($id: ID!, $input: UpdateVulnerabilityInput!) {
  updateVulnerability(id: $id, input: $input) {
    id
    status
    updatedAt
  }
}
```

**Variables:**

```json
{
  "id": "vuln-12345",
  "input": {
    "status": "IGNORED",
    "ignoreReason": "FALSE_POSITIVE",
    "comment": "This is test code, not production."
  }
}
```

---

### Bulk Update Vulnerabilities

```graphql
mutation BulkUpdateVulnerabilities($ids: [ID!]!, $input: UpdateVulnerabilityInput!) {
  bulkUpdateVulnerabilities(ids: $ids, input: $input) {
    id
    status
  }
}
```

**Variables:**

```json
{
  "ids": ["vuln-1", "vuln-2", "vuln-3"],
  "input": {
    "status": "IGNORED",
    "ignoreReason": "ACCEPTED_RISK"
  }
}
```

---

## Subscriptions

Subscriptions enable real-time updates via WebSocket.

### Connect to WebSocket

```javascript
import { createClient } from 'graphql-ws';

const client = createClient({
  url: 'wss://api.aenealabs.com/v1/graphql',
  connectionParams: {
    authorization: `Bearer ${AURA_TOKEN}`,
  },
});

// Subscribe to new vulnerabilities
client.subscribe(
  {
    query: `
      subscription OnVulnerabilityDetected($repositoryId: ID) {
        vulnerabilityDetected(repositoryId: $repositoryId) {
          id
          title
          severity
          repository {
            name
          }
        }
      }
    `,
    variables: { repositoryId: 'repo-12345' },
  },
  {
    next: (data) => console.log('New vulnerability:', data),
    error: (error) => console.error('Error:', error),
    complete: () => console.log('Subscription complete'),
  }
);
```

---

### Subscribe to Patch Status Changes

```graphql
subscription OnPatchGenerated($repositoryId: ID) {
  patchGenerated(repositoryId: $repositoryId) {
    id
    status
    confidenceScore
    vulnerability {
      id
      title
    }
    generatedAt
  }
}
```

---

### Subscribe to Approval Requests

```graphql
subscription OnApprovalRequested {
  approvalRequested {
    id
    patch {
      vulnerability {
        title
        severity
      }
    }
    repository {
      name
    }
    expiresAt
  }
}
```

---

## Pagination

GraphQL uses cursor-based pagination following the Relay specification:

```graphql
query PaginatedVulnerabilities($first: Int, $after: String) {
  vulnerabilities(pagination: { first: $first, after: $after }) {
    edges {
      node {
        id
        title
      }
      cursor
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
    totalCount
  }
}
```

---

## Error Handling

GraphQL errors are returned in the `errors` array:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Insufficient permissions to approve patch",
      "locations": [{ "line": 2, "column": 3 }],
      "path": ["approvePatch"],
      "extensions": {
        "code": "AURA-AUTH-002",
        "requiredRole": "SECURITY_ADMIN"
      }
    }
  ]
}
```

---

## Rate Limiting

GraphQL requests count toward the same rate limits as REST. Complex queries may count as multiple requests based on estimated cost.

---

## Related Documentation

- [API Reference Index](./index.md)
- [REST API Reference](./rest-api.md)
- [Webhooks](./webhooks.md)
- [Authentication Guide](../troubleshooting/security-issues.md)

---

*Last updated: January 2026 | Version 1.0*

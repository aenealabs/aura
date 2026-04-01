# DynamoDB Schema Reference

**Status:** Phase 0 Prerequisite for ADR-049 (Self-Hosted Deployment)
**Date:** 2026-01-03
**Purpose:** Document all DynamoDB table schemas for PostgreSQL migration planning

---

## Overview

Project Aura uses **37 DynamoDB tables** across 8 deployment layers. This document provides the schema reference needed to design PostgreSQL equivalents for self-hosted deployments.

### Table Count by Layer

| Layer | Count | Tables |
|-------|-------|--------|
| Layer 2 (Data) | 13 | Core platform tables |
| Layer 4 (Application) | 2 | Onboarding tables |
| Layer 6 (Serverless) | 11 | Chat, checkpoint, A2A, SSR tables |
| Layer 7 (Sandbox) | 4 | HITL workflow tables |
| Layer 8 (Security) | 2 | Red team tables |
| Other | 5 | Test environments, marketplace |

---

## Layer 2: Data Layer Tables

### 2.1 Cost Tracking Table

**Table Name:** `aura-cost-tracking-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Track user cost/usage metrics

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `userId` | S | HASH | User identifier |
| `timestamp` | N | RANGE | Unix timestamp |
| `date` | S | - | Date string (YYYY-MM-DD) |

**GSIs:**
- `DateIndex` (date HASH, timestamp RANGE) - Query by date

**Features:** DynamoDB Streams, PITR enabled

---

### 2.2 User Sessions Table

**Table Name:** `aura-user-sessions-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Active user session management

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `sessionId` | S | HASH | Session UUID |
| `userId` | S | - | User identifier |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `UserIdIndex` (userId HASH) - Find sessions by user

**Features:** TTL enabled, PITR enabled

---

### 2.3 Code Generation Jobs Table

**Table Name:** `aura-codegen-jobs-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Track code generation job lifecycle

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `jobId` | S | HASH | Job UUID |
| `userId` | S | - | User identifier |
| `createdAt` | N | - | Unix timestamp |
| `status` | S | - | Job status (PENDING, RUNNING, COMPLETED, FAILED) |

**GSIs:**
- `UserIdIndex` (userId HASH, createdAt RANGE) - User's jobs by time
- `StatusIndex` (status HASH, createdAt RANGE) - Jobs by status

**Features:** DynamoDB Streams, PITR enabled

---

### 2.4 Ingestion Jobs Table

**Table Name:** `aura-ingestion-jobs-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Track git repository ingestion jobs

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `jobId` | S | HASH | Job UUID |
| `repositoryId` | S | - | Repository identifier |
| `status` | S | - | Job status |
| `createdAt` | N | - | Unix timestamp |
| `datePartition` | S | - | Date partition (YYYY-MM-DD) |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `RepositoryIndex` (repositoryId HASH, createdAt RANGE) - Jobs by repo
- `StatusIndex` (status HASH, createdAt RANGE) - Jobs by status
- `DatePartitionIndex` (datePartition HASH, createdAt RANGE) - Efficient time-range queries

**Features:** TTL enabled, DynamoDB Streams, PITR enabled

---

### 2.5 Codebase Metadata Table

**Table Name:** `aura-codebase-metadata-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Store metadata about ingested codebases

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `codebaseId` | S | HASH | Codebase UUID |
| `userId` | S | - | Owner user ID |

**GSIs:**
- `UserIdIndex` (userId HASH) - User's codebases

**Features:** PITR enabled

---

### 2.6 Platform Settings Table

**Table Name:** `aura-platform-settings-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Store platform configuration settings

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `settings_type` | S | HASH | Setting category |
| `settings_key` | S | RANGE | Setting key |

**Features:** PITR enabled

**Note:** Composite key design for hierarchical settings (e.g., `settings_type="autonomy"`, `settings_key="default_policy"`)

---

### 2.7 Anomalies Table

**Table Name:** `aura-anomalies-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Audit trail for detected anomalies

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `anomaly_id` | S | HASH | Anomaly UUID |
| `sort_key` | S | RANGE | Sort key for versioning |
| `status` | S | - | Anomaly status |
| `severity` | S | - | Severity level (LOW, MEDIUM, HIGH, CRITICAL) |
| `created_at` | S | - | ISO timestamp |
| `dedup_key` | S | - | Deduplication key |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `status-created_at-index` (status HASH, created_at RANGE)
- `severity-created_at-index` (severity HASH, created_at RANGE)
- `dedup_key-index` (dedup_key HASH) - Deduplication lookup

**Features:** TTL enabled, DynamoDB Streams, PITR enabled

---

### 2.8 Autonomy Policies Table

**Table Name:** `aura-autonomy-policies-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Store organization autonomy configurations (ADR-032)

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `policy_id` | S | HASH | Policy UUID |
| `organization_id` | S | - | Organization identifier |

**GSIs:**
- `organization-index` (organization_id HASH) - Policies by org

**Features:** PITR enabled

---

### 2.9 Policy Audit Table

**Table Name:** `aura-policy-audit-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Audit trail for policy changes

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `audit_id` | S | HASH | Audit entry UUID |
| `policy_id` | S | - | Related policy ID |
| `changed_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `policy-changed_at-index` (policy_id HASH, changed_at RANGE)

**Features:** TTL enabled, PITR enabled

---

### 2.10 Autonomy Decisions Table

**Table Name:** `aura-autonomy-decisions-{env}`
**Source:** `deploy/cloudformation/dynamodb.yaml`
**Purpose:** Record autonomous decisions made by agents

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `decision_id` | S | HASH | Decision UUID |
| `execution_id` | S | - | Related execution ID |
| `timestamp` | S | - | ISO timestamp |
| `organization_id` | S | - | Organization identifier |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `execution-index` (execution_id HASH)
- `org-timestamp-index` (organization_id HASH, timestamp RANGE)

**Features:** TTL enabled, PITR enabled

---

### 2.11-2.13 Repository Onboarding Tables (ADR-043)

**Source:** `deploy/cloudformation/repository-tables.yaml`

#### Repositories Table
**Table Name:** `aura-repositories-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `repository_id` | S | HASH | Repository UUID |
| `user_id` | S | - | Owner user ID |
| `created_at` | S | - | ISO timestamp |
| `provider` | S | - | Git provider (github, gitlab, bitbucket) |

**GSIs:**
- `user-index` (user_id HASH, created_at RANGE)
- `user-provider-index` (user_id HASH, provider RANGE)

#### OAuth Connections Table
**Table Name:** `aura-oauth-connections-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `connection_id` | S | HASH | Connection UUID |
| `user_id` | S | - | User identifier |
| `provider` | S | - | OAuth provider |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `user-provider-index` (user_id HASH, provider RANGE)

#### Repository Ingestion Jobs Table
**Table Name:** `aura-repo-ingestion-jobs-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `job_id` | S | HASH | Job UUID |
| `user_id` | S | - | User identifier |
| `repository_id` | S | - | Repository identifier |
| `status` | S | - | Job status |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `user-status-index` (user_id HASH, status RANGE)
- `repository-index` (repository_id HASH)

---

## Layer 4: Application Layer Tables

### 4.1-4.2 Customer Onboarding Tables (ADR-047)

**Source:** `deploy/cloudformation/onboarding.yaml`

#### User Onboarding Table
**Table Name:** `aura-user-onboarding-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `user_id` | S | HASH | User identifier |
| `organization_id` | S | - | Organization ID |
| `created_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `organization-index` (organization_id HASH, created_at RANGE)

**Stored Data:** Welcome modal state, checklist progress, tour completion, video watch history

#### Team Invitations Table
**Table Name:** `aura-team-invitations-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `invitation_id` | S | HASH | Invitation UUID |
| `organization_id` | S | - | Organization ID |
| `status` | S | - | Status (pending, accepted, expired) |
| `invitee_email` | S | - | Invited email address |
| `invitation_token` | S | - | Secure token for acceptance |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `organization-status-index` (organization_id HASH, status RANGE)
- `email-index` (invitee_email HASH)
- `token-index` (invitation_token HASH) - KEYS_ONLY projection

---

## Layer 6: Serverless Layer Tables

### 6.1-6.4 Chat Assistant Tables

**Source:** `deploy/cloudformation/chat-assistant.yaml`

#### Chat Conversations Table
**Table Name:** `aura-chat-conversations-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `PK` | S | HASH | Partition key (CONV#{conv_id}) |
| `SK` | S | RANGE | Sort key (META or MSG#{timestamp}) |
| `user_id` | S | - | User identifier |
| `updated_at` | S | - | ISO timestamp |
| `tenant_id` | S | - | Tenant identifier |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `user-conversations-index` (user_id HASH, updated_at RANGE)
- `tenant-conversations-index` (tenant_id HASH, updated_at RANGE)

**Note:** Uses single-table design pattern (PK/SK composite key)

#### Chat Messages Table
**Table Name:** `aura-chat-messages-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `PK` | S | HASH | Partition key (CONV#{conv_id}) |
| `SK` | S | RANGE | Sort key (MSG#{timestamp}) |
| `tenant_id` | S | - | Tenant identifier |
| `created_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `tenant-messages-index` (tenant_id HASH, created_at RANGE)

#### Chat Connections Table
**Table Name:** `aura-chat-connections-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `connection_id` | S | HASH | WebSocket connection ID |
| `user_id` | S | - | User identifier |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `user-connections-index` (user_id HASH)

#### Research Tasks Table
**Table Name:** `aura-research-tasks-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `task_id` | S | HASH | Task UUID |
| `user_id` | S | - | User identifier |
| `tenant_id` | S | - | Tenant identifier |
| `created_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `user-tasks-index` (user_id HASH, created_at RANGE)
- `tenant-tasks-index` (tenant_id HASH, created_at RANGE)

---

### 6.5-6.6 Checkpoint Tables (ADR-042)

**Source:** `deploy/cloudformation/checkpoint-dynamodb.yaml`

#### Checkpoints Table
**Table Name:** `aura-checkpoints-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `checkpoint_id` | S | HASH | Checkpoint UUID |
| `execution_id` | S | - | Execution identifier |
| `status` | S | - | Status (pending, approved, rejected) |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `execution-status-index` (execution_id HASH, status RANGE)

#### WebSocket Connections Table
**Table Name:** `aura-ws-connections-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `connection_id` | S | HASH | WebSocket connection ID |
| `execution_id` | S | - | Execution identifier |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `execution-index` (execution_id HASH)

---

### 6.7-6.8 A2A Infrastructure Tables

**Source:** `deploy/cloudformation/a2a-infrastructure.yaml`

#### A2A Agent Registry Table
**Table Name:** `aura-a2a-agents-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `agentId` | S | HASH | Agent UUID |
| `provider` | S | - | Agent provider |
| `status` | S | - | Agent status |
| `registeredAt` | S | - | ISO timestamp |
| `expiresAt` | N | - | TTL timestamp |

**GSIs:**
- `ProviderIndex` (provider HASH, registeredAt RANGE)
- `StatusIndex` (status HASH, registeredAt RANGE)

**Features:** TTL on expiresAt

#### A2A Tasks Table
**Table Name:** `aura-a2a-tasks-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `taskId` | S | HASH | Task UUID |
| `status` | S | - | Task status |
| `createdAt` | S | - | ISO timestamp |
| `requesterAgentId` | S | - | Requesting agent ID |
| `expiresAt` | N | - | TTL timestamp |

**GSIs:**
- `StatusIndex` (status HASH, createdAt RANGE)
- `RequesterIndex` (requesterAgentId HASH, createdAt RANGE)

**Features:** DynamoDB Streams, TTL on expiresAt

---

### 6.9 SSR Training State Table (ADR-050)

**Source:** `deploy/cloudformation/ssr-training.yaml`

**Table Name:** `aura-ssr-training-state-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `artifact_id` | S | HASH | Training artifact UUID |
| `repository_id` | S | - | Source repository ID |
| `created_at` | S | - | ISO timestamp |
| `status` | S | - | Training status |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `repository-created-index` (repository_id HASH, created_at RANGE)
- `status-created-index` (status HASH, created_at RANGE)

---

## Layer 7: Sandbox Layer Tables

**Source:** `deploy/cloudformation/sandbox.yaml`

### 7.1 Approval Requests Table

**Table Name:** `aura-approval-requests-{env}`
**Purpose:** Track HITL approval workflow state

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `approval_id` | S | HASH | Approval UUID |
| `status` | S | - | Status (PENDING, APPROVED, REJECTED) |
| `created_at` | S | - | ISO timestamp |
| `reviewer_email` | S | - | Assigned reviewer |
| `statusBucket` | S | - | Partition bucket (PENDING#0-9) |
| `createdAtTimestamp` | N | - | Unix timestamp |
| `reviewedAtMonth` | S | - | Month partition (YYYY-MM) |
| `reviewedAtTimestamp` | N | - | Review Unix timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `status-created_at-index` (status HASH, created_at RANGE)
- `reviewer-status-index` (reviewer_email HASH, status RANGE)
- `StatusBucketIndex` (statusBucket HASH, createdAtTimestamp RANGE) - Hot partition prevention
- `ReviewedAtIndex` (reviewedAtMonth HASH, reviewedAtTimestamp RANGE) - Audit queries

**Note:** Uses partition spreading pattern (statusBucket) to prevent hot partitions

---

### 7.2 Sandbox State Table

**Table Name:** `aura-sandbox-state-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `sandbox_id` | S | HASH | Sandbox UUID |
| `status` | S | - | Lifecycle status |
| `created_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `status-created_at-index` (status HASH, created_at RANGE)

---

### 7.3 Sandbox Results Table

**Table Name:** `aura-sandbox-results-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `result_id` | S | HASH | Result UUID |
| `sandbox_id` | S | - | Parent sandbox ID |
| `created_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `sandbox-id-index` (sandbox_id HASH, created_at RANGE)

---

### 7.4 Patch Workflows Table

**Table Name:** `aura-patch-workflows-{env}`

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `workflow_id` | S | HASH | Workflow UUID |
| `status` | S | - | Workflow status |
| `created_at` | S | - | ISO timestamp |
| `ttl` | N | - | TTL timestamp |

**GSIs:**
- `status-created_at-index` (status HASH, created_at RANGE)

---

## PostgreSQL Migration Considerations

### Data Type Mapping

| DynamoDB | PostgreSQL | Notes |
|----------|------------|-------|
| S (String) | TEXT or VARCHAR | Use TEXT for UUIDs and long strings |
| N (Number) | BIGINT or NUMERIC | BIGINT for timestamps, NUMERIC for decimals |
| BOOL | BOOLEAN | Direct mapping |
| M (Map) | JSONB | Native JSON support |
| L (List) | JSONB or ARRAY | JSONB for heterogeneous, ARRAY for homogeneous |

### GSI to Index Mapping

- Each GSI becomes a PostgreSQL index
- Composite GSIs become composite indexes
- Consider partial indexes for status-based queries

### TTL Implementation

```sql
-- Option 1: pg_cron for scheduled cleanup
SELECT cron.schedule('cleanup-expired', '0 * * * *',
  $$DELETE FROM sessions WHERE ttl < EXTRACT(EPOCH FROM NOW())$$);

-- Option 2: Application-level cleanup on read
SELECT * FROM sessions WHERE ttl > EXTRACT(EPOCH FROM NOW());
```

### DynamoDB Streams → PostgreSQL

- Replace with PostgreSQL LISTEN/NOTIFY
- Or use logical replication with pg_logical
- Or trigger-based change capture

### Partition Spreading

Tables using `statusBucket` pattern (e.g., approval-requests) don't need this in PostgreSQL - use standard indexes instead.

---

## Table Inventory Summary

| # | Table Name Pattern | Layer | ADR | TTL | Streams | PITR |
|---|-------------------|-------|-----|-----|---------|------|
| 1 | cost-tracking | 2.1 | - | No | Yes | Yes |
| 2 | user-sessions | 2.1 | - | Yes | No | Yes |
| 3 | codegen-jobs | 2.1 | - | No | Yes | Yes |
| 4 | ingestion-jobs | 2.1 | - | Yes | Yes | Yes |
| 5 | codebase-metadata | 2.1 | - | No | No | Yes |
| 6 | platform-settings | 2.1 | - | No | No | Yes |
| 7 | anomalies | 2.1 | - | Yes | Yes | Yes |
| 8 | autonomy-policies | 2.1 | ADR-032 | No | No | Yes |
| 9 | policy-audit | 2.1 | ADR-032 | Yes | No | Yes |
| 10 | autonomy-decisions | 2.1 | ADR-032 | Yes | No | Yes |
| 11 | repositories | 2.6 | ADR-043 | No | No | Yes |
| 12 | oauth-connections | 2.6 | ADR-043 | Yes | No | Yes |
| 13 | repo-ingestion-jobs | 2.6 | ADR-043 | Yes | No | Yes |
| 14 | user-onboarding | 4.10 | ADR-047 | Yes | No | Yes |
| 15 | team-invitations | 4.10 | ADR-047 | Yes | No | Yes |
| 16 | chat-conversations | 6.7 | - | Yes | No | Yes |
| 17 | chat-messages | 6.7 | - | Yes | No | Yes |
| 18 | chat-connections | 6.7 | - | Yes | No | No |
| 19 | research-tasks | 6.7 | - | Yes | No | Yes |
| 20 | checkpoints | 6.11 | ADR-042 | Yes | No | Yes |
| 21 | ws-connections | 6.11 | ADR-042 | Yes | No | No |
| 22 | a2a-agents | 6.x | - | Yes | No | Prod |
| 23 | a2a-tasks | 6.x | - | Yes | Yes | Prod |
| 24 | ssr-training-state | 6.x | ADR-050 | Yes | No | Prod |
| 25 | approval-requests | 7.1 | - | Yes | No | Prod |
| 26 | sandbox-state | 7.1 | - | Yes | No | Prod |
| 27 | sandbox-results | 7.1 | - | Yes | No | No |
| 28 | patch-workflows | 7.1 | - | Yes | No | Prod |

**Legend:**
- TTL: Time-To-Live enabled
- Streams: DynamoDB Streams enabled
- PITR: Point-In-Time Recovery (Yes = all envs, Prod = prod only)

---

## Next Steps (Phase 0)

1. **Validate schemas against Python code** - Ensure documented attributes match actual usage
2. **Identify undocumented attributes** - DynamoDB is schemaless; find attributes set in code
3. **Design PostgreSQL schema** - Create equivalent tables with proper normalization
4. **Plan migration tooling** - Export/import utilities for SaaS → self-hosted migration
5. **Document access patterns** - Query patterns to inform index design

---

## References

- ADR-049: Self-Hosted Deployment Strategy
- ADR-032: Configurable Autonomy Framework
- ADR-042: Real-Time Agent Intervention
- ADR-043: Repository Onboarding
- ADR-047: Customer Onboarding
- ADR-050: Self-Play SWE-RL Integration

# API Reference Guide

This guide provides an overview of the Aura Platform API for developers integrating with the platform.

---

## API Overview

Aura exposes a RESTful API for programmatic access to platform features.

### Base URLs

| Environment | URL |
|-------------|-----|
| Production | `https://api.aenealabs.com/api/v1` |
| Development | `https://api.dev.aenealabs.com/api/v1` |

### Authentication

All API requests require authentication via JWT tokens from AWS Cognito.

**Headers Required**:

```
Authorization: Bearer <your-jwt-token>
Content-Type: application/json
```

### Response Format

All responses follow this structure:

```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "Optional message",
  "timestamp": "2025-12-16T12:00:00Z"
}
```

---

## Core APIs

### Health Check

Check platform health status.

**Endpoint**: `GET /health`

**Response**:

```json
{
  "status": "healthy",
  "components": {
    "api": "healthy",
    "neptune": "healthy",
    "opensearch": "healthy",
    "bedrock": "healthy"
  }
}
```

| Status Code | Meaning |
|-------------|---------|
| 200 | All systems healthy |
| 503 | One or more systems degraded |

---

### Vulnerabilities

#### List Vulnerabilities

**Endpoint**: `GET /vulnerabilities`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `severity` | string | Filter by severity (CRITICAL, HIGH, MEDIUM, LOW) |
| `status` | string | Filter by status (OPEN, IN_PROGRESS, RESOLVED) |
| `repository` | string | Filter by repository name |
| `limit` | integer | Number of results (default: 50) |
| `offset` | integer | Pagination offset |

**Response**:

```json
{
  "status": "success",
  "data": {
    "vulnerabilities": [
      {
        "id": "vuln-123",
        "title": "SQL Injection in auth module",
        "severity": "HIGH",
        "status": "OPEN",
        "cvss_score": 8.5,
        "file_path": "src/auth/login.py",
        "line_number": 42,
        "description": "User input not sanitized before SQL query",
        "created_at": "2025-12-16T10:00:00Z"
      }
    ],
    "total": 150,
    "limit": 50,
    "offset": 0
  }
}
```

#### Get Vulnerability Details

**Endpoint**: `GET /vulnerabilities/{id}`

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": "vuln-123",
    "title": "SQL Injection in auth module",
    "severity": "HIGH",
    "status": "OPEN",
    "cvss_score": 8.5,
    "file_path": "src/auth/login.py",
    "line_number": 42,
    "description": "User input not sanitized before SQL query",
    "code_snippet": "cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
    "recommendation": "Use parameterized queries",
    "compliance_impact": ["OWASP A03:2021", "CWE-89"],
    "created_at": "2025-12-16T10:00:00Z",
    "patches": []
  }
}
```

#### Request Patch Generation

**Endpoint**: `POST /vulnerabilities/{id}/patch`

**Request**:

```json
{
  "priority": "HIGH",
  "notes": "Please prioritize this fix"
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "job_id": "job-456",
    "status": "QUEUED",
    "estimated_completion": "2025-12-16T10:05:00Z"
  }
}
```

---

### Approvals

#### List Pending Approvals

**Endpoint**: `GET /approvals`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | PENDING, APPROVED, REJECTED |
| `severity` | string | Filter by patch severity |
| `limit` | integer | Number of results |
| `offset` | integer | Pagination offset |

**Response**:

```json
{
  "status": "success",
  "data": {
    "approvals": [
      {
        "id": "approval-789",
        "patch_id": "patch-456",
        "vulnerability_id": "vuln-123",
        "status": "PENDING",
        "severity": "HIGH",
        "title": "Fix SQL injection in auth module",
        "created_at": "2025-12-16T10:00:00Z",
        "expires_at": "2025-12-17T10:00:00Z",
        "sandbox_results": {
          "status": "PASSED",
          "tests_run": 24,
          "tests_passed": 24
        }
      }
    ],
    "total": 5
  }
}
```

#### Approve Patch

**Endpoint**: `POST /approvals/{id}/approve`

**Request**:

```json
{
  "comment": "Reviewed and approved"
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": "approval-789",
    "status": "APPROVED",
    "approved_by": "user@example.com",
    "approved_at": "2025-12-16T11:00:00Z"
  }
}
```

#### Reject Patch

**Endpoint**: `POST /approvals/{id}/reject`

**Request**:

```json
{
  "reason": "Patch introduces breaking change",
  "feedback": "Please preserve backward compatibility"
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": "approval-789",
    "status": "REJECTED",
    "rejected_by": "user@example.com",
    "rejected_at": "2025-12-16T11:00:00Z"
  }
}
```

---

### Orchestration

#### Submit Orchestration Job

**Endpoint**: `POST /orchestrate`

**Request**:

```json
{
  "task_type": "vulnerability_analysis",
  "repository": "my-repo",
  "priority": "HIGH",
  "parameters": {
    "scan_type": "full",
    "include_tests": true
  }
}
```

**Response** (202 Accepted):

```json
{
  "status": "success",
  "data": {
    "job_id": "job-abc123",
    "status": "QUEUED",
    "priority": "HIGH"
  }
}
```

#### Get Job Status

**Endpoint**: `GET /orchestrate/{job_id}`

**Response**:

```json
{
  "status": "success",
  "data": {
    "job_id": "job-abc123",
    "status": "RUNNING",
    "progress": 65,
    "phase": "REVIEW",
    "started_at": "2025-12-16T10:00:00Z",
    "estimated_completion": "2025-12-16T10:10:00Z"
  }
}
```

| Status Values |
|---------------|
| QUEUED |
| DISPATCHED |
| RUNNING |
| SUCCEEDED |
| FAILED |
| CANCELLED |

#### Cancel Job

**Endpoint**: `DELETE /orchestrate/{job_id}`

**Response**:

```json
{
  "status": "success",
  "data": {
    "job_id": "job-abc123",
    "status": "CANCELLED"
  }
}
```

---

### Environments

#### List Environments

**Endpoint**: `GET /environments`

**Response**:

```json
{
  "status": "success",
  "data": {
    "environments": [
      {
        "id": "env-123",
        "name": "test-api-dev",
        "type": "standard",
        "status": "RUNNING",
        "template": "python-fastapi",
        "created_at": "2025-12-16T08:00:00Z",
        "expires_at": "2025-12-17T08:00:00Z",
        "cost_to_date": 0.45
      }
    ],
    "total": 2
  }
}
```

#### Create Environment

**Endpoint**: `POST /environments`

**Request**:

```json
{
  "name": "my-test-env",
  "template_id": "python-fastapi",
  "ttl_hours": 24
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": "env-456",
    "name": "my-test-env",
    "status": "PROVISIONING",
    "template": "python-fastapi",
    "estimated_ready": "2025-12-16T10:05:00Z"
  }
}
```

#### Get Environment Details

**Endpoint**: `GET /environments/{id}`

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": "env-456",
    "name": "my-test-env",
    "status": "RUNNING",
    "template": "python-fastapi",
    "connection_info": {
      "endpoint": "https://env-456.test.aenealabs.com",
      "kubeconfig": "...",
      "credentials": {
        "username": "admin",
        "password_secret": "arn:aws:secretsmanager:..."
      }
    },
    "resources": {
      "cpu": "2 cores",
      "memory": "4 GB",
      "storage": "20 GB"
    }
  }
}
```

#### Terminate Environment

**Endpoint**: `DELETE /environments/{id}`

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": "env-456",
    "status": "TERMINATING"
  }
}
```

---

### Autonomy Policies

#### Get Current Policy

**Endpoint**: `GET /autonomy/policies`

**Response**:

```json
{
  "status": "success",
  "data": {
    "policy": {
      "id": "policy-123",
      "organization_id": "org-456",
      "preset": "enterprise_standard",
      "default_level": "CRITICAL_HITL",
      "hitl_enabled": true,
      "overrides": [],
      "created_at": "2025-12-01T00:00:00Z"
    }
  }
}
```

#### Check HITL Requirement

**Endpoint**: `POST /autonomy/check`

**Request**:

```json
{
  "operation": "patch_deployment",
  "severity": "HIGH",
  "repository": "my-repo"
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "requires_hitl": true,
    "reason": "HIGH severity requires approval per CRITICAL_HITL policy",
    "is_guardrail": false
  }
}
```

---

### Settings

#### Get Settings

**Endpoint**: `GET /settings`

**Response**:

```json
{
  "status": "success",
  "data": {
    "integrationMode": "enterprise",
    "hitlSettings": {
      "requireApprovalForPatches": true,
      "requireApprovalForDeployments": true,
      "autoApproveMinorPatches": false,
      "approvalTimeoutHours": 24,
      "minApprovers": 1
    },
    "mcpSettings": {
      "enabled": true,
      "gatewayUrl": "https://gateway.agentcore.io",
      "monthlyBudgetUsd": 500,
      "dailyLimitUsd": 50,
      "externalToolsEnabled": ["slack", "jira", "github"]
    },
    "securitySettings": {
      "retainLogsForDays": 90,
      "sandboxIsolationLevel": "vpc",
      "auditAllActions": true
    }
  }
}
```

#### Update Integration Mode

**Endpoint**: `PUT /settings/integration-mode`

**Request**:

```json
{
  "mode": "hybrid"
}
```

---

### Chat Assistant

#### Send Message

**Endpoint**: `POST /chat/message`

**Request**:

```json
{
  "conversation_id": "conv-123",
  "message": "Show me critical vulnerabilities in the auth module"
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "message_id": "msg-456",
    "response": "I found 3 critical vulnerabilities in the auth module...",
    "tool_calls": [
      {
        "tool": "vulnerability_metrics",
        "result": { ... }
      }
    ]
  }
}
```

#### WebSocket Connection

**Endpoint**: `wss://api.aenealabs.com/api/v1/chat/ws`

Connect for real-time streaming responses.

---

## WebSocket APIs

### Job Streaming

**Endpoint**: `wss://api.aenealabs.com/api/v1/orchestrate/{job_id}/stream`

Connect to receive real-time job updates.

**Message Types**:

| Type | Description |
|------|-------------|
| `status` | Job status change |
| `progress` | Progress update |
| `log` | Log message |
| `result` | Job completion result |
| `error` | Error occurred |

**Example Message**:

```json
{
  "type": "progress",
  "data": {
    "job_id": "job-123",
    "progress": 75,
    "phase": "VALIDATE",
    "message": "Running sandbox tests"
  }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid severity value",
    "details": {
      "field": "severity",
      "value": "INVALID",
      "allowed": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or expired token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Temporary unavailability |

### Rate Limits

| Endpoint Category | Limit |
|-------------------|-------|
| Standard endpoints | 60 requests/minute |
| Critical operations (approve/reject) | 2 requests/minute |
| Admin operations | 5 requests/minute |

---

## Pagination

All list endpoints support pagination:

| Parameter | Default | Max |
|-----------|---------|-----|
| `limit` | 50 | 100 |
| `offset` | 0 | - |

**Response includes**:

```json
{
  "data": {
    "items": [...],
    "total": 150,
    "limit": 50,
    "offset": 0
  }
}
```

---

## Filtering and Sorting

### Filter Syntax

Multiple filters can be combined:

```
GET /vulnerabilities?severity=HIGH&status=OPEN&repository=my-repo
```

### Sort Syntax

```
GET /vulnerabilities?sort=created_at:desc
```

| Sort Direction |
|----------------|
| `asc` (ascending) |
| `desc` (descending) |

---

## SDK Support

### TypeScript/JavaScript SDK

```typescript
import { AuraClient } from '@aenealabs/aura-sdk';

const client = new AuraClient({
  baseUrl: 'https://api.aenealabs.com/api/v1',
  token: 'your-jwt-token'
});

// List vulnerabilities
const vulns = await client.vulnerabilities.list({
  severity: 'HIGH',
  status: 'OPEN'
});

// Approve a patch
await client.approvals.approve('approval-123', {
  comment: 'Reviewed and approved'
});
```

### React Hooks

```typescript
import { useApprovals, useVulnerabilities } from '@aenealabs/aura-sdk/react';

function Dashboard() {
  const { approvals, loading, error } = useApprovals();
  const { vulnerabilities } = useVulnerabilities({ severity: 'HIGH' });

  // ... render components
}
```

---

## API Versioning

The API uses URL-based versioning:

- Current version: `v1`
- Format: `/api/v1/...`

### Version Lifecycle

| Status | Description |
|--------|-------------|
| **Current** | Latest stable version |
| **Deprecated** | Still functional, migration recommended |
| **Sunset** | No longer available |

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Getting Started](./getting-started.md) | Platform basics |
| [Integrations](./integrations.md) | External tool connections |
| [Configuration](./configuration.md) | Settings reference |
| [Troubleshooting](./troubleshooting.md) | API issue resolution |

# API Reference Guide

This guide provides an overview of the Aura Platform API for developers integrating with the platform.

---

## API Overview

Aura exposes a RESTful API for programmatic access to platform features. The authoritative list of mounted routes and schemas is the OpenAPI document served by the API at `/docs`, `/redoc`, and `/openapi.json`.

> **Implementation status:** Sections marked **(Planned)** below describe routes that are not mounted today: the `/vulnerabilities` routes and the `/autonomy` routes. The chat assistant is served by a separate API Gateway + Lambda stack, not by the main API. Response bodies are returned without the `status`/`data` envelope shown in some examples; see [Response Format](#response-format).

### Base URLs

| Environment | URL |
|-------------|-----|
| Any environment | `https://{your-aura-api-host}/api/v1` |

Hostnames are deployment-specific (DEV and QA run in AWS Commercial Cloud). Health probes are served at the host root (`/health`).

### Authentication

API requests are authenticated with JWT tokens from AWS Cognito. Routers that declare the `get_current_user` dependency (approvals, repositories, OAuth connections, dashboards, and others) reject requests without a valid token; several routers (including settings, environments' admin views, team, onboarding, integrations, and model router) do not yet enforce authentication on every route.

**Headers Required**:

```
Authorization: Bearer <your-jwt-token>
Content-Type: application/json
```

### Response Format

**Current behavior:** successful responses return the endpoint's response model directly as JSON (no envelope). Errors return `{"error": "...", "status_code": 404, "path": "...", "request_id": "..."}`; request-validation failures return FastAPI's `422` body (`{"detail": [...]}`).

The `status`/`data` envelope used in the examples in this guide is a **Planned** format; read the examples for field meaning, not for the literal wrapper:

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
  "timestamp": "2025-12-16T12:00:00Z"
}
```

`/health` is a lightweight load-balancer check. Per-component detail is available at `GET /health/detailed`, and Kubernetes probes at `/health/live`, `/health/ready`, and `/health/startup` (the readiness and startup probes return `503` when the service is not ready).

---

### Vulnerabilities (Planned)

> No `/vulnerabilities` routes are mounted today. Vulnerability details reach users through approval requests (`GET /approvals`, `vulnerability` field). The routes below are a planned design.

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

Query parameters: `status` (`pending`, `approved`, `rejected`), `severity`, and `limit` (default 50, max 200). Approve, reject, and cancel require the `security-engineer` or `admin` role; reviewer identity comes from the token, and self-approval is rejected.

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

### Autonomy Policies (Planned)

> The autonomy policy router (`src/api/autonomy_endpoints.py`) exists in the codebase but is not mounted in `src/api/main.py`, so `/autonomy/*` routes return `404` today. HITL approval settings are available at `GET/PUT /settings/hitl`.

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

> The chat assistant is served by a separate API Gateway REST API and Lambda functions (`deploy/cloudformation/chat-assistant.yaml`, `src/lambda/chat/`), not by the main `/api/v1` service. Its base URL is the chat API Gateway endpoint configured in the console as `VITE_CHAT_API_URL`; when that variable is not set at build time, the console uses built-in mock chat responses.

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

**Endpoint**: the chat stack's API Gateway WebSocket URL (configured in the console as `VITE_CHAT_WS_URL`)

Connect for real-time streaming responses.

---

## WebSocket APIs

### Job Streaming

**Endpoint**: `wss://{your-aura-api-host}/api/v1/orchestrate/{job_id}/stream`

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

**Current format:**

```json
{
  "error": "Invalid severity value",
  "status_code": 400,
  "path": "/api/v1/approvals",
  "request_id": "6f1c..."
}
```

The structured format below, and the string error codes in the next table, are **Planned**:

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
| Public endpoints | 100 requests/minute |
| Standard endpoints | 60 requests/minute |
| Sensitive operations | 10 requests/minute |
| Admin operations | 5 requests/minute |
| Critical operations | 2 requests/minute |
| Webhook endpoints | 200 requests/minute |

Limits apply only to routes that declare a rate-limit dependency, and counters are kept in memory per API replica.

---

## Pagination

**Current behavior:** pagination parameters are endpoint-specific; many list routes accept only `limit` and return the full result set up to that limit (for example `GET /approvals?limit=50`). The `limit`/`offset` scheme below is **Planned** as a uniform convention.

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

> The `/vulnerabilities` examples in this section are **Planned**. Filters on implemented routes are endpoint-specific query parameters listed in `/docs`; there is no generic `sort` parameter.

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

The TypeScript SDK lives in `sdk/typescript/` (package `@aenealabs/aura-sdk`, version 0.2.0). The client exposes `extension`, `approvals`, `incidents`, and `settings` APIs; there is no `vulnerabilities` client because no `/vulnerabilities` route exists. Authenticate with `jwtToken` (the `apiKey` option sends an `X-API-Key` header that the API does not accept).

```typescript
import { AuraClient } from '@aenealabs/aura-sdk';

const client = new AuraClient({
  baseUrl: 'https://{your-aura-api-host}',
  jwtToken: 'your-jwt-token'
});

// List approval requests
const approvals = await client.approvals.list();

// Approve a patch
await client.approvals.approve('approval-123', {
  comment: 'Reviewed and approved'
});
```

### React Hooks

The hooks are exported from `@aenealabs/aura-sdk/react`. `useVulnerabilities` reads findings from the IDE extension routes (`/api/v1/extension/findings`), which currently return placeholder pattern-matching results.

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

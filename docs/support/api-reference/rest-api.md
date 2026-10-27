# REST API Reference

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document describes the Project Aura REST API. The authoritative, always-current list of mounted routes, parameters, and schemas is the OpenAPI document the API server generates at `/docs`, `/redoc`, and `/openapi.json`.

**Base URL:** `https://{your-aura-host}/api/v1` (all application routes use the `/api/v1` prefix; health probes are at the host root)

### Implementation Status

Sections below are labeled. **Implemented** sections match routes mounted in `src/api/main.py`. **Planned** sections describe API design that has no route today; calling those paths returns `404`.

| Section | Status | Implemented alternative |
|---------|--------|-------------------------|
| Authentication (`/auth/login`, `/auth/refresh`, `/auth/logout`) | Planned | Cognito Hosted UI sign-in; `GET /api/v1/auth/me`, `GET /api/v1/auth/validate` |
| Repositories | Implemented (with differences noted) | `GET/POST /repositories`, `GET/PUT/DELETE /repositories/{id}`, `POST /repositories/{id}/sync`, `POST /repositories/ingest` |
| Vulnerabilities | Planned | Findings surface through approvals (`vulnerability` field). The IDE extension routes (`/api/v1/extension/scan`, `/findings`, `/patches`) exist but currently run placeholder pattern-matching analysis and generated patches, not the agent pipeline |
| Patches | Planned | Patch review and decisions use `/api/v1/approvals` |
| Approvals | Implemented | `GET /approvals`, `GET /approvals/stats`, `GET /approvals/{id}`, `POST /approvals/{id}/approve`, `/reject`, `/cancel` |
| Agents (`/agents/status`, `/agents/executions`) | Planned | `GET /api/v1/agents` (agent registry), `GET /api/v1/orchestrate` (orchestration jobs) |
| `GET /health` | Implemented | Also `/health/live`, `/health/ready`, `/health/startup`, `/health/detailed` |
| `GET /metrics` | Planned on the API server | The agent job server exposes Prometheus `/metrics` |
| Settings (`/settings/hitl`) | Implemented (schema differs; see below) | `GET/PUT /api/v1/settings/hitl` |
| Webhook management (`/webhooks`) | Planned | Inbound GitHub webhook receiver: `POST /webhook/github` |

### Authentication Coverage

Authentication uses Amazon Cognito JWTs (`Authorization: Bearer <token>`), validated in `src/api/auth.py`. Routers that declare the `get_current_user` dependency (for example approvals, repositories, OAuth connections, dashboards, guardrails, security alerts) reject requests without a valid token. Several mounted routers do not yet declare an authentication dependency on their routes, including settings, team, onboarding, integrations, model router, traces, ticketing, and the agent registry; access to those routes depends on network-level controls in front of the API. Role checks are enforced only where a route declares them (for example approve/reject/cancel require the `security-engineer` or `admin` role).

---

## Authentication Endpoints

### POST /auth/login (Planned)

> Not implemented. Users sign in through the Cognito Hosted UI from the web console; the API has no password-login route.

Authenticate with email and password.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "your-password",
  "mfa_code": "123456"  // Optional, required if MFA enabled
}
```

**Response:**

```json
{
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": "user-12345",
      "email": "user@example.com",
      "name": "John Doe",
      "roles": ["developer"]
    }
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid credentials |
| 401 | MFA required |
| 429 | Too many login attempts |

---

### POST /auth/refresh (Planned)

> Not implemented on the API. Token refresh is handled by the console against Cognito.

Refresh an expired access token.

**Request:**

```json
{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4..."
}
```

**Response:**

```json
{
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  }
}
```

---

### POST /auth/logout (Planned)

> Not implemented on the API.

Invalidate current session and refresh token.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "data": {
    "message": "Logged out successfully"
  }
}
```

---

## Repository Endpoints

### GET /repositories

List all repositories accessible to the current user. **Implemented** (requires authentication).

> **Current behavior:** supported query parameters are `status` and `provider`. The response is a JSON array of repository objects with the fields `repository_id`, `name`, `provider`, `clone_url`, `branch`, `languages`, `scan_frequency`, `status`, `last_ingestion_at`, `file_count`, `entity_count`, `webhook_active`, `created_at`, and `updated_at`. The `per_page`, `cursor`, and `q` parameters, vulnerability counts, and the `data`/`pagination` wrapper shown below are **Planned**. When AWS credentials are unavailable and `AURA_DEV_MOCK_ON_AWS_ERROR` is not set to `false`, this route returns seeded demo repositories instead of an error.

**Planned query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `per_page` | integer | 20 | Results per page (max 100) |
| `cursor` | string | - | Pagination cursor |
| `status` | string | - | Filter by status: `active`, `inactive`, `scanning` |
| `q` | string | - | Search by name |

**Response:**

```json
{
  "data": [
    {
      "id": "repo-a1b2c3d4",
      "name": "backend-api",
      "url": "https://github.com/acme/backend-api",
      "default_branch": "main",
      "status": "active",
      "last_scan_at": "2026-01-19T10:30:00Z",
      "vulnerability_counts": {
        "critical": 2,
        "high": 5,
        "medium": 12,
        "low": 8
      },
      "created_at": "2025-12-01T09:00:00Z",
      "updated_at": "2026-01-19T10:30:00Z"
    }
  ],
  "pagination": {
    "total": 15,
    "per_page": 20,
    "cursor": null
  }
}
```

---

### POST /repositories

Connect a new repository. **Implemented** (requires authentication).

> **Current behavior:** the request body accepts `name` (required), either `connection_id` + `provider_repo_id` (OAuth) or `clone_url` + `token` (manual; GitHub and GitLab URLs only), plus `branch` (default `main`), `languages`, `scan_frequency` (`on_push`, `daily`, `weekly`, `manual`), `exclude_patterns`, and `enable_webhook`. The nested `credentials`/`scan_config` shape below is **Planned**.

**Planned request shape:**

```json
{
  "name": "backend-api",
  "url": "https://github.com/acme/backend-api",
  "default_branch": "main",
  "credentials": {
    "type": "oauth",
    "integration_id": "github-12345"
  },
  "scan_config": {
    "enabled": true,
    "schedule": "0 2 * * *",
    "languages": ["python", "javascript"]
  }
}
```

**Response:**

```json
{
  "data": {
    "id": "repo-a1b2c3d4",
    "name": "backend-api",
    "url": "https://github.com/acme/backend-api",
    "status": "pending_scan",
    "created_at": "2026-01-19T12:00:00Z"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 201 | Repository created |
| 400 | Invalid request |
| 409 | Repository already connected |

---

### GET /repositories/{id}

Get detailed information about a repository. **Implemented**; returns the same repository object as the list route. The `vulnerability_counts`, `statistics`, and `team` fields below are **Planned**.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Repository ID |

**Response:**

```json
{
  "data": {
    "id": "repo-a1b2c3d4",
    "name": "backend-api",
    "url": "https://github.com/acme/backend-api",
    "default_branch": "main",
    "status": "active",
    "provider": "github",
    "last_scan_at": "2026-01-19T10:30:00Z",
    "scan_config": {
      "enabled": true,
      "schedule": "0 2 * * *",
      "languages": ["python", "javascript"]
    },
    "vulnerability_counts": {
      "critical": 2,
      "high": 5,
      "medium": 12,
      "low": 8
    },
    "statistics": {
      "total_lines_of_code": 45000,
      "total_files": 320,
      "last_commit": "2026-01-18T15:45:00Z"
    },
    "team": {
      "id": "team-56789",
      "name": "Platform Team"
    },
    "created_at": "2025-12-01T09:00:00Z",
    "updated_at": "2026-01-19T10:30:00Z"
  }
}
```

---

### PATCH /repositories/{id} (Planned)

> Not implemented as `PATCH`. Use `PUT /api/v1/repositories/{id}` with the same body as `POST /repositories`.

Update repository settings.

**Request:**

```json
{
  "name": "backend-api-v2",
  "default_branch": "develop",
  "scan_config": {
    "enabled": true,
    "schedule": "0 */6 * * *"
  }
}
```

**Response:**

```json
{
  "data": {
    "id": "repo-a1b2c3d4",
    "name": "backend-api-v2",
    "updated_at": "2026-01-19T12:30:00Z"
  }
}
```

---

### DELETE /repositories/{id}

Disconnect a repository.

**Response:**

```json
{
  "data": {
    "message": "Repository disconnected successfully"
  }
}
```

---

### POST /repositories/{id}/scan (Planned)

> Not implemented. To re-ingest a repository use `POST /api/v1/repositories/{id}/sync`; to start ingestion jobs for several repositories use `POST /api/v1/repositories/ingest` and poll `GET /api/v1/repositories/ingestion-status`.

Trigger an immediate vulnerability scan.

**Request:**

```json
{
  "branch": "main",
  "full_scan": false,
  "notify_on_complete": true
}
```

**Response:**

```json
{
  "data": {
    "scan_id": "scan-xyz123",
    "status": "queued",
    "estimated_duration_seconds": 300
  }
}
```

---

## Vulnerability Endpoints (Planned)

> No `/vulnerabilities` routes exist today. Vulnerability details appear in the `vulnerability` field of approval requests (`/api/v1/approvals`). The IDE extension findings routes (`/api/v1/extension/findings`) return results from a placeholder pattern-matching analyzer. The routes in this section are a planned design.

### GET /vulnerabilities

List vulnerabilities across all repositories.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `per_page` | integer | 20 | Results per page |
| `cursor` | string | - | Pagination cursor |
| `repository_id` | string | - | Filter by repository |
| `severity` | string | - | Filter: `critical`, `high`, `medium`, `low` |
| `status` | string | - | Filter: `open`, `in_progress`, `resolved`, `ignored` |
| `cve_id` | string | - | Filter by CVE ID |
| `q` | string | - | Search in title/description |

**Response:**

```json
{
  "data": [
    {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "description": "User input not properly sanitized in database query",
      "severity": "critical",
      "status": "open",
      "cve_id": "CVE-2026-1234",
      "cwes": ["CWE-89"],
      "cvss_score": 9.8,
      "repository": {
        "id": "repo-a1b2c3d4",
        "name": "backend-api"
      },
      "location": {
        "file": "src/services/user_service.py",
        "line_start": 45,
        "line_end": 52,
        "function": "get_user_by_id"
      },
      "patch": {
        "id": "patch-67890",
        "status": "pending_approval"
      },
      "detected_at": "2026-01-18T08:00:00Z",
      "created_at": "2026-01-18T08:00:00Z"
    }
  ],
  "pagination": {
    "total": 45,
    "per_page": 20,
    "cursor": "eyJpZCI6InZ1bG4tMTIzNDUifQ=="
  }
}
```

---

### GET /vulnerabilities/{id}

Get detailed vulnerability information.

**Response:**

```json
{
  "data": {
    "id": "vuln-12345",
    "title": "SQL Injection in User Query",
    "description": "User input from the `user_id` parameter is concatenated directly into a SQL query without sanitization, allowing SQL injection attacks.",
    "severity": "critical",
    "status": "open",
    "cve_id": "CVE-2026-1234",
    "cwes": ["CWE-89"],
    "cvss_score": 9.8,
    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api",
      "url": "https://github.com/acme/backend-api"
    },
    "location": {
      "file": "src/services/user_service.py",
      "line_start": 45,
      "line_end": 52,
      "function": "get_user_by_id",
      "code_snippet": "def get_user_by_id(user_id):\n    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n    return db.execute(query)"
    },
    "remediation": {
      "recommendation": "Use parameterized queries instead of string concatenation",
      "references": [
        "https://owasp.org/www-community/attacks/SQL_Injection",
        "https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html"
      ]
    },
    "patch": {
      "id": "patch-67890",
      "status": "pending_approval",
      "generated_at": "2026-01-18T09:00:00Z"
    },
    "scan": {
      "id": "scan-abc123",
      "completed_at": "2026-01-18T08:00:00Z"
    },
    "history": [
      {
        "timestamp": "2026-01-18T08:00:00Z",
        "action": "detected",
        "actor": "system"
      },
      {
        "timestamp": "2026-01-18T09:00:00Z",
        "action": "patch_generated",
        "actor": "coder-agent"
      }
    ],
    "detected_at": "2026-01-18T08:00:00Z",
    "created_at": "2026-01-18T08:00:00Z",
    "updated_at": "2026-01-18T09:00:00Z"
  }
}
```

---

### PATCH /vulnerabilities/{id}

Update vulnerability status.

**Request:**

```json
{
  "status": "ignored",
  "ignore_reason": "false_positive",
  "comment": "This is a test file, not production code"
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `open` | Vulnerability detected, no action taken |
| `in_progress` | Patch being generated or tested |
| `resolved` | Vulnerability fixed and deployed |
| `ignored` | Marked as false positive or accepted risk |

**Ignore Reasons:**

| Reason | Description |
|--------|-------------|
| `false_positive` | Detection was incorrect |
| `accepted_risk` | Risk acknowledged and accepted |
| `not_applicable` | Code path never executed |
| `compensating_control` | Mitigated by other means |

---

## Patch Endpoints (Planned)

> No `/patches` routes exist today. Generated patches are reviewed and decided through the approval routes below (`POST /api/v1/approvals/{id}/approve` and `/reject`). Deployment after approval is driven by the HITL workflow, not by a `/patches/{id}/deploy` call. The routes in this section are a planned design.

### GET /patches

List all generated patches.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `per_page` | integer | 20 | Results per page |
| `cursor` | string | - | Pagination cursor |
| `vulnerability_id` | string | - | Filter by vulnerability |
| `repository_id` | string | - | Filter by repository |
| `status` | string | - | Filter: `pending`, `approved`, `rejected`, `deployed` |

**Response:**

```json
{
  "data": [
    {
      "id": "patch-67890",
      "vulnerability": {
        "id": "vuln-12345",
        "title": "SQL Injection in User Query"
      },
      "repository": {
        "id": "repo-a1b2c3d4",
        "name": "backend-api"
      },
      "status": "pending_approval",
      "confidence_score": 0.95,
      "sandbox_results": {
        "syntax_check": "passed",
        "unit_tests": "passed",
        "security_scan": "passed",
        "performance": "passed"
      },
      "generated_at": "2026-01-18T09:00:00Z",
      "created_at": "2026-01-18T09:00:00Z"
    }
  ]
}
```

---

### GET /patches/{id}

Get detailed patch information including diff.

**Response:**

```json
{
  "data": {
    "id": "patch-67890",
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "severity": "critical"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "status": "pending_approval",
    "confidence_score": 0.95,
    "files_changed": [
      {
        "path": "src/services/user_service.py",
        "additions": 3,
        "deletions": 2,
        "diff": "@@ -43,5 +43,6 @@\n def get_user_by_id(user_id):\n-    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n-    return db.execute(query)\n+    query = \"SELECT * FROM users WHERE id = %s\"\n+    return db.execute(query, (user_id,))"
      }
    ],
    "sandbox_results": {
      "syntax_check": {
        "status": "passed",
        "details": "Code parses successfully"
      },
      "unit_tests": {
        "status": "passed",
        "passed": 45,
        "failed": 0,
        "skipped": 2
      },
      "security_scan": {
        "status": "passed",
        "details": "No new vulnerabilities introduced"
      },
      "performance": {
        "status": "passed",
        "latency_change_percent": -2.5
      }
    },
    "agent_reasoning": "Replaced string concatenation with parameterized query using psycopg2's native parameter binding. This prevents SQL injection by ensuring user input is properly escaped.",
    "generated_by": {
      "agent": "coder-agent",
      "model": "claude-3.5-sonnet",
      "context_tokens_used": 4500
    },
    "approval": null,
    "generated_at": "2026-01-18T09:00:00Z",
    "created_at": "2026-01-18T09:00:00Z",
    "updated_at": "2026-01-18T09:30:00Z"
  }
}
```

---

### POST /patches/{id}/approve

Approve a patch for deployment.

**Request:**

```json
{
  "comment": "Reviewed and approved. Parameterized query correctly implemented.",
  "deploy_immediately": false,
  "target_environment": "staging"
}
```

**Response:**

```json
{
  "data": {
    "id": "patch-67890",
    "status": "approved",
    "approval": {
      "approved_by": {
        "id": "user-12345",
        "name": "John Doe"
      },
      "approved_at": "2026-01-19T12:00:00Z",
      "comment": "Reviewed and approved. Parameterized query correctly implemented."
    }
  }
}
```

---

### POST /patches/{id}/reject

Reject a patch.

**Request:**

```json
{
  "reason": "incomplete_fix",
  "comment": "The fix addresses the main query but there's another vulnerable query at line 78."
}
```

**Rejection Reasons:**

| Reason | Description |
|--------|-------------|
| `incomplete_fix` | Does not fully address vulnerability |
| `introduces_bug` | Creates functional issues |
| `poor_implementation` | Better approach exists |
| `security_concern` | Introduces new security issues |
| `other` | Other reason (comment required) |

---

### POST /patches/{id}/deploy

Deploy an approved patch.

**Request:**

```json
{
  "target_branch": "main",
  "create_pull_request": true,
  "reviewers": ["user-23456", "user-34567"]
}
```

**Response:**

```json
{
  "data": {
    "deployment_id": "deploy-abc123",
    "status": "in_progress",
    "pull_request": {
      "url": "https://github.com/acme/backend-api/pull/456",
      "number": 456
    }
  }
}
```

---

## Approval Workflow Endpoints

All approval routes are **Implemented**, require authentication, and are scoped to the caller's organization. Approve, reject, and cancel additionally require the `security-engineer` or `admin` role, take the reviewer identity from the token, and block self-approval.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/approvals` | List approval requests |
| GET | `/api/v1/approvals/stats` | Counts by status |
| GET | `/api/v1/approvals/{id}` | Approval detail, including patch diff and explainability evidence |
| POST | `/api/v1/approvals/{id}/approve` | Approve; body `{"comment": "optional"}` |
| POST | `/api/v1/approvals/{id}/reject` | Reject; body `{"reason": "required"}` |
| POST | `/api/v1/approvals/{id}/cancel` | Cancel a pending request |

### GET /approvals

List approval requests.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter: `pending`, `approved`, `rejected` |
| `severity` | string | - | Filter: `critical`, `high`, `medium`, `low` |
| `limit` | integer | 50 | Maximum results (1-200) |

**Current response shape:** `{"approvals": [...], "total": n, "pending": n, "approved": n, "rejected": n}`, where each item has `id`, `title`, `vulnerability`, `patch`, `status`, `severity`, `created_at`, `requested_by`, and the approval/rejection actor and timestamp fields.

**Planned response shape:**

```json
{
  "data": [
    {
      "id": "approval-xyz789",
      "type": "patch_approval",
      "patch": {
        "id": "patch-67890",
        "vulnerability_title": "SQL Injection in User Query"
      },
      "repository": {
        "id": "repo-a1b2c3d4",
        "name": "backend-api"
      },
      "status": "pending",
      "required_role": "security_admin",
      "expires_at": "2026-01-20T09:00:00Z",
      "created_at": "2026-01-19T09:00:00Z"
    }
  ]
}
```

---

### GET /approvals/{id}

Get approval details. **Implemented**; the exact fields are defined by `ApprovalDetailResponse` in `/docs`. The `policy` and `notifications_sent` fields below are **Planned**.

**Response:**

```json
{
  "data": {
    "id": "approval-xyz789",
    "type": "patch_approval",
    "patch": {
      "id": "patch-67890",
      "vulnerability": {
        "id": "vuln-12345",
        "title": "SQL Injection in User Query",
        "severity": "critical"
      },
      "diff_preview": "@@ -43,5 +43,6 @@\n-    query = f\"SELECT...",
      "sandbox_results": {
        "all_passed": true
      }
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "status": "pending",
    "required_role": "security_admin",
    "policy": {
      "name": "CMMC_LEVEL_3",
      "approval_required_for": ["critical", "high"]
    },
    "notifications_sent": [
      {
        "channel": "email",
        "sent_at": "2026-01-19T09:00:00Z"
      },
      {
        "channel": "slack",
        "sent_at": "2026-01-19T09:00:00Z"
      }
    ],
    "expires_at": "2026-01-20T09:00:00Z",
    "created_at": "2026-01-19T09:00:00Z"
  }
}
```

---

## Agent Endpoints (Planned)

> `/agents/status` and `/agents/executions` are not implemented. The implemented agent-registry routes are under `GET /api/v1/agents` (`/internal`, `/external`, `/marketplace`, `/{agent_id}`, `/{agent_id}/metrics`); their connection-test route currently returns simulated latency and success values. Orchestration jobs are listed at `GET /api/v1/orchestrate`.

### GET /agents/status

Get status of all AI agents.

**Response:**

```json
{
  "data": {
    "orchestrator": {
      "status": "healthy",
      "active_tasks": 3,
      "queue_depth": 5,
      "last_heartbeat": "2026-01-19T12:00:00Z"
    },
    "coder": {
      "status": "healthy",
      "active_tasks": 1,
      "average_response_time_ms": 45000,
      "last_heartbeat": "2026-01-19T12:00:00Z"
    },
    "reviewer": {
      "status": "healthy",
      "active_tasks": 2,
      "average_response_time_ms": 15000,
      "last_heartbeat": "2026-01-19T12:00:00Z"
    },
    "validator": {
      "status": "healthy",
      "active_sandboxes": 1,
      "average_test_duration_ms": 180000,
      "last_heartbeat": "2026-01-19T12:00:00Z"
    }
  }
}
```

---

### GET /agents/executions

List recent agent executions.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `per_page` | integer | 20 | Results per page |
| `agent` | string | - | Filter by agent: `coder`, `reviewer`, `validator` |
| `status` | string | - | Filter: `running`, `completed`, `failed`, `timeout` |

**Response:**

```json
{
  "data": [
    {
      "id": "exec-12345",
      "agent": "coder",
      "task_type": "patch_generation",
      "status": "completed",
      "vulnerability_id": "vuln-12345",
      "started_at": "2026-01-19T11:55:00Z",
      "completed_at": "2026-01-19T11:55:45Z",
      "duration_ms": 45000,
      "tokens_used": 4500
    }
  ]
}
```

---

## System Endpoints

### GET /health

System health check (no authentication required). **Implemented.** Kubernetes probes are also available at `/health/live`, `/health/ready`, and `/health/startup`, and component detail at `/health/detailed`.

> **Current behavior:** `/health` is a lightweight ALB check that returns a status and timestamp. Per-component status is reported by `/health/detailed`. The response below is illustrative.

**Response:**

```json
{
  "status": "healthy",
  "version": "1.6.0",
  "components": {
    "api": "healthy",
    "agents": "healthy",
    "neptune": "healthy",
    "opensearch": "healthy",
    "bedrock": "healthy"
  },
  "timestamp": "2026-01-19T12:00:00Z"
}
```

---

### GET /metrics (Planned)

> Not implemented on the API server. Dashboard metrics are available from the `/api/v1/dashboard/metrics/*` and `/api/v1/dashboards` routes.

Get system metrics (requires admin role).

**Response:**

```json
{
  "data": {
    "api": {
      "requests_total": 1250000,
      "requests_per_minute": 450,
      "error_rate_percent": 0.02,
      "latency_p50_ms": 45,
      "latency_p95_ms": 180,
      "latency_p99_ms": 350
    },
    "vulnerabilities": {
      "total_detected": 1250,
      "total_resolved": 980,
      "mttr_hours": 3.5
    },
    "patches": {
      "total_generated": 1100,
      "approval_rate_percent": 92,
      "deployment_success_rate_percent": 99.5
    },
    "agents": {
      "total_executions_24h": 450,
      "success_rate_percent": 98.5
    }
  }
}
```

---

## Settings Endpoints

### GET /settings/hitl

Get HITL configuration. **Implemented.**

> **Current behavior:** the response fields are `require_approval_for_patches`, `require_approval_for_deployments`, `auto_approve_minor_patches`, `approval_timeout_hours` (1-168), `min_approvers` (1-5), `notify_on_approval_request`, and `notify_on_approval_timeout`, returned without a `data` wrapper. The `autonomy_level`, `policy_preset`, and per-severity `required_approvers` fields below are **Planned** for this route (autonomy policies are managed by a separate, not-yet-mounted autonomy router).

**Planned response shape:**

```json
{
  "data": {
    "autonomy_level": "HITL_CRITICAL",
    "policy_preset": "SOX_COMPLIANCE",
    "approval_timeout_hours": 24,
    "auto_escalation_enabled": true,
    "notification_channels": ["email", "slack"],
    "required_approvers": {
      "critical": 2,
      "high": 1,
      "medium": 0,
      "low": 0
    }
  }
}
```

---

### PUT /settings/hitl

Update HITL configuration. **Implemented**, with the same body fields as the `GET` response. The route applies the admin rate-limit tier but does not currently enforce authentication or an admin role check (enforcement is **Planned**).

**Request:**

```json
{
  "autonomy_level": "FULL_HITL",
  "policy_preset": "CMMC_LEVEL_3",
  "approval_timeout_hours": 48,
  "auto_escalation_enabled": true,
  "notification_channels": ["email", "slack", "teams"]
}
```

---

## Webhook Management (Planned)

> Outbound webhook subscription management is not implemented; there are no `/webhooks` routes. The implemented webhook route is the inbound GitHub receiver at `POST /webhook/github`.

### GET /webhooks

List configured webhooks.

### POST /webhooks

Create a new webhook subscription.

**Request:**

```json
{
  "url": "https://example.com/aura-webhook",
  "events": ["vulnerability.detected", "patch.approved", "patch.deployed"],
  "secret": "your-webhook-secret",
  "enabled": true
}
```

For complete webhook documentation, see [Webhooks](./webhooks.md).

---

## API Changelog

### v1.0.0 (January 2026)

- Initial release of the REST API under `/api/v1`
- Sections marked **Planned** above are not yet implemented

---

## Related Documentation

- [API Reference Index](./index.md)
- [GraphQL API](./graphql-api.md) (Planned)
- [Webhooks](./webhooks.md)
- [Common Issues](../troubleshooting/common-issues.md)

---

*Last updated: January 2026 | Version 1.0*

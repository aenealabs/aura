# REST API Reference

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document provides the complete REST API specification for Project Aura. All endpoints require authentication unless otherwise noted.

**Base URL:** `https://api.aenealabs.com/v1`

---

## Authentication Endpoints

### POST /auth/login

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

### POST /auth/refresh

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

### POST /auth/logout

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

List all repositories accessible to the current user.

**Query Parameters:**

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

Connect a new repository.

**Request:**

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

Get detailed information about a repository.

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

### PATCH /repositories/{id}

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

### POST /repositories/{id}/scan

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

## Vulnerability Endpoints

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

## Patch Endpoints

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

### GET /approvals

List pending approvals.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `per_page` | integer | 20 | Results per page |
| `status` | string | `pending` | Filter: `pending`, `approved`, `rejected`, `expired` |
| `repository_id` | string | - | Filter by repository |

**Response:**

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

Get approval details.

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

## Agent Endpoints

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

System health check (no authentication required).

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

### GET /metrics

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

Get HITL configuration.

**Response:**

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

Update HITL configuration (requires admin role).

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

## Webhook Management

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

- Initial stable release
- All endpoints documented and stable

---

## Related Documentation

- [API Reference Index](./index.md)
- [GraphQL API](./graphql-api.md)
- [Webhooks](./webhooks.md)
- [Common Issues](../troubleshooting/common-issues.md)

---

*Last updated: January 2026 | Version 1.0*

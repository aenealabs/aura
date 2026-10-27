# API Reference

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This section provides API documentation for integrating with Project Aura. The API enables programmatic access to repository onboarding, HITL approval workflows, platform settings, dashboards, and system configuration.

> **Implementation status:** The API is a FastAPI REST service (`src/api/main.py`) served under the `/api/v1` path prefix. Interactive OpenAPI documentation for every mounted route is generated at `/docs` (Swagger UI), `/redoc`, and `/openapi.json`, and is the authoritative endpoint list. Some capabilities described in this section are planned rather than shipped: there is no GraphQL API, no password-login endpoint, no top-level `/vulnerabilities` or `/patches` resource, no outbound-webhook subscription API, and no uniform response envelope. Each page marks those items as **Planned**.

---

## API Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [REST API Reference](./rest-api.md) | Full REST endpoint specifications | Developers, Integration Engineers |
| [GraphQL API](./graphql-api.md) | GraphQL schema and operations (**Planned -- not implemented**) | Developers |
| [Webhooks](./webhooks.md) | Event notifications and payloads | Developers, Operations |

---

## Quick Start

### Authentication

Authenticated API requests require a valid Amazon Cognito JWT in the Authorization header (validated against the user pool JWKS in `src/api/auth.py`). Health probes (`/health`, `/health/live`, `/health/ready`, `/health/startup`) do not require a token. Note that a number of routers do not yet enforce authentication on every route; see the [REST API Reference](./rest-api.md#authentication-coverage).

```bash
curl -X GET https://{your-aura-host}/api/v1/repositories \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json"
```

### Obtaining an Access Token

Access tokens are issued by Amazon Cognito. Users sign in through the Cognito Hosted UI (OAuth 2.0 authorization-code flow) from the web console; the console stores the resulting tokens and sends them as `Bearer` tokens. The API itself has no email/password login endpoint (a `POST /auth/login` endpoint is **Planned**). To confirm a token is valid:

```bash
# Returns {"valid": true, "user": {...}} for a valid token, {"valid": false} otherwise
curl -X GET https://{your-aura-host}/api/v1/auth/validate \
  -H "Authorization: Bearer ${AURA_TOKEN}"

# Returns the caller's sub, email, name, roles, and groups (401 without a valid token)
curl -X GET https://{your-aura-host}/api/v1/auth/me \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

### Base URL

All application routes are served under the `/api/v1` path prefix of the Aura API host (for example `https://{your-aura-host}/api/v1`). Health probes are served at the host root (`/health`). Hostnames are deployment-specific; ask your administrator for the API host of your DEV, QA, or self-hosted environment.

---

## API Design Principles

### RESTful Conventions

Project Aura's API follows REST conventions:

| HTTP Method | Usage | Example |
|-------------|-------|---------|
| GET | Retrieve resource(s) | `GET /repositories` |
| POST | Create resource | `POST /repositories` |
| PUT | Replace or update resource | `PUT /repositories/{id}` |
| DELETE | Remove resource | `DELETE /repositories/{id}` |

`PATCH` is not currently used by any route; updates use `PUT`.

### Response Format

All responses are JSON. **Current behavior:** successful responses return the resource or list directly (the endpoint's Pydantic response model), without a `data`/`meta` wrapper. Errors raised by an endpoint return:

```json
{
  "error": "Approval not found",
  "status_code": 404,
  "path": "/api/v1/approvals/appr-123",
  "request_id": "6f1c..."
}
```

Request-validation failures return FastAPI's standard `422` body (`{"detail": [...]}`), and unexpected server errors return `{"error": "Internal server error", "message": "...", "path": "...", "request_id": "..."}`.

**Planned envelope format (not implemented):** the examples below describe a planned uniform envelope.

**Success Response:**

```json
{
  "data": {
    "id": "repo-a1b2c3d4",
    "name": "my-repository",
    "url": "https://github.com/org/repo"
  },
  "meta": {
    "request_id": "req-12345",
    "timestamp": "2026-01-19T12:00:00Z"
  }
}
```

**List Response:**

```json
{
  "data": [
    { "id": "repo-1", "name": "repo-one" },
    { "id": "repo-2", "name": "repo-two" }
  ],
  "meta": {
    "request_id": "req-12345",
    "timestamp": "2026-01-19T12:00:00Z"
  },
  "pagination": {
    "total": 42,
    "page": 1,
    "per_page": 20,
    "total_pages": 3
  }
}
```

**Error Response:**

```json
{
  "error": {
    "code": "AURA-API-002",
    "message": "Invalid request payload",
    "details": [
      {
        "field": "url",
        "message": "Must be a valid URL"
      }
    ]
  },
  "meta": {
    "request_id": "req-12345",
    "timestamp": "2026-01-19T12:00:00Z"
  }
}
```

---

## Common Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | Bearer token: `Bearer {token}` |
| `Content-Type` | Yes (POST/PUT/PATCH) | `application/json` |
| `Accept` | No | `application/json` (default) |
| `X-Request-ID` | No | Client-provided request ID for tracing (echoed back; generated when absent) |

Organization context is taken from the authenticated token; an `X-Org-ID` override header is not supported.

---

## Pagination

**Current behavior:** there is no uniform pagination scheme. List endpoints accept endpoint-specific parameters such as `limit` (for example `GET /api/v1/approvals?limit=50`); check each route in `/docs`. The cursor-based scheme below is **Planned**.

```bash
# First page
curl -X GET "https://api.aenealabs.com/v1/repositories?per_page=20" \
  -H "Authorization: Bearer ${AURA_TOKEN}"

# Next page using cursor
curl -X GET "https://api.aenealabs.com/v1/repositories?per_page=20&cursor=eyJpZCI6InJlcG8tMjAifQ==" \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

**Pagination Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `per_page` | integer | 20 | Items per page (max: 100) |
| `cursor` | string | - | Cursor for next page |
| `sort` | string | `created_at` | Sort field |
| `order` | string | `desc` | Sort order: `asc` or `desc` |

---

## Rate Limiting

Rate limits are applied per endpoint category by `src/services/api_rate_limiter.py` (sliding window, keyed by user when available and otherwise by client IP). Limits are not tied to subscription plan. Counters are held in memory in each API process, so limits apply per replica rather than cluster-wide.

| Endpoint tier | Default limit | Window |
|---------------|---------------|--------|
| Public | 100 | 1 minute |
| Standard (authenticated) | 60 | 1 minute |
| Sensitive | 10 | 1 minute |
| Admin | 5 | 1 minute |
| Critical (HITL, deployments) | 2 | 1 minute |
| Webhook | 200 | 1 minute |

Not every router applies a rate-limit dependency; routes without one are not rate limited by the API process.

**Rate Limit Headers:**

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1737288060
X-RateLimit-Tier: standard
```

A `429` response includes a `Retry-After` header.

**Handling Rate Limits:**

```python
import time
import requests

def api_call_with_backoff(url, headers, max_retries=5):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)

        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            time.sleep(retry_after * (2 ** attempt))
            continue

        return response

    raise Exception("Rate limit exceeded after retries")
```

---

## Filtering and Searching

**Current behavior:** filters are endpoint-specific query parameters (for example `GET /api/v1/approvals?status=pending&severity=critical`, `GET /api/v1/repositories?status=active&provider=github`). The `/vulnerabilities` examples below are **Planned**; no `/vulnerabilities` route exists today.

```bash
# Filter by field
curl -X GET "https://api.aenealabs.com/v1/vulnerabilities?severity=critical" \
  -H "Authorization: Bearer ${AURA_TOKEN}"

# Multiple filters (AND)
curl -X GET "https://api.aenealabs.com/v1/vulnerabilities?severity=critical&status=open" \
  -H "Authorization: Bearer ${AURA_TOKEN}"

# Search across fields
curl -X GET "https://api.aenealabs.com/v1/vulnerabilities?q=sql+injection" \
  -H "Authorization: Bearer ${AURA_TOKEN}"

# Date range
curl -X GET "https://api.aenealabs.com/v1/vulnerabilities?created_after=2026-01-01&created_before=2026-01-31" \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

---

## API Versioning

The API version is included in the URL path (`/api/v1/`). Breaking changes require a new major version. `v1` is the only version served; there is no `v0` route set.

**Deprecation Headers (Planned):**

The API does not emit deprecation headers today. When endpoints are deprecated in the future, the planned headers are:

```
Deprecation: true
Sunset: Sat, 01 Jun 2026 00:00:00 GMT
Link: <https://api.aenealabs.com/v1/new-endpoint>; rel="successor-version"
```

---

## Error Codes

**Current behavior:** errors are identified by HTTP status code and the `error` message string. The `AURA-*` error codes below are **Planned** and are not returned by the API today.

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AURA-AUTH-001 | 401 | Invalid or expired token |
| AURA-AUTH-002 | 403 | Insufficient permissions |
| AURA-AUTH-003 | 401 | MFA verification required |
| AURA-API-001 | 429 | Rate limit exceeded |
| AURA-API-002 | 400 | Invalid request payload |
| AURA-API-003 | 404 | Resource not found |
| AURA-API-004 | 409 | Resource conflict |
| AURA-API-005 | 422 | Unprocessable entity |
| AURA-SRV-001 | 500 | Internal server error |
| AURA-SRV-002 | 503 | Service unavailable |
| AURA-SRV-003 | 504 | Gateway timeout |

---

## SDK Support

| Language | Package | Status |
|----------|---------|--------|
| TypeScript/JavaScript | `@aenealabs/aura-sdk` (source in `sdk/typescript/`, version 0.2.0) | Available in the repository. Covers approvals, incidents, settings, and the IDE extension endpoints. Authenticate with `jwtToken`; the `apiKey` option sends an `X-API-Key` header that the API does not currently accept. |
| Python | `aura-sdk` | **Planned** |
| Go | `aura-go` | **Planned** |

**Python SDK Example (Planned -- illustrative only):**

```python
from aura_sdk import AuraClient

client = AuraClient(
    api_key="your-api-key",
    base_url="https://api.aenealabs.com/v1"
)

# List repositories
repos = client.repositories.list()
for repo in repos:
    print(f"{repo.name}: {repo.vulnerability_count} vulnerabilities")

# Get specific vulnerability
vuln = client.vulnerabilities.get("vuln-12345")
print(f"Severity: {vuln.severity}, Status: {vuln.status}")

# Approve a patch
client.patches.approve(
    patch_id="patch-67890",
    comment="Reviewed and approved"
)
```

---

## API Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT APPLICATIONS                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Web UI    │  │   CLI       │  │  Integrations│                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (WAF)                            │
│  - Rate limiting                                                     │
│  - Request validation                                                │
│  - TLS termination                                                   │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION                                │
│  - JWT validation                                                    │
│  - RBAC authorization                                                │
│  - Session management                                                │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 REST API (/api/v1; GraphQL planned)                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  /repositories  /approvals  /settings  /dashboards  /...    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       BACKEND SERVICES                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │
│  │ Orchestrator  │  │ Context Svc   │  │ HITL Service  │           │
│  └───────────────┘  └───────────────┘  └───────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Changelog

### v1.0.0 (January 2026)

- Initial stable release
- Repository onboarding (OAuth connections, repositories, ingestion jobs)
- HITL approval workflows
- Platform settings, dashboards, and operational endpoints
- Vulnerability and patch resources, outbound webhook subscriptions, and GraphQL remain **Planned**

### v0.9.0 (December 2025) - Deprecated

- Beta release
- Limited endpoint support
- Breaking changes expected

---

## Related Documentation

- [REST API Reference](./rest-api.md)
- [GraphQL API](./graphql-api.md)
- [Webhooks](./webhooks.md)
- [Support Documentation Index](../index.md)
- [Troubleshooting](../troubleshooting/index.md)

---

*Last updated: January 2026 | Version 1.0*

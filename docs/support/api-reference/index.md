# API Reference

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This section provides comprehensive API documentation for integrating with Project Aura. The API enables programmatic access to vulnerability management, patch generation, approval workflows, and system configuration.

---

## API Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [REST API Reference](./rest-api.md) | Full REST endpoint specifications | Developers, Integration Engineers |
| [GraphQL API](./graphql-api.md) | GraphQL schema and operations | Developers |
| [Webhooks](./webhooks.md) | Event notifications and payloads | Developers, Operations |

---

## Quick Start

### Authentication

All API requests require a valid JWT token in the Authorization header:

```bash
curl -X GET https://api.aenealabs.com/v1/repositories \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json"
```

### Obtaining an Access Token

```bash
# Login with email/password
curl -X POST https://api.aenealabs.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your-password"
  }'

# Response
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://api.aenealabs.com/v1` |
| Staging | `https://api.staging.aenealabs.com/v1` |
| Self-Hosted | `https://{your-domain}/api/v1` |

---

## API Design Principles

### RESTful Conventions

Project Aura's API follows REST conventions:

| HTTP Method | Usage | Example |
|-------------|-------|---------|
| GET | Retrieve resource(s) | `GET /repositories` |
| POST | Create resource | `POST /repositories` |
| PUT | Replace resource | `PUT /repositories/{id}` |
| PATCH | Partial update | `PATCH /repositories/{id}` |
| DELETE | Remove resource | `DELETE /repositories/{id}` |

### Response Format

All responses use JSON with a consistent structure:

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
| `X-Request-ID` | No | Client-provided request ID for tracing |
| `X-Org-ID` | No | Override default organization context |

---

## Pagination

List endpoints support cursor-based pagination:

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

API requests are rate-limited to ensure fair usage:

| Tier | Limit | Window | Burst |
|------|-------|--------|-------|
| Free | 100 | 1 minute | 10 |
| Professional | 1000 | 1 minute | 100 |
| Enterprise | 10000 | 1 minute | 1000 |

**Rate Limit Headers:**

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1737288060
```

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

Most list endpoints support filtering:

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

The API version is included in the URL path (`/v1/`). Breaking changes require a new major version.

**Version Support Policy:**

| Version | Status | Support Until |
|---------|--------|---------------|
| v1 | Current | Active |
| v0 (beta) | Deprecated | June 2026 |

**Deprecation Headers:**

When using deprecated endpoints:

```
Deprecation: true
Sunset: Sat, 01 Jun 2026 00:00:00 GMT
Link: <https://api.aenealabs.com/v1/new-endpoint>; rel="successor-version"
```

---

## Error Codes

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

Official SDKs are available for common languages:

| Language | Package | Documentation |
|----------|---------|---------------|
| Python | `pip install aura-sdk` | [PyPI](https://pypi.org/project/aura-sdk) |
| JavaScript | `npm install @aenealabs/aura-sdk` | [npm](https://npmjs.com/package/@aenealabs/aura-sdk) |
| Go | `go get github.com/aenealabs/aura-go` | [pkg.go.dev](https://pkg.go.dev/github.com/aenealabs/aura-go) |

**Python SDK Example:**

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
│                      REST API / GraphQL                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  /repositories  /vulnerabilities  /patches  /approvals      │   │
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
- Full CRUD for repositories, vulnerabilities, patches
- HITL approval workflows
- Webhook subscriptions
- GraphQL API support

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

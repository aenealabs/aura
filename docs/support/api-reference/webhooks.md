# Webhooks

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

Webhooks enable real-time event notifications from Project Aura to your systems. When events occur (such as vulnerability detection or patch approval), Aura sends HTTP POST requests to your configured endpoints with event details.

---

## Quick Start

### Create a Webhook

```bash
curl -X POST https://api.aenealabs.com/v1/webhooks \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/aura-webhook",
    "events": ["vulnerability.detected", "patch.approved"],
    "secret": "your-webhook-secret-key"
  }'
```

### Webhook Payload Structure

```json
{
  "id": "evt-abc123def456",
  "type": "vulnerability.detected",
  "timestamp": "2026-01-19T12:00:00Z",
  "data": {
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "severity": "critical"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    }
  },
  "organization": {
    "id": "org-xyz789",
    "name": "Acme Corp"
  }
}
```

---

## Event Types

### Vulnerability Events

| Event Type | Description |
|------------|-------------|
| `vulnerability.detected` | New vulnerability found during scan |
| `vulnerability.updated` | Vulnerability status or details changed |
| `vulnerability.resolved` | Vulnerability marked as resolved |
| `vulnerability.reopened` | Previously resolved vulnerability detected again |

### Patch Events

| Event Type | Description |
|------------|-------------|
| `patch.generated` | AI generated a new patch |
| `patch.approved` | Patch approved by reviewer |
| `patch.rejected` | Patch rejected by reviewer |
| `patch.deployed` | Patch successfully deployed |
| `patch.failed` | Patch deployment failed |

### Scan Events

| Event Type | Description |
|------------|-------------|
| `scan.started` | Repository scan initiated |
| `scan.completed` | Scan finished successfully |
| `scan.failed` | Scan encountered an error |

### Approval Events

| Event Type | Description |
|------------|-------------|
| `approval.requested` | New approval waiting for review |
| `approval.reminder` | Reminder for pending approval |
| `approval.expired` | Approval timed out without decision |

### Repository Events

| Event Type | Description |
|------------|-------------|
| `repository.connected` | New repository added |
| `repository.disconnected` | Repository removed |
| `repository.sync_failed` | Repository sync encountered error |

### System Events

| Event Type | Description |
|------------|-------------|
| `system.maintenance` | Scheduled maintenance notification |
| `system.incident` | System incident detected |
| `system.resolved` | System incident resolved |

---

## Event Payloads

### vulnerability.detected

```json
{
  "id": "evt-abc123",
  "type": "vulnerability.detected",
  "timestamp": "2026-01-19T12:00:00Z",
  "data": {
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "description": "User input not properly sanitized",
      "severity": "critical",
      "cve_id": "CVE-2026-1234",
      "cwes": ["CWE-89"],
      "cvss_score": 9.8,
      "location": {
        "file": "src/services/user_service.py",
        "line_start": 45,
        "line_end": 52
      },
      "detected_at": "2026-01-19T12:00:00Z"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api",
      "url": "https://github.com/acme/backend-api"
    },
    "scan": {
      "id": "scan-xyz789",
      "type": "scheduled"
    }
  },
  "organization": {
    "id": "org-xyz789",
    "name": "Acme Corp"
  }
}
```

---

### patch.generated

```json
{
  "id": "evt-def456",
  "type": "patch.generated",
  "timestamp": "2026-01-19T12:30:00Z",
  "data": {
    "patch": {
      "id": "patch-67890",
      "status": "pending_approval",
      "confidence_score": 0.95,
      "files_changed": 1,
      "additions": 3,
      "deletions": 2,
      "generated_at": "2026-01-19T12:30:00Z"
    },
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "severity": "critical"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "sandbox_results": {
      "all_passed": true,
      "syntax_check": "passed",
      "unit_tests": "passed",
      "security_scan": "passed"
    }
  }
}
```

---

### patch.approved

```json
{
  "id": "evt-ghi789",
  "type": "patch.approved",
  "timestamp": "2026-01-19T14:00:00Z",
  "data": {
    "patch": {
      "id": "patch-67890",
      "status": "approved"
    },
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "approval": {
      "approved_by": {
        "id": "user-12345",
        "name": "John Doe",
        "email": "john@acme.com"
      },
      "approved_at": "2026-01-19T14:00:00Z",
      "comment": "Reviewed and approved"
    }
  }
}
```

---

### patch.deployed

```json
{
  "id": "evt-jkl012",
  "type": "patch.deployed",
  "timestamp": "2026-01-19T15:00:00Z",
  "data": {
    "patch": {
      "id": "patch-67890",
      "status": "deployed"
    },
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "status": "resolved"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "deployment": {
      "id": "deploy-abc123",
      "target_branch": "main",
      "commit_sha": "a1b2c3d4e5f6",
      "pull_request": {
        "url": "https://github.com/acme/backend-api/pull/456",
        "number": 456
      },
      "deployed_at": "2026-01-19T15:00:00Z"
    }
  }
}
```

---

### approval.requested

```json
{
  "id": "evt-mno345",
  "type": "approval.requested",
  "timestamp": "2026-01-19T12:35:00Z",
  "data": {
    "approval": {
      "id": "approval-xyz789",
      "type": "patch_approval",
      "status": "pending",
      "required_role": "security_admin",
      "expires_at": "2026-01-20T12:35:00Z"
    },
    "patch": {
      "id": "patch-67890",
      "confidence_score": 0.95
    },
    "vulnerability": {
      "id": "vuln-12345",
      "title": "SQL Injection in User Query",
      "severity": "critical"
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "links": {
      "review_url": "https://app.aenealabs.com/approvals/approval-xyz789"
    }
  }
}
```

---

### scan.completed

```json
{
  "id": "evt-pqr678",
  "type": "scan.completed",
  "timestamp": "2026-01-19T12:00:00Z",
  "data": {
    "scan": {
      "id": "scan-xyz789",
      "type": "scheduled",
      "duration_seconds": 180,
      "files_scanned": 320,
      "lines_scanned": 45000
    },
    "repository": {
      "id": "repo-a1b2c3d4",
      "name": "backend-api"
    },
    "results": {
      "vulnerabilities_found": 5,
      "by_severity": {
        "critical": 1,
        "high": 2,
        "medium": 1,
        "low": 1
      },
      "new_vulnerabilities": 2,
      "resolved_vulnerabilities": 1
    }
  }
}
```

---

## Webhook Security

### Signature Verification

All webhook requests include an HMAC-SHA256 signature header for verification:

```
X-Aura-Signature: sha256=a1b2c3d4e5f6...
```

**Verification Pseudo-Code:**

```python
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

# Usage
payload = request.body
signature = request.headers.get("X-Aura-Signature")
secret = "your-webhook-secret-key"

if not verify_webhook(payload, signature, secret):
    return Response(status=401, body="Invalid signature")
```

**Python Example:**

```python
from flask import Flask, request
import hmac
import hashlib
import json

app = Flask(__name__)
WEBHOOK_SECRET = "your-webhook-secret-key"

@app.route("/aura-webhook", methods=["POST"])
def handle_webhook():
    # Verify signature
    signature = request.headers.get("X-Aura-Signature", "")
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        request.data,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return "Invalid signature", 401

    # Process event
    event = json.loads(request.data)
    event_type = event["type"]

    if event_type == "vulnerability.detected":
        vuln = event["data"]["vulnerability"]
        print(f"New {vuln['severity']} vulnerability: {vuln['title']}")

    elif event_type == "patch.approved":
        patch = event["data"]["patch"]
        print(f"Patch {patch['id']} approved")

    return "OK", 200
```

**Node.js Example:**

```javascript
const express = require('express');
const crypto = require('crypto');

const app = express();
const WEBHOOK_SECRET = 'your-webhook-secret-key';

app.use(express.raw({ type: 'application/json' }));

app.post('/aura-webhook', (req, res) => {
  // Verify signature
  const signature = req.headers['x-aura-signature'];
  const expected = 'sha256=' + crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(req.body)
    .digest('hex');

  if (!crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))) {
    return res.status(401).send('Invalid signature');
  }

  // Process event
  const event = JSON.parse(req.body);

  switch (event.type) {
    case 'vulnerability.detected':
      console.log(`New vulnerability: ${event.data.vulnerability.title}`);
      break;
    case 'patch.approved':
      console.log(`Patch approved: ${event.data.patch.id}`);
      break;
  }

  res.status(200).send('OK');
});

app.listen(3000);
```

---

## Webhook Headers

Every webhook request includes these headers:

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `X-Aura-Signature` | HMAC-SHA256 signature |
| `X-Aura-Event` | Event type (e.g., `vulnerability.detected`) |
| `X-Aura-Delivery` | Unique delivery ID |
| `X-Aura-Timestamp` | Unix timestamp of event |
| `User-Agent` | `Aura-Webhook/1.0` |

---

## Retry Behavior

Aura automatically retries failed webhook deliveries:

| Attempt | Delay | Total Time |
|---------|-------|------------|
| 1 | Immediate | 0s |
| 2 | 1 minute | 1m |
| 3 | 5 minutes | 6m |
| 4 | 30 minutes | 36m |
| 5 | 2 hours | 2h 36m |
| 6 | 6 hours | 8h 36m |

**Retry Conditions:**

- HTTP 5xx response
- Connection timeout (30 seconds)
- DNS resolution failure
- TLS/SSL errors

**Non-Retry Conditions:**

- HTTP 2xx (success)
- HTTP 4xx (client error, except 429)
- HTTP 429 with Retry-After header (honored)

---

## Managing Webhooks

### List Webhooks

```bash
curl -X GET https://api.aenealabs.com/v1/webhooks \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

**Response:**

```json
{
  "data": [
    {
      "id": "webhook-12345",
      "url": "https://example.com/aura-webhook",
      "events": ["vulnerability.detected", "patch.approved"],
      "enabled": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

---

### Create Webhook

```bash
curl -X POST https://api.aenealabs.com/v1/webhooks \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/aura-webhook",
    "events": ["vulnerability.detected", "patch.approved", "patch.deployed"],
    "secret": "your-webhook-secret-key",
    "enabled": true
  }'
```

---

### Update Webhook

```bash
curl -X PATCH https://api.aenealabs.com/v1/webhooks/webhook-12345 \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "events": ["vulnerability.detected"],
    "enabled": false
  }'
```

---

### Delete Webhook

```bash
curl -X DELETE https://api.aenealabs.com/v1/webhooks/webhook-12345 \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

---

### Test Webhook

Send a test event to verify your endpoint:

```bash
curl -X POST https://api.aenealabs.com/v1/webhooks/webhook-12345/test \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "vulnerability.detected"
  }'
```

**Test Event Payload:**

```json
{
  "id": "evt-test-12345",
  "type": "vulnerability.detected",
  "timestamp": "2026-01-19T12:00:00Z",
  "test": true,
  "data": {
    "vulnerability": {
      "id": "vuln-test",
      "title": "Test Vulnerability",
      "severity": "medium"
    },
    "repository": {
      "id": "repo-test",
      "name": "test-repository"
    }
  }
}
```

---

### View Delivery History

```bash
curl -X GET "https://api.aenealabs.com/v1/webhooks/webhook-12345/deliveries?limit=10" \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

**Response:**

```json
{
  "data": [
    {
      "id": "delivery-abc123",
      "event_id": "evt-xyz789",
      "event_type": "vulnerability.detected",
      "status": "success",
      "http_status": 200,
      "response_time_ms": 250,
      "attempts": 1,
      "delivered_at": "2026-01-19T12:00:00Z"
    },
    {
      "id": "delivery-def456",
      "event_id": "evt-uvw123",
      "event_type": "patch.approved",
      "status": "failed",
      "http_status": 500,
      "error": "Internal Server Error",
      "attempts": 3,
      "last_attempt_at": "2026-01-19T11:30:00Z",
      "next_retry_at": "2026-01-19T12:00:00Z"
    }
  ]
}
```

---

### Redeliver Event

```bash
curl -X POST https://api.aenealabs.com/v1/webhooks/webhook-12345/deliveries/delivery-abc123/redeliver \
  -H "Authorization: Bearer ${AURA_TOKEN}"
```

---

## Best Practices

### Endpoint Design

1. **Return 2xx quickly** - Process events asynchronously if needed
2. **Handle duplicates** - Events may be delivered more than once
3. **Verify signatures** - Always validate the HMAC signature
4. **Log deliveries** - Keep records for debugging
5. **Monitor failures** - Alert on repeated failures

### Security

1. **Use HTTPS** - Plaintext HTTP is not supported
2. **Keep secrets secure** - Never expose webhook secrets in code
3. **Validate payloads** - Check expected fields exist
4. **Restrict IP if possible** - Aura sends from documented IP ranges

### Aura Webhook IP Ranges

```
# Production
52.23.0.0/16
34.192.0.0/12

# Staging
52.55.0.0/16
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| No deliveries | Webhook disabled | Enable webhook |
| Signature mismatch | Wrong secret | Verify secret matches |
| Timeout failures | Slow endpoint | Optimize response time |
| SSL errors | Invalid certificate | Use valid TLS certificate |

### Debug Mode

Enable verbose delivery logging:

```bash
curl -X PATCH https://api.aenealabs.com/v1/webhooks/webhook-12345 \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"debug_mode": true}'
```

Debug mode logs full request/response details for 24 hours.

---

## Related Documentation

- [API Reference Index](./index.md)
- [REST API Reference](./rest-api.md)
- [GraphQL API](./graphql-api.md)
- [Troubleshooting](../troubleshooting/common-issues.md)

---

*Last updated: January 2026 | Version 1.0*

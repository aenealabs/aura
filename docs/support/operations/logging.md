# Logging Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide covers log management for Project Aura, including log formats, collection, retention, and analysis techniques.

---

## Log Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOG ARCHITECTURE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

    APPLICATION LOGS                    INFRASTRUCTURE LOGS
    ┌─────────────────┐                ┌─────────────────┐
    │ API Service     │                │ CloudTrail      │
    │ Agents          │                │ VPC Flow Logs   │
    │ Lambda          │                │ ALB Access      │
    │ HITL Service    │                │ WAF Logs        │
    └────────┬────────┘                └────────┬────────┘
             │                                   │
             └─────────────┬─────────────────────┘
                           │
                           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     CloudWatch Logs                                  │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │ Log Groups                                                   │   │
    │  │ - /aura/api                                                  │   │
    │  │ - /aura/agents/orchestrator                                  │   │
    │  │ - /aura/agents/coder                                         │   │
    │  │ - /aura/security/audit                                       │   │
    │  │ - /aws/lambda/aura-*                                         │   │
    │  │ - /vpc/flow-logs                                             │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ Logs Insights│ │   S3 Export  │ │    SIEM      │
    │   Queries    │ │  (Archive)   │ │ Integration  │
    └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Log Formats

### Structured JSON Log Format

All application logs use structured JSON:

```json
{
  "timestamp": "2026-01-19T12:00:00.123Z",
  "level": "INFO",
  "logger": "aura.api.routes.repositories",
  "message": "Repository scan completed",
  "request_id": "req-abc123def456",
  "user_id": "user-12345",
  "organization_id": "org-xyz789",
  "service": "api",
  "environment": "prod",
  "context": {
    "repository_id": "repo-a1b2c3d4",
    "scan_id": "scan-xyz789",
    "vulnerabilities_found": 5,
    "duration_ms": 180000
  },
  "trace_id": "1-5f84c7a5-c5c4c5c4c5c4c5c4",
  "span_id": "c5c4c5c4c5c4c5c4"
}
```

### Log Fields Reference

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `timestamp` | ISO 8601 | Event time | Yes |
| `level` | string | DEBUG, INFO, WARNING, ERROR, CRITICAL | Yes |
| `logger` | string | Logger name (module path) | Yes |
| `message` | string | Human-readable message | Yes |
| `request_id` | string | Request correlation ID | Yes (API) |
| `user_id` | string | Authenticated user ID | If authenticated |
| `organization_id` | string | Organization context | If applicable |
| `service` | string | Service name | Yes |
| `environment` | string | Deployment environment | Yes |
| `context` | object | Additional structured data | Optional |
| `trace_id` | string | X-Ray trace ID | If tracing enabled |
| `error` | object | Error details (stack trace) | If error |

### Error Log Format

```json
{
  "timestamp": "2026-01-19T12:00:00.123Z",
  "level": "ERROR",
  "logger": "aura.agents.coder",
  "message": "Patch generation failed",
  "request_id": "req-abc123def456",
  "service": "coder-agent",
  "environment": "prod",
  "error": {
    "type": "BedrockInvocationError",
    "message": "Model invocation timeout",
    "code": "AURA-AGT-001",
    "stack": "Traceback (most recent call last):\n  File \"...\", line 45, in generate_patch\n    ...",
    "cause": {
      "type": "TimeoutError",
      "message": "Request exceeded 30s timeout"
    }
  },
  "context": {
    "vulnerability_id": "vuln-12345",
    "model": "claude-3.5-sonnet",
    "tokens_requested": 8000
  }
}
```

---

## Log Groups

### Application Log Groups

| Log Group | Content | Retention |
|-----------|---------|-----------|
| `/aura/api` | API request/response, errors | 90 days |
| `/aura/agents/orchestrator` | Agent coordination | 90 days |
| `/aura/agents/coder` | Patch generation | 90 days |
| `/aura/agents/reviewer` | Code review | 90 days |
| `/aura/agents/validator` | Sandbox testing | 90 days |
| `/aura/hitl` | Approval workflow | 365 days |
| `/aura/security/audit` | Security events | 365 days |

### Infrastructure Log Groups

| Log Group | Content | Retention |
|-----------|---------|-----------|
| `/aws/eks/aura-cluster-${ENV}/cluster` | EKS control plane | 90 days |
| `/aws/lambda/aura-*` | Lambda execution | 90 days |
| `/vpc/flow-logs` | VPC network traffic | 365 days |
| `/aws/waf/aura-waf` | WAF requests | 90 days |
| `/aws/cloudtrail/aura` | AWS API calls | 365 days |

---

## Log Collection

### EKS Pod Logging

Logs are collected via Fluent Bit DaemonSet:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: amazon-cloudwatch
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Daemon        off
        Parsers_File  parsers.conf

    [INPUT]
        Name              tail
        Tag               kube.*
        Path              /var/log/containers/*aura*.log
        Parser            docker
        DB                /var/fluent-bit/state/flb_container.db
        Mem_Buf_Limit     50MB
        Skip_Long_Lines   On
        Refresh_Interval  10

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_Tag_Prefix     kube.var.log.containers.
        Merge_Log           On
        K8S-Logging.Parser  On
        K8S-Logging.Exclude Off

    [OUTPUT]
        Name                cloudwatch_logs
        Match               kube.*
        region              ${AWS_REGION}
        log_group_name      /aura/${namespace}
        log_stream_prefix   ${pod_name}/
        auto_create_group   true
```

### Lambda Logging

Lambda logs are automatically sent to CloudWatch:

```python
import logging
import json

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_entry["error"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stack": self.formatException(record.exc_info)
            }
        return json.dumps(log_entry)

handler = logging.StreamHandler()
handler.setFormatter(StructuredFormatter())
logger.addHandler(handler)
```

---

## Log Analysis

### CloudWatch Logs Insights Queries

**Find errors in the last hour:**

```sql
fields @timestamp, @message, error.type, error.message
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

**API latency analysis:**

```sql
fields @timestamp, context.duration_ms as latency
| filter logger like /api.routes/
| stats avg(latency), p50(latency), p95(latency), p99(latency) by bin(5m)
```

**Count errors by type:**

```sql
fields error.type
| filter level = "ERROR"
| stats count(*) as error_count by error.type
| sort error_count desc
```

**Find slow requests:**

```sql
fields @timestamp, @message, context.duration_ms, request_id
| filter context.duration_ms > 5000
| sort context.duration_ms desc
| limit 50
```

**User activity audit:**

```sql
fields @timestamp, user_id, @message
| filter user_id = "user-12345"
| sort @timestamp desc
| limit 100
```

**Security event analysis:**

```sql
fields @timestamp, @message, user_id, context.action
| filter logger = "aura.security.audit"
| filter context.action in ["login", "logout", "password_change", "mfa_enable"]
| sort @timestamp desc
```

### Common Log Patterns

**Request tracing:**

```bash
# Find all logs for a specific request
aws logs filter-log-events \
  --log-group-name /aura/api \
  --filter-pattern '{ $.request_id = "req-abc123def456" }' \
  --start-time $(date -d '1 hour ago' +%s000)
```

**Error spike investigation:**

```bash
# Count errors per minute
aws logs filter-log-events \
  --log-group-name /aura/api \
  --filter-pattern '{ $.level = "ERROR" }' \
  --start-time $(date -d '1 hour ago' +%s000) \
  --query 'events[*].timestamp' | jq -c 'group_by(./60000|floor) | map(length)'
```

---

## Log Retention and Archival

### Retention Policies

| Log Type | CloudWatch | S3 Archive | Glacier |
|----------|------------|------------|---------|
| Application | 90 days | 1 year | 7 years |
| Security/Audit | 365 days | 7 years | N/A |
| VPC Flow | 365 days | 1 year | 7 years |
| CloudTrail | 365 days | 7 years | N/A |

### S3 Export Configuration

```bash
# Create export task
aws logs create-export-task \
  --log-group-name /aura/api \
  --from $(date -d '1 day ago' +%s000) \
  --to $(date +%s000) \
  --destination aura-logs-archive-${ENV} \
  --destination-prefix api/$(date +%Y/%m/%d)
```

### S3 Lifecycle Policy

```json
{
  "Rules": [
    {
      "ID": "ArchiveOldLogs",
      "Status": "Enabled",
      "Filter": {"Prefix": "logs/"},
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 365,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 2555
      }
    }
  ]
}
```

---

## Security Logging

### Audit Events

Security-relevant events logged to `/aura/security/audit`:

| Event Type | Description | Data |
|------------|-------------|------|
| `auth.login` | User login | user_id, ip, user_agent |
| `auth.logout` | User logout | user_id, session_duration |
| `auth.failed` | Failed login | email, ip, reason |
| `auth.mfa_enabled` | MFA enabled | user_id |
| `patch.approved` | Patch approved | patch_id, approver, comment |
| `patch.rejected` | Patch rejected | patch_id, rejector, reason |
| `settings.changed` | Settings modified | setting_key, old_value, new_value |
| `user.created` | User created | user_id, email, roles |
| `user.deleted` | User deleted | user_id |

### Sensitive Data Handling

**Data Masking:**

```python
def mask_sensitive(data: dict) -> dict:
    """Mask sensitive fields in log data."""
    sensitive_fields = ['password', 'token', 'secret', 'api_key', 'credentials']

    def mask_value(key: str, value: any) -> any:
        if any(sf in key.lower() for sf in sensitive_fields):
            if isinstance(value, str) and len(value) > 8:
                return value[:4] + '****' + value[-4:]
            return '****'
        return value

    return {k: mask_value(k, v) for k, v in data.items()}
```

**PII Redaction:**

- Email addresses: `j***@example.com`
- IP addresses: Hashed in application logs
- Full audit trail preserved in security logs (access-controlled)

---

## Troubleshooting with Logs

### Common Investigation Patterns

**1. Request failed - find root cause:**

```sql
-- Step 1: Find the error
fields @timestamp, @message, error.type, error.message, request_id
| filter request_id = "req-abc123"
| filter level = "ERROR"

-- Step 2: Get full request context
fields @timestamp, @message
| filter request_id = "req-abc123"
| sort @timestamp asc
```

**2. Performance degradation - identify slow operations:**

```sql
fields @timestamp, context.operation, context.duration_ms
| filter context.duration_ms > 1000
| stats avg(context.duration_ms) as avg_ms, count(*) as count by context.operation
| sort avg_ms desc
```

**3. Authentication issues - check auth logs:**

```sql
fields @timestamp, @message, user_id, error.message
| filter logger like /auth/
| filter level = "ERROR" or level = "WARNING"
| sort @timestamp desc
```

---

## Related Documentation

- [Operations Index](./index.md)
- [Monitoring Guide](./monitoring.md)
- [Troubleshooting](../troubleshooting/index.md)
- [Security Architecture](../architecture/security-architecture.md)

---

*Last updated: January 2026 | Version 1.0*

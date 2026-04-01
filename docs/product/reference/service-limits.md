# Service Limits

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document details the platform quotas, rate limits, and capacity constraints for Project Aura. Understanding these limits helps you plan deployments, optimize usage, and avoid service interruptions.

All limits are subject to change. Contact your Aenea Labs account representative to discuss limit increases for Enterprise customers.

---

## Subscription Tiers

Project Aura is available in three subscription tiers with different capabilities and limits.

| Feature | Free | Team | Enterprise |
|---------|------|------|------------|
| **Target Users** | Individual developers | Small to medium teams | Large organizations |
| **Support Level** | Community | Standard (email) | Premium (24/7) |
| **SLA** | None | 99.5% uptime | 99.9% uptime |
| **Deployment Options** | SaaS only | SaaS only | SaaS, Self-hosted, GovCloud |
| **Price** | $0/month | Contact sales | Contact sales |

---

## Repository Limits

Limits on source code repositories connected to Aura.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Repositories per organization | 3 | 25 | Unlimited |
| Maximum repository size | 500 MB | 2 GB | 10 GB |
| Maximum files per repository | 10,000 | 50,000 | 250,000 |
| Maximum file size (individual) | 1 MB | 5 MB | 25 MB |
| Branches per repository | 10 | 100 | 500 |
| Protected branch rules | 2 | 10 | Unlimited |
| Repository webhooks | 5 | 20 | 100 |

### File Type Support

| Category | Supported Extensions |
|----------|---------------------|
| Python | `.py`, `.pyx`, `.pyi` |
| JavaScript/TypeScript | `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs` |
| Java | `.java`, `.kt`, `.scala` |
| Go | `.go` |
| Rust | `.rs` |
| C/C++ | `.c`, `.cpp`, `.h`, `.hpp` |
| C# | `.cs` |
| Ruby | `.rb` |
| PHP | `.php` |
| Configuration | `.yaml`, `.yml`, `.json`, `.toml`, `.xml` |
| Infrastructure | `.tf`, `.hcl`, `.cfn`, `.sam` |

---

## Scan Limits

Limits on vulnerability scanning operations.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Scans per day | 5 | 50 | Unlimited |
| Concurrent scans | 1 | 3 | 10 |
| Maximum scan duration | 30 minutes | 2 hours | 8 hours |
| Files per scan | 5,000 | 25,000 | 100,000 |
| Lines of code per scan | 500,000 | 2,500,000 | 10,000,000 |
| Scheduled scans | 1 (weekly) | 10 (daily minimum) | Unlimited |

### Scan Frequency Recommendations

| Repository Size | Recommended Frequency | Notes |
|-----------------|----------------------|-------|
| < 100,000 LOC | Daily | Minimal resource impact |
| 100,000 - 1M LOC | Daily | Standard processing time |
| 1M - 10M LOC | Daily or per-commit | Monitor queue depth |
| > 10M LOC | Per-commit or scheduled | Enterprise tier recommended |

---

## Agent Limits

Limits on AI agent operations.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Concurrent agents | 2 | 8 | 32 |
| Agent task timeout | 10 minutes | 30 minutes | 60 minutes |
| Patches per hour | 5 | 25 | 100 |
| Sandbox environments (concurrent) | 1 | 5 | 20 |
| Sandbox environment duration | 15 minutes | 1 hour | 4 hours |
| Constitutional AI evaluations/day | 100 | 1,000 | Unlimited |

### Agent Types and Limits

| Agent Type | Free | Team | Enterprise |
|------------|------|------|------------|
| Coder Agent instances | 1 | 3 | 10 |
| Reviewer Agent instances | 1 | 3 | 10 |
| Validator Agent instances | 1 | 4 | 16 |
| Monitor Agent instances | 1 | 2 | 4 |
| Environment Validator instances | 1 | 2 | 4 |

---

## API Rate Limits

Limits on API requests. All limits are per organization.

### REST API

| Endpoint Category | Free | Team | Enterprise |
|-------------------|------|------|------------|
| Read operations | 100/minute | 500/minute | 2,000/minute |
| Write operations | 20/minute | 100/minute | 500/minute |
| Bulk operations | 5/minute | 25/minute | 100/minute |
| File uploads | 10/minute | 50/minute | 200/minute |
| Report generation | 5/hour | 30/hour | 120/hour |

### GraphQL API

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Requests per minute | 50 | 250 | 1,000 |
| Maximum query depth | 5 | 10 | 20 |
| Maximum query complexity | 100 | 500 | 2,000 |
| Batch queries per request | 3 | 10 | 25 |

### Webhooks

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Webhook endpoints per org | 5 | 20 | 100 |
| Events per second (outbound) | 10 | 50 | 200 |
| Payload size | 64 KB | 256 KB | 1 MB |
| Retry attempts | 3 | 5 | 10 |
| Retry window | 1 hour | 4 hours | 24 hours |

### Rate Limit Headers

All API responses include rate limit information in HTTP headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests in current window |
| `X-RateLimit-Remaining` | Remaining requests in current window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `Retry-After` | Seconds to wait (only on 429 responses) |

---

## Dashboard Limits

Limits on dashboard customization and visualization.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Dashboards per user | 3 | 10 | 50 |
| Dashboards per organization | 10 | 100 | 500 |
| Widgets per dashboard | 10 | 25 | 50 |
| Custom widgets per org | 0 | 10 | Unlimited |
| Dashboard sharing recipients | 3 | 25 | Unlimited |
| Scheduled reports per dashboard | 1 | 5 | 20 |
| Embedded dashboards | 0 | 5 | Unlimited |
| Data refresh rate (minimum) | 5 minutes | 1 minute | 30 seconds |

### Widget Limits

| Widget Type | Maximum Data Points | Refresh Rate |
|-------------|---------------------|--------------|
| Metric card | N/A | Real-time |
| Sparkline | 30 days | 1 minute |
| Line chart | 90 days | 5 minutes |
| Bar chart | 365 days | 5 minutes |
| Pie chart | N/A | 5 minutes |
| Heatmap | 30 days | 15 minutes |
| Data table | 1,000 rows | 5 minutes |
| Activity feed | 100 items | Real-time |

---

## User and Organization Limits

Limits on users, teams, and organizational structure.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Users per organization | 5 | 50 | Unlimited |
| Teams per organization | 2 | 20 | 200 |
| Users per team | 5 | 25 | Unlimited |
| Roles (custom) | 0 | 5 | Unlimited |
| API keys per user | 2 | 5 | 20 |
| API keys per organization | 5 | 25 | 100 |
| SSO/SAML configuration | Not available | 1 IdP | Unlimited IdPs |
| Active sessions per user | 3 | 5 | 10 |

### Permission Granularity

| Permission Level | Free | Team | Enterprise |
|------------------|------|------|------------|
| Organization-wide | Yes | Yes | Yes |
| Team-based | No | Yes | Yes |
| Repository-based | No | Yes | Yes |
| Branch-based | No | No | Yes |
| Custom policies | No | No | Yes |

---

## Storage Limits

Limits on data storage and retention.

### Data Retention

| Data Type | Free | Team | Enterprise |
|-----------|------|------|------------|
| Scan results | 30 days | 90 days | 2 years |
| Patch history | 30 days | 1 year | 7 years |
| Audit logs | 7 days | 90 days | 7 years |
| Code embeddings | 30 days | 1 year | Unlimited |
| Agent conversation history | 7 days | 30 days | 1 year |
| Dashboard snapshots | 7 days | 90 days | 1 year |
| Compliance reports | 30 days | 1 year | 7 years |

### Storage Quotas

| Storage Type | Free | Team | Enterprise |
|--------------|------|------|------------|
| Total storage per org | 1 GB | 25 GB | 500 GB |
| Artifact storage | 500 MB | 10 GB | 200 GB |
| Backup storage | N/A | Included | Included |
| Export storage | 100 MB | 5 GB | 50 GB |

---

## GPU Workload Limits

Limits on GPU-accelerated workloads.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| GPU jobs per day | 0 | 10 | Unlimited |
| Concurrent GPU jobs | 0 | 2 | 8 |
| Maximum GPU job duration | N/A | 2 hours | 8 hours |
| GPU memory per job | N/A | 8 GB | 24 GB |
| GPU queue priority levels | N/A | 2 | 4 |
| Spot instance usage | N/A | Optional | Optional |

### GPU Instance Types (Enterprise)

| Instance Type | GPUs | GPU Memory | Availability |
|---------------|------|------------|--------------|
| g4dn.xlarge | 1 | 16 GB | Default |
| g4dn.2xlarge | 1 | 16 GB | On request |
| g5.xlarge | 1 | 24 GB | On request |
| g5.2xlarge | 1 | 24 GB | On request |
| p4d.24xlarge | 8 | 320 GB | Enterprise+ |

### Embedding Generation Capacity

| Codebase Size | Estimated Time (1 GPU) | Estimated Time (8 GPU) |
|---------------|------------------------|------------------------|
| 1M LOC | 15-30 minutes | 2-4 minutes |
| 10M LOC | 2.5-5 hours | 20-40 minutes |
| 40M LOC | 10-20 hours | 1.5-2.5 hours |
| 100M LOC | 25-50 hours | 3-6 hours |

---

## Notification Limits

Limits on notification and alerting capabilities.

| Limit | Free | Team | Enterprise |
|-------|------|------|------------|
| Email notifications/day | 50 | 500 | Unlimited |
| Slack channels | 1 | 10 | Unlimited |
| Microsoft Teams channels | 0 | 10 | Unlimited |
| Custom webhook integrations | 2 | 10 | Unlimited |
| Alert rules | 5 | 50 | Unlimited |
| Notification groups | 2 | 20 | 100 |

---

## Compliance and Audit Limits

Limits specific to compliance features.

| Feature | Free | Team | Enterprise |
|---------|------|------|------------|
| Compliance frameworks supported | 1 | 3 | Unlimited |
| Custom compliance rules | 0 | 10 | Unlimited |
| Audit report generation | 1/month | 10/month | Unlimited |
| Evidence collection automation | No | Limited | Full |
| Compliance dashboard access | Basic | Standard | Advanced |
| Third-party audit support | No | No | Yes |

### Supported Compliance Frameworks

| Framework | Free | Team | Enterprise |
|-----------|------|------|------------|
| OWASP Top 10 | Yes | Yes | Yes |
| CWE Top 25 | Yes | Yes | Yes |
| NIST 800-53 | No | Yes | Yes |
| CMMC Level 2/3 | No | No | Yes |
| SOX Section 404 | No | No | Yes |
| FedRAMP | No | No | Yes |
| HIPAA | No | Yes | Yes |
| PCI-DSS | No | Yes | Yes |

---

## Self-Hosted Deployment Limits

Limits for self-hosted (on-premises) deployments. Available only on Enterprise tier.

| Resource | Minimum | Recommended | Maximum |
|----------|---------|-------------|---------|
| Kubernetes nodes | 3 | 6 | No limit |
| Node CPU (each) | 4 vCPU | 8 vCPU | No limit |
| Node memory (each) | 16 GB | 32 GB | No limit |
| Node storage (each) | 100 GB SSD | 500 GB SSD | No limit |
| PostgreSQL storage | 50 GB | 200 GB | No limit |
| Elasticsearch storage | 100 GB | 500 GB | No limit |

### Container Resource Limits

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| API Gateway | 250m | 1000m | 512Mi | 2Gi |
| Orchestrator | 500m | 2000m | 1Gi | 4Gi |
| Coder Agent | 1000m | 4000m | 2Gi | 8Gi |
| Reviewer Agent | 500m | 2000m | 1Gi | 4Gi |
| Validator Agent | 500m | 2000m | 1Gi | 4Gi |
| Context Retrieval | 500m | 2000m | 1Gi | 4Gi |

---

## Requesting Limit Increases

### Automatic Limit Increases

Some limits automatically increase based on usage patterns and account standing:

- API rate limits may increase after 30 days of consistent usage
- Storage quotas may increase with tier upgrades
- Scan limits may increase during security incidents (temporary)

### Manual Limit Increase Requests

To request a limit increase:

1. **Free Tier:** Upgrade to Team or Enterprise tier
2. **Team Tier:** Contact support with business justification
3. **Enterprise Tier:** Contact your account representative

**Required Information:**
- Organization ID
- Current limit and requested limit
- Business justification
- Expected timeline for increased usage

### Limit Increase SLAs

| Tier | Response Time | Approval Time |
|------|---------------|---------------|
| Free | N/A | N/A |
| Team | 48 hours | 5 business days |
| Enterprise | 4 hours | 1-2 business days |

---

## Monitoring Your Usage

### Usage Dashboard

Access your organization's usage dashboard at **Settings > Usage & Billing** to view:

- Current usage vs. limits for all categories
- Usage trends over time
- Projected usage and limit warnings
- Cost breakdown by feature

### Usage Alerts

Configure alerts to be notified when approaching limits:

| Alert Type | Default Threshold | Configurable |
|------------|------------------|--------------|
| Warning | 80% of limit | Yes |
| Critical | 95% of limit | Yes |
| Exceeded | 100% of limit | No |

### API Usage Endpoint

```
GET /api/v1/organizations/{org_id}/usage
```

Returns current usage metrics for programmatic monitoring.

---

## Fair Use Policy

All usage is subject to Aenea Labs' Fair Use Policy. Actions that may be considered abuse include:

- Automated scraping or bulk data extraction
- Intentional circumvention of rate limits
- Resource exhaustion attacks
- Using the platform for purposes other than security remediation

Violations may result in temporary or permanent account suspension.

---

**Related Documentation:**
- [System Requirements](../getting-started/system-requirements.md) - Infrastructure requirements
- [API Reference](../../support/api-reference/index.md) - API documentation
- [Pricing](https://aenealabs.com/pricing) - Current pricing information
- [Glossary](./glossary.md) - Term definitions

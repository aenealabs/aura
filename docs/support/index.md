# Support Documentation

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This Support Documentation provides comprehensive technical guidance for developers, DevOps engineers, cybersecurity professionals, and IT administrators working with Project Aura. The content includes in-depth troubleshooting procedures, API references, architecture documentation, and operational guides.

This documentation is designed to be searchable via the global chat assistant and serves as the primary technical reference for support scenarios.

---

## Documentation Structure

```
docs/support/
├── index.md                          # This file - Support documentation overview
├── troubleshooting/
│   ├── index.md                      # Troubleshooting guide overview
│   ├── common-issues.md              # Frequently encountered problems
│   ├── deployment-issues.md          # CloudFormation, EKS, container issues
│   ├── performance-issues.md         # Latency, memory, scaling problems
│   └── security-issues.md            # Auth failures, permission errors
├── api-reference/
│   ├── index.md                      # API documentation overview
│   ├── rest-api.md                   # REST endpoints, request/response formats
│   ├── graphql-api.md                # GraphQL schema and operations
│   └── webhooks.md                   # Webhook events, payloads, retry logic
├── architecture/
│   ├── index.md                      # Architecture documentation overview
│   ├── system-overview.md            # High-level system architecture
│   ├── data-flow.md                  # How data moves through the system
│   ├── security-architecture.md      # Security controls and network isolation
│   └── disaster-recovery.md          # Backup, recovery, RTO/RPO
├── operations/
│   ├── index.md                      # Operations guide overview
│   ├── monitoring.md                 # CloudWatch, dashboards, alerts
│   ├── logging.md                    # Log formats, retention, analysis
│   ├── backup-restore.md             # Data backup and restoration
│   └── scaling.md                    # Horizontal/vertical scaling
└── faq.md                            # Frequently Asked Questions
```

---

## Quick Links by Role

### For Developers

| Resource | Description | Link |
|----------|-------------|------|
| REST API Reference | Endpoint specifications, authentication, examples | [api-reference/rest-api.md](./api-reference/rest-api.md) |
| Webhook Events | Event types, payload formats, retry behavior | [api-reference/webhooks.md](./api-reference/webhooks.md) |
| Common Issues | Frequently encountered problems and solutions | [troubleshooting/common-issues.md](./troubleshooting/common-issues.md) |
| Data Flow | How data moves through the system | [architecture/data-flow.md](./architecture/data-flow.md) |

### For DevOps / SRE

| Resource | Description | Link |
|----------|-------------|------|
| Deployment Issues | CloudFormation, EKS, container troubleshooting | [troubleshooting/deployment-issues.md](./troubleshooting/deployment-issues.md) |
| Monitoring Guide | CloudWatch dashboards, metrics, alerts | [operations/monitoring.md](./operations/monitoring.md) |
| Scaling Guide | Auto-scaling, capacity planning | [operations/scaling.md](./operations/scaling.md) |
| Backup and Restore | Data protection and recovery procedures | [operations/backup-restore.md](./operations/backup-restore.md) |

### For Security Engineers

| Resource | Description | Link |
|----------|-------------|------|
| Security Architecture | Network isolation, encryption, access control | [architecture/security-architecture.md](./architecture/security-architecture.md) |
| Security Issues | Authentication, authorization, permission errors | [troubleshooting/security-issues.md](./troubleshooting/security-issues.md) |
| System Overview | End-to-end architecture with security boundaries | [architecture/system-overview.md](./architecture/system-overview.md) |

### For IT Administrators

| Resource | Description | Link |
|----------|-------------|------|
| Operations Overview | Day-to-day operational procedures | [operations/index.md](./operations/index.md) |
| Logging Guide | Log collection, retention, analysis | [operations/logging.md](./operations/logging.md) |
| FAQ | Answers to common questions | [faq.md](./faq.md) |
| Disaster Recovery | Business continuity and recovery | [architecture/disaster-recovery.md](./architecture/disaster-recovery.md) |

---

## System Requirements Quick Reference

### Minimum Requirements

| Component | Specification |
|-----------|---------------|
| CPU | 4 vCPUs (8 recommended for production) |
| Memory | 16 GB RAM (32 GB recommended) |
| Storage | 100 GB SSD |
| Network | 100 Mbps (1 Gbps recommended) |

### Supported Environments

| Deployment Type | Supported Versions |
|-----------------|-------------------|
| Kubernetes | 1.28+ (EKS 1.34 recommended) |
| Podman | 4.0+ |
| Docker | 24.0+ (development only) |
| Python | 3.11+ |
| Node.js | 20 LTS |

### Cloud Services (AWS)

| Service | Version / Configuration |
|---------|------------------------|
| EKS | 1.34 with EC2 Managed Node Groups |
| Neptune | Engine 1.2.1.0+ |
| OpenSearch | 2.11+ |
| Bedrock | Claude 3.5 Sonnet |

---

## Error Code Quick Reference

Project Aura uses structured error codes to help identify and resolve issues quickly.

### Error Code Format

```
AURA-{CATEGORY}-{NUMBER}

Categories:
- AUTH: Authentication and authorization
- API:  API request/response errors
- AGT:  Agent-related errors
- INF:  Infrastructure errors
- DB:   Database errors
- NET:  Network errors
```

### Common Error Codes

| Code | Description | Quick Fix |
|------|-------------|-----------|
| AURA-AUTH-001 | Invalid or expired token | Refresh authentication token |
| AURA-AUTH-002 | Insufficient permissions | Verify RBAC role assignments |
| AURA-AUTH-003 | MFA verification failed | Re-authenticate with valid MFA code |
| AURA-API-001 | Rate limit exceeded | Implement exponential backoff |
| AURA-API-002 | Invalid request payload | Validate JSON schema |
| AURA-API-003 | Resource not found | Verify resource ID exists |
| AURA-AGT-001 | Agent timeout | Check agent health, increase timeout |
| AURA-AGT-002 | Agent communication failure | Verify network connectivity |
| AURA-AGT-003 | Orchestrator unavailable | Check orchestrator service status |
| AURA-INF-001 | CloudFormation deployment failed | Review stack events |
| AURA-INF-002 | EKS node unhealthy | Check node conditions |
| AURA-INF-003 | VPC endpoint unreachable | Verify security groups |
| AURA-DB-001 | Neptune connection failed | Check VPC endpoint, credentials |
| AURA-DB-002 | OpenSearch query timeout | Optimize query, increase timeout |
| AURA-DB-003 | DynamoDB throttled | Increase provisioned capacity |
| AURA-NET-001 | DNS resolution failed | Verify dnsmasq configuration |
| AURA-NET-002 | TLS handshake failed | Check certificate validity |
| AURA-NET-003 | Connection refused | Verify target service is running |

For detailed error information, see [troubleshooting/common-issues.md](./troubleshooting/common-issues.md).

---

## Diagnostic Commands

### Health Check Commands

```bash
# Check overall platform health
curl -s https://api.aenealabs.com/v1/health | jq

# Check specific service health
curl -s https://api.aenealabs.com/v1/health/agents | jq
curl -s https://api.aenealabs.com/v1/health/databases | jq

# Kubernetes cluster health (self-hosted)
kubectl get nodes -o wide
kubectl get pods -n aura-system --field-selector=status.phase!=Running
```

### Log Collection Commands

```bash
# Collect recent API logs
kubectl logs -n aura-system -l app=aura-api --tail=1000 --since=1h

# Collect agent orchestrator logs
kubectl logs -n aura-system -l app=orchestrator --tail=1000 --since=1h

# Export logs to file
kubectl logs -n aura-system -l app=aura-api --since=24h > aura-api-logs.txt
```

### Database Diagnostic Commands

```bash
# Neptune connectivity test
aws neptune-db describe-db-cluster-endpoints \
  --db-cluster-identifier aura-neptune-cluster-${ENV}

# OpenSearch health check
curl -s https://opensearch.aura.local:9200/_cluster/health | jq

# DynamoDB table status
aws dynamodb describe-table --table-name aura-approval-requests-${ENV}
```

---

## Support Channels

### Self-Service Resources

| Resource | URL | Description |
|----------|-----|-------------|
| Documentation | docs.aenealabs.com | Full documentation site |
| Status Page | status.aenealabs.com | Real-time service status |
| Community Forum | community.aenealabs.com | Peer support and discussions |
| Knowledge Base | kb.aenealabs.com | Searchable article database |

### Contact Support

| Priority | Channel | Response Time |
|----------|---------|---------------|
| P1 - Critical | support@aenealabs.com | 1 hour |
| P2 - High | support@aenealabs.com | 4 hours |
| P3 - Medium | Support Portal | 1 business day |
| P4 - Low | Support Portal | 3 business days |

### Enterprise Support

Enterprise customers have access to:

- Dedicated Technical Account Manager (TAM)
- Direct Slack channel with engineering team
- Priority queue for support tickets
- Quarterly business reviews
- On-site training and workshops

Contact your account representative or email enterprise@aenealabs.com for enterprise support inquiries.

---

## Version Information

| Component | Current Version | Release Date |
|-----------|-----------------|--------------|
| Aura Platform | 1.6.0 | January 2026 |
| API Version | v1 | January 2026 |
| Documentation | 1.0 | January 2026 |

### Change Log

For detailed release notes, see:
- [Platform CHANGELOG](../../CHANGELOG.md)
- [API Changelog](./api-reference/rest-api.md#changelog)

---

## Related Documentation

### Product Documentation

- [Getting Started Guide](../product/getting-started/index.md) - Platform overview and quick start
- [Core Concepts](../product/core-concepts/index.md) - Technical foundations
- [Installation Guide](../product/getting-started/installation.md) - Deployment options

### Architecture Decision Records

- [ADR Index](../architecture-decisions/) - All architecture decisions
- [ADR-032 Autonomy Framework](../architecture-decisions/ADR-032-autonomy-framework.md) - HITL configuration
- [ADR-034 Context Engineering](../architecture-decisions/ADR-034-context-engineering.md) - GraphRAG architecture

### Security Documentation

- [Security Services Overview](../security/SECURITY_SERVICES_OVERVIEW.md) - Security architecture
- [Compliance Profiles](../security/COMPLIANCE_PROFILES.md) - CMMC, SOX, NIST controls
- [Developer Security Guidelines](../security/DEVELOPER_SECURITY_GUIDELINES.md) - Secure coding practices

---

## Feedback

Help us improve this documentation:

- **Report Issues:** Create an issue in the documentation repository
- **Suggest Improvements:** Submit a pull request with proposed changes
- **Request Topics:** Email docs-feedback@aenealabs.com

---

*Last updated: January 2026 | Version 1.0*

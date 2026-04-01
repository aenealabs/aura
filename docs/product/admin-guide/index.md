# Administration Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This Administration Guide provides comprehensive documentation for deploying, configuring, and managing Project Aura in enterprise environments. Whether you are deploying the fully managed SaaS offering, a self-hosted Kubernetes cluster, or a hybrid configuration, this guide covers the essential administrative tasks.

Project Aura is an autonomous AI SaaS platform that enables machines to reason across entire enterprise codebases through a hybrid graph-based architecture. It automates vulnerability detection, patch generation, and security remediation with configurable human-in-the-loop approval processes.

---

## Guide Contents

| Document | Description | Audience |
|----------|-------------|----------|
| [Deployment Options](./deployment-options.md) | Deployment configurations for SaaS, self-hosted, hybrid, and GovCloud | Platform Engineers, DevOps |
| [Configuration Reference](./configuration-reference.md) | Complete environment variables, feature flags, and settings | Platform Engineers, DevOps |
| [User Management](./user-management.md) | Users, roles, teams, API keys, and service accounts | IT Admins, Security Teams |
| [SSO Integration](./sso-integration.md) | Single Sign-On with Okta, Azure AD, Google, and SAML/OIDC | IT Admins, Identity Teams |

---

## Architecture Overview

```
+-----------------------------------------------------------------------------+
|                           PROJECT AURA ARCHITECTURE                          |
+-----------------------------------------------------------------------------+

    +-------------------------+     +-------------------------+
    |     PRESENTATION LAYER  |     |      EXTERNAL SYSTEMS   |
    |  +-------------------+  |     |  +-------------------+  |
    |  |   Web Dashboard   |  |     |  |   GitHub/GitLab   |  |
    |  |   REST API        |  |     |  |   Jira/ServiceNow |  |
    |  |   GraphQL API     |  |     |  |   Slack/Teams     |  |
    |  +-------------------+  |     |  +-------------------+  |
    +------------+------------+     +------------+------------+
                 |                               |
                 +---------------+---------------+
                                 |
    +---------------------------+|+---------------------------+
    |                           |||                           |
    v                           v|v                           v
+-----------------------------------------------------------------------------+
|                           ORCHESTRATION LAYER                                |
|  +---------------------+  +---------------------+  +---------------------+  |
|  |   Agent Orchestrator|  |  Context Retrieval  |  |   HITL Workflow     |  |
|  |   - Coder Agent     |  |  - Hybrid GraphRAG  |  |   - Approvals       |  |
|  |   - Reviewer Agent  |  |  - Vector Search    |  |   - Escalations     |  |
|  |   - Validator Agent |  |  - Graph Traversal  |  |   - Audit Logging   |  |
|  +---------------------+  +---------------------+  +---------------------+  |
+-----------------------------------------------------------------------------+
                                 |
    +---------------------------+|+---------------------------+
    |                           |||                           |
    v                           v|v                           v
+-----------------------------------------------------------------------------+
|                              DATA LAYER                                      |
|  +---------------------+  +---------------------+  +---------------------+  |
|  |   AWS Neptune       |  |   AWS OpenSearch    |  |   AWS DynamoDB      |  |
|  |   (Graph Database)  |  |   (Vector Search)   |  |   (Document Store)  |  |
|  +---------------------+  +---------------------+  +---------------------+  |
|                                                                              |
|  Self-Hosted Alternatives:                                                  |
|  - Neo4j (Graph)   - OpenSearch (Self-Managed)   - PostgreSQL (Documents)  |
+-----------------------------------------------------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------------------+
|                          INFRASTRUCTURE LAYER                                |
|  +---------------------+  +---------------------+  +---------------------+  |
|  |   AWS EKS / K8s     |  |   AWS Bedrock       |  |   Security Controls |  |
|  |   - Worker Nodes    |  |   - Claude 3.5      |  |   - IAM / RBAC      |  |
|  |   - IRSA            |  |   - Model Selection |  |   - Encryption      |  |
|  |   - Auto Scaling    |  |   - Guardrails      |  |   - VPC Isolation   |  |
|  +---------------------+  +---------------------+  +---------------------+  |
+-----------------------------------------------------------------------------+
```

---

## Deployment Models

Project Aura supports multiple deployment models to meet diverse enterprise requirements:

| Model | Description | Best For |
|-------|-------------|----------|
| **SaaS** | Fully managed by Aenea Labs | Fast deployment, minimal ops overhead |
| **Self-Hosted Kubernetes** | Deploy on your own EKS, AKS, GKE, or on-premises K8s | Data sovereignty, compliance requirements |
| **Self-Hosted Podman** | Single-node deployment for development or small teams | Evaluation, development, small workloads |
| **Hybrid** | Data on-premises, compute in cloud | Regulated industries, data residency |
| **GovCloud** | AWS GovCloud deployment | Federal customers, FedRAMP, CMMC |

See [Deployment Options](./deployment-options.md) for detailed instructions for each model.

---

## Quick Start for Administrators

### SaaS Deployment (Recommended)

1. **Sign up** at [aenealabs.com/signup](https://aenealabs.com/signup)
2. **Configure SSO** (recommended for enterprise) - See [SSO Integration](./sso-integration.md)
3. **Create users and teams** - See [User Management](./user-management.md)
4. **Connect repositories** - OAuth integration with GitHub, GitLab, Bitbucket
5. **Set security policies** - Configure HITL autonomy levels

### Self-Hosted Deployment

1. **Review system requirements** - See [Deployment Options](./deployment-options.md)
2. **Choose deployment method** - Helm (production) or Podman (development)
3. **Deploy infrastructure** - Databases, Kubernetes, networking
4. **Configure environment** - See [Configuration Reference](./configuration-reference.md)
5. **Verify deployment** - Health checks and functional tests

---

## Security Highlights

Project Aura is designed for regulated industries with comprehensive security controls:

| Category | Controls |
|----------|----------|
| **Compliance** | CMMC Level 3, SOX, HIPAA, FedRAMP, SOC 2 |
| **Encryption** | AES-256 at rest, TLS 1.3 in transit, customer-managed KMS keys |
| **Access Control** | RBAC, IRSA, MFA, SSO, API key rotation |
| **Network** | VPC isolation, private subnets, VPC endpoints, WAF |
| **Audit** | Full audit trails, 7-year retention, immutable logs |
| **AI Safety** | Bedrock Guardrails, prompt injection protection, sandboxed execution |

> **Security Best Practice:** Always configure SSO with MFA enforcement for production deployments. Local authentication should be reserved for break-glass scenarios only.

---

## Administrative Tasks Matrix

| Task | Frequency | Guide Section |
|------|-----------|---------------|
| Add/remove users | As needed | [User Management](./user-management.md) |
| Rotate API keys | Quarterly | [User Management](./user-management.md#api-key-management) |
| Review audit logs | Weekly | [User Management](./user-management.md#audit-logging) |
| Update SSO certificates | Annually | [SSO Integration](./sso-integration.md) |
| Upgrade deployment | Monthly | [Deployment Options](./deployment-options.md#upgrades) |
| Review security policies | Quarterly | [Configuration Reference](./configuration-reference.md#agent-configuration) |
| Capacity planning | Monthly | [Deployment Options](./deployment-options.md) |
| Backup verification | Weekly | Operations Guide |

---

## Support Resources

### Documentation

- **Product Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **API Reference:** [api.aenealabs.com/docs](https://api.aenealabs.com/docs)
- **Release Notes:** [changelog.aenealabs.com](https://changelog.aenealabs.com)

### Support Channels

| Tier | Channel | Response Time |
|------|---------|---------------|
| **Enterprise** | Dedicated Slack, phone, email | 1 hour (P1), 4 hours (P2) |
| **Professional** | Email, support portal | 4 hours (P1), 8 hours (P2) |
| **Starter** | Support portal, community forum | 24 hours |

### Contact Information

- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Security Issues:** security@aenealabs.com
- **Sales Inquiries:** sales@aenealabs.com

---

## Related Documentation

- [Getting Started Guide](../getting-started/index.md)
- [Installation Guide](../getting-started/installation.md)
- [Core Concepts](../core-concepts/index.md)
- [HITL Workflows](../core-concepts/hitl-workflows.md)
- [Architecture Overview](../../support/architecture/index.md)
- [Security Architecture](../../support/architecture/security-architecture.md)
- [Operations Guide](../../support/operations/index.md)

---

*Last updated: January 2026 | Version 1.0*

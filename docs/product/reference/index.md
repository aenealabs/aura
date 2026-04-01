# Reference Documentation

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This section provides quick-reference materials for Project Aura users, administrators, and developers. Use these resources to find definitions, understand platform constraints, and track product changes.

---

## Reference Materials

### [Glossary](./glossary.md)

A comprehensive alphabetical listing of terms, acronyms, and concepts used throughout Project Aura documentation. Use this resource when you encounter unfamiliar terminology or need precise definitions for compliance documentation.

**Includes:**
- AI and machine learning terminology (GraphRAG, RAG, embeddings)
- Security and compliance terms (CMMC, FedRAMP, CVSS, CVE)
- Platform components (agents, services, databases)
- AWS infrastructure concepts (EKS, Fargate, Neptune)

---

### [Service Limits](./service-limits.md)

Detailed documentation of platform quotas, rate limits, and capacity constraints. Essential reading before planning large-scale deployments or enterprise onboarding.

**Covers:**
- Repository and scan limits by subscription tier
- API rate limits and throttling policies
- Storage and retention quotas
- Concurrent operation limits
- GPU workload constraints

---

### [Release Notes](./release-notes.md)

Chronological record of platform changes, including new features, improvements, bug fixes, and deprecations. Subscribe to release notifications to stay informed about platform updates.

**Includes:**
- Version numbering conventions
- Release cadence information
- Recent release highlights (v1.3.x series)
- Breaking change notices
- Deprecation timeline

---

## Quick Links

| Resource | Description |
|----------|-------------|
| [Getting Started](../getting-started/index.md) | Platform overview and initial setup |
| [Core Concepts](../core-concepts/index.md) | Deep-dive into platform architecture |
| [Troubleshooting](../../support/troubleshooting/index.md) | Common issues and solutions |
| [API Reference](../../support/api-reference/index.md) | REST and GraphQL API documentation |
| [FAQ](../../support/faq.md) | Frequently asked questions |

---

## Reference Documentation by Role

### Security Engineers

| Resource | Key Sections |
|----------|--------------|
| [Glossary](./glossary.md) | CVE, CVSS, vulnerability severity definitions |
| [Service Limits](./service-limits.md) | Concurrent scan limits, agent timeouts |
| [Release Notes](./release-notes.md) | Security improvements, compliance updates |

### DevOps Engineers

| Resource | Key Sections |
|----------|--------------|
| [Glossary](./glossary.md) | Infrastructure terms, deployment concepts |
| [Service Limits](./service-limits.md) | API rate limits, storage quotas |
| [Release Notes](./release-notes.md) | Infrastructure changes, deprecations |

### Compliance Officers

| Resource | Key Sections |
|----------|--------------|
| [Glossary](./glossary.md) | Compliance framework definitions |
| [Service Limits](./service-limits.md) | Audit log retention, data residency |
| [Release Notes](./release-notes.md) | Compliance certifications, audit changes |

### Platform Administrators

| Resource | Key Sections |
|----------|--------------|
| [Glossary](./glossary.md) | All platform terminology |
| [Service Limits](./service-limits.md) | Organization and user limits |
| [Release Notes](./release-notes.md) | All platform changes |

---

## Document Conventions

Throughout the reference documentation, the following conventions are used:

### Status Indicators

| Symbol | Meaning |
|--------|---------|
| Supported | Feature is fully available and supported |
| Preview | Feature is available but may change |
| Deprecated | Feature will be removed in a future release |
| Enterprise Only | Feature requires Enterprise subscription |

### Tier Abbreviations

| Abbreviation | Tier |
|--------------|------|
| Free | Free tier (individual developers) |
| Team | Team tier (small to medium teams) |
| Enterprise | Enterprise tier (large organizations) |

### Environment Abbreviations

| Abbreviation | Environment |
|--------------|-------------|
| DEV | Development environment |
| QA | Quality Assurance environment |
| PROD | Production environment |
| GovCloud | AWS GovCloud (US) deployment |

---

## Feedback

Found an error or have a suggestion for improving reference documentation? Contact your Aenea Labs account representative or submit feedback through the platform's Help menu.

---

**Related Documentation:**
- [System Requirements](../getting-started/system-requirements.md)
- [Architecture Overview](../../support/architecture/system-overview.md)
- [Security Architecture](../../support/architecture/security-architecture.md)

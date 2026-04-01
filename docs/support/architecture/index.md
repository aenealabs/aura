# Architecture Documentation

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This section provides comprehensive architecture documentation for Project Aura, enabling platform engineers, security architects, and operations teams to understand system design, data flows, security boundaries, and disaster recovery procedures.

---

## Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| [System Overview](./system-overview.md) | High-level architecture and component relationships | All technical roles |
| [Data Flow](./data-flow.md) | How data moves through the system | Platform Engineers, Security |
| [Security Architecture](./security-architecture.md) | Security controls, encryption, network isolation | Security Engineers, Compliance |
| [Disaster Recovery](./disaster-recovery.md) | Backup, recovery, RTO/RPO | Operations, Platform Engineers |

---

## Architecture Principles

Project Aura's architecture is guided by these core principles:

### 1. Security First

Every architectural decision prioritizes security:

- Zero-trust network architecture
- Encryption at rest and in transit
- Principle of least privilege for all components
- Defense in depth with multiple security layers

### 2. Compliance by Design

Built for regulated industries from inception:

- CMMC Level 3 controls embedded in architecture
- Immutable audit trails for all operations
- Data isolation for multi-tenancy
- GovCloud deployment path

### 3. Scalability and Resilience

Designed for enterprise workloads:

- Horizontal scaling for all compute layers
- Multi-AZ deployment for high availability
- Graceful degradation under load
- Automated recovery from failures

### 4. Operational Excellence

Infrastructure as code and automation:

- CloudFormation for all AWS resources
- GitOps for Kubernetes deployments
- Centralized logging and monitoring
- Self-healing infrastructure

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 8                                     │
│                        SECURITY & COMPLIANCE                             │
│           AWS Config | GuardDuty | CloudTrail | Drift Detection          │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 7                                     │
│                          SANDBOX ISOLATION                               │
│              HITL Workflow | Step Functions | ECS Fargate                │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 6                                     │
│                            SERVERLESS                                    │
│           Lambda | EventBridge | Step Functions | Chat Assistant         │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 5                                     │
│                          OBSERVABILITY                                   │
│         CloudWatch | Secrets Manager | Cost Alerts | Prometheus          │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 4                                     │
│                           APPLICATION                                    │
│              API Services | Bedrock LLM | Frontend | Agents              │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 3                                     │
│                             COMPUTE                                      │
│                  EKS Cluster | EC2 Node Groups | ECR                     │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 2                                     │
│                               DATA                                       │
│             Neptune (Graph) | OpenSearch (Vector) | DynamoDB             │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYER 1                                     │
│                            FOUNDATION                                    │
│           VPC | IAM | WAF | Security Groups | VPC Endpoints              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### Compute Platform

| Component | Technology | Purpose |
|-----------|------------|---------|
| Container Orchestration | AWS EKS 1.34 | Kubernetes workload management |
| Node Groups | EC2 Managed | GovCloud-compatible compute |
| Container Registry | Amazon ECR | Private container image storage |
| Service Mesh | None (simplified) | Direct service-to-service communication |

### Data Platform

| Component | Technology | Purpose |
|-----------|------------|---------|
| Graph Database | Amazon Neptune | Code structure and relationships |
| Vector Database | Amazon OpenSearch | Semantic search and embeddings |
| State Store | Amazon DynamoDB | Agent state, approvals, sessions |
| Object Storage | Amazon S3 | Artifacts, logs, backups |

### AI/ML Platform

| Component | Technology | Purpose |
|-----------|------------|---------|
| LLM Provider | Amazon Bedrock | Claude 3.5 Sonnet for AI agents |
| Embedding Model | Bedrock Titan | Code and text embeddings |
| Context Engine | Custom (GraphRAG) | Hybrid retrieval for code context |

### Security Platform

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Application Firewall | AWS WAF | Request filtering, rate limiting |
| Threat Detection | Amazon GuardDuty | Runtime threat detection |
| Configuration Compliance | AWS Config | Drift detection, compliance rules |
| Identity Management | IAM + IRSA | Service authentication |

---

## Deployment Environments

| Environment | Purpose | AWS Region | Notes |
|-------------|---------|------------|-------|
| Development | Feature development | us-east-1 | Reduced capacity |
| QA | Integration testing | us-east-1 | Production-like config |
| Staging | Pre-production validation | us-east-1 | Production mirror |
| Production | Live customer workloads | us-gov-west-1 | GovCloud |

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            AWS WAF                                       │
│                    (Rate Limiting, Geo Blocking)                         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     APPLICATION LOAD BALANCER                            │
│                        (TLS Termination)                                 │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
          ┌──────────────────────┴──────────────────────┐
          │                                             │
          ▼                                             ▼
┌────────────────────────┐                ┌────────────────────────┐
│      PUBLIC SUBNET     │                │      PUBLIC SUBNET     │
│        (AZ-a)          │                │        (AZ-b)          │
│    NAT Gateway         │                │    NAT Gateway         │
└──────────┬─────────────┘                └──────────┬─────────────┘
           │                                         │
           ▼                                         ▼
┌────────────────────────┐                ┌────────────────────────┐
│     PRIVATE SUBNET     │                │     PRIVATE SUBNET     │
│        (AZ-a)          │                │        (AZ-b)          │
│  ┌──────────────────┐  │                │  ┌──────────────────┐  │
│  │   EKS Workers    │  │  ◄──────────►  │  │   EKS Workers    │  │
│  └──────────────────┘  │                │  └──────────────────┘  │
└──────────┬─────────────┘                └──────────┬─────────────┘
           │                                         │
           └─────────────────┬───────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA SUBNET                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Neptune   │  │ OpenSearch  │  │  DynamoDB   │  │     S3      │    │
│  │   Cluster   │  │   Domain    │  │  (Endpoint) │  │  (Endpoint) │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Service Discovery

Internal service communication uses DNS-based discovery:

| Service | DNS Name | Port |
|---------|----------|------|
| Neptune | neptune.aura.local | 8182 |
| OpenSearch | opensearch.aura.local | 9200 |
| Orchestrator | orchestrator.aura.local | 8080 |
| Context Retrieval | context-retrieval.aura.local | 8080 |
| API Service | api.aura.local | 8080 |

DNS is managed by dnsmasq deployed as a DaemonSet with DNSSEC support.

---

## Technology Stack Summary

| Category | Technologies |
|----------|--------------|
| **Languages** | Python 3.11, TypeScript, Go |
| **Frameworks** | FastAPI, React 18, Next.js 14 |
| **Databases** | Neptune, OpenSearch, DynamoDB |
| **Container** | Podman, Docker, EKS |
| **Infrastructure** | CloudFormation, Kubernetes, Terraform (planned) |
| **Monitoring** | CloudWatch, Prometheus, Grafana |
| **Security** | WAF, GuardDuty, AWS Config, KMS |

---

## Architecture Decision Records

Key architectural decisions are documented in ADRs:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-004 | Cloud Abstraction Layer | Deployed |
| ADR-024 | Titan Neural Memory Architecture | Deployed |
| ADR-032 | Autonomy Framework | Deployed |
| ADR-034 | Context Engineering | Deployed |
| ADR-037 | AWS Agent Parity | Deployed |
| ADR-042 | Real-Time Agent Intervention | Phase 1 |
| ADR-049 | Self-Hosted Deployment | Deployed |
| ADR-051 | Recursive Context & Embedding | Deployed |

Full ADR index: [docs/architecture-decisions/](../../architecture-decisions/)

---

## Related Documentation

- [System Overview](./system-overview.md)
- [Data Flow](./data-flow.md)
- [Security Architecture](./security-architecture.md)
- [Disaster Recovery](./disaster-recovery.md)
- [Operations Guide](../operations/index.md)
- [Core Concepts](../../product/core-concepts/index.md)

---

*Last updated: January 2026 | Version 1.0*

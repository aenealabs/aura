# ADR-049: Self-Hosted Deployment Strategy

**Status:** Deployed (All Phases Complete)
**Date:** 2025-12-31
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-004 (Cloud Abstraction Layer), ADR-036 (Multi-Platform Container Builds)

> **Implementation Details:** See [ADR-049-IMPLEMENTATION-DETAILS.md](../self-hosted/ADR-049-IMPLEMENTATION-DETAILS.md) for technical specifications, expert reviews, and appendices.

---

## Executive Summary

This ADR documents the decision to enable Project Aura as a self-hosted application supporting Windows, Linux (Ubuntu, RHEL), and macOS platforms, in addition to the existing AWS SaaS deployment.

**Key Outcomes:**
- Cross-platform deployment support (Windows, Ubuntu, RHEL, macOS)
- Open-core licensing model with Community and Enterprise editions
- Multiple deployment methods: Podman Compose, Helm Charts, Native Installers
- Cloud-agnostic database adapters (Neptune → Neo4j, OpenSearch → self-managed)
- Pluggable LLM layer (vLLM, TGI, cloud providers via PrivateLink)
- Air-gapped deployment support for regulated industries
- Unified codebase with feature flags for edition differentiation

---

## Context

### Current State

Project Aura is deployed as a SaaS platform on AWS:
- **Infrastructure:** EKS, Neptune, OpenSearch, DynamoDB, S3, Cognito
- **Deployment:** CloudFormation via CodeBuild CI/CD
- **Target:** AWS Commercial and GovCloud regions

### Market Demand

Enterprise customers in regulated industries require self-hosted options:

| Sector | Requirement |
|--------|-------------|
| Government/Defense | Air-gapped, FedRAMP/CMMC, data sovereignty |
| Healthcare | HIPAA, patient data on-premises |
| Financial Services | SOX compliance, data residency |
| Critical Infrastructure | Disconnected operations |

### Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Support Windows Server 2019+, Ubuntu 20.04+, RHEL 8+, macOS 12+ | P0 |
| R2 | Single-command installation for evaluation | P0 |
| R3 | Kubernetes deployment for production | P0 |
| R4 | Air-gapped installation without internet | P1 |
| R5 | Feature parity between SaaS and self-hosted | P1 |
| R6 | Automated updates with rollback | P1 |
| R7 | License management with offline validation | P1 |
| R8 | Native OS installers (MSI, DEB, RPM, PKG) | P2 |

---

## Decision

**Implement a multi-tier self-hosted deployment strategy with open-core licensing, leveraging the existing Cloud Abstraction Layer (ADR-004).**

### Critical Decision: Hybrid LLM Strategy

**Self-hosted LLM inference is NOT recommended for most enterprises.** Cloud LLM APIs are preferred:

| Tier | Use Case | LLM Strategy | GPU Required |
|------|----------|--------------|--------------|
| **Tier 1: Cloud-Connected** | Most enterprises | AWS Bedrock via PrivateLink | No |
| **Tier 2: Multi-Cloud** | Cloud-agnostic | Azure OpenAI + Bedrock failover | No |
| **Tier 3: Air-Gapped** | Defense/classified (<5%) | vLLM + Mistral on-prem | Yes |

### Container Runtime: Podman over Docker

| Factor | Docker | Podman |
|--------|--------|--------|
| Licensing | Paid for enterprise | Free (Apache 2.0) |
| Security | Root daemon | Daemonless, rootless |
| RHEL Support | Third-party | Native (Red Hat) |
| CLI Compatibility | N/A | Drop-in alias |

### Licensing Model

```
┌─────────────────────────────────────────────────────────────┐
│  ENTERPRISE EDITION (Paid)                                  │
│  - SSO/SAML, Advanced RBAC, Audit logging, Multi-tenant     │
│  - Air-gapped tools, Compliance reporting, Priority support │
├─────────────────────────────────────────────────────────────┤
│  COMMUNITY EDITION (Apache 2.0)                             │
│  - Full GraphRAG, HITL workflows, Security scanning         │
│  - Sandbox testing, Basic RBAC, Community support           │
└─────────────────────────────────────────────────────────────┘
```

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT MODES                          │
├───────────────────┬───────────────────┬─────────────────────┤
│  Podman Compose   │  Kubernetes/Helm  │  Native Installers  │
│  (Dev/Small)      │  (Production)     │  (CLI Tools)        │
│  <100 users       │  100-10,000 users │  MSI/DEB/RPM/PKG    │
└───────────────────┴───────────────────┴─────────────────────┘
                              │
                    Cloud Abstraction Layer (ADR-004)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Graph Database      Vector Database      Document Store
   SaaS: Neptune       SaaS: OpenSearch     SaaS: DynamoDB
   Self: Neo4j         Self: OpenSearch     Self: PostgreSQL
```

---

## Implementation Phases

| Phase | Duration | Scope | Status |
|-------|----------|-------|--------|
| Phase 0 | 2 weeks | Prerequisites (query strategy, NetworkPolicy, Ed25519 license) | ✅ Complete |
| Phase 1 | 10 weeks | Foundation (Neo4j adapter, Podman Compose, security) | ✅ Complete |
| Phase 1.5 | 3 weeks | Migration Toolkit (SaaS→Self-Hosted) | ✅ Complete |
| Phase 2 | 6 weeks | Kubernetes/Helm (production) | ✅ Complete |
| Phase 3 | 8 weeks | Air-Gap Support (offline bundles, FIPS) | ✅ Complete |
| Phase 4 | 4 weeks | Distribution (Native installers, Homebrew) | ✅ Complete |

**Total: 33 weeks**

### Phase Checklists

<details>
<summary>Phase 0: Pre-Implementation</summary>

- [x] Document existing DynamoDB table schemas
- [x] Decide query language strategy (Gremlin via Neo4j plugin)
- [x] Design Ed25519 license validation scheme
- [x] Implement default-deny NetworkPolicy template
- [x] Map feature flags to Community/Enterprise editions
</details>

<details>
<summary>Phase 1: Foundation</summary>

- [x] Extend ADR-004 with SELF_HOSTED provider
- [x] Implement Neo4j adapter with TLS
- [x] Implement PostgreSQL adapter for DynamoDB
- [x] Implement LLM provider abstraction
- [x] Create Podman/Docker Compose configuration
- [x] Add container security contexts
- [x] Community Edition license validation (Ed25519)
</details>

<details>
<summary>Phase 1.5: Migration Toolkit</summary>

- [x] Extend export API for graph/vector data
- [x] Create `aura-bundle` export format
- [x] Build import CLI tool
- [x] Document schema versioning
</details>

<details>
<summary>Phase 2: Production Ready</summary>

- [x] Helm chart development
- [x] Kubernetes manifests with HTTPS probes
- [x] HPA and PDB configuration
- [x] Default-deny NetworkPolicy
- [x] cert-manager integration
- [x] External Secrets Operator support
</details>

<details>
<summary>Phase 3: Enterprise Features</summary>

- [x] Air-gapped installation package
- [x] Offline license validation
- [x] SAML/SSO integration (Keycloak)
- [x] Backup/restore tooling
- [x] FIPS 140-2 compliance option
</details>

<details>
<summary>Phase 4: Distribution</summary>

- [x] Native CLI installers (MSI, DEB, RPM, PKG)
- [x] Homebrew formula
- [x] Documentation portal
- [x] Tiered testing strategy
</details>

---

## Key Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Feature drift SaaS/self-hosted | High | Unified codebase with feature flags |
| Security vulnerabilities | High | Regular releases, CVE monitoring |
| Database adapter bugs | High | Integration testing, Tier 1/2/3 strategy |
| LLM license violations | High | Documentation, license acceptance workflow |
| Gremlin/Cypher incompatibility | High | Neo4j Gremlin plugin |
| Test matrix explosion (864 combos) | Medium | Tiered testing (Tier 1 every PR) |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Installation success rate | >95% |
| Time to first deployment | <30 min |
| Self-hosted customer satisfaction | >4.0/5.0 |
| Support tickets per customer | <2/month |
| Self-hosted revenue contribution | 20% of total |

---

## Alternatives Considered

| Alternative | Decision | Reason |
|-------------|----------|--------|
| SaaS-Only | Rejected | Excludes regulated industries |
| Managed Private Cloud Only | Rejected | Doesn't address air-gapped |
| Source-Available Without Support | Rejected | Fragments community |
| Partner-Only Distribution | Rejected | Adds friction |
| Ollama as Default LLM | Rejected | Model licensing unclear |

---

## Consequences

### Positive

- Access to regulated industry markets (government, healthcare, finance)
- Competitive parity with GitLab, Snyk, Sentry
- Data sovereignty for international customers
- Exit strategy for vendor lock-in concerns
- Community contribution potential

### Negative

- Increased engineering complexity (multiple deployment modes)
- Support burden for diverse environments
- Security responsibility shared with customers
- Slower feature velocity (cross-platform testing)
- Revenue cannibalization risk (SaaS → self-hosted)

---

## References

- [Implementation Details](../self-hosted/ADR-049-IMPLEMENTATION-DETAILS.md) - Technical specs, expert reviews, appendices
- [GitLab Self-Managed](https://docs.gitlab.com/ee/install/)
- [Replicated KOTS](https://docs.replicated.com/)
- [ADR-004: Cloud Abstraction Layer](./ADR-004-cloud-abstraction-layer.md)
- [vLLM Documentation](https://docs.vllm.ai/)

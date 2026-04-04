# ADR-074: Palantir AIP Integration for Data-Informed Code Security

## Status

Deployed

## Date

2026-01-29

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Systems Review | Senior Systems Architect | 2026-01-28 | Conditional Approval |
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Principal Data Engineer | - | - |

### Review Summary

**Senior Systems Architect (2026-01-28):** Conditional approval with 5 required changes incorporated:
1. ✅ Added EnterpriseDataPlatformAdapter abstraction layer for future Databricks/Snowflake/ServiceNow support
2. ✅ Added Circuit Breaker design section with explicit failure thresholds and fallback behavior
3. ✅ Added Observability infrastructure specification with CloudWatch metrics and alarms
4. ✅ Added Tenant Isolation rules for GovCloud multi-tenant deployments
5. ✅ Added Conflict Resolution matrix per object type with clear authority rules

Additional enhancements incorporated:
- Schema versioning strategy for API and event schemas
- Use Cases 4 (Insider Threat) and 5 (Compliance Drift) for stronger value proposition
- Event stream throughput specifications
- Quantitative MTTR differentiators in competitive positioning

## Context

### Strategic Opportunity

Palantir's Artificial Intelligence Platform (AIP) is a widely adopted enterprise data integration and decision intelligence platform, with public deployments in defense, healthcare, and financial services (as of January 2026, per Palantir's publicly disclosed customers). Publicly documented strengths include:

- **Ontology-based data modeling**: Unified semantic layer across disparate data sources
- **AIP Logic**: LLM-powered decision workflows grounded in enterprise data
- **Foundry Pipelines**: Large-scale data transformation and enrichment
- **GovCloud presence**: FedRAMP High, IL5/IL6 certifications

Aura's complementary strengths:

- **Autonomous code security**: LLM-powered vulnerability detection and remediation
- **Hybrid GraphRAG**: Structural + semantic code understanding
- **HITL governance**: Configurable autonomy with human approval workflows
- **Sandbox validation**: Safe patch verification in isolated environments

### Gap Analysis

| Capability | Palantir AIP | Aura | Integration Value |
|------------|--------------|------|-------------------|
| Threat intelligence | ✅ Aggregates from multiple feeds | ❌ Not integrated | Prioritize remediation by active threats |
| Asset inventory | ✅ Comprehensive CMDB | ⚠️ Repository-scoped | Correlate vulns to business-critical assets |
| Vulnerability data | ⚠️ CVE feeds only | ✅ Deep code analysis | Enrich threat models with code context |
| SBOM management | ⚠️ Basic tracking | ✅ Full dependency graphs | Supply chain risk visibility |
| Remediation | ❌ Manual workflows | ✅ Autonomous patching | Close the loop from detection to fix |
| Compliance evidence | ✅ Audit trails | ✅ Patch verification | End-to-end compliance automation |

### Target Customers

The integration targets organizations requiring both data-centric security operations and autonomous code remediation:

1. **Defense Industrial Base (DIB)**: CMMC compliance, supply chain security
2. **Healthcare**: HIPAA-compliant vulnerability management
3. **Financial Services**: SOX compliance, real-time threat response
4. **Critical Infrastructure**: NERC CIP, ICS/OT security

### Competitive Landscape

The following landscape reflects publicly documented capabilities as of January 2026. Each referenced vendor offers capabilities Aura does not (e.g., Snyk's developer ecosystem integrations, Splunk's mature SIEM analytics, ServiceNow's ITSM platform breadth, GitHub's developer platform scale). The table highlights specific gaps relevant to autonomous code remediation paired with enterprise data context.

| Stack (as of Jan 2026) | Data Integration | Code Remediation | Publicly Documented Gap for this Use Case |
|------------|------------------|------------------|---------------------|
| Snyk + Splunk | Log aggregation | Primarily advisory/fix suggestions | No publicly documented autonomous remediation workflow |
| Veracode + ServiceNow | ITSM ticketing | Prioritization + manual fix workflows | No publicly documented autonomous patch generation |
| GitHub + Datadog | Observability | Dependabot (version bumps) | No publicly documented threat-intel-driven prioritization |
| **Aura + Palantir (this ADR)** | **Ontology-based** | **Autonomous with HITL** | **N/A – target architecture** |

### Target Differentiators

The following are internal targets for the integrated Aura + Palantir architecture described in this ADR. They reflect design goals, not measured industry averages:

| Metric | Aura + Palantir Target | Notes |
|--------|-----------------|-------|
| Mean Time to Remediation (MTTR) | 2 hours (target) | Industry MTTR varies widely by vulnerability class and organization |
| Threat-to-patch correlation | 97% (design target) | Dependent on Palantir threat intel coverage |
| Autonomous remediation rate | 85%+ (design target) | Requires HITL approval gates per ADR-032 |
| False positive deployment rate | <1% (design target) | Measured against sandbox validation outcomes |

## Decision

Implement a bidirectional integration between Aura and Palantir AIP to enable "Data-Informed Code Security" — where Palantir's threat intelligence and asset context enriches Aura's remediation prioritization, and Aura's code security insights flow back to Palantir's operational dashboards.

## Architecture

### High-Level Integration

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PALANTIR AIP                                       │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │     Ontology     │  │    AIP Logic     │  │     Foundry      │          │
│  │     Objects      │  │    Workflows     │  │    Pipelines     │          │
│  │                  │  │                  │  │                  │          │
│  │  • ThreatActor   │  │  • Risk Scoring  │  │  • CVE Feeds     │          │
│  │  • Vulnerability │  │  • Prioritization│  │  • Asset Import  │          │
│  │  • Asset         │  │  • Alerting      │  │  • SBOM Ingest   │          │
│  │  • Repository    │  │  • Remediation   │  │  • Enrichment    │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
└───────────┼─────────────────────┼─────────────────────┼─────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       INTEGRATION LAYER                                      │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Ontology Bridge │  │  Event Stream    │  │  Federated       │          │
│  │     Service      │  │   Connector      │  │   Identity       │          │
│  │                  │  │                  │  │                  │          │
│  │  • Object Sync   │  │  • Kafka/Kinesis │  │  • SAML/OIDC     │          │
│  │  • Schema Map    │  │  • CDC Events    │  │  • mTLS Auth     │          │
│  │  • Conflict Res  │  │  • Replay/DLQ    │  │  • Token Exchange│          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
└───────────┼─────────────────────┼─────────────────────┼─────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AURA PLATFORM                                        │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │    GraphRAG      │  │     Agent        │  │    Sandbox       │          │
│  │    Context       │  │   Orchestrator   │  │   Validation     │          │
│  │                  │  │                  │  │                  │          │
│  │  • Code Graph    │  │  • Prioritized   │  │  • Patch Test    │          │
│  │  • Dependency    │  │    Remediation   │  │  • Security Scan │          │
│  │  • Vuln Mapping  │  │  • HITL Approval │  │  • Perf Bench    │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Enterprise Data Platform Abstraction

To enable future integrations with Databricks, Snowflake, ServiceNow, and other enterprise platforms without architectural changes, the integration layer uses an abstract adapter pattern.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                 ENTERPRISE DATA PLATFORM ABSTRACTION LAYER                   │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Palantir AIP    │  │   Databricks     │  │   Snowflake      │          │
│  │    Adapter       │  │    Adapter       │  │    Adapter       │          │
│  │  (Implemented)   │  │   (Future)       │  │   (Future)       │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   ServiceNow     │  │    Alation       │  │    Collibra      │          │
│  │    Adapter       │  │    Adapter       │  │    Adapter       │          │
│  │   (Future)       │  │   (Future)       │  │   (Future)       │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
│           └─────────────────────┼─────────────────────┘                     │
│                                 │                                           │
│                                 ▼                                           │
│           ┌─────────────────────────────────────────────────┐              │
│           │      EnterpriseDataPlatformAdapter (ABC)        │              │
│           │                                                 │              │
│           │  @abstractmethod                                │              │
│           │  async def get_threat_context(cves) -> list     │              │
│           │                                                 │              │
│           │  @abstractmethod                                │              │
│           │  async def get_asset_criticality(repo) -> Asset │              │
│           │                                                 │              │
│           │  @abstractmethod                                │              │
│           │  async def publish_event(event) -> bool         │              │
│           └─────────────────────────────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Platform-Specific Implementations

| Platform | Type | Threat Source | Asset Source | Event Sink |
|----------|------|---------------|--------------|------------|
| **Palantir AIP** | Ontology | Ontology ThreatActor | Ontology Asset | Foundry Pipelines |
| **Databricks** | Lakehouse | Unity Catalog threat tables | Asset metadata tables | Delta Live Tables |
| **Snowflake** | Lakehouse | Secure Data Sharing | CMDB tables | Snowpipe ingestion |
| **ServiceNow** | ITSM | Security Incident Response | CMDB CI records | Event Management |
| **Alation** | Data Catalog | N/A | Data asset catalog | N/A |

#### Abstract Interface Definition

```python
# src/services/integrations/enterprise_data_platform.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class EnterprisePlatformType(Enum):
    """Categories of enterprise data platforms."""
    ONTOLOGY = "ontology"        # Palantir, ServiceNow CMDB
    LAKEHOUSE = "lakehouse"      # Databricks, Snowflake
    DATA_CATALOG = "data_catalog"  # Alation, Collibra

@dataclass
class ThreatContext:
    """Platform-agnostic threat context."""
    threat_id: str
    source_platform: str
    cves: list[str]
    epss_score: float | None
    mitre_ttps: list[str]
    targeted_industries: list[str]
    raw_metadata: dict  # Platform-specific fields

@dataclass
class AssetContext:
    """Platform-agnostic asset criticality."""
    asset_id: str
    criticality_score: int  # 1-10
    data_classification: str
    business_owner: str | None
    pii_handling: bool
    phi_handling: bool

class EnterpriseDataPlatformAdapter(ABC):
    """Abstract adapter for enterprise data platforms."""

    @abstractmethod
    async def get_threat_context(self, cve_ids: list[str]) -> list[ThreatContext]:
        """Retrieve threat context for given CVEs."""

    @abstractmethod
    async def get_asset_criticality(self, repo_id: str) -> AssetContext | None:
        """Get asset criticality for a repository."""

    @abstractmethod
    async def publish_remediation_event(self, event: RemediationEvent) -> bool:
        """Publish remediation status to the platform."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify platform connectivity."""
```

### Data Flow Architecture

```text
                    PALANTIR → AURA (Enrichment)
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  Threat Intelligence Feed                                                    │
│  ────────────────────────                                                    │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   MITRE     │     │    NVD/     │     │  Internal   │                   │
│  │   ATT&CK    │────▶│    CVE      │────▶│   Threat    │                   │
│  │   Mapping   │     │   Feeds     │     │   Intel     │                   │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                   │
│                                                  │                          │
│                                                  ▼                          │
│                           ┌─────────────────────────────────┐              │
│                           │    Palantir Ontology Objects    │              │
│                           │                                 │              │
│                           │  ThreatActor:                   │              │
│                           │    • actor_id, name, ttps       │              │
│                           │    • active_campaigns[]         │              │
│                           │    • targeted_industries[]      │              │
│                           │                                 │              │
│                           │  Vulnerability:                 │              │
│                           │    • cve_id, cvss, epss         │              │
│                           │    • exploited_in_wild          │              │
│                           │    • associated_actors[]        │              │
│                           │                                 │              │
│                           │  Asset:                         │              │
│                           │    • asset_id, criticality      │              │
│                           │    • business_owner             │              │
│                           │    • data_classification        │              │
│                           └──────────────┬──────────────────┘              │
│                                          │                                  │
│                                          │ Ontology Bridge                  │
│                                          │ (REST/gRPC)                      │
│                                          ▼                                  │
│                           ┌─────────────────────────────────┐              │
│                           │     Aura Context Enrichment     │              │
│                           │                                 │              │
│                           │  • Threat-informed priority     │              │
│                           │  • Asset criticality scoring    │              │
│                           │  • Actor TTP correlation        │              │
│                           │  • Exploit prediction (EPSS)    │              │
│                           └─────────────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                    AURA → PALANTIR (Remediation Status)
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  Code Security Events                                                        │
│  ────────────────────                                                        │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   Vuln      │     │   Patch     │     │  Sandbox    │                   │
│  │  Detection  │────▶│  Generation │────▶│ Validation  │                   │
│  │   Event     │     │   Event     │     │   Event     │                   │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                   │
│                                                  │                          │
│                                                  ▼                          │
│                           ┌─────────────────────────────────┐              │
│                           │      Aura Event Stream          │              │
│                           │                                 │              │
│                           │  VulnerabilityDetected:         │              │
│                           │    • vuln_id, cve_id, severity  │              │
│                           │    • affected_files[]           │              │
│                           │    • code_snippet               │              │
│                           │                                 │              │
│                           │  PatchGenerated:                │              │
│                           │    • patch_id, vuln_id          │              │
│                           │    • confidence_score           │              │
│                           │    • requires_approval          │              │
│                           │                                 │              │
│                           │  RemediationComplete:           │              │
│                           │    • patch_id, status           │              │
│                           │    • test_results               │              │
│                           │    • deployed_at                │              │
│                           └──────────────┬──────────────────┘              │
│                                          │                                  │
│                                          │ Event Stream                     │
│                                          │ (Kafka/Kinesis)                  │
│                                          ▼                                  │
│                           ┌─────────────────────────────────┐              │
│                           │   Palantir Foundry Ingest       │              │
│                           │                                 │              │
│                           │  • Remediation dashboards       │              │
│                           │  • MTTR metrics                 │              │
│                           │  • Compliance evidence          │              │
│                           │  • Risk posture trending        │              │
│                           └─────────────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. Ontology Bridge Service

Synchronizes Palantir Ontology objects with Aura's internal data model.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ONTOLOGY BRIDGE SERVICE                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         API Layer                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │   │
│  │  │   REST      │  │   gRPC      │  │  GraphQL    │  │  Webhook   │ │   │
│  │  │  /api/v1/   │  │  Bridge.*   │  │  /graphql   │  │  /hooks/   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Object Mapper                                   │   │
│  │                                                                      │   │
│  │  Palantir Object          Aura Model           Mapping Rules         │   │
│  │  ──────────────           ──────────           ─────────────         │   │
│  │  ThreatActor       ──▶    ThreatContext    ──▶ actor_id → id        │   │
│  │  Vulnerability     ──▶    VulnerabilityEnrichment ──▶ cve_id → cve  │   │
│  │  Asset             ──▶    AssetContext     ──▶ asset_id → repo_id   │   │
│  │  Repository        ──▶    Repository       ──▶ 1:1 mapping          │   │
│  │  Compliance        ──▶    ComplianceReq    ──▶ control → adr_ref    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Sync Engine                                     │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │   │
│  │  │   Full      │  │ Incremental │  │  Conflict   │  │   Audit    │ │   │
│  │  │   Sync      │  │    Sync     │  │ Resolution  │  │    Log     │ │   │
│  │  │  (hourly)   │  │  (realtime) │  │ (LWW/merge) │  │ (immutable)│ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 2. Event Stream Connector

Publishes Aura events to Palantir Foundry for dashboarding and analytics.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EVENT STREAM CONNECTOR                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Event Sources (Aura)                             │   │
│  │                                                                      │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │   │
│  │  │   Agent    │ │  Sandbox   │ │   HITL     │ │  GraphRAG  │       │   │
│  │  │Orchestrator│ │ Validator  │ │  Approval  │ │  Context   │       │   │
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘       │   │
│  │        │              │              │              │               │   │
│  │        └──────────────┴──────────────┴──────────────┘               │   │
│  │                              │                                       │   │
│  └──────────────────────────────┼───────────────────────────────────────┘   │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Event Router                                     │   │
│  │                                                                      │   │
│  │  Event Type               Topic                   Schema             │   │
│  │  ──────────               ─────                   ──────             │   │
│  │  VulnerabilityDetected    aura.vuln.detected      VulnEventV1       │   │
│  │  PatchGenerated           aura.patch.generated    PatchEventV1      │   │
│  │  SandboxValidated         aura.sandbox.validated  ValidationEventV1 │   │
│  │  RemediationComplete      aura.remediation.done   RemediationEventV1│   │
│  │  HITLApproval             aura.hitl.decision      HITLEventV1       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Delivery Targets                                 │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │   │
│  │  │   Kafka          │  │   Kinesis        │  │   Foundry        │  │   │
│  │  │   (Self-hosted)  │  │   (AWS Native)   │  │   (Direct API)   │  │   │
│  │  │                  │  │                  │  │                  │  │   │
│  │  │  • GovCloud      │  │  • Commercial    │  │  • Batch ingest  │  │   │
│  │  │  • Air-gapped    │  │  • Low-latency   │  │  • Small volume  │  │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Event Stream Throughput Specifications:**

| Specification | Value | Notes |
|---------------|-------|-------|
| Expected volume | 1,000-10,000 events/day | Per typical customer |
| Burst capacity | 100 events/second | For incident response scenarios |
| Kafka partitions | 3 per topic | Customer-based partition key |
| Retention | 7 days | Configurable per tenant |
| Max event size | 256 KB | Larger payloads use S3 reference |
| DLQ retention | 14 days | For failed delivery retry |
| Replay window | 72 hours | For reprocessing after outages |

**Ontology Sync Volume Limits:**

| Sync Type | Limit | Pagination |
|-----------|-------|------------|
| Full sync | 100,000 objects per type | 1,000 objects/page |
| Incremental sync | No limit | CDC-based streaming |
| Customer exceeds limit | Tier upgrade required | Custom engagement |

#### 3. Federated Identity Provider

Enables SSO and cross-platform authorization.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FEDERATED IDENTITY ARCHITECTURE                          │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                        Identity Flow                                   │ │
│  │                                                                        │ │
│  │  ┌─────────────┐    SAML/OIDC    ┌─────────────┐                     │ │
│  │  │  Palantir   │◀───Assertion───▶│    Aura     │                     │ │
│  │  │    IdP      │                 │   Cognito   │                     │ │
│  │  └──────┬──────┘                 └──────┬──────┘                     │ │
│  │         │                               │                             │ │
│  │         │  User Attributes              │  User Attributes            │ │
│  │         │  ───────────────              │  ───────────────            │ │
│  │         │  • palantir_user_id           │  • cognito_sub              │ │
│  │         │  • organization               │  • tenant_id                │ │
│  │         │  • data_classification        │  • roles[]                  │ │
│  │         │  • project_access[]           │  • clearance_level          │ │
│  │         │                               │                             │ │
│  │         ▼                               ▼                             │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │                   Attribute Mapping                              │ │ │
│  │  │                                                                  │ │ │
│  │  │  Palantir Attribute      Aura Attribute       Transformation    │ │ │
│  │  │  ──────────────────      ──────────────       ──────────────    │ │ │
│  │  │  organization        ──▶ tenant_id        ──▶ lookup_mapping    │ │ │
│  │  │  data_classification ──▶ clearance_level  ──▶ enum_conversion   │ │ │
│  │  │  project_access[]    ──▶ repository_ids[] ──▶ array_mapping     │ │ │
│  │  │  role_assignments    ──▶ roles[]          ──▶ role_translation  │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      Token Exchange                                    │ │
│  │                                                                        │ │
│  │  Step 1: User authenticates to Palantir                               │ │
│  │  Step 2: Palantir issues SAML assertion                               │ │
│  │  Step 3: Aura validates assertion, maps attributes                    │ │
│  │  Step 4: Aura issues session token with unified claims                │ │
│  │  Step 5: API calls include both platform contexts                     │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Unified Token Claims:                                          │  │ │
│  │  │  {                                                              │  │ │
│  │  │    "sub": "user-123",                                          │  │ │
│  │  │    "palantir_org": "acme-corp",                                │  │ │
│  │  │    "aura_tenant": "tenant-456",                                │  │ │
│  │  │    "clearance": "secret",                                      │  │ │
│  │  │    "repositories": ["repo-a", "repo-b"],                       │  │ │
│  │  │    "permissions": ["vuln:read", "patch:approve"]               │  │ │
│  │  │  }                                                              │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4. Circuit Breaker Pattern

Prevents cascading failures when Palantir API is unavailable.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CIRCUIT BREAKER CONFIGURATION                           │
│                                                                              │
│  State Machine                                                               │
│  ─────────────                                                               │
│                                                                              │
│      ┌────────────┐    5 failures     ┌────────────┐                       │
│      │   CLOSED   │───────────────────▶│    OPEN    │                       │
│      │ (Normal)   │                    │ (Failing)  │                       │
│      └────────────┘                    └─────┬──────┘                       │
│            ▲                                 │                               │
│            │                                 │ 60 seconds                    │
│            │ Success                         ▼                               │
│            │                           ┌────────────┐                       │
│            └───────────────────────────│ HALF_OPEN  │                       │
│                                        │  (Testing) │                       │
│                                        └────────────┘                       │
│                                                                              │
│  Configuration                                                               │
│  ─────────────                                                               │
│  • Failure threshold: 5 failures in 30 seconds triggers OPEN                │
│  • OPEN state duration: 60 seconds before transitioning to HALF_OPEN        │
│  • HALF_OPEN: Single test request; success → CLOSED, failure → OPEN         │
│  • Timeout per request: 10 seconds                                          │
│                                                                              │
│  Fallback Behavior (OPEN State)                                             │
│  ─────────────────────────────                                               │
│  • Use cached threat context (max age: 1 hour)                              │
│  • Use cached asset criticality (max age: 4 hours)                          │
│  • Queue events for retry when circuit closes                               │
│  • Log degraded mode entry to CloudWatch                                    │
│                                                                              │
│  Degraded Mode Operation                                                     │
│  ───────────────────────                                                     │
│  • Remediation continues WITHOUT Palantir enrichment                        │
│  • Default criticality score applied (configurable per tenant)              │
│  • Alert: "Palantir integration degraded" sent to ops channel              │
│  • Automatic recovery when circuit closes                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5. Observability Infrastructure

Comprehensive monitoring for integration health.

```yaml
# CloudWatch Metrics
Metrics:
  Namespace: Aura/PalantirIntegration

  OntologyBridge:
    - Name: OntologySyncLatencyMs
      Unit: Milliseconds
      Dimensions: [ObjectType, SyncType]

    - Name: ObjectsSynced
      Unit: Count
      Dimensions: [ObjectType, Direction]

    - Name: SyncErrorRate
      Unit: Percent
      Dimensions: [ObjectType]

  EventStream:
    - Name: EventPublishLatencyMs
      Unit: Milliseconds
      Dimensions: [EventType, Target]

    - Name: EventsPublished
      Unit: Count
      Dimensions: [EventType]

    - Name: EventStreamLagSeconds
      Unit: Seconds
      Dimensions: [Topic]

    - Name: DLQDepth
      Unit: Count
      Dimensions: [Topic]

  CircuitBreaker:
    - Name: CircuitState
      Unit: None
      Values: [0=CLOSED, 1=HALF_OPEN, 2=OPEN]

    - Name: DegradedModeMinutes
      Unit: Minutes

  Authentication:
    - Name: TokenRefreshFailures
      Unit: Count

    - Name: SAMLAssertionLatencyMs
      Unit: Milliseconds

# CloudWatch Alarms
Alarms:
  - Name: OntologySyncLatencyHigh
    Metric: OntologySyncLatencyMs
    Threshold: p95 > 500ms for 5 minutes
    Action: SNS → ops-alerts

  - Name: EventStreamLagCritical
    Metric: EventStreamLagSeconds
    Threshold: > 300 seconds (5 min) for 5 minutes
    Action: SNS → ops-critical, PagerDuty

  - Name: PalantirAPIUnreachable
    Metric: SyncErrorRate
    Threshold: > 10% for 5 minutes
    Action: SNS → ops-alerts

  - Name: CircuitBreakerOpen
    Metric: CircuitState
    Threshold: = 2 for 1 minute
    Action: SNS → ops-critical

  - Name: DLQBacklogGrowing
    Metric: DLQDepth
    Threshold: > 1000 for 15 minutes
    Action: SNS → ops-alerts

# Dashboard
Dashboard:
  Name: Palantir-Integration-Health
  Widgets:
    - Title: Sync Latency (p50, p95, p99)
      Type: Line
      Metrics: [OntologySyncLatencyMs]

    - Title: Events Published (by type)
      Type: Stacked Area
      Metrics: [EventsPublished]

    - Title: Circuit Breaker State
      Type: Number
      Metrics: [CircuitState]

    - Title: Error Rate Heatmap
      Type: Heatmap
      Metrics: [SyncErrorRate]
```

#### 6. Tenant Isolation Rules

Multi-tenant isolation for GovCloud deployments.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TENANT ISOLATION ARCHITECTURE                           │
│                                                                              │
│  Identity Mapping                                                            │
│  ────────────────                                                            │
│  • Palantir organization ID maps 1:1 to Aura tenant                         │
│  • Mapping stored in DynamoDB: palantir-tenant-mapping table                │
│  • No cross-tenant data sharing without bilateral agreement                 │
│                                                                              │
│  Data Isolation                                                              │
│  ──────────────                                                              │
│  • Event stream topics are tenant-scoped:                                   │
│      aura.{tenant_id}.vuln.detected                                         │
│      aura.{tenant_id}.patch.generated                                       │
│      aura.{tenant_id}.remediation.done                                      │
│                                                                              │
│  • Ontology sync jobs are tenant-scoped:                                    │
│      - Separate sync job per tenant                                         │
│      - Tenant ID in all sync requests                                       │
│      - Objects tagged with tenant_id in Aura storage                        │
│                                                                              │
│  • Cache keys are tenant-prefixed:                                          │
│      threat:{tenant_id}:{cve_id}                                            │
│      asset:{tenant_id}:{repo_id}                                            │
│                                                                              │
│  Access Control                                                              │
│  ──────────────                                                              │
│  • All API endpoints require tenant_id in JWT claims                        │
│  • ABAC policies (ADR-073) enforce tenant boundary                          │
│  • Cross-tenant queries blocked at middleware layer                         │
│                                                                              │
│  Audit Isolation                                                             │
│  ───────────────                                                             │
│  • Audit logs include tenant_id for forensic isolation                      │
│  • CloudWatch Log Groups: /aura/palantir/{tenant_id}/                       │
│  • S3 audit bucket: s3://aura-audit/{tenant_id}/palantir/                   │
│                                                                              │
│  Cross-Tenant Access (Exception Process)                                     │
│  ────────────────────────────────────────                                    │
│  • Requires: Written agreement from both tenants                            │
│  • Requires: Security review and approval                                   │
│  • Implementation: Explicit grant in cross-tenant-access table              │
│  • Audit: All cross-tenant access logged with justification                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 7. Conflict Resolution Matrix

Rules for handling data conflicts between Palantir and Aura.

| Object Type | Authority | Conflict Strategy | Manual Override | Notes |
|-------------|-----------|-------------------|-----------------|-------|
| **ThreatActor** | Palantir | Palantir authoritative | Read-only in Aura | Aura consumes, never modifies |
| **Vulnerability** | Merge | Union of fields | Yes | Palantir CVE data + Aura code analysis |
| **Asset** | Split | Field-level authority | Partial | Palantir: criticality; Aura: vuln status |
| **Repository** | Aura | Aura authoritative | No | Aura is source of truth for code repos |
| **Compliance** | Palantir | Palantir authoritative | Read-only | Compliance reqs flow from Palantir |
| **Remediation** | Aura | Aura authoritative | No | Patch status owned by Aura |

```text
Conflict Resolution Flow:

  Palantir Update                    Aura Update
       │                                  │
       ▼                                  ▼
  ┌─────────────────────────────────────────────────────────┐
  │                   Conflict Detector                      │
  │                                                          │
  │  1. Compare timestamps (last_modified)                   │
  │  2. Check authority matrix                               │
  │  3. Apply resolution strategy                            │
  │                                                          │
  │  Strategies:                                             │
  │  • AUTHORITATIVE: Winner takes all                       │
  │  • MERGE: Union of non-conflicting fields               │
  │  • SPLIT: Field-level authority rules                   │
  │  • MANUAL: Queue for human review                        │
  └─────────────────────────────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │                   Resolved Object                        │
  │                                                          │
  │  • Stored with resolution_metadata                       │
  │  • conflict_detected: true/false                        │
  │  • resolution_strategy: AUTHORITATIVE/MERGE/SPLIT       │
  │  • resolved_at: timestamp                               │
  │  • audit_trail: [source, strategy, fields_affected]     │
  └─────────────────────────────────────────────────────────┘
```

#### 8. Schema Versioning Strategy

Forward-compatible schema evolution for APIs and events.

```yaml
# Event Schema Versioning
Event Schema:
  Version Format: semantic (MAJOR.MINOR.PATCH)

  Rules:
    - All events include schema_version field
    - Consumers MUST handle unknown fields gracefully (forward compatibility)
    - MINOR version: New optional fields (backward compatible)
    - MAJOR version: Breaking changes require new event type
        Example: VulnerabilityDetectedV2

  Deprecation Policy:
    - 6 months notice before removing old schemas
    - Deprecation warning in event metadata
    - Migration guide published with each major version

  Example Event:
    event_type: "VulnerabilityDetected"
    schema_version: "1.2.0"
    timestamp: "2026-01-28T10:00:00Z"
    payload: { ... }
    _metadata:
      deprecated: false
      min_supported_version: "1.0.0"

# API Versioning
API Versioning:
  Strategy: URL path versioning (/api/v1/, /api/v2/)

  Rules:
    - New endpoints added to current version
    - Breaking changes require new version
    - Old versions supported for 12 months minimum
    - Sunset header indicates deprecation date

  Ontology Object Versioning:
    - Schema changes negotiated with Palantir quarterly
    - Object mapper supports multiple schema versions
    - Version negotiation during handshake

  Example:
    GET /api/v1/threats/active
    Response-Header: Sunset: Sat, 28 Jan 2027 00:00:00 GMT
    Response-Header: Deprecation: true
```

### Use Case Workflows

#### Use Case 1: Threat-Informed Remediation

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│              THREAT-INFORMED REMEDIATION WORKFLOW                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ TRIGGER: Active threat campaign targeting Log4j (CVE-2021-44228)   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Threat Intelligence Correlation                       │   │
│  │                                                                      │   │
│  │  • Detects active APT campaign exploiting Log4j                     │   │
│  │  • Correlates with MITRE ATT&CK: T1190 (Exploit Public App)        │   │
│  │  • Identifies targeted industries: Healthcare, Finance              │   │
│  │  • Calculates EPSS score: 97.5% (actively exploited)               │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Ontology Bridge                         │
│                                   │ (ThreatContext sync)                    │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Prioritized Vulnerability Scan                                │   │
│  │                                                                      │   │
│  │  • Receives threat context: Log4j + active campaign                 │   │
│  │  • Scans all repositories for Log4j dependencies                    │   │
│  │  • Prioritizes by:                                                  │   │
│  │    1. EPSS score (97.5% - critical)                                │   │
│  │    2. Asset criticality (from Palantir CMDB)                       │   │
│  │    3. Exposure (internet-facing vs internal)                        │   │
│  │  • Result: 12 repos affected, 3 critical priority                  │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Autonomous Remediation (Critical 3 repos)                     │   │
│  │                                                                      │   │
│  │  • Agent Orchestrator activates Coder Agent                         │   │
│  │  • Generates patches: log4j 2.17.0 upgrade                         │   │
│  │  • Sandbox validation: tests pass, security scan clean             │   │
│  │  • HITL: Auto-approved (Autonomy Level 3 for critical CVE)         │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Event Stream                            │
│                                   │ (RemediationComplete)                   │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Risk Posture Update                                   │   │
│  │                                                                      │   │
│  │  • Receives remediation status from Aura                            │   │
│  │  • Updates asset vulnerability status                               │   │
│  │  • Recalculates organizational risk score                           │   │
│  │  • Generates compliance evidence (SOX, CMMC)                        │   │
│  │  • Notifies stakeholders via AIP Logic workflow                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  OUTCOME: 3 critical vulnerabilities remediated within 2 hours of           │
│           threat intelligence detection, with full audit trail              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Use Case 2: DIB Supply Chain Security

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│              DIB SUPPLY CHAIN SECURITY WORKFLOW                              │
│                                                                              │
│  CONTEXT: Defense contractor must validate software supply chain            │
│           per DFARS 252.204-7012 and CMMC Level 2                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Vendor Risk Management                                │   │
│  │                                                                      │   │
│  │  • Maintains vendor risk scores from multiple sources               │   │
│  │  • Tracks SBOM submissions from suppliers                           │   │
│  │  • Correlates vendor incidents (breaches, sanctions)               │   │
│  │  • Flags: "Vendor X compromised - review all dependencies"         │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Dependency Graph Analysis                                     │   │
│  │                                                                      │   │
│  │  • GraphRAG traverses full dependency tree                          │   │
│  │  • Identifies all repos using Vendor X components                   │   │
│  │  • Calculates transitive dependency exposure                        │   │
│  │  • Generates SBOM delta: what changed since last scan              │   │
│  │  • Flags license compliance issues (ITAR-restricted)               │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Automated Remediation Options                                 │   │
│  │                                                                      │   │
│  │  Option A: Upgrade to patched version (if available)               │   │
│  │  Option B: Replace with alternative package                         │   │
│  │  Option C: Isolate/sandbox affected component                       │   │
│  │  Option D: Accept risk with compensating controls                   │   │
│  │                                                                      │   │
│  │  HITL Required: All options require security team approval          │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Compliance Dashboard                                  │   │
│  │                                                                      │   │
│  │  • SBOM compliance status per contract                             │   │
│  │  • Vendor risk trending over time                                   │   │
│  │  • CMMC control mapping (SC.L2-3.13.1 - Boundary Protection)       │   │
│  │  • Audit-ready evidence export                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Use Case 3: Healthcare HIPAA Compliance

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│              HEALTHCARE HIPAA COMPLIANCE WORKFLOW                            │
│                                                                              │
│  CONTEXT: Healthcare organization must ensure PHI-handling code             │
│           meets HIPAA Security Rule requirements                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Data Classification & Lineage                         │   │
│  │                                                                      │   │
│  │  • Maintains data catalog with PHI tagging                          │   │
│  │  • Tracks data lineage: PHI flows through which services           │   │
│  │  • Maps repositories to data classification levels                  │   │
│  │  • Flags: "Repository Y handles PHI - elevated security required"  │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: PHI-Aware Security Scanning                                   │   │
│  │                                                                      │   │
│  │  • Applies elevated scanning profile for PHI repositories           │   │
│  │  • Checks: encryption at rest, encryption in transit               │   │
│  │  • Checks: access logging, audit trail completeness                │   │
│  │  • Checks: credential handling, secrets in code                    │   │
│  │  • Result: 3 findings require remediation                          │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: HIPAA-Compliant Remediation                                   │   │
│  │                                                                      │   │
│  │  Finding 1: Hardcoded database credentials                         │   │
│  │    → Patch: Move to AWS Secrets Manager                            │   │
│  │                                                                      │   │
│  │  Finding 2: Missing audit logging on PHI access                    │   │
│  │    → Patch: Add CloudWatch Logs with PHI access events            │   │
│  │                                                                      │   │
│  │  Finding 3: Unencrypted S3 bucket for PHI exports                  │   │
│  │    → Patch: Enable SSE-KMS encryption                              │   │
│  │                                                                      │   │
│  │  HITL: Compliance Officer approval required for PHI changes        │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Compliance Evidence Generation                        │   │
│  │                                                                      │   │
│  │  • Maps remediation to HIPAA controls:                             │   │
│  │    - 164.312(a)(1): Access Control                                 │   │
│  │    - 164.312(b): Audit Controls                                    │   │
│  │    - 164.312(e)(1): Transmission Security                          │   │
│  │  • Generates audit trail for OCR inspection                        │   │
│  │  • Updates compliance dashboard                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Use Case 4: Insider Threat Detection

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│              INSIDER THREAT DETECTION WORKFLOW                               │
│                                                                              │
│  CONTEXT: Correlating abnormal developer behavior with code changes         │
│           to detect potentially malicious insider activity                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: User Behavior Analytics                               │   │
│  │                                                                      │   │
│  │  • Integrates with Saviynt/SailPoint for access patterns           │   │
│  │  • Detects unusual access: after-hours, unusual repos, bulk access │   │
│  │  • Correlates with HR data: resignation notice, PIP status         │   │
│  │  • Flags user as "elevated risk" with risk score                   │   │
│  │  • Example: "User X accessed 15 repos outside normal pattern"      │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Ontology Bridge                         │
│                                   │ (UserRiskContext sync)                  │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Elevated Scrutiny Mode                                        │   │
│  │                                                                      │   │
│  │  • Receives elevated-risk user context from Palantir               │   │
│  │  • Automatically adjusts HITL requirements for their PRs:          │   │
│  │    - Normal user: Autonomy Level 3 (auto-approve low severity)     │   │
│  │    - Elevated risk: Autonomy Level 1 (human approval required)     │   │
│  │  • Triggers deep scan of recent commits by flagged user            │   │
│  │  • Applies backdoor detection patterns to their code changes       │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Threat Pattern Analysis                                       │   │
│  │                                                                      │   │
│  │  Scan for insider threat indicators:                                │   │
│  │  • Hardcoded credentials or API keys                               │   │
│  │  • Disabled security controls (logging, auth checks)               │   │
│  │  • Data exfiltration patterns (bulk exports, external endpoints)   │   │
│  │  • Privilege escalation attempts                                    │   │
│  │  • Time bombs or logic bombs                                        │   │
│  │                                                                      │   │
│  │  Result: 2 suspicious patterns detected                            │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Event Stream                            │
│                                   │ (InsiderThreatAlert)                    │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Security Operations Response                          │   │
│  │                                                                      │   │
│  │  • Receives insider threat alert from Aura                         │   │
│  │  • Correlates with user's access patterns in unified timeline      │   │
│  │  • Triggers SOC investigation workflow                             │   │
│  │  • Preserves forensic evidence chain                               │   │
│  │  • Option: Automatic access revocation via Saviynt integration     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  OUTCOME: Potential insider threat detected and escalated within hours,    │
│           with full behavior-to-code correlation for investigation          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Use Case 5: Compliance Drift Detection

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│              COMPLIANCE DRIFT DETECTION WORKFLOW                             │
│                                                                              │
│  CONTEXT: Continuous compliance monitoring between Palantir GRC and Aura   │
│           to automatically detect and remediate compliance drift           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: GRC Integration (AuditBoard/ServiceNow GRC)          │   │
│  │                                                                      │   │
│  │  • Tracks compliance framework control status                       │   │
│  │  • Monitors: SOX, CMMC, HIPAA, PCI-DSS, NIST 800-53               │   │
│  │  • Identifies control failures from audit findings                 │   │
│  │  • Maps controls to technical implementation requirements          │   │
│  │  • Example: "AC-3: Access Enforcement - FAILED (3 repos)"         │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Ontology Bridge                         │
│                                   │ (ComplianceControl sync)                │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Control-to-Code Mapping                                       │   │
│  │                                                                      │   │
│  │  • Receives failed control: AC-3 (Access Enforcement)              │   │
│  │  • Maps to code requirements:                                       │   │
│  │    - Authentication on all API endpoints                           │   │
│  │    - Authorization checks before data access                       │   │
│  │    - Role-based access control implementation                      │   │
│  │  • Scans affected repositories for compliance gaps                 │   │
│  │  • Result: 3 endpoints missing authorization checks                │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AURA: Automated Compliance Remediation                              │   │
│  │                                                                      │   │
│  │  Finding 1: /api/users endpoint missing @require_auth decorator    │   │
│  │    → Patch: Add authentication middleware                          │   │
│  │                                                                      │   │
│  │  Finding 2: Data access without ABAC check                         │   │
│  │    → Patch: Add authorization policy evaluation                    │   │
│  │                                                                      │   │
│  │  Finding 3: Missing audit logging on sensitive operations          │   │
│  │    → Patch: Add audit log calls                                    │   │
│  │                                                                      │   │
│  │  HITL: Compliance Officer approval required                        │   │
│  │  Sandbox: All patches validated before deployment                  │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Event Stream                            │
│                                   │ (ComplianceRemediationComplete)         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PALANTIR AIP: Control Status Update                                 │   │
│  │                                                                      │   │
│  │  • Receives remediation confirmation from Aura                     │   │
│  │  • Updates control status: AC-3 → PASSED                           │   │
│  │  • Generates evidence artifacts for auditors                       │   │
│  │  • Links code changes to control requirements                      │   │
│  │  • Updates compliance dashboard and risk score                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  OUTCOME: Compliance drift detected and remediated autonomously,           │
│           with complete audit trail from control failure to code fix        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### API Specification

#### Ontology Bridge API

```yaml
openapi: 3.0.0
info:
  title: Aura-Palantir Ontology Bridge API
  version: 1.0.0

paths:
  /api/v1/ontology/sync:
    post:
      summary: Trigger full ontology synchronization
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                object_types:
                  type: array
                  items:
                    type: string
                    enum: [ThreatActor, Vulnerability, Asset, Repository]
                since:
                  type: string
                  format: date-time
      responses:
        202:
          description: Sync job accepted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SyncJob'

  /api/v1/ontology/objects/{type}:
    get:
      summary: Get synced objects by type
      parameters:
        - name: type
          in: path
          required: true
          schema:
            type: string
        - name: palantir_id
          in: query
          schema:
            type: string
      responses:
        200:
          description: Object list
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/OntologyObject'

  /api/v1/threats/active:
    get:
      summary: Get active threat contexts from Palantir
      responses:
        200:
          description: Active threats
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/ThreatContext'

  /api/v1/assets/{repo_id}/criticality:
    get:
      summary: Get asset criticality score from Palantir CMDB
      parameters:
        - name: repo_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Asset criticality
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssetCriticality'

components:
  schemas:
    ThreatContext:
      type: object
      properties:
        threat_id:
          type: string
        actor_name:
          type: string
        cves:
          type: array
          items:
            type: string
        mitre_ttps:
          type: array
          items:
            type: string
        epss_score:
          type: number
        targeted_industries:
          type: array
          items:
            type: string
        active_since:
          type: string
          format: date-time

    AssetCriticality:
      type: object
      properties:
        asset_id:
          type: string
        criticality_score:
          type: integer
          minimum: 1
          maximum: 10
        business_owner:
          type: string
        data_classification:
          type: string
          enum: [public, internal, confidential, restricted]
        pii_handling:
          type: boolean
        phi_handling:
          type: boolean
```

#### Event Stream Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Aura Event Stream Schema",
  "definitions": {
    "VulnerabilityDetectedEvent": {
      "type": "object",
      "properties": {
        "event_type": { "const": "VulnerabilityDetected" },
        "event_id": { "type": "string", "format": "uuid" },
        "timestamp": { "type": "string", "format": "date-time" },
        "payload": {
          "type": "object",
          "properties": {
            "vulnerability_id": { "type": "string" },
            "cve_id": { "type": "string", "pattern": "^CVE-\\d{4}-\\d+$" },
            "severity": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
            "cvss_score": { "type": "number", "minimum": 0, "maximum": 10 },
            "repository_id": { "type": "string" },
            "affected_files": { "type": "array", "items": { "type": "string" } },
            "detection_method": { "type": "string" },
            "palantir_asset_id": { "type": "string" }
          },
          "required": ["vulnerability_id", "severity", "repository_id"]
        }
      }
    },
    "RemediationCompleteEvent": {
      "type": "object",
      "properties": {
        "event_type": { "const": "RemediationComplete" },
        "event_id": { "type": "string", "format": "uuid" },
        "timestamp": { "type": "string", "format": "date-time" },
        "payload": {
          "type": "object",
          "properties": {
            "remediation_id": { "type": "string" },
            "vulnerability_id": { "type": "string" },
            "patch_id": { "type": "string" },
            "status": { "type": "string", "enum": ["success", "partial", "failed", "reverted"] },
            "repository_id": { "type": "string" },
            "sandbox_results": {
              "type": "object",
              "properties": {
                "tests_passed": { "type": "boolean" },
                "security_scan_clean": { "type": "boolean" },
                "performance_regression": { "type": "boolean" }
              }
            },
            "hitl_approval": {
              "type": "object",
              "properties": {
                "required": { "type": "boolean" },
                "approved_by": { "type": "string" },
                "approved_at": { "type": "string", "format": "date-time" }
              }
            },
            "deployed_at": { "type": "string", "format": "date-time" },
            "mttr_seconds": { "type": "integer" }
          },
          "required": ["remediation_id", "vulnerability_id", "status"]
        }
      }
    }
  }
}
```

### Security & Compliance

#### Authentication & Authorization

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                   SECURITY ARCHITECTURE                                      │
│                                                                              │
│  Network Security                                                            │
│  ────────────────                                                            │
│  • mTLS between Aura and Palantir endpoints                                 │
│  • VPC peering or PrivateLink (no public internet)                          │
│  • WAF with rate limiting on API Gateway                                    │
│  • IP allowlisting for Palantir Foundry ranges                              │
│                                                                              │
│  Authentication                                                              │
│  ──────────────                                                              │
│  • SAML 2.0 federation (Palantir IdP → Aura Cognito)                       │
│  • Service-to-service: mTLS + API key rotation (90-day)                     │
│  • Token exchange for cross-platform operations                             │
│                                                                              │
│  Authorization                                                               │
│  ─────────────                                                               │
│  • ABAC policies (ADR-073) extended for Palantir attributes                │
│  • Data classification enforcement at API layer                             │
│  • Cross-tenant access requires explicit grants                             │
│                                                                              │
│  Data Protection                                                             │
│  ───────────────                                                             │
│  • Encryption in transit: TLS 1.3                                           │
│  • Encryption at rest: KMS customer-managed keys                            │
│  • Field-level encryption for PII/PHI in event streams                     │
│  • Data residency controls (GovCloud isolation)                             │
│                                                                              │
│  Audit & Compliance                                                          │
│  ─────────────────                                                           │
│  • All API calls logged to CloudWatch + Palantir audit log                 │
│  • Cross-reference IDs for traceability                                     │
│  • CMMC/FedRAMP control mapping in both systems                             │
│  • Quarterly access reviews                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### GovCloud Deployment

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                   GOVCLOUD DEPLOYMENT TOPOLOGY                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 AWS GovCloud (US-West)                               │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────┐  ┌─────────────────────────┐          │   │
│  │  │     Palantir AIP        │  │        Aura              │          │   │
│  │  │     (GovCloud)          │  │     (GovCloud)           │          │   │
│  │  │                         │  │                          │          │   │
│  │  │  FedRAMP High           │  │  FedRAMP High            │          │   │
│  │  │  IL5 Authorized         │  │  IL5 Ready               │          │   │
│  │  │                         │  │                          │          │   │
│  │  └───────────┬─────────────┘  └─────────────┬────────────┘          │   │
│  │              │                              │                        │   │
│  │              └──────────┬───────────────────┘                        │   │
│  │                         │                                            │   │
│  │                         ▼                                            │   │
│  │              ┌─────────────────────┐                                 │   │
│  │              │   PrivateLink       │                                 │   │
│  │              │   (No Internet)     │                                 │   │
│  │              └─────────────────────┘                                 │   │
│  │                                                                      │   │
│  │  FIPS 140-2 Validated Crypto                                        │   │
│  │  STIG-Hardened Baselines                                            │   │
│  │  FedRAMP Continuous Monitoring                                      │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Crawl (Months 1-3)

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| 1.1 | Palantir API authentication | mTLS handshake successful |
| 1.2 | Basic ontology mapping | ThreatActor, Vulnerability objects sync |
| 1.3 | Event stream setup | Events flow to Foundry (Kinesis/Kafka) |
| 1.4 | SAML federation | SSO working for test users |

**Exit Criteria:** Single threat context synced and visible in Aura prioritization.

### Phase 2: Walk (Months 4-8)

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| 2.1 | Full ontology sync | All object types bidirectional |
| 2.2 | Event stream reliability | DLQ, replay, exactly-once delivery |
| 2.3 | Asset criticality integration | CMDB scores affect Aura prioritization |
| 2.4 | Compliance dashboard | Remediation status visible in Palantir |
| 2.5 | ABAC attribute mapping | Palantir attributes in Aura policies |

**Exit Criteria:** End-to-end workflow: Palantir threat → Aura remediation → Palantir dashboard.

### Phase 3: Run (Months 9-12)

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| 3.1 | AIP Logic integration | Palantir workflows trigger Aura actions |
| 3.2 | GovCloud deployment | Full integration in IL5 environment |
| 3.3 | Joint customer POC | 2+ customers validate integration |
| 3.4 | Performance optimization | <500ms ontology sync latency |
| 3.5 | GA readiness | Documentation, support runbooks |

**Exit Criteria:** Production deployment with joint customers.

## Consequences

### Positive

1. **Threat-informed prioritization**: Remediation focuses on actively exploited vulnerabilities
2. **Reduced MTTR**: Autonomous patching closes the loop from detection to fix
3. **Compliance acceleration**: Unified audit trail across both platforms
4. **Market expansion**: Access to Palantir's enterprise customer base
5. **GovCloud synergy**: Both platforms FedRAMP High, natural fit for DIB

### Negative

1. **Integration complexity**: Two complex platforms require careful API management
2. **Vendor dependency**: Deep integration creates switching costs for customers
3. **Data sovereignty**: Cross-platform data flows require careful governance
4. **Support complexity**: Joint troubleshooting across two vendor support orgs

### Joint Operations Model

To mitigate support complexity, establish clear operational boundaries:

```text
Joint Operations Framework:
────────────────────────────

Communication:
• Shared Slack channel for P1/P2 issues (customer-specific)
• Monthly sync meeting for integration health review
• Quarterly roadmap alignment sessions

Escalation Path:
• Aura L1 → Aura L2 → Joint Aura/Palantir triage → Palantir L3

Incident Classification:
• Aura owns: Event Stream issues, remediation failures, sandbox problems
• Palantir owns: Ontology sync issues, AIP Logic failures, Foundry ingest
• Joint: Authentication/federation, data consistency, performance

Documentation:
• Shared runbook: docs/operations/PALANTIR_INTEGRATION_RUNBOOK.md
• Joint troubleshooting guide with decision tree
• Escalation contact matrix updated quarterly
```

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Palantir API changes | Medium | High | Version pinning, deprecation monitoring |
| Data sync conflicts | Medium | Medium | LWW conflict resolution, manual override UI |
| Performance degradation | Low | High | Circuit breakers, async processing |
| Compliance gaps | Low | Critical | Joint compliance review, audit attestations |

## Implementation Resources

### CloudFormation Templates

| Template | Layer | Description |
|----------|-------|-------------|
| `deploy/cloudformation/iam-palantir-integration.yaml` | 4.13 | IAM roles and policies for Palantir integration |

### IAM Resources Created

| Resource | Type | Purpose |
|----------|------|---------|
| `${ProjectName}-palantir-integration-role-${Environment}` | IAM Role | Service role for all Palantir integration components |
| `${ProjectName}-palantir-ontology-bridge-${Environment}` | Managed Policy | DynamoDB, ElastiCache, CloudWatch Logs access |
| `${ProjectName}-palantir-event-stream-${Environment}` | Managed Policy | Kinesis, SQS, S3 for event publishing |
| `${ProjectName}-palantir-federated-identity-${Environment}` | Managed Policy | Cognito SAML provider management |
| `${ProjectName}-palantir-observability-${Environment}` | Managed Policy | CloudWatch metrics, alarms, dashboards |
| `${ProjectName}-palantir-secrets-${Environment}` | Managed Policy | Secrets Manager, KMS, ACM access |

### CI/CD Integration

The Palantir integration IAM template is deployed via:
- **Buildspec:** `deploy/buildspecs/buildspec-application-irsa.yml`
- **CodeBuild Project:** `aura-application-irsa-deploy-${Environment}`
- **Trigger:** Part of application layer deployment pipeline

### Deployment Commands

```bash
# Manual deployment (for testing)
aws cloudformation deploy \
  --stack-name aura-iam-palantir-integration-dev \
  --template-file deploy/cloudformation/iam-palantir-integration.yaml \
  --parameter-overrides \
    ProjectName=aura \
    Environment=dev \
    EKSOIDCProviderArn=arn:aws:iam::ACCOUNT:oidc-provider/oidc.eks.REGION.amazonaws.com/id/CLUSTER \
    EKSOIDCIssuer=oidc.eks.REGION.amazonaws.com/id/CLUSTER \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=aura Environment=dev ADR=ADR-074

# Via CodeBuild (recommended)
aws codebuild start-build --project-name aura-application-irsa-deploy-dev
```

## References

- [Palantir AIP Documentation](https://www.palantir.com/platforms/aip/)
- [Palantir Foundry Ontology](https://www.palantir.com/docs/foundry/ontology/)
- [ADR-032: Configurable Autonomy Framework](./ADR-032-configurable-autonomy-framework.md)
- [ADR-065: Semantic Guardrails Engine](./ADR-065-semantic-guardrails-engine.md)
- [ADR-073: Attribute-Based Access Control](./ADR-073-attribute-based-access-control.md)
- [NIST SP 800-53 Security Controls](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- [CMMC Level 2 Requirements](https://dodcio.defense.gov/CMMC/)

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*

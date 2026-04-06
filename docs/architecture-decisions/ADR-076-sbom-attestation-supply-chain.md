# ADR-076: SBOM Attestation and Supply Chain Security

## Status

Deployed

## Date

2026-02-02

## Context

### Market Opportunity

Software supply chain attacks have increased substantially since 2019 (see Sonatype State of the Software Supply Chain reports, which have reported multi-hundred-percent growth figures in multiple years). Executive Order 14028 mandates SBOM for federal software. Target markets served by vendors such as Snyk and Wiz, as well as defense customers, increasingly require cryptographic attestation of software provenance (as of February 2026).

### Current State

Project Aura has `SBOMDetectionService` (`src/services/sbom_detection_service.py`) that:
- Detects dependencies from 8 manifest file types
- Generates internal SBOM format
- Integrates with `ThreatIntelligenceAgent` for vulnerability matching

**Gaps:**
- No cryptographic attestation (Sigstore/cosign)
- No standard SBOM formats (CycloneDX 1.5, SPDX 2.3)
- No dependency confusion detection
- No license compliance automation
- No in-toto provenance predicates

### Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| R1 | Generate CycloneDX 1.5 and SPDX 2.3 format SBOMs | EO 14028, NTIA |
| R2 | Sign SBOMs with Sigstore (keyless) or HSM (air-gapped) | Parity with capabilities publicly documented by Snyk and similar vendors |
| R3 | Store attestations in Rekor transparency log | Supply chain integrity |
| R4 | Detect typosquatting and namespace hijacking | Parity with capabilities publicly documented by Wiz and similar vendors |
| R5 | Analyze license compatibility and generate attribution | Legal compliance |
| R6 | Query provenance chain for any component | Auditability |
| R7 | Support VEX documents for vulnerability exceptions | CISA guidance |

## Decision

Implement a Supply Chain Security service cluster extending the existing `SBOMDetectionService` with three new services:

### 1. SBOM Attestation Service

**Responsibilities:**
- Generate CycloneDX 1.5 and SPDX 2.3 format SBOMs
- Sign SBOMs using Sigstore (keyless) or offline keys (air-gapped)
- Record attestations in Rekor transparency log
- Store SBOM/attestation in Neptune graph and OpenSearch
- Generate VEX documents for vulnerability exceptions

**Integration Points:**
- Extends existing `SBOMDetectionService` for dependency detection
- Stores attestations in Neptune as `SBOM -[ATTESTED_BY]-> Attestation` edges
- Indexes in OpenSearch for provenance queries
- Triggers on repository analysis completion via EventBridge

### 2. Dependency Confusion Detector

**Responsibilities:**
- Detect typosquatting via Levenshtein distance to popular packages
- Detect namespace hijacking (internal namespaces on public registries)
- Detect combosquatting (legitimate-name-suffix patterns)
- Score package risk based on age, downloads, maintainer reputation
- Integrate with `SemanticGuardrailsEngine` (ADR-065) for alerting

**Detection Methods:**
- Edit distance threshold (<=2) to top 1000 packages per ecosystem
- Organization namespace registry for hijack detection
- Publication timing analysis (new packages mimicking old)
- Maintainer email domain verification

### 3. License Compliance Engine

**Responsibilities:**
- Identify licenses using SPDX identifiers
- Check license compatibility with project license
- Enforce organization license policies
- Generate attribution/NOTICE files
- Track license obligations (disclosure, attribution, copyleft)

**License Categories:**
- Permissive: MIT, Apache-2.0, BSD
- Weak Copyleft: LGPL, MPL
- Strong Copyleft: GPL, AGPL
- Commercial/Proprietary

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Supply Chain Security Architecture                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Repository Analysis Complete (EventBridge)                             │
│                          │                                               │
│                          ▼                                               │
│              ┌───────────────────────────────────────────────────────┐  │
│              │           SBOM Attestation Service                     │  │
│              │                                                        │  │
│              │  ┌─────────────────┐  ┌─────────────────────────────┐ │  │
│              │  │ SBOMDetection   │  │ Format Conversion           │ │  │
│              │  │ Service         │──│ - CycloneDX 1.5             │ │  │
│              │  │ (existing)      │  │ - SPDX 2.3                  │ │  │
│              │  └─────────────────┘  └─────────────────────────────┘ │  │
│              │                                │                       │  │
│              │                                ▼                       │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Signing Layer                                    │  │  │
│              │  │ ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │  │
│              │  │ │ Sigstore    │  │ HSM/YubiKey │  │ Offline   │ │  │  │
│              │  │ │ (keyless)   │  │ (enterprise)│  │ (air-gap) │ │  │  │
│              │  │ └─────────────┘  └─────────────┘  └───────────┘ │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              │                                │                       │  │
│              │                                ▼                       │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Storage Layer                                    │  │  │
│              │  │ - DynamoDB (SBOM + Attestation metadata)         │  │  │
│              │  │ - S3 (SBOM artifacts)                            │  │  │
│              │  │ - Neptune (provenance graph)                     │  │  │
│              │  │ - OpenSearch (search index)                      │  │  │
│              │  │ - Rekor (transparency log)                       │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              └───────────────────────────────────────────────────────┘  │
│                          │                                               │
│         ┌────────────────┼────────────────┐                             │
│         ▼                ▼                ▼                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │ Dependency  │  │ License     │  │ K8s         │                     │
│  │ Confusion   │  │ Compliance  │  │ Admission   │                     │
│  │ Detector    │  │ Engine      │  │ Controller  │                     │
│  │             │  │             │  │ (Phase 2)   │                     │
│  └─────────────┘  └─────────────┘  └─────────────┘                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Core SBOM Attestation (Weeks 1-4)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Extend SBOMDetectionService | 1 week | CycloneDX/SPDX conversion |
| Implement Sigstore signing | 1 week | Keyless and offline modes |
| Build storage layer | 1 week | DynamoDB, S3, Neptune integration |
| API endpoints | 1 week | FastAPI router, 8 endpoints |

### Phase 2: Dependency Confusion (Weeks 5-7)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Typosquatting detection | 1 week | Levenshtein + popular package DB |
| Namespace hijacking | 1 week | Organization registry, detection |
| Integration | 1 week | SemanticGuardrailsEngine alerts |

### Phase 3: License Compliance (Weeks 8-10)

| Task | Effort | Deliverables |
|------|--------|--------------|
| License identification | 1 week | SPDX database, heuristics |
| Compatibility checking | 1 week | Policy engine, violation detection |
| Attribution generation | 1 week | Markdown/HTML NOTICE files |

## Data Models

### Neptune Graph Schema

```gremlin
// New Vertex Types
g.addV('SBOM')
  .property('id', sbom_id)
  .property('format', 'cyclonedx-1.5')
  .property('repository_id', repo_id)
  .property('commit_sha', sha)
  .property('component_count', 127)
  .property('created_at', timestamp)

g.addV('Attestation')
  .property('id', attestation_id)
  .property('predicate_type', 'https://slsa.dev/provenance/v1')
  .property('signature', base64_sig)
  .property('signer_identity', 'ci@company.com')
  .property('rekor_log_index', 12345678)
  .property('created_at', timestamp)

g.addV('License')
  .property('spdx_id', 'Apache-2.0')
  .property('category', 'permissive')
  .property('osi_approved', true)
  .property('copyleft', false)

// New Edge Types
g.addE('ATTESTED_BY').from(sbom).to(attestation)
g.addE('CONTAINS').from(sbom).to(dependency)
g.addE('LICENSED_UNDER').from(dependency).to(license)
g.addE('SUPERSEDES').from(new_attestation).to(old_attestation)
```

### DynamoDB Tables

**aura-sbom-documents-{env}:**
- PK: `sbom_id`
- GSI: `repository_id + created_at`
- Attributes: format, spec_version, component_count, hash

**aura-attestations-{env}:**
- PK: `attestation_id`
- GSI: `sbom_id`, `subject_digest`
- Attributes: predicate_type, signature, certificate, rekor_index

### OpenSearch Index

```json
{
  "aura-sbom-attestations": {
    "mappings": {
      "properties": {
        "sbom_id": { "type": "keyword" },
        "repository_id": { "type": "keyword" },
        "components": {
          "type": "nested",
          "properties": {
            "name": { "type": "keyword" },
            "version": { "type": "keyword" },
            "purl": { "type": "keyword" }
          }
        },
        "generated_at": { "type": "date" }
      }
    }
  }
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/supply-chain/sbom/generate` | Generate SBOM for repository |
| GET | `/api/v1/supply-chain/sbom/{id}` | Get SBOM document |
| GET | `/api/v1/supply-chain/sbom/{id}/download` | Download SBOM file |
| POST | `/api/v1/supply-chain/attestation/sign` | Sign SBOM |
| POST | `/api/v1/supply-chain/attestation/verify` | Verify attestation |
| GET | `/api/v1/supply-chain/provenance/{purl}` | Query provenance chain |
| POST | `/api/v1/supply-chain/confusion/analyze` | Analyze for confusion attacks |
| POST | `/api/v1/supply-chain/license/check` | Check license compliance |
| POST | `/api/v1/supply-chain/license/attribution` | Generate attribution file |

## Security Considerations

1. **Signing Key Protection:**
   - Sigstore keyless uses OIDC (no persistent keys)
   - HSM integration for enterprise (keys never leave HSM)
   - Offline keys for air-gapped (Ed25519, stored encrypted)

2. **Attestation Integrity:**
   - All attestations recorded in Rekor (tamper-evident)
   - Attestation includes subject digest (content-addressable)
   - Certificate chain validation for non-keyless

3. **Supply Chain Threats:**
   - Dependency confusion detector runs on all SBOM generation
   - Block HIGH/CRITICAL confusion scores by default
   - Alert on namespace hijack attempts

## Success Metrics

| Metric | Target |
|--------|--------|
| SBOM generation time | <30s for 1000 dependencies |
| Attestation signing time | <5s including Rekor |
| Confusion detection accuracy | >95% on known attacks |
| License identification accuracy | >99% for top 100 licenses |
| API availability | 99.9% |

## Alternatives Considered

### Alternative 1: Integrate Third-Party SBOM Tool

Use existing tools like Syft, Trivy, or CycloneDX CLI.

**Pros:**
- Faster initial implementation
- Community-maintained

**Cons:**
- External dependency for critical security function
- Less integration with Aura graph
- Limited customization

**Decision:** Rejected - supply chain security is core differentiator

### Alternative 2: Sigstore Only (No Offline Support)

Require Sigstore for all signing.

**Pros:**
- Simpler implementation
- Keyless reduces key management burden

**Cons:**
- Air-gapped environments cannot use Sigstore
- Defense customers require offline operation

**Decision:** Rejected - must support air-gapped per ADR-049

## Consequences

### Positive

- Addresses the supply chain security market segment served by vendors such as Snyk and Wiz (as of February 2026)
- Enables federal compliance (EO 14028)
- Differentiates with graph-based provenance queries
- Foundation for Phase 2 Kubernetes admission control

### Negative

- Additional infrastructure (Rekor dependency for non-air-gapped)
- Increased storage costs (SBOM artifacts)
- Complexity of supporting multiple signing modes

## References

- [EO 14028 - Improving the Nation's Cybersecurity](https://www.whitehouse.gov/briefing-room/presidential-actions/2021/05/12/executive-order-on-improving-the-nations-cybersecurity/)
- [NTIA SBOM Minimum Elements](https://www.ntia.gov/files/ntia/publications/sbom_minimum_elements_report.pdf)
- [Sigstore Documentation](https://docs.sigstore.dev/)
- [CycloneDX Specification](https://cyclonedx.org/specification/overview/)
- [SPDX Specification](https://spdx.github.io/spdx-spec/)
- [ADR-049: Self-Hosted Deployment Strategy](/docs/architecture-decisions/ADR-049-self-hosted-deployment-strategy.md)
- [Existing SBOMDetectionService](/src/services/sbom_detection_service.py)

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*

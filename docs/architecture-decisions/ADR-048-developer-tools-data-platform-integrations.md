# ADR-048: Developer Tools and Data Platform Integrations

**Status:** Accepted
**Date:** 2025-12-31 | **Target:** Q1-Q2 2026
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-046 (Support Ticketing Connectors), ADR-037 (AWS Agent Capability), ADR-034 (Context Engineering)
**Reviews:** Product Manager (B+), Systems Architect (Medium Risk), Security Analyst (HIGH Risk - Mitigated)

---

## Executive Summary

This ADR documents the decision to implement integrations with developer tools (IDEs, notebooks) and data platform services to extend Aura's security intelligence capabilities to where developers work and enable enterprise data pipeline connectivity.

**Key Outcomes:**
- IDE extensions for VSCode, Jupyter, and PyCharm bringing Aura's security intelligence to the development environment
- **GraphRAG Context Visualization** (P0 differentiator) - Unique code relationship visualization in IDEs
- Data platform connectors (Dataiku, Fivetran) for enterprise MLOps governance
- Generic Export API for BI/analytics tools (replaces dedicated Qlik connector)

**Strategic Value:**
- Shift-left security at the point of code creation
- **GraphRAG as Key Differentiator:** Neptune-powered code relationship visualization unavailable in competing tools
- Coverage for underserved data science security gap
- Enterprise sales enablement through data pipeline integration

---

## Context

### Current State

Project Aura provides autonomous code intelligence and security vulnerability detection through a web-based interface. Developers and data scientists must context-switch to the Aura UI to view security findings and approve patches.

Current limitations:
- Security feedback occurs after code is committed (CI/CD stage)
- Data science code (notebooks) often bypasses security review
- No direct integration with enterprise data/analytics platforms
- Business users lack visibility without accessing technical Aura UI

### Problem Statement

1. **Developer Friction:** Security feedback at CI/CD is too late in the development cycle
2. **Data Science Gap:** Jupyter notebooks and ML pipelines are underserved by traditional security tools
3. **Enterprise Requirements:** Large customers expect integrations with existing toolchains
4. **Business Visibility:** CISOs and executives need security metrics in their BI tools

### Target User Personas

| Persona | Primary Pain Point | Integration Need |
|---------|-------------------|------------------|
| Software Engineers | Context-switching to security tools | IDE integration |
| Data Scientists | No security review for notebook code | Jupyter integration |
| ML Engineers | MLOps pipeline security gaps | Dataiku integration |
| Enterprise IT | Data integration complexity | Fivetran integration |
| CISOs/Executives | Lack of security visibility | Qlik integration |

---

## Decision

**Implement a phased integration strategy prioritizing developer-facing tools (highest user value) followed by data platform connectors (enterprise enablement).**

### Integration Categories

#### Category 1: Developer Tools (High Priority)
- **VSCode Extension** - Primary IDE, largest developer audience (Phase 1)
- **Jupyter Extension** - Data science security coverage, high ROI (Phase 2)
- **PyCharm Plugin** - Python-focused teams, enterprise presence (Phase 3)

#### Category 2: Data Platforms (Medium Priority)
- **Dataiku** - Enterprise MLOps governance (Phase 4)
- **Fivetran** - Data pipeline connectivity (Phase 5)
- **Generic Export API** - Replaces dedicated Qlik connector; enables any BI tool (Phase 5)

> **Note:** Qlik dedicated connector removed per Product Manager review. Generic Export API provides broader coverage with lower maintenance.

---

## Architecture Overview

### IDE Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IDE INTEGRATION ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │  VSCode          │  │  PyCharm         │  │  Jupyter         │
  │  Extension       │  │  Plugin          │  │  Extension       │
  │                  │  │                  │  │                  │
  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │
  │  │ CodeLens   │  │  │  │ Inspection │  │  │  │ Cell       │  │
  │  │ Provider   │  │  │  │ Provider   │  │  │  │ Inspector  │  │
  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │
  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │
  │  │ Diagnostic │  │  │  │ Quick Fix  │  │  │  │ Sidebar    │  │
  │  │ Provider   │  │  │  │ Provider   │  │  │  │ Panel      │  │
  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │
  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │
  │  │ Status Bar │  │  │  │ Tool       │  │  │  │ Magic      │  │
  │  │ Item       │  │  │  │ Window     │  │  │  │ Commands   │  │
  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │
  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
           │                     │                     │
           └─────────────────────┼─────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Aura IDE SDK          │
                    │   (Shared TypeScript)   │
                    │                         │
                    │   - API Client          │
                    │   - Auth Handler        │
                    │   - Cache Manager       │
                    │   - Event Emitter       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Aura API Gateway      │
                    │   /api/v1/extension/*   │
                    │   (Extends existing)    │
                    │                         │
                    │   POST /scan            │
                    │   GET /findings/{file}  │
                    │   POST /fix/apply       │
                    │   GET /graph/context    │  ← GraphRAG P0
                    │   WS /stream            │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Aura Core Services    │
                    │                         │
                    │   - Vulnerability       │
                    │     Detection           │
                    │   - Patch Generation    │
                    │   - GraphRAG Context    │
                    │   - HITL Workflow       │
                    └─────────────────────────┘
```

### Data Platform Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                DATA PLATFORM INTEGRATION ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────┐
                    │   Aura Core Platform    │
                    │                         │
                    │   - Security Findings   │
                    │   - Metrics & KPIs      │
                    │   - Audit Logs          │
                    │   - Agent Activity      │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Dataiku        │ │  Fivetran       │ │  Qlik           │
    │  Connector      │ │  Connector      │ │  Connector      │
    │                 │ │                 │ │                 │
    │  - Project      │ │  - Source:      │ │  - Data Source  │
    │    Scanning     │ │    Aura API     │ │    Connection   │
    │  - Flow         │ │  - Dest:        │ │  - Pre-built    │
    │    Analysis     │ │    Warehouse    │ │    Dashboard    │
    │  - Model        │ │  - Incremental  │ │  - Custom       │
    │    Governance   │ │    Sync         │ │    Analytics    │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Dataiku DSS    │ │  Data Warehouse │ │  Qlik Sense     │
    │  Platform       │ │  (Snowflake/    │ │  Cloud          │
    │                 │ │   Redshift/BQ)  │ │                 │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Component Specifications

### 1. VSCode Extension

**Technology:** TypeScript, VSCode Extension API

**Features:**
| Feature | Description | Priority |
|---------|-------------|----------|
| Real-time Scanning | Scan files on save/change | P0 |
| Vulnerability Diagnostics | Underline issues with severity | P0 |
| CodeLens Actions | "Fix with Aura" above vulnerable code | P0 |
| **GraphRAG Context Panel** | **Show file relationships in sidebar (Key Differentiator)** | **P0** |
| Quick Fix Integration | Cmd+. to apply Aura-suggested fixes | P1 |
| Status Bar | Connection status, finding count | P1 |
| HITL Approval | Request approval from IDE | P2 |

**API Endpoints Required:** (Extends existing `/api/v1/extension/*`)
```
POST /api/v1/extension/scan
  Body: { file_path, content, language }
  Response: { findings: [...], context: {...} }
  Security: Secrets pre-scan filter applied before graph storage

GET /api/v1/extension/findings/{file_hash}
  Response: { findings: [...], last_scan: timestamp }

POST /api/v1/extension/fix/preview
  Body: { finding_id, file_content }
  Response: { diff, confidence, explanation }

POST /api/v1/extension/fix/apply
  Body: { finding_id, file_path }
  Response: { success, new_content }

GET /api/v1/extension/graph/context
  Body: { file_path, depth: 2 }
  Response: { nodes: [...], edges: [...], relationships: {...} }
  Note: GraphRAG visualization - Key differentiator (P0)
```

### 2. PyCharm Plugin

**Technology:** Kotlin, IntelliJ Platform SDK

**Features:**
| Feature | Description | Priority |
|---------|-------------|----------|
| Inspection Provider | Custom inspections for Aura findings | P0 |
| Quick Fix Actions | Alt+Enter to apply fixes | P0 |
| Tool Window | Dedicated Aura panel | P1 |
| Annotator | Gutter icons for severity | P1 |
| Run Configuration | "Scan with Aura" run config | P2 |

### 3. Jupyter Extension

**Technology:** TypeScript, JupyterLab Extension API

**Features:**
| Feature | Description | Priority |
|---------|-------------|----------|
| Cell Scanning | Scan code cells on execution | P0 |
| Sidebar Panel | Findings per notebook | P0 |
| Cell Annotations | Visual indicators on cells | P1 |
| Magic Commands | `%aura_scan`, `%aura_fix` | P1 |
| Secrets Detection | Hardcoded credentials alert | P0 |
| Dependency Check | Package vulnerability scan | P1 |

### 4. Dataiku Connector

**Technology:** Python, Dataiku Plugin SDK

**Features:**
| Feature | Description | Priority |
|---------|-------------|----------|
| Project Scanner | Scan Dataiku projects for vulnerabilities | P0 |
| Flow Analysis | Security analysis of data flows | P1 |
| Model Governance | Track model security metadata | P1 |
| Recipe Inspection | Scan Python/SQL recipes | P0 |
| Custom Dataset | Aura findings as dataset | P2 |

### 5. Fivetran Connector

**Technology:** Fivetran Connector SDK (Python)

**Features:**
| Feature | Description | Priority |
|---------|-------------|----------|
| Aura Source | Export findings to warehouse | P0 |
| Incremental Sync | Sync new findings efficiently | P0 |
| Schema Mapping | Standard schema for findings | P1 |
| Webhook Support | Real-time sync on new findings | P2 |

**Exported Tables:**
- `aura_findings` - Vulnerability findings
- `aura_patches` - Generated patches
- `aura_approvals` - HITL approval records
- `aura_agents` - Agent activity logs
- `aura_metrics` - Security KPIs

### 6. Qlik Connector

**Technology:** Qlik Connector SDK, REST API

**Features:**
| Feature | Description | Priority |
|---------|-------------|----------|
| Data Connection | REST connector to Aura API | P0 |
| Pre-built App | Executive security dashboard | P1 |
| Custom Measures | MTTR, finding trends, risk score | P1 |
| Alerting | Threshold-based alerts | P2 |

**Dashboard Components:**
- Security Posture Overview (risk score gauge)
- Vulnerability Trend (line chart)
- Finding by Severity (donut chart)
- Remediation Velocity (bar chart)
- Agent Activity (table)
- Repository Risk Matrix (heatmap)

---

## Implementation Plan

> **Note:** Phase order updated per Product Manager review: Jupyter elevated to Phase 2 (higher ROI), PyCharm moved to Phase 3, Qlik removed (replaced by Generic Export API)

### Phase 0: Integration Abstraction Layer (Week 0)

**Deliverables:**
- [ ] Base adapter interface (`src/services/integrations/base_adapter.py`)
- [ ] Secrets pre-scan filter service
- [ ] Export authorization service (row-level security)
- [ ] Shared error handling and retry logic

**Success Criteria:**
- All future integrations implement base adapter interface
- 100% test coverage on security services

### Phase 1: VSCode Extension (Weeks 1-4)

**Deliverables:**
- [ ] VSCode extension scaffold with TypeScript
- [ ] Aura IDE SDK (shared library)
- [ ] Backend `/api/v1/extension/*` endpoints
- [ ] Real-time scanning on file save
- [ ] Diagnostic provider for findings
- [ ] CodeLens for fix suggestions
- [ ] **GraphRAG Context Panel** (P0 differentiator)
- [ ] Status bar integration
- [ ] Extension marketplace packaging (EV certificate signed)

**Success Criteria:**
- Scan latency < 500ms for files under 1000 lines
- Findings appear within 2 seconds of file save
- 99% accuracy matching web UI findings
- GraphRAG panel loads relationships in < 1 second

### Phase 2: Jupyter Extension (Weeks 5-7)

**Deliverables:**
- [ ] JupyterLab extension scaffold
- [ ] Cell scanning on execution
- [ ] Sidebar findings panel
- [ ] Magic commands implementation (`%aura_scan`, `%aura_fix`)
- [ ] Secrets detection highlighting
- [ ] PyPI trusted publisher packaging

**Success Criteria:**
- Scan cells in < 1 second
- Zero false positives on common notebook patterns
- Secrets detection rate > 95%

### Phase 3: PyCharm Plugin (Weeks 8-10)

**Deliverables:**
- [ ] IntelliJ plugin scaffold with Kotlin
- [ ] Kotlin SDK wrapper for Aura API
- [ ] Inspection provider integration
- [ ] Quick fix actions
- [ ] Tool window panel with GraphRAG visualization
- [ ] JetBrains Marketplace packaging (signed)

**Success Criteria:**
- Feature parity with VSCode extension
- Compatible with PyCharm 2023.x+, IntelliJ IDEA

### Phase 4: Dataiku Connector (Weeks 11-13)

**Deliverables:**
- [ ] Dataiku plugin scaffold
- [ ] Project scanner component
- [ ] Flow analysis integration
- [ ] Recipe inspection
- [ ] Dataiku Plugin Store packaging

**Success Criteria:**
- Full project scan in < 5 minutes
- Integration with Dataiku governance features

### Phase 5: Fivetran Connector + Generic Export API (Weeks 14-16)

**Deliverables:**
- [ ] Fivetran connector implementation
- [ ] Schema definition for all tables
- [ ] Incremental sync logic with row-level security
- [ ] Connector certification submission
- [ ] Generic Export API (`/api/v1/export/*`) for any BI tool

**Success Criteria:**
- Initial sync completes in < 10 minutes
- Incremental sync latency < 1 minute
- Row-level security enforced on all exports

---

## Alternatives Considered

### Alternative 1: Web-Only Interface
**Rejected:** Requires context-switching, poor developer experience, late-stage feedback.

### Alternative 2: Generic Language Server Protocol (LSP)
**Considered:** Could enable broader IDE support. Rejected for Phase 1 due to complexity; may revisit for Phase 2 expansion.

### Alternative 3: Browser Extension Instead of IDE
**Rejected:** Limited code access, cannot provide inline fixes, security sandbox restrictions.

### Alternative 4: Build Custom BI Dashboards
**Rejected:** Duplicates existing customer investments. Better to integrate with tools customers already use.

---

## Security Considerations

> **Security Review:** HIGH Risk identified - mitigations below address 5 critical/high findings

### IDE Extensions
1. **Authentication:** OAuth 2.0 with PKCE for device flow
2. **Token Storage:** OS keychain integration (macOS Keychain, Windows Credential Manager)
3. **Data in Transit:** TLS 1.3 for all API communication
4. **Local Caching:** Encrypted cache with configurable TTL
5. **Telemetry:** Opt-in only, no code content transmitted

### Critical Security Controls (From Security Review)

#### 1. Secrets Pre-Scan Filter (CRITICAL)
```
Code → Secrets Scanner → [REDACT] → GraphRAG Storage
```
- Apply regex + ML-based secrets detection BEFORE code reaches Neptune
- Redact detected secrets with `[REDACTED:type]` placeholders
- Log secret detection events for audit trail
- Implementation: `src/services/secrets_prescan_filter.py`

#### 2. Supply Chain Security (HIGH)
- VSCode extension: Sign with EV certificate, submit to Microsoft verification
- PyCharm plugin: Sign with JetBrains-verified certificate
- Jupyter extension: PyPI trusted publisher workflow
- All: SBOM generation, dependency vulnerability scanning in CI

#### 3. Row-Level Security for Data Exports (HIGH)
- Fivetran connector must respect Aura's RBAC
- Filter exported data based on user's organization and permissions
- Implement in `src/services/export_authorization_service.py`

#### 4. GovCloud/CUI Handling (MEDIUM)
- If code may contain CUI markers, apply CUI-aware filtering
- Disable telemetry by default in GovCloud deployments
- Document handling procedures for CUI-marked code

### Data Platform Connectors
1. **API Keys:** Stored in customer's secret management (AWS Secrets Manager)
2. **Data Export:** Row-level security enforced, configurable field exclusion
3. **Audit Logging:** All data access logged with user context
4. **Network:** Respect VPC boundaries, support PrivateLink

---

## Success Metrics

### Developer Tools
| Metric | Target |
|--------|--------|
| Extension install rate | 50% of active users within 90 days |
| Daily active users | 30% of installed base |
| Mean time to first fix | < 5 minutes from finding |
| Fix acceptance rate | > 60% |

### Data Platforms
| Metric | Target |
|--------|--------|
| Connector adoption | 20% of enterprise customers |
| Dashboard engagement | Weekly view by 80% of CISOs |
| Data freshness | < 15 minutes lag |

---

## Dependencies

1. **Backend API:** Extend existing `/api/v1/extension/*` endpoints (per Architect review)
2. **Authentication:** Device flow OAuth with PKCE support
3. **Rate Limiting:** IDE-specific rate limits (higher than web), Redis caching
4. **WebSocket:** Real-time scanning updates
5. **Security Services:** Secrets pre-scan filter, export authorization (Phase 0)
6. **Marketplace Accounts:** VSCode (EV cert), JetBrains (signed), PyPI (trusted publisher), Fivetran
7. **Infrastructure:** Redis cluster for caching, provisioned Lambda for latency

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| IDE API changes break extensions | High | Pin to stable APIs, automated compatibility tests |
| Performance impact on IDE | High | Background processing, debounced scans |
| Marketplace rejection | Medium | Follow platform guidelines, pre-submission review |
| Data platform API rate limits | Medium | Caching, incremental sync, backoff |
| Enterprise firewall blocks | Medium | Configurable proxy support, offline mode |

---

## Cost Estimate

| Component | Development | Maintenance (Annual) |
|-----------|-------------|---------------------|
| Abstraction Layer + Security | 1 week | 0.5 week |
| VSCode Extension | 4 weeks | 2 weeks |
| Jupyter Extension | 3 weeks | 1 week |
| PyCharm Plugin | 3 weeks | 2 weeks |
| Dataiku Connector | 3 weeks | 1 week |
| Fivetran + Generic Export API | 2 weeks | 1 week |
| **Total** | **16 weeks** | **7.5 weeks/year** |

> **Note:** Qlik connector removed (-2 weeks dev, -1 week maintenance). Generic Export API addresses BI use case with lower ongoing cost.

---

## References

- VSCode Extension API: https://code.visualstudio.com/api
- IntelliJ Platform SDK: https://plugins.jetbrains.com/docs/intellij
- JupyterLab Extensions: https://jupyterlab.readthedocs.io/en/stable/extension
- Dataiku Plugin SDK: https://doc.dataiku.com/dss/latest/plugins
- Fivetran Connector SDK: https://fivetran.com/docs/connectors/connector-sdk

---

## Agent Review Summary

### Product Manager Review (Grade: B+)
- **Recommendation:** Elevate GraphRAG Context Panel to P0 (key differentiator)
- **Recommendation:** Swap Jupyter (Phase 2) and PyCharm (Phase 3) for higher ROI
- **Recommendation:** Cut Qlik connector, replace with Generic Export API
- **Status:** Incorporated

### Systems Architect Review (Risk: Medium)
- **Recommendation:** Consolidate API to existing `/api/v1/extension/*`
- **Recommendation:** Add Phase 0 for Integration Abstraction Layer
- **Recommendation:** Add Redis caching and provisioned Lambda for latency
- **Status:** Incorporated

### Security Analyst Review (Risk: HIGH → Mitigated)
- **Critical:** Secrets pre-scan filter before GraphRAG storage
- **High:** Supply chain security (EV certs, signed packages, trusted publishers)
- **High:** Row-level security for data exports
- **Medium:** GovCloud/CUI handling procedures
- **Status:** Mitigations documented, Phase 0 includes security services

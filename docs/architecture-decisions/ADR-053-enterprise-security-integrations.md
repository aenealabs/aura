# ADR-053: Enterprise Security Integrations (Zscaler, Saviynt, AuditBoard)

**Status:** Proposed
**Date:** 2026-01-05
**Decision Makers:** Project Aura Platform Team, Security Architecture Team
**Related:** ADR-028 (External Tool Connectors), ADR-048 (Developer Tools Integration), ADR-004 (Cloud Abstraction Layer)

---

## Executive Summary

This ADR establishes the architecture for integrating three enterprise security platforms into Project Aura: **Zscaler** (Zero Trust security), **Saviynt** (Identity Governance), and **AuditBoard** (GRC/Compliance). These integrations extend ADR-028's connector framework to provide comprehensive security context for autonomous code intelligence operations.

**Core Thesis:** Enterprise security is not siloed—threats detected by Zscaler inform identity risks in Saviynt, which map to compliance controls in AuditBoard. By integrating all three platforms, Aura gains a unified security posture view that enhances vulnerability prioritization, HITL approval workflows, and compliance reporting.

**Key Outcomes:**
- Unified security context from Zero Trust, Identity, and Compliance platforms
- Enhanced HITL approval with identity governance context
- Bidirectional compliance sync (Aura findings ↔ AuditBoard controls)
- GovCloud-compatible authentication for all three integrations
- ~4,700 lines of new code with 70%+ test coverage

---

## Context

### The Enterprise Security Integration Gap

Project Aura currently integrates with several security tools (Splunk, CrowdStrike, Qualys) but lacks coverage in three critical domains:

| Domain | Current Gap | Business Impact |
|--------|-------------|-----------------|
| **Zero Trust Network** | No visibility into web security policies, DLP incidents, or user risk scores | Cannot correlate code vulnerabilities with network-level threats |
| **Identity Governance** | No integration with IGA/PAM systems | HITL approvers lack identity context; no SoD validation |
| **GRC/Compliance** | Manual compliance evidence collection | Audit findings not synced; control testing status unknown |

### Existing Connector Architecture

ADR-028 established the external tool connector framework with the following patterns:

```
src/services/
├── external_tool_connectors.py    # Base classes, registry
├── splunk_connector.py            # SIEM integration
├── crowdstrike_connector.py       # EDR integration
├── qualys_connector.py            # VMDR integration
└── connectors/
    └── __init__.py                # Connector registry
```

**Key Patterns:**
- `ExternalToolConnector` base class with health check, rate limiting, retry logic
- `ConnectorResult` dataclass for standardized responses
- `@require_enterprise_mode` decorator for license enforcement
- Async/await pattern for all API operations
- Secrets Manager integration for credential storage

### Target Platforms

#### Zscaler

**Category:** Zero Trust Security Platform
**Products:** ZIA (Internet Access), ZPA (Private Access)
**FedRAMP Status:** FedRAMP High (zscalergov.net cloud)

| Capability | API | Value to Aura |
|------------|-----|---------------|
| Threat Logs | ZIA `/threatLogs` | Identify malicious dependencies, compromised endpoints |
| DLP Incidents | ZIA `/dlpIncidents` | Detect data exposure in code repositories |
| URL Filtering | ZIA `/urlFilteringRules` | Security policy context for sandbox isolation |
| User Risk Scores | ZIA `/userRiskScoring` | Prioritize HITL reviews for high-risk users |
| Access Policies | ZPA `/policySet` | Private application access context |

#### Saviynt

**Category:** Identity Governance and Administration (IGA)
**Products:** Enterprise Identity Cloud, PAM, Access Certifications
**FedRAMP Status:** FedRAMP Moderate

| Capability | API | Value to Aura |
|------------|-----|---------------|
| User Management | `/ECM/api/v5/users` | Map code changes to identity profiles |
| Entitlements | `/ECM/api/v5/entitlements` | Validate HITL approver permissions |
| Access Requests | `/ECM/api/v5/accessRequests` | Integrate approval workflows |
| Certifications | `/ECM/api/v5/certifications` | Periodic access review status |
| PAM Sessions | `/ECM/api/v5/privilegedSessions` | Privileged action audit trail |
| Risk Analytics | `/ECM/api/v5/analytics/riskScores` | User and access risk scoring |

#### AuditBoard

**Category:** Governance, Risk, and Compliance (GRC)
**Products:** Audit Management, Risk Management, Compliance Management
**FedRAMP Status:** SOC 2 Type II (GovCloud deployment available on request)

| Capability | API | Value to Aura |
|------------|-----|---------------|
| Controls | `/api/v1/controls` | Map vulnerabilities to control failures |
| Risks | `/api/v1/risks` | Enterprise risk context for prioritization |
| Findings | `/api/v1/findings` | Bidirectional sync with Aura vulnerabilities |
| Evidence | `/api/v1/evidence` | Export HITL approvals as audit evidence |
| Frameworks | `/api/v1/frameworks` | CMMC, SOC 2, NIST mapping |

---

## Decision

**Implement three new enterprise security connectors following ADR-028 patterns, with category assignments that reflect their primary function in Aura's security architecture.**

### Integration Category Classification

```
CONNECTOR REGISTRY TAXONOMY (Updated)

┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL TOOL CATEGORIES                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SECURITY (Threat Detection & Response)                                     │
│  ─────────────────────────────────────                                      │
│  ├── SIEM:        Splunk                                                    │
│  ├── EDR:         CrowdStrike                                               │
│  ├── VMDR:        Qualys                                                    │
│  ├── Zero Trust:  Zscaler  ← NEW                                            │
│  └── IGA/PAM:     Saviynt  ← NEW                                            │
│                                                                             │
│  COMPLIANCE (Audit & Risk Management)  ← NEW CATEGORY                       │
│  ────────────────────────────────────                                       │
│  └── GRC:         AuditBoard  ← NEW                                         │
│                                                                             │
│  TICKETING (Issue Tracking)                                                 │
│  ─────────────────────────                                                  │
│  ├── Zendesk                                                                │
│  ├── ServiceNow                                                             │
│  └── Linear                                                                 │
│                                                                             │
│  DEVOPS (CI/CD & Infrastructure)                                            │
│  ───────────────────────────────                                            │
│  ├── Terraform Cloud                                                        │
│  └── Azure DevOps                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Connector Registry Updates

```python
# Additions to src/services/connectors/__init__.py

CONNECTOR_REGISTRY = {
    # ... existing connectors ...

    "zscaler": {
        "module": "src.services.zscaler_connector",
        "class": "ZscalerConnector",
        "category": "security",
        "subcategory": "zero_trust",
        "description": "Zscaler Zero Trust cloud security platform (ZIA, ZPA)",
        "auth_methods": ["api_key", "oauth2"],
        "govcloud_compatible": True,
        "govcloud_cloud": "zscalergov.net",
        "data_models": [
            "ZscalerThreatEvent",
            "ZscalerDLPIncident",
            "ZscalerPolicy",
            "ZscalerUserRisk",
        ],
    },

    "saviynt": {
        "module": "src.services.saviynt_connector",
        "class": "SaviyntConnector",
        "category": "security",
        "subcategory": "identity_governance",
        "description": "Saviynt identity governance, PAM, and access certification",
        "auth_methods": ["oauth2", "basic"],
        "govcloud_compatible": True,
        "data_models": [
            "SaviyntUser",
            "SaviyntEntitlement",
            "SaviyntAccessRequest",
            "SaviyntCertification",
            "SaviyntPrivilegedSession",
        ],
    },

    "auditboard": {
        "module": "src.services.auditboard_connector",
        "class": "AuditBoardConnector",
        "category": "compliance",
        "subcategory": "grc",
        "description": "AuditBoard audit, risk, and compliance management",
        "auth_methods": ["api_key", "oauth2"],
        "govcloud_compatible": True,  # On-request deployment
        "data_models": [
            "AuditBoardControl",
            "AuditBoardRisk",
            "AuditBoardFinding",
            "AuditBoardEvidence",
            "AuditBoardFramework",
        ],
    },
}
```

---

## Architecture

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE SECURITY DATA FLOW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INBOUND (Security Context Enrichment)                                      │
│  ─────────────────────────────────────                                      │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   ZSCALER   │     │   SAVIYNT   │     │ AUDITBOARD  │                   │
│  │  (Threats)  │     │ (Identity)  │     │(Compliance) │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  AURA SECURITY CONTEXT SERVICE                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  Threat Intelligence     Identity Context    Control Status  │    │   │
│  │  │  - DLP incidents         - User risk scores  - Control gaps  │    │   │
│  │  │  - Malware detections    - Entitlements      - Risk ratings  │    │   │
│  │  │  - URL categories        - PAM sessions      - Framework map │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      AURA CORE SERVICES                              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Vulnerability │  │    HITL      │  │  Compliance  │               │   │
│  │  │ Prioritization│  │   Workflow   │  │  Reporting   │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ Uses:        │  │ Uses:        │  │ Uses:        │               │   │
│  │  │ - Zscaler    │  │ - Saviynt    │  │ - AuditBoard │               │   │
│  │  │   threat ctx │  │   approver   │  │   controls   │               │   │
│  │  │ - Risk scores│  │   identity   │  │ - Framework  │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  OUTBOUND (Finding Export & Evidence)                                       │
│  ────────────────────────────────────                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      AURA → AUDITBOARD                               │   │
│  │                                                                      │   │
│  │  Vulnerability Findings  ──────────────►  Control Testing Evidence  │   │
│  │  HITL Approval Records   ──────────────►  Audit Evidence            │   │
│  │  Remediation Status      ──────────────►  Finding Remediation       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Authentication Architecture

| Integration | Primary Method | Token Lifetime | Refresh Strategy | GovCloud Notes |
|-------------|----------------|----------------|------------------|----------------|
| **Zscaler ZIA** | API Key + HMAC-MD5 | Session-based | Re-auth on 401 | Use `zscalergov.net` |
| **Zscaler ZPA** | OAuth2 Client Credentials | 1 hour | Proactive at T-5min | Same as ZIA |
| **Saviynt** | OAuth2 Client Credentials | 1 hour | Proactive at T-5min | Verify tenant region |
| **AuditBoard** | API Key (Bearer) | Long-lived | Key rotation via Secrets Manager | Contact vendor |

### Secrets Management

```yaml
# CloudFormation: deploy/cloudformation/secrets-enterprise-integrations.yaml

Resources:
  ZscalerSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub '${ProjectName}/${Environment}/integrations/zscaler'
      SecretString: |
        {
          "zia_api_key": "",
          "zia_username": "",
          "zia_password": "",
          "zia_cloud": "zscaler.net",
          "zpa_client_id": "",
          "zpa_client_secret": "",
          "zpa_customer_id": ""
        }

  SaviyntSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub '${ProjectName}/${Environment}/integrations/saviynt'
      SecretString: |
        {
          "base_url": "https://tenant.saviyntcloud.com",
          "client_id": "",
          "client_secret": ""
        }

  AuditBoardSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub '${ProjectName}/${Environment}/integrations/auditboard'
      SecretString: |
        {
          "base_url": "https://company.auditboard.com",
          "api_key": ""
        }
```

---

## Implementation

### Phase 1: Infrastructure (Week 1)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `deploy/cloudformation/secrets-enterprise-integrations.yaml` | Secrets Manager resources | ~100 |
| IAM policy updates | Secrets access for EKS service accounts | ~50 |
| Connector registry updates | Add three new entries | ~50 |

### Phase 2: Zscaler Connector (Weeks 2-3)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/zscaler_connector.py` | ZIA/ZPA API client | ~900 |
| `tests/test_zscaler_connector.py` | Unit tests (70%+ coverage) | ~400 |

**Key Methods:**
```python
class ZscalerConnector(ExternalToolConnector):
    async def authenticate_zia(self) -> bool
    async def authenticate_zpa(self) -> bool
    async def get_threat_logs(self, hours: int = 24, ...) -> ConnectorResult
    async def get_dlp_incidents(self, hours: int = 24, ...) -> ConnectorResult
    async def get_url_filtering_rules(self) -> ConnectorResult
    async def get_user_risk_score(self, user: str) -> ConnectorResult
    async def get_zpa_applications(self) -> ConnectorResult
    async def get_zpa_access_policies(self) -> ConnectorResult
```

### Phase 3: Saviynt Connector (Weeks 3-4)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/saviynt_connector.py` | Enterprise Identity Cloud client | ~800 |
| `tests/test_saviynt_connector.py` | Unit tests (70%+ coverage) | ~400 |

**Key Methods:**
```python
class SaviyntConnector(ExternalToolConnector):
    async def get_user(self, username: str) -> ConnectorResult
    async def search_users(self, filters: dict) -> ConnectorResult
    async def get_user_entitlements(self, username: str) -> ConnectorResult
    async def get_pending_certifications(self, certifier: str = None) -> ConnectorResult
    async def get_sod_violations(self, user: str = None) -> ConnectorResult
    async def get_privileged_sessions(self, hours: int = 24) -> ConnectorResult
    async def get_user_risk_score(self, username: str) -> ConnectorResult
```

### Phase 4: AuditBoard Connector (Weeks 4-5)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/auditboard_connector.py` | GRC platform client | ~700 |
| `tests/test_auditboard_connector.py` | Unit tests (70%+ coverage) | ~400 |

**Key Methods:**
```python
class AuditBoardConnector(ExternalToolConnector):
    async def list_controls(self, framework: str = None, ...) -> ConnectorResult
    async def get_control(self, control_id: str) -> ConnectorResult
    async def update_control_status(self, control_id: str, status: ...) -> ConnectorResult
    async def create_finding(self, finding: AuditBoardFindingCreate) -> ConnectorResult
    async def add_evidence(self, control_id: str, evidence: ...) -> ConnectorResult
    async def get_risk_register(self, category: str = None) -> ConnectorResult
    async def get_compliance_dashboard(self, framework: str) -> ConnectorResult
```

### Phase 5: API Endpoints & Documentation (Week 6)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/api/enterprise_security_endpoints.py` | FastAPI routes | ~400 |
| `docs/integrations/ENTERPRISE_SECURITY_INTEGRATIONS.md` | Integration guide | ~500 |

**API Endpoints:**
```
GET  /api/v1/integrations/zscaler/threats
GET  /api/v1/integrations/zscaler/dlp-incidents
GET  /api/v1/integrations/zscaler/user/{username}/risk

GET  /api/v1/integrations/saviynt/users/{username}
GET  /api/v1/integrations/saviynt/users/{username}/entitlements
GET  /api/v1/integrations/saviynt/certifications/pending

GET  /api/v1/integrations/auditboard/controls
POST /api/v1/integrations/auditboard/findings
POST /api/v1/integrations/auditboard/evidence
GET  /api/v1/integrations/auditboard/compliance/{framework}
```

---

## Rate Limiting and Error Handling

### Rate Limits

| Integration | Rate Limit | Burst | Backoff Strategy |
|-------------|------------|-------|------------------|
| **Zscaler ZIA** | 100 req/min | 200 | Exponential (1s, 2s, 4s, 8s, max 60s) |
| **Zscaler ZPA** | 50 req/min | 100 | Exponential |
| **Saviynt** | 600 req/min | 1000 | Linear (1s, 2s, 3s, max 10s) |
| **AuditBoard** | 300 req/min | 500 | Exponential |

### Error Handling Pattern

```python
async def _make_request(
    self,
    method: str,
    url: str,
    **kwargs
) -> ConnectorResult:
    """Standardized request with retry and error handling."""
    for attempt in range(self.max_retries):
        try:
            async with self._session.request(method, url, **kwargs) as resp:
                if resp.status == 429:  # Rate limited
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status == 401:  # Auth expired
                    await self._refresh_auth()
                    continue

                if resp.status >= 500:  # Server error
                    await asyncio.sleep(2 ** attempt)
                    continue

                data = await resp.json()
                return ConnectorResult(
                    success=resp.status < 400,
                    status_code=resp.status,
                    data=data if resp.status < 400 else {},
                    error=data.get("message") if resp.status >= 400 else None,
                )

        except asyncio.TimeoutError:
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return ConnectorResult(success=False, error="Request timeout")

    return ConnectorResult(success=False, error="Max retries exceeded")
```

---

## GovCloud Compatibility

### Service Availability

| Integration | Commercial AWS | GovCloud (US) | Configuration |
|-------------|----------------|---------------|---------------|
| **Zscaler** | Full | Full (FedRAMP High) | Set `zia_cloud: "zscalergov.net"` |
| **Saviynt** | Full | Full (FedRAMP Moderate) | Use GovCloud tenant URL |
| **AuditBoard** | Full | On-request | Contact vendor for GovCloud instance |

### Auto-Detection Pattern

```python
def __init__(self, ...):
    # Auto-detect GovCloud region
    region = os.environ.get("AWS_REGION", "")
    if region.startswith("us-gov-"):
        self._govcloud_mode = True
        if self.name == "zscaler":
            self.zia_cloud = ZscalerCloud.ZSCALERGOV
            logger.info("GovCloud detected: using zscalergov.net")
```

---

## Security Considerations

### Data Classification

| Data Type | Classification | Handling |
|-----------|----------------|----------|
| Zscaler threat logs | Confidential | Encrypt at rest, 90-day retention |
| Saviynt user data | PII | Encrypt, mask in logs, GDPR compliant |
| AuditBoard controls | Internal | Standard encryption |
| API credentials | Secret | Secrets Manager only, never logged |

### Access Control

```python
# All connector methods require enterprise mode
@require_enterprise_mode
async def get_threat_logs(self, ...):
    """Requires ENTERPRISE or HYBRID license mode."""
    pass
```

### Audit Logging

All connector operations are logged to CloudWatch with:
- Timestamp
- User/service identity
- Operation type
- Target resource
- Success/failure status
- Latency

---

## Consequences

### Positive

1. **Unified Security View:** Correlate threats across Zero Trust, Identity, and Compliance domains
2. **Enhanced HITL:** Approvers see identity context (entitlements, risk scores, certifications)
3. **Automated Compliance:** Bidirectional sync eliminates manual evidence collection
4. **GovCloud Ready:** All integrations support FedRAMP deployments
5. **Consistent Architecture:** Follows established ADR-028 connector patterns

### Negative

1. **Vendor Dependencies:** Three new external service dependencies
2. **Credential Management:** Three additional secrets to rotate
3. **API Variability:** Each vendor has different API patterns and rate limits
4. **Cost:** API usage may incur vendor charges (varies by license tier)

### Mitigations

| Negative | Mitigation |
|----------|------------|
| Vendor Dependencies | Health checks, circuit breakers, graceful degradation |
| Credential Management | Automated rotation via Secrets Manager |
| API Variability | Unified `ConnectorResult` abstraction |
| Cost | Caching, request batching, configurable polling intervals |

---

## Success Criteria

### Quantitative

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Coverage | ≥ 70% | pytest-cov |
| API Latency (p95) | < 2s | CloudWatch |
| Error Rate | < 1% | CloudWatch |
| Availability | > 99.5% | Health checks |

### Qualitative

| Criterion | Validation |
|-----------|------------|
| HITL approvers find identity context useful | User feedback |
| Compliance team adopts AuditBoard sync | Adoption metrics |
| Security team uses Zscaler threat correlation | Usage analytics |

---

## Test Coverage Requirements

Per `pyproject.toml`, minimum 70% coverage is required:

```python
# tests/test_zscaler_connector.py
class TestZscalerConnector:
    def test_zia_authentication(self): ...
    def test_zpa_authentication(self): ...
    def test_threat_log_retrieval(self): ...
    def test_dlp_incident_retrieval(self): ...
    def test_rate_limit_handling(self): ...
    def test_govcloud_auto_detection(self): ...

# tests/test_saviynt_connector.py
class TestSaviyntConnector:
    def test_oauth_token_refresh(self): ...
    def test_user_lookup(self): ...
    def test_entitlement_retrieval(self): ...
    def test_certification_status(self): ...

# tests/test_auditboard_connector.py
class TestAuditBoardConnector:
    def test_control_listing(self): ...
    def test_finding_creation(self): ...
    def test_evidence_upload(self): ...
    def test_compliance_dashboard(self): ...
```

---

## Implementation Summary

| Phase | Deliverables | LOC | Duration |
|-------|--------------|-----|----------|
| 1: Infrastructure | CloudFormation, IAM, Registry | ~200 | Week 1 |
| 2: Zscaler | Connector + Tests | ~1,300 | Weeks 2-3 |
| 3: Saviynt | Connector + Tests | ~1,200 | Weeks 3-4 |
| 4: AuditBoard | Connector + Tests | ~1,100 | Weeks 4-5 |
| 5: API & Docs | Endpoints + Guide | ~900 | Week 6 |
| **Total** | | **~4,700** | **6 weeks** |

---

## Decision Outcome

**PROPOSED** - Pending implementation approval.

### Conditions for Approval

1. Security review of credential handling approach
2. Cost analysis from vendor API usage estimates
3. GovCloud tenant confirmation from AuditBoard

### Next Steps

1. Obtain vendor API documentation and sandbox credentials
2. Deploy Phase 1 infrastructure (secrets, IAM)
3. Implement Zscaler connector first (highest security value)
4. Validate with security team before proceeding to Phase 3-4

---

## References

1. **ADR-028** - External Tool Connectors Framework
2. **ADR-048** - Developer Tools Integration
3. **Zscaler API Documentation** - https://help.zscaler.com/zia/api
4. **Saviynt API Documentation** - https://docs.saviyntcloud.com/
5. **AuditBoard API Documentation** - https://api-docs.auditboard.com/
6. **NIST 800-53** - Security and Privacy Controls
7. **FedRAMP Marketplace** - Authorization status for vendors

---

## Appendix A: Data Models

### Zscaler Data Models

```python
@dataclass
class ZscalerThreatEvent:
    event_id: str
    timestamp: str
    user: str
    department: str | None
    url: str | None
    threat_category: str  # malware, phishing, botnet, etc.
    threat_name: str
    action: str  # blocked, allowed, cautioned
    source_ip: str | None
    destination_ip: str | None

@dataclass
class ZscalerDLPIncident:
    incident_id: str
    timestamp: str
    user: str
    dlp_engine: str
    dlp_dictionary: str
    severity: str  # critical, high, medium, low
    action: str
    destination: str | None
```

### Saviynt Data Models

```python
@dataclass
class SaviyntUser:
    user_key: str
    username: str
    email: str
    status: str  # Active, Inactive, Terminated
    manager: str | None
    department: str | None
    risk_score: float | None
    last_login: str | None

@dataclass
class SaviyntEntitlement:
    entitlement_key: str
    entitlement_name: str
    entitlement_type: str
    application: str
    risk_level: str | None
```

### AuditBoard Data Models

```python
@dataclass
class AuditBoardControl:
    control_id: str
    control_name: str
    framework: str
    status: str  # effective, ineffective, not_tested
    owner: str | None
    last_tested: str | None
    evidence_count: int

@dataclass
class AuditBoardFinding:
    finding_id: str
    title: str
    status: str  # open, in_progress, remediated, closed
    severity: str
    owner: str | None
    due_date: str | None
    related_controls: list[str]
```

---

## Appendix B: CloudFormation Template

See `deploy/cloudformation/secrets-enterprise-integrations.yaml` for the complete template.

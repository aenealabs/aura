# Security Services Overview

## Project Aura - Security Architecture

This document provides an overview of Project Aura's security services, their capabilities, and how they integrate together.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER/API REQUEST                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API SECURITY LAYER                                   │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   Rate Limiting     │  │   Authentication    │  │   Authorization     │  │
│  │   (429 errors)      │  │   (JWT validation)  │  │   (RBAC check)      │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INPUT VALIDATION SERVICE                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • SQL Injection Detection     • Command Injection Detection        │    │
│  │  • XSS Detection               • Path Traversal Detection           │    │
│  │  • SSRF Detection              • Prompt Injection Detection         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
┌────────────────────────────────┐  ┌────────────────────────────────────────┐
│   SECRETS DETECTION SERVICE    │  │        APPLICATION LOGIC               │
│  ┌──────────────────────────┐  │  │  ┌──────────────────────────────────┐  │
│  │ • AWS Keys/Tokens        │  │  │  │  • GraphRAG Context Retrieval   │  │
│  │ • API Keys (30+ types)   │  │  │  │  • Agent Orchestration          │  │
│  │ • Private Keys           │  │  │  │  • Sandbox Management           │  │
│  │ • Database Credentials   │  │  │  │  • Patch Generation             │  │
│  │ • High-Entropy Strings   │  │  │  └──────────────────────────────────┘  │
│  └──────────────────────────┘  │  └────────────────────────────────────────┘
└────────────────────────────────┘                    │
                │                                     │
                └──────────────┬──────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SECURITY AUDIT SERVICE                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Event Logging          • Severity Classification                 │    │
│  │  • Context Capture        • Compliance Tagging                      │    │
│  │  • CloudWatch Export      • DynamoDB Persistence                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SECURITY ALERTS SERVICE                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Alert Generation       • Priority Classification (P1-P5)         │    │
│  │  • HITL Request Creation  • SNS Notification                        │    │
│  │  • Alert Lifecycle        • Remediation Steps                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
┌─────────────────────────────┐  ┌────────────────────────────────────────────┐
│    SNS NOTIFICATIONS        │  │         HITL WORKFLOW                      │
│  ┌───────────────────────┐  │  │  ┌────────────────────────────────────┐    │
│  │ • Email Alerts        │  │  │  │  • Approval Dashboard              │    │
│  │ • PagerDuty           │  │  │  │  • Step Functions Workflow         │    │
│  │ • Slack Integration   │  │  │  │  • Callback API                    │    │
│  └───────────────────────┘  │  │  └────────────────────────────────────┘    │
└─────────────────────────────┘  └────────────────────────────────────────────┘
```

---

## Service Components

### 1. Input Validation Service

**Location:** `src/services/input_validation_service.py`

**Purpose:** Validates and sanitizes all user input to prevent injection attacks.

**Capabilities:**

| Threat Type | Detection Method | Action |
|-------------|------------------|--------|
| SQL Injection | Regex patterns + heuristics | Block/Sanitize |
| XSS (Cross-Site Scripting) | HTML/JS pattern detection | Escape/Block |
| Command Injection | Shell metacharacter detection | Block |
| Path Traversal | Directory traversal patterns | Block |
| SSRF | Localhost/private IP detection | Block |
| Prompt Injection | LLM manipulation patterns | Block/Sanitize |

**Key Classes:**
- `InputValidator` - Main validation class
- `ThreatType` - Enum of threat categories
- `ValidationResult` - Validation outcome with sanitized value

**Usage:**
```python
from src.services.input_validation_service import InputValidator

validator = InputValidator(strict_mode=True)
result = validator.validate_string(user_input, check_sql_injection=True, check_xss=True)

if not result.is_valid:
    raise SecurityError(result.threats_detected)
```

---

### 2. Secrets Detection Service

**Location:** `src/services/secrets_detection_service.py`

**Purpose:** Scans code and configuration for hardcoded secrets.

**Detected Secret Types (30+):**

| Category | Types |
|----------|-------|
| Cloud Providers | AWS Access Key, AWS Secret Key, GCP API Key, Azure Key |
| Version Control | GitHub Token, GitLab Token, Bitbucket Token |
| Communication | Slack Token, Slack Webhook, Discord Token, Twilio Key |
| Payment | Stripe Key, Square Token, PayPal Client ID |
| Email | SendGrid API Key, Mailgun Key, Mailchimp Key |
| Databases | MongoDB URI, PostgreSQL URI, MySQL URI, Redis URL |
| Cryptographic | Private Key (RSA, EC, PGP), JWT Secret |
| Generic | API Key, Bearer Token, High-Entropy String |

**Key Classes:**
- `SecretsDetectionService` - Main scanner
- `SecretType` - Enum of secret categories
- `SecretSeverity` - CRITICAL, HIGH, MEDIUM, LOW
- `SecretFinding` - Individual finding with location
- `ScanResult` - Aggregated scan results

**Usage:**
```python
from src.services.secrets_detection_service import SecretsDetectionService

scanner = SecretsDetectionService(enable_entropy_detection=True)
result = scanner.scan_file("path/to/file.py")

if result.has_secrets:
    for finding in result.findings:
        print(f"{finding.secret_type}: {finding.redacted_value}")
```

---

### 3. Security Audit Service

**Location:** `src/services/security_audit_service.py`

**Purpose:** Logs all security-relevant events for compliance and forensics.

**Event Categories:**

| Category | Event Types |
|----------|-------------|
| Authentication | Login success/failure, logout, token refresh/revoke |
| Authorization | Permission check, RBAC violation, privilege escalation |
| Threats | Command/SQL/prompt injection, XSS, secrets exposure |
| Input Validation | Sanitization, validation failure, injection attempt |
| Agent Security | Tool authorization, sandbox escape, context poisoning |
| Data Operations | Access, export, deletion |
| GraphRAG | Query anomaly, context manipulation |
| System | Configuration change, service status |

**Severity Levels:**
- `CRITICAL` - Immediate response required
- `HIGH` - Urgent attention needed
- `MEDIUM` - Standard priority
- `LOW` - Informational
- `INFO` - Routine logging

**Key Classes:**
- `SecurityAuditService` - Main audit logger
- `SecurityEvent` - Event data structure
- `SecurityContext` - User/request context
- `SecurityEventType` - Event type enum
- `SecurityEventSeverity` - Severity enum

**Usage:**
```python
from src.services.security_audit_service import (
    log_security_event,
    SecurityEventType,
    SecurityEventSeverity,
    SecurityContext,
)

log_security_event(
    event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
    severity=SecurityEventSeverity.INFO,
    message="User logged in",
    context=SecurityContext(user_id="user-123", ip_address="10.0.0.1"),
)
```

---

### 4. Security Alerts Service

**Location:** `src/services/security_alerts_service.py`

**Purpose:** Generates actionable alerts from security events and integrates with HITL workflow.

**Alert Priorities:**

| Priority | Response Time | HITL Required | Examples |
|----------|---------------|---------------|----------|
| P1 - Critical | Immediate | Yes | Command injection, secrets exposure |
| P2 - High | 1 hour | Yes | Prompt injection, privilege escalation |
| P3 - Medium | 4 hours | No | Validation failures, suspicious patterns |
| P4 - Low | 24 hours | No | Configuration issues |
| P5 - Informational | Next business day | No | Audit events |

**Alert Lifecycle:**
```
NEW → ACKNOWLEDGED → IN_PROGRESS → RESOLVED
                              ↘ FALSE_POSITIVE
```

**Key Classes:**
- `SecurityAlertsService` - Alert management
- `SecurityAlert` - Alert data structure
- `HITLApprovalRequest` - HITL integration
- `AlertPriority` - P1-P5 enum
- `AlertStatus` - Lifecycle states

**Usage:**
```python
from src.services.security_alerts_service import get_alerts_service

service = get_alerts_service()

# Process security event (auto-creates alert if needed)
alert = service.process_security_event(security_event)

# Acknowledge alert
service.acknowledge_alert(alert.alert_id, user_id="analyst@company.com")

# Resolve alert
service.resolve_alert(
    alert.alert_id,
    user_id="analyst@company.com",
    resolution="Blocked IP and rotated credentials",
)
```

---

### 5. API Security Integration

**Location:** `src/api/security_integration.py`

**Purpose:** Integrates all security services into FastAPI endpoints.

**Components:**

| Component | Purpose |
|-----------|---------|
| `ValidatedIngestionRequest` | Validates repository URLs, branches |
| `ValidatedQueryRequest` | Validates search queries |
| `ValidatedWebhookPayload` | Validates webhook payloads |
| `@audit_endpoint` | Decorator for automatic audit logging |
| `@require_no_secrets` | Decorator to scan request body for secrets |
| `validate_and_sanitize()` | Helper function for input validation |
| `get_security_context()` | Extracts user context from request |

**Usage:**
```python
from src.api.security_integration import (
    audit_endpoint,
    require_no_secrets,
    ValidatedQueryRequest,
)

@app.post("/query")
@audit_endpoint(event_type=SecurityEventType.DATA_ACCESS)
@require_no_secrets(block_on_critical=True)
async def query(request: ValidatedQueryRequest):
    # All validation and auditing happens automatically
    return {"result": process(request.query)}
```

---

## Developer Tools

### Pre-Commit Hooks

**Location:** `scripts/security_hooks/`

| Hook | File | Purpose |
|------|------|---------|
| Secrets Scanner | `secrets_hook.py` | Block commits with secrets |
| Config Validator | `config_hook.py` | Validate config files |

**Installation:**
```bash
pip install pre-commit
pre-commit install
```

### Security CLI

**Location:** `scripts/aura_security_cli.py`

**Commands:**

| Command | Purpose | Example |
|---------|---------|---------|
| `scan` | Scan files for secrets | `python aura_security_cli.py scan . -r` |
| `validate` | Validate input text | `python aura_security_cli.py validate "text"` |
| `quick` | Quick scan of sensitive files | `python aura_security_cli.py quick` |
| `report` | Generate security report | `python aura_security_cli.py report -o report.json` |
| `stats` | Show scanning statistics | `python aura_security_cli.py stats` |

---

## Test Coverage

| Service | Test File | Test Count |
|---------|-----------|------------|
| Input Validation | `test_input_validation_service.py` | 76 |
| Secrets Detection | `test_secrets_detection_service.py` | 66 |
| Security Audit | `test_security_audit_service.py` | 76 |
| Security Alerts | `test_security_alerts_service.py` | 29 |
| API Integration | `test_security_integration.py` | 39 |
| **Total** | | **286** |

**Run all security tests:**
```bash
pytest tests/test_security*.py tests/test_input*.py tests/test_secrets*.py -v
```

---

## Compliance Mapping

### CMMC Level 3

| Control | Service | Implementation |
|---------|---------|----------------|
| AC.1.001 | Input Validation | RBAC, input sanitization |
| AC.2.005 | Security Audit | Principle of least privilege |
| AU.2.041 | Security Audit | Event logging |
| AU.2.042 | Security Audit | Audit record content |
| IR.2.092 | Security Alerts | Event detection |
| IR.2.093 | Security Alerts | Event triage |
| SC.1.175 | Input Validation | Transmission confidentiality |
| SC.3.177 | Input Validation | FIPS-validated crypto |

### SOC 2

| Criteria | Service | Implementation |
|----------|---------|----------------|
| CC6.1 | Input Validation | Logical access controls |
| CC6.6 | Input Validation | System boundary protection |
| CC6.7 | Secrets Detection | Data classification |
| CC7.2 | Security Audit | Security event monitoring |
| CC7.3 | Security Alerts | Event evaluation |
| CC7.4 | Security Alerts | Incident response |

### NIST 800-53

| Control | Service | Implementation |
|---------|---------|----------------|
| AU-2 | Security Audit | Audit events |
| AU-3 | Security Audit | Audit record content |
| AU-6 | Security Alerts | Audit review |
| IR-4 | Security Alerts | Incident handling |
| SI-3 | Secrets Detection | Malicious code protection |
| SI-10 | Input Validation | Input validation |

---

## Integration Points

### AWS Services

| Service | Integration |
|---------|-------------|
| CloudWatch Logs | Audit event export |
| SNS | Alert notifications |
| EventBridge | Real-time event routing |
| DynamoDB | Event persistence |
| Secrets Manager | Credential storage |
| SSM Parameter Store | Configuration storage |

### Internal Services

| Service | Integration |
|---------|-------------|
| HITL Workflow | Alert approval requests |
| Agent Orchestrator | Agent security monitoring |
| Sandbox Network | Isolation enforcement |
| Context Retrieval | GraphRAG security |

---

## Related Documentation

- [Security Incident Response Runbook](./SECURITY_INCIDENT_RESPONSE.md)
- [Developer Security Guidelines](./DEVELOPER_SECURITY_GUIDELINES.md)
- [HITL Sandbox Architecture](./HITL_SANDBOX_ARCHITECTURE.md)
- [GovCloud Readiness Tracker](./GOVCLOUD_READINESS_TRACKER.md)

---

## IAM Permission Scoping (Dec 29, 2025)

CodeBuild data layer IAM permissions have been scoped from `Resource: '*'` to project-specific ARNs:

**Neptune/RDS Permissions:**
- `arn:${AWS::Partition}:rds:${AWS::Region}:${AWS::AccountId}:cluster:${ProjectName}-neptune-*`
- `arn:${AWS::Partition}:rds:${AWS::Region}:${AWS::AccountId}:db:${ProjectName}-neptune-*`
- Includes subnet groups, parameter groups, cluster parameter groups

**OpenSearch Permissions:**
- `arn:${AWS::Partition}:es:${AWS::Region}:${AWS::AccountId}:domain/${ProjectName}-*`

**Template:** `deploy/cloudformation/codebuild-data.yaml`

This change eliminates overly permissive wildcards and enforces least privilege principle.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.1 | 2025-12-29 | Project Aura Team | Added IAM permission scoping section |
| 1.0 | 2025-12-12 | Project Aura Team | Initial release |

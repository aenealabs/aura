# Human-in-the-Loop Workflows

**Version:** 1.0
**Last Updated:** January 2026

---

## Overview

Human-in-the-Loop (HITL) Workflows form the governance layer of Project Aura, ensuring that autonomous AI operations are subject to appropriate human oversight. HITL is not simply a brake on automation; it is a configurable policy framework that allows organizations to balance automation speed with compliance requirements.

This document explains how HITL works, the four configurable autonomy levels, industry-specific policy presets, and the guardrails that always require human approval regardless of policy settings.

---

## Why HITL Matters

Autonomous code remediation is powerful, but enterprises operate under different constraints:

| Constraint | Example | HITL Requirement |
|------------|---------|------------------|
| **Regulatory Compliance** | CMMC Level 3, SOX, HIPAA | Mandatory approval chains |
| **Risk Tolerance** | Defense contractors vs. startups | Variable by organization |
| **Audit Requirements** | Change management trails | Documented decisions |
| **Liability** | Critical infrastructure | Human accountability |

A defense contractor deploying to classified systems has fundamentally different requirements than a startup iterating on a SaaS product. HITL Workflows allow both to use Aura effectively.

### The Trust Spectrum

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUTONOMY SPECTRUM                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FULL_HITL                                              FULL_AUTONOMOUS │
│      │                                                          │       │
│      ▼                                                          ▼       │
│  ┌────────┐  ┌────────────┐  ┌─────────────┐  ┌───────────────────┐     │
│  │ Human  │  │   Human    │  │    Audit    │  │      Fully        │     │ 
│  │Approval│  │  Approval  │  │    Only     │  │    Autonomous     │     │
│  │  All   │  │ CRIT/HIGH  │  │  (Logging)  │  │    Operation      │     │
│  │  Ops   │  │   Only     │  │             │  │                   │     │
│  └────────┘  └────────────┘  └─────────────┘  └───────────────────┘     │
│      │             |                 |                  |               │
│      │             |                 |                  |               │
│  Defense         Financial        Internal         Commercial           │
│  Contractors     Services         Tools            Dev/Test             │
│  Healthcare      Enterprise       Low-Risk         Startups             │
│  GovCloud        Standard         Repos                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Autonomy Levels

Aura provides four configurable autonomy levels that determine when human approval is required.

### Level 1: FULL_HITL

**Human approval required for all operations.**

| Aspect | Behavior |
|--------|----------|
| **Approval Required** | All vulnerability remediations |
| **Automatic Actions** | Detection, patch generation, sandbox testing |
| **Human Actions** | Review and approve/reject all patches |
| **Timeout** | 24 hours (configurable) |
| **Use Case** | Defense contractors, healthcare, government |

```python
# FULL_HITL behavior
patch_generated = coder_agent.generate_patch(vulnerability)
sandbox_result = sandbox.validate(patch_generated)

# Always stops here for human review
approval = hitl_service.request_approval(
    patch=patch_generated,
    sandbox_results=sandbox_result,
    timeout_hours=24
)

if approval.status == "APPROVED":
    deployer.deploy(patch_generated)
```

### Level 2: HITL_CRITICAL (Critical HITL)

**Human approval required for HIGH and CRITICAL severity only.**

| Aspect | Behavior |
|--------|----------|
| **Approval Required** | HIGH and CRITICAL severity vulnerabilities |
| **Automatic Actions** | LOW/MEDIUM severity patches auto-deploy after sandbox |
| **Human Actions** | Review HIGH/CRITICAL patches only |
| **Timeout** | 24 hours for CRITICAL, 48 hours for HIGH |
| **Use Case** | Financial services, enterprise standard |

```python
# CRITICAL_HITL behavior
if vulnerability.severity in ["CRITICAL", "HIGH"]:
    approval = hitl_service.request_approval(patch, sandbox_results)
    if approval.status != "APPROVED":
        return  # Human rejected or timed out
else:
    # LOW/MEDIUM auto-deploy after sandbox passes
    pass

deployer.deploy(patch_generated)
```

### Level 3: AUDIT_ONLY

**Log all decisions but do not block for approval.**

| Aspect | Behavior |
|--------|----------|
| **Approval Required** | None (except guardrails) |
| **Automatic Actions** | All remediations proceed automatically |
| **Human Actions** | Review audit logs, investigate anomalies |
| **Audit Trail** | Full decision logging for compliance |
| **Use Case** | Internal tools, low-risk repositories |

```python
# AUDIT_ONLY behavior
audit_log.record(
    decision="AUTO_APPROVE",
    vulnerability=vulnerability,
    patch=patch_generated,
    confidence=coder_agent.confidence,
    timestamp=datetime.utcnow()
)

deployer.deploy(patch_generated)
```

### Level 4: FULL_AUTONOMOUS

**Fully automated operation with minimal human interaction.**

| Aspect | Behavior |
|--------|----------|
| **Approval Required** | Guardrails only (see below) |
| **Automatic Actions** | All remediations including deployment |
| **Human Actions** | Exception handling, guardrail approvals |
| **Monitoring** | Real-time dashboards, anomaly alerts |
| **Use Case** | Commercial dev/test, rapid iteration |

**Important:** Even FULL_AUTONOMOUS respects guardrails. Production deployments, credential changes, and other critical operations always require human approval.

### Autonomy Level Comparison

| Level | CRITICAL | HIGH | MEDIUM | LOW | Guardrails |
|-------|----------|------|--------|-----|------------|
| FULL_HITL | Human | Human | Human | Human | Human |
| HITL_CRITICAL | Human | Human | Auto | Auto | Human |
| AUDIT_ONLY | Auto (logged) | Auto (logged) | Auto (logged) | Auto (logged) | Human |
| FULL_AUTONOMOUS | Auto | Auto | Auto | Auto | Human |

---

## Industry Policy Presets

Aura includes seven pre-built policy presets designed for specific industries and compliance frameworks. Organizations can use these presets as-is or customize them.

### Preset Overview

| Preset | Default Level | HITL Enabled | Target Industry | Compliance Frameworks |
|--------|---------------|--------------|-----------------|----------------------|
| `defense_contractor` | FULL_HITL | Yes | Defense, Aerospace | CMMC L3+, NIST 800-171 |
| `financial_services` | FULL_HITL | Yes | Banking, Insurance | SOX, PCI-DSS, GLBA |
| `healthcare` | FULL_HITL | Yes | Hospitals, Pharma | HIPAA, HITECH, FDA 21 CFR |
| `government_contractor` | FULL_HITL | Yes | Federal Systems | FedRAMP, FISMA |
| `fintech_startup` | HITL_CRITICAL | Yes | Growth Companies | SOC 2, limited SOX |
| `enterprise_standard` | HITL_CRITICAL | Yes | Fortune 500 | General enterprise |
| `internal_tools` | AUDIT_ONLY | No | Internal Dev Teams | Minimal compliance |

### Defense Contractor Preset

```json
{
  "preset_id": "defense_contractor",
  "default_level": "FULL_HITL",
  "hitl_enabled": true,
  "description": "Strictest oversight for classified and controlled systems",
  "compliance_frameworks": ["CMMC_L3", "NIST_800_171", "ITAR"],
  "severity_overrides": {},
  "operation_overrides": {},
  "timeout_hours": {
    "CRITICAL": 12,
    "HIGH": 24,
    "MEDIUM": 48,
    "LOW": 72
  },
  "approver_requirements": {
    "min_approvers": 2,
    "require_security_clearance": true,
    "allowed_roles": ["CISO", "Security Manager", "Cleared Engineer"]
  }
}
```

### Financial Services Preset

```json
{
  "preset_id": "financial_services",
  "default_level": "FULL_HITL",
  "hitl_enabled": true,
  "description": "SOX and PCI-DSS compliant change management",
  "compliance_frameworks": ["SOX", "PCI_DSS", "GLBA"],
  "severity_overrides": {},
  "operation_overrides": {
    "database_migration": "DUAL_APPROVAL"
  },
  "timeout_hours": {
    "CRITICAL": 4,
    "HIGH": 12,
    "MEDIUM": 24,
    "LOW": 48
  },
  "approver_requirements": {
    "min_approvers": 1,
    "require_change_ticket": true,
    "allowed_roles": ["Change Manager", "Security Lead", "Release Manager"]
  }
}
```

### Healthcare Preset

```json
{
  "preset_id": "healthcare",
  "default_level": "FULL_HITL",
  "hitl_enabled": true,
  "description": "HIPAA-compliant workflow with PHI protections",
  "compliance_frameworks": ["HIPAA", "HITECH", "FDA_21_CFR_11"],
  "severity_overrides": {},
  "operation_overrides": {
    "phi_access_code": "DUAL_APPROVAL",
    "encryption_change": "DUAL_APPROVAL"
  },
  "timeout_hours": {
    "CRITICAL": 4,
    "HIGH": 8,
    "MEDIUM": 24,
    "LOW": 48
  },
  "approver_requirements": {
    "min_approvers": 1,
    "require_hipaa_training": true,
    "allowed_roles": ["Privacy Officer", "Security Officer", "Compliance Lead"]
  }
}
```

### Enterprise Standard Preset

```json
{
  "preset_id": "enterprise_standard",
  "default_level": "HITL_CRITICAL",
  "hitl_enabled": true,
  "description": "Balanced automation with critical oversight",
  "compliance_frameworks": ["SOC2", "ISO_27001"],
  "severity_overrides": {
    "LOW": "AUDIT_ONLY",
    "MEDIUM": "AUDIT_ONLY"
  },
  "operation_overrides": {},
  "timeout_hours": {
    "CRITICAL": 8,
    "HIGH": 24
  },
  "approver_requirements": {
    "min_approvers": 1,
    "allowed_roles": ["Security Engineer", "DevOps Lead", "Engineering Manager"]
  }
}
```

### Applying a Preset

```python
# Apply a preset to an organization
from aura.services import AutonomyPolicyService

policy_service = AutonomyPolicyService()

# Create policy from preset
policy = policy_service.create_policy_from_preset(
    organization_id="org-acme-defense",
    preset_id="defense_contractor",
    customizations={
        "timeout_hours": {"CRITICAL": 8}  # Override default
    }
)

# Policy is now active for the organization
```

---

## Guardrails: Operations That Always Require Approval

Regardless of autonomy level or policy preset, certain operations always require human approval. These guardrails cannot be bypassed, disabled, or overridden.

### Guardrail Operations

| Operation | Description | Why It Requires Approval |
|-----------|-------------|--------------------------|
| `production_deployment` | Deploying changes to production | Business-critical, high blast radius |
| `credential_modification` | Changing API keys, secrets, passwords | Security-critical, potential for lockout |
| `access_control_change` | Modifying IAM, RBAC, permissions | Authorization boundary changes |
| `database_migration` | Schema changes, data modifications | Data integrity risk |
| `infrastructure_change` | Cloud resource modifications | Cost and availability impact |

### Guardrail Enforcement

```python
# Guardrails are enforced at the service layer, not configurable
GUARDRAIL_OPERATIONS = frozenset([
    "production_deployment",
    "credential_modification",
    "access_control_change",
    "database_migration",
    "infrastructure_change"
])

def requires_hitl_approval(
    operation: str,
    severity: str,
    policy: AutonomyPolicy
) -> bool:
    """
    Determine if HITL approval is required.
    Guardrails are checked FIRST and cannot be bypassed.
    """
    # Guardrails always require approval - no exceptions
    if operation in GUARDRAIL_OPERATIONS:
        return True

    # Policy-based determination
    return policy.requires_approval(operation, severity)
```

### Why Guardrails Are Non-Negotiable

1. **Regulatory Requirements**: SOX, CMMC, and HIPAA all require human approval for production changes
2. **Liability**: Autonomous systems cannot bear legal responsibility for critical failures
3. **Reversibility**: Some operations are difficult or impossible to reverse
4. **Blast Radius**: Production and infrastructure changes affect many users
5. **Security Boundaries**: Credential and access changes define security perimeters

---

## Policy Override Hierarchy

When evaluating whether HITL approval is required, Aura follows a strict priority order.

### Override Priority

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     POLICY RESOLUTION HIERARCHY                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Priority 1 (Highest): GUARDRAILS                                       │
│  ─────────────────────────────────────                                  │
│  Always enforced, cannot be overridden                                  │
│  Examples: production_deployment, credential_modification               │
│                                                                         │
│                           │                                             │
│                           ▼                                             │
│                                                                         │
│  Priority 2: REPOSITORY OVERRIDES                                       │
│  ─────────────────────────────────                                      │
│  Per-repository configurations                                          │
│  Example: "legacy-monolith" repo requires FULL_HITL                     │
│                                                                         │
│                           │                                             │
│                           ▼                                             │
│                                                                         │
│  Priority 3: OPERATION OVERRIDES                                        │
│  ─────────────────────────────────                                      │
│  Per-operation type configurations                                      │
│  Example: "encryption_change" always requires approval                  │
│                                                                         │
│                           │                                             │
│                           ▼                                             │
│                                                                         │
│  Priority 4: SEVERITY OVERRIDES                                         │
│  ─────────────────────────────────                                      │
│  Per-severity level configurations                                      │
│  Example: CRITICAL requires approval, MEDIUM is auto                    │
│                                                                         │
│                           │                                             │
│                           ▼                                             │
│                                                                         │
│  Priority 5 (Lowest): DEFAULT LEVEL                                     │
│  ─────────────────────────────────                                      │
│  Policy's default autonomy level                                        │
│  Example: HITL_CRITICAL as base policy                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Override Example

```json
{
  "organization_id": "org-acme-corp",
  "default_level": "HITL_CRITICAL",
  "repository_overrides": {
    "payment-gateway": "FULL_HITL",
    "internal-docs": "FULL_AUTONOMOUS"
  },
  "operation_overrides": {
    "encryption_change": "FULL_HITL",
    "logging_config": "AUDIT_ONLY"
  },
  "severity_overrides": {
    "LOW": "FULL_AUTONOMOUS",
    "MEDIUM": "AUDIT_ONLY"
  }
}
```

**Resolution for "payment-gateway" repo, MEDIUM severity:**
1. Guardrails? No (not a guardrail operation)
2. Repository override? Yes -> FULL_HITL
3. Result: Requires human approval (repository override takes precedence)

**Resolution for "main-app" repo, LOW severity:**
1. Guardrails? No
2. Repository override? No (not specified)
3. Operation override? No (standard patch)
4. Severity override? Yes -> FULL_AUTONOMOUS
5. Result: Auto-approve

---

## The Approval Workflow

When HITL approval is required, Aura executes a structured workflow.

### Workflow Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: DETECTION & GENERATION                      │
│  ─────────────────────────────────────────────────────────────────────  │
│  [Reviewer Agent] Detects vulnerability                                 │
│  [Coder Agent] Generates security patch                                 │
│  Output: Patch code, confidence score                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: SANDBOX VALIDATION                          │
│  ─────────────────────────────────────────────────────────────────────  │
│  [Sandbox Orchestrator] Provisions isolated environment                 │
│  [Test Runner] Executes test suite                                      │
│  - Syntax validation                                                    │
│  - Unit tests                                                           │
│  - Security scans                                                       │
│  - Performance benchmarks                                               │
│  Output: Test results (pass/fail), metrics                              │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: APPROVAL REQUEST                            │
│  ─────────────────────────────────────────────────────────────────────  │
│  [HITL Service] Creates approval request                                │
│  [Notification Service] Alerts security team                            │
│  - Email via SES                                                        │
│  - Slack webhook (optional)                                             │
│  - Dashboard notification                                               │
│  Output: Approval ID, pending status                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: HUMAN REVIEW                                │
│  ─────────────────────────────────────────────────────────────────────  │
│  [Approval Dashboard] Reviewer examines:                                │
│  - Original vulnerable code                                             │
│  - AI-generated patch (diff view)                                       │
│  - Sandbox test results                                                 │
│  - Confidence score                                                     │
│  - Context and reasoning                                                │
│                                                                         │
│  DECISIONS:                                                             │
│  [APPROVE] ──▶ Proceed to deployment                                    │
│  [REJECT] ──▶ Patch discarded, logged                                   │
│  [REQUEST CHANGES] ──▶ Feedback to Coder Agent                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                    [APPROVED]         [REJECTED]
                          │                 │
                          ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 5: DEPLOYMENT / CLOSURE                        │
│  ─────────────────────────────────────────────────────────────────────  │
│  If APPROVED:                                                           │
│  - Deploy to production                                                 │
│  - Monitor for 24 hours                                                 │
│  - Record success metrics                                               │
│                                                                         │
│  If REJECTED:                                                           │
│  - Log rejection reason                                                 │
│  - Update AI feedback loop                                              │
│  - Cleanup sandbox                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Approval Request Contents

Reviewers receive comprehensive information for decision-making:

```
┌─────────────────────────────────────────────────────────────────────────┐
│              APPROVAL REQUEST: approval-2026-01-19-abc123               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  VULNERABILITY                                                          │
│  ─────────────                                                          │
│  Type:        SQL Injection                                             │
│  Severity:    CRITICAL                                                  │
│  File:        src/services/user_service.py                              │
│  Line:        47                                                        │
│  CVE:         CVE-2026-12345 (if applicable)                            │
│                                                                         │
│  ORIGINAL CODE                                                          │
│  ─────────────                                                          │
│  def get_user(user_id):                                                 │
│      query = f"SELECT * FROM users WHERE id = '{user_id}'"              │
│      return db.execute(query)  # Vulnerable to injection                │
│                                                                         │
│  AI-GENERATED PATCH                                                     │
│  ─────────────────                                                      │
│  def get_user(user_id: str) -> User:                                    │
│      # Parameterized query prevents SQL injection                       │
│      return db.query(User).filter(User.id == user_id).first()           │
│                                                                         │
│  AI CONFIDENCE: 0.94                                                    │
│  REASONING: Pattern matches 847 similar remediations with 99.2%         │
│             success rate. Using SQLAlchemy ORM for parameterization.    │
│                                                                         │
│  SANDBOX RESULTS                                                        │
│  ───────────────                                                        │
│  Unit Tests:      47/47 passed                                          │
│  Security Scan:   No new vulnerabilities                                │
│  Performance:     +2ms latency (acceptable)                             │
│  Test Report:     [View Full Report]                                    │
│                                                                         │
│  TIMEOUT: 24 hours (expires 2026-01-20 14:32:00 UTC)                    │
│                                                                         │
│  [APPROVE]    [REJECT]    [REQUEST CHANGES]                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Timeout and Escalation

Approval requests do not wait indefinitely. Aura implements a timeout and escalation system.

### Timeout Behavior

| Severity | Default Timeout | Warning At | Escalation Timeout |
|----------|-----------------|------------|-------------------|
| CRITICAL | 24 hours | 18 hours (75%) | 12 hours |
| HIGH | 24 hours | 18 hours (75%) | 12 hours |
| MEDIUM | 48 hours | 36 hours (75%) | N/A (expires) |
| LOW | 72 hours | 54 hours (75%) | N/A (expires) |

### Escalation Logic

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ESCALATION PROCESSING FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                    [Hourly EventBridge Trigger]
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │  Scan PENDING Requests   │
                    └──────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
    [Age < 75%]              [Age >= 75%]             [Age >= 100%]
         │                   warning=false                   │
         │                         │                         │
    No action              Send Warning             ┌────────┴────────┐
                           Notification             │                 │
                                                    ▼                 ▼
                                          [CRITICAL/HIGH]      [MEDIUM/LOW]
                                          escalations < 2              │
                                                    │                  │
                                                    ▼                  ▼
                                              ESCALATE            EXPIRE
                                           - New reviewer      - Mark expired
                                           - Reset timeout     - Re-queue
                                           - Notify backup     - Notify team
```

### Escalation Configuration

```json
{
  "escalation_config": {
    "timeout_hours": 24,
    "escalation_timeout_hours": 12,
    "warning_threshold_percent": 0.75,
    "max_escalations": 2,
    "backup_reviewers": [
      "security-lead@company.com",
      "ciso@company.com"
    ]
  }
}
```

---

## Audit Trail and Compliance

Every HITL decision is logged for compliance and auditing.

### Logged Events

| Event | Data Captured | Retention |
|-------|---------------|-----------|
| Approval Request Created | Vulnerability, patch, sandbox results, timestamp | 7 years |
| Notification Sent | Recipient, channel, timestamp, delivery status | 7 years |
| Human Decision | Approver identity, decision, comments, timestamp | 7 years |
| Escalation | Original reviewer, backup reviewer, escalation reason | 7 years |
| Deployment | Patch applied, environment, deployment timestamp | 7 years |
| Timeout/Expiration | Original request, timeout duration, final status | 7 years |

### Audit Log Format

```json
{
  "event_id": "evt-2026-01-19-xyz789",
  "event_type": "APPROVAL_DECISION",
  "timestamp": "2026-01-19T15:45:00Z",
  "approval_id": "approval-2026-01-19-abc123",
  "organization_id": "org-acme-corp",
  "actor": {
    "email": "security.lead@acme.com",
    "role": "Security Engineer",
    "ip_address": "10.0.1.50",
    "user_agent": "Mozilla/5.0..."
  },
  "decision": "APPROVED",
  "comments": "Verified fix is correct. Standard parameterization pattern.",
  "vulnerability": {
    "id": "vuln-12345",
    "type": "SQL_INJECTION",
    "severity": "CRITICAL"
  },
  "policy_context": {
    "autonomy_level": "HITL_CRITICAL",
    "preset": "financial_services",
    "override_applied": null
  },
  "compliance_tags": ["SOX", "PCI_DSS"],
  "immutable_hash": "sha256:a1b2c3d4e5f6..."
}
```

### Compliance Framework Mapping

| Framework | HITL Requirement | Aura Compliance |
|-----------|------------------|-----------------|
| **SOX Section 404** | Change management approval | Full audit trail |
| **CMMC Level 3** | Access control (AC.2.016) | Approver role enforcement |
| **HIPAA** | Audit controls (164.312) | 7-year retention |
| **PCI-DSS 4.0** | Change control (6.5.3) | Separation of duties |
| **NIST 800-53** | CM-3 Configuration Change | Documented approvals |
| **FedRAMP** | CM-3, CM-4 Impact Analysis | Sandbox validation |

---

## Configuring HITL Policies

### Via API

```python
from aura.services import AutonomyPolicyService
from aura.models import AutonomyLevel

policy_service = AutonomyPolicyService()

# Create a new policy
policy = policy_service.create_policy(
    organization_id="org-acme-corp",
    default_level=AutonomyLevel.HITL_CRITICAL,
    hitl_enabled=True,
    severity_overrides={
        "LOW": AutonomyLevel.FULL_AUTONOMOUS,
        "MEDIUM": AutonomyLevel.AUDIT_ONLY
    },
    repository_overrides={
        "payment-gateway": AutonomyLevel.FULL_HITL
    }
)

# Check if HITL is required for a specific operation
requires_approval = policy_service.requires_hitl_approval(
    organization_id="org-acme-corp",
    operation="vulnerability_remediation",
    severity="HIGH",
    repository="main-app"
)
# Returns: True (HITL_CRITICAL requires approval for HIGH severity)
```

### Via Dashboard

The Aura Dashboard provides a visual interface for configuring HITL policies:

1. Navigate to **Settings** > **Autonomy Policies**
2. Select your organization
3. Choose a preset or configure custom levels
4. Add repository and severity overrides as needed
5. Configure approver roles and escalation paths
6. Save and activate the policy

---

## Key Takeaways

> **HITL is configurable, not fixed.** Organizations choose their autonomy level based on compliance requirements and risk tolerance.

> **Guardrails are absolute.** Production deployments, credential changes, and infrastructure modifications always require human approval, regardless of policy settings.

> **Presets simplify compliance.** Seven industry-specific presets cover common compliance frameworks (CMMC, SOX, HIPAA, etc.) out of the box.

> **Every decision is audited.** Complete audit trails support SOX, CMMC, HIPAA, and other compliance frameworks with 7-year retention.

> **Escalation prevents bottlenecks.** Timeout and escalation mechanisms ensure critical vulnerabilities are not blocked by unavailable reviewers.

---

## Related Concepts

- [Autonomous Security Intelligence](./autonomous-security-intelligence.md) - AI decision-making that triggers HITL
- [Multi-Agent System](./multi-agent-system.md) - Agents that generate patches for review
- [Sandbox Security](./sandbox-security.md) - Validation that occurs before HITL review
- [Hybrid GraphRAG](./hybrid-graphrag.md) - Context provided to reviewers

---

## Technical References

- ADR-032: Configurable Autonomy Framework
- ADR-005: HITL Sandbox Architecture
- ADR-016: HITL Auto-Escalation Strategy
- ADR-021: Guardrails Cognitive Architecture
- `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Detailed technical specification

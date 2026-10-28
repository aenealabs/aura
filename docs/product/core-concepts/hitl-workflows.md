# Human-in-the-Loop Workflows

**Version:** 1.0
**Last Updated:** October 2026

---

## Overview

Human-in-the-Loop (HITL) Workflows form the governance layer of Project Aura, ensuring that autonomous AI operations are subject to appropriate human oversight. HITL is not simply a brake on automation; it is a configurable policy framework that allows organizations to balance automation speed with compliance requirements.

This document explains how HITL works, the four configurable autonomy levels, industry-specific policy presets, and the guardrails that always require human approval regardless of policy settings.

> **Implementation status (October 2026).** What runs today:
>
> - The production job server (`src/agents/orchestrator_server.py`) runs `execute_request_with_hitl` for every job and **always** creates a manual approval request for a patch that passes review, validation, and the sandbox step. It does not consult an autonomy policy, so no patch is auto-approved.
> - Approval requests are stored in DynamoDB (`aura-approval-requests-{env}`) when `AWS_REGION` is set, otherwise in memory with seeded demo data. The approvals API (`/api/v1/approvals`) supports list, detail, stats, approve, reject, and cancel, with role checks and separation of duties.
> - Approving a request records the decision and notifies; it does **not** deploy or open a pull request. Deployment after approval is planned.
> - Autonomy policies and presets are implemented in `AutonomyPolicyService`, but its REST router (`src/api/autonomy_endpoints.py`) is not mounted in `src/api/main.py`, and `HITLApprovalService.create_or_auto_approve` has no production caller. Policy-driven auto-approval (the per-level behavior described below) is planned.

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

**Human approval required for all operations.** This is the behavior every job gets today, regardless of the configured policy.

| Aspect | Behavior |
|--------|----------|
| **Approval Required** | All vulnerability remediations |
| **Automatic Actions** | Detection, patch generation, sandbox testing |
| **Human Actions** | Review and approve/reject all patches |
| **Timeout** | 24 hours (configurable) |
| **Use Case** | Defense contractors, healthcare, government |

```python
# FULL_HITL behavior (illustrative; deployment after approval is planned)
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

### Level 2: CRITICAL_HITL (Critical HITL)

**Human approval required for HIGH and CRITICAL severity only.**

| Aspect | Behavior |
|--------|----------|
| **Approval Required** | HIGH and CRITICAL severity vulnerabilities |
| **Automatic Actions** | LOW/MEDIUM severity patches auto-deploy after sandbox |
| **Human Actions** | Review HIGH/CRITICAL patches only |
| **Timeout** | 24 hours (single default for all severities) |
| **Use Case** | Financial services, enterprise standard |

```python
# CRITICAL_HITL behavior (planned; not yet applied by the job server)
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
# AUDIT_ONLY behavior (planned; not yet applied by the job server)
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
| CRITICAL_HITL | Human | Human | Auto | Auto | Human |
| AUDIT_ONLY | Auto (logged) | Auto (logged) | Auto (logged) | Auto (logged) | Human |
| FULL_AUTONOMOUS | Auto | Auto | Auto | Auto | Human |

---

## Industry Policy Presets

Aura includes seven pre-built policy presets (`AutonomyPolicy.from_preset`, `src/services/autonomy_policy_service.py:321`). Organizations can use these presets as-is or customize them.

### Preset Overview

| Preset | Default Level | Severity / Operation Overrides | HITL Enabled | Target Industry |
|--------|---------------|-------------------------------|--------------|-----------------|
| `defense_contractor` | FULL_HITL | LOW: CRITICAL_HITL | Yes | Defense, Aerospace (CMMC) |
| `financial_services` | FULL_HITL | LOW: AUDIT_ONLY | Yes | Banking, Insurance (SOX, PCI-DSS) |
| `healthcare` | FULL_HITL | LOW: AUDIT_ONLY | Yes | Hospitals, Pharma (HIPAA) |
| `fintech_startup` | CRITICAL_HITL | LOW, MEDIUM: AUDIT_ONLY | Yes | Growth Companies |
| `enterprise_standard` | CRITICAL_HITL | LOW: FULL_AUTONOMOUS, MEDIUM: AUDIT_ONLY | Yes | General enterprise |
| `internal_tools` | FULL_AUTONOMOUS | `credential_modification`: FULL_HITL, `production_deployment`: CRITICAL_HITL | Yes | Internal Dev Teams |
| `fully_autonomous` | FULL_AUTONOMOUS | None | No (guardrails still apply) | Commercial dev/test |

Every preset also carries the default guardrail list (see [Guardrails](#guardrails-operations-that-always-require-approval)).

> **Not yet implemented.** Per-preset approval timeouts, approver requirements (minimum approvers, required roles, clearance or training flags), and compliance-framework tags are not part of `AutonomyPolicy`. All approval requests use a single timeout (24 hours by default, `HITLApprovalService.DEFAULT_TIMEOUT_HOURS`). The preset JSON below shows the fields the policy actually stores.

### Defense Contractor Preset

```json
{
  "preset_name": "defense_contractor",
  "name": "Defense Contractor Policy",
  "description": "Maximum oversight for CMMC Level 3+ compliance",
  "hitl_enabled": true,
  "default_level": "full_hitl",
  "severity_overrides": {"LOW": "critical_hitl"},
  "operation_overrides": {},
  "repository_overrides": {},
  "guardrails": [
    "production_deployment",
    "credential_modification",
    "access_control_change",
    "database_migration",
    "infrastructure_change"
  ]
}
```

### Financial Services Preset

```json
{
  "preset_name": "financial_services",
  "name": "Financial Services Policy",
  "description": "High oversight for SOX/PCI-DSS compliance",
  "hitl_enabled": true,
  "default_level": "full_hitl",
  "severity_overrides": {"LOW": "audit_only"},
  "operation_overrides": {}
}
```

### Healthcare Preset

```json
{
  "preset_name": "healthcare",
  "name": "Healthcare Policy",
  "description": "High oversight for HIPAA compliance",
  "hitl_enabled": true,
  "default_level": "full_hitl",
  "severity_overrides": {"LOW": "audit_only"},
  "operation_overrides": {}
}
```

### Enterprise Standard Preset

```json
{
  "preset_name": "enterprise_standard",
  "name": "Enterprise Standard Policy",
  "description": "Standard enterprise autonomy with oversight for critical",
  "hitl_enabled": true,
  "default_level": "critical_hitl",
  "severity_overrides": {
    "LOW": "full_autonomous",
    "MEDIUM": "audit_only"
  },
  "operation_overrides": {}
}
```

### Applying a Preset

```python
# Apply a preset to an organization
from src.services.autonomy_policy_service import create_autonomy_policy_service

policy_service = create_autonomy_policy_service()

# Create policy from preset
policy = policy_service.create_policy_from_preset(
    organization_id="org-acme-defense",
    preset_name="defense_contractor",
    created_by="admin@example.com",
)

# Policy is now active for the organization
```

---

## Guardrails: Operations That Always Require Approval

Regardless of autonomy level or policy preset, certain operations always require human approval when a policy is evaluated. Two of them, `production_deployment` and `credential_modification`, are hard-coded in `AutonomyPolicy.IMMUTABLE_GUARDRAILS` and cannot be removed by any policy. The other three are in every policy's default `guardrails` list; a custom policy that supplies its own list can omit them.

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
# src/services/autonomy_policy_service.py (abridged)
class AutonomyPolicy:
    IMMUTABLE_GUARDRAILS = frozenset({
        "credential_modification",
        "production_deployment",
    })

    def get_autonomy_level(self, severity, operation, repository=""):
        if operation in self.IMMUTABLE_GUARDRAILS:
            return AutonomyLevel.FULL_HITL
        if operation in self.guardrails:  # default list of five
            return AutonomyLevel.FULL_HITL
        ...
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
│  Priority 2: OPERATION OVERRIDES                                        │
│  ─────────────────────────────────                                      │
│  Per-operation type configurations                                      │
│  Example: "encryption_change" always requires approval                  │
│                                                                         │
│                           │                                             │
│                           ▼                                             │
│                                                                         │
│  Priority 3: REPOSITORY OVERRIDES                                       │
│  ─────────────────────────────────                                      │
│  Per-repository configurations                                          │
│  Example: "legacy-monolith" repo requires FULL_HITL                     │
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
│  Example: CRITICAL_HITL as base policy                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Override Example

```json
{
  "organization_id": "org-acme-corp",
  "default_level": "CRITICAL_HITL",
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

**Resolution for "payment-gateway" repo, MEDIUM severity, standard patch:**

1. Guardrails? No (not a guardrail operation)
2. Operation override? No (standard patch)
3. Repository override? Yes -> FULL_HITL
4. Result: Requires human approval (repository override takes precedence over severity)

**Resolution for "main-app" repo, LOW severity:**

1. Guardrails? No
2. Operation override? No (standard patch)
3. Repository override? No (not specified)
4. Severity override? Yes -> FULL_AUTONOMOUS
5. Result: Auto-approve

---

## The Approval Workflow

When HITL approval is required, Aura executes a structured workflow. The stages below show the target design; current status per stage:

| Stage | Status today |
|-------|--------------|
| 1. Detection and generation | Implemented as prompt-driven generation: the job's prompt, not a scanner finding, selects the target, and the code comes from the configured sample project. |
| 2. Sandbox validation | Partial. Skipped unless `SANDBOX_ENABLED=true`; when enabled, the ECS task does not yet receive the patched code. The per-category test list below is planned. |
| 3. Approval request | Implemented. Notifications go by SES email (and Slack or Teams when a webhook is configured). |
| 4. Human review | Implemented: approve, reject, cancel. "Request changes" is planned; the dashboard button calls `/request-changes`, which the API does not serve. |
| 5. Deployment / closure | Planned. Approval records the decision only. |

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
│  [REQUEST CHANGES] ──▶ Feedback to Coder Agent (planned)                │
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

The mock-up below shows the target layout. A request created by the job server today carries the patch ID, vulnerability ID (the job's task ID unless supplied), severity (mapped from the reviewer's severity), a line-by-line diff against the sample project file, the sandbox result block (often `SKIPPED`, marked as not runtime-tested), the decision confidence and its source, and the original prompt. File/line, CVE, reasoning text, and per-category test results are not populated yet.

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

All severities share one timeout (`DEFAULT_TIMEOUT_HOURS = 24`, or the `TimeoutHours` parameter of `deploy/cloudformation/hitl-scheduler.yaml`). Severity changes only what happens at expiry:

| Severity | Default Timeout | Warning At | On Expiry |
|----------|-----------------|------------|-----------|
| CRITICAL | 24 hours | 18 hours (75%) | Escalate to next backup reviewer (up to 2 times), then expire |
| HIGH | 24 hours | 18 hours (75%) | Escalate to next backup reviewer (up to 2 times), then expire |
| MEDIUM | 24 hours | 18 hours (75%) | Expire |
| LOW | 24 hours | 18 hours (75%) | Expire |

Each escalation extends the deadline by `escalation_timeout_hours`, which defaults to the main timeout.

### Escalation Logic

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ESCALATION PROCESSING FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                    [EventBridge schedule, default rate(3 hours)]
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
                                           - Reset timeout     - Notify team
                                           - Notify backup
```

### Escalation Configuration

```json
{
  "escalation_config": {
    "timeout_hours": 24,
    "escalation_timeout_hours": 24,
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

> **Retention.** Approval records carry a 90-day DynamoDB TTL (`hitl_approval_service.py:295`). The 7-year retention shown below is a compliance target that is not yet configured. The audit-log example shows the target format. `HITLApprovalService.get_audit_log` builds entries from decided approval records and returns the approval ID, patch ID, vulnerability ID, status, severity, reviewer, review time, decision reason, and creation time; it does not record IP address, user agent, policy context, compliance tags, or an immutable hash.

### Logged Events

| Event | Data Captured | Retention |
|-------|---------------|-----------|
| Approval Request Created | Vulnerability, patch, sandbox results, timestamp | 90 days (7-year target planned) |
| Notification Sent | Recipient, channel, timestamp, delivery status | 90 days (7-year target planned) |
| Human Decision | Approver identity, decision, comments, timestamp | 90 days (7-year target planned) |
| Escalation | Original reviewer, backup reviewer, escalation reason | 90 days (7-year target planned) |
| Deployment | Planned (no deployment step yet) | Planned |
| Timeout/Expiration | Original request, timeout duration, final status | 90 days (7-year target planned) |

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
    "autonomy_level": "CRITICAL_HITL",
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
| **HIPAA** | Audit controls (164.312) | Audit log (7-year retention planned) |
| **PCI-DSS 4.0** | Change control (6.5.3) | Separation of duties |
| **NIST 800-53** | CM-3 Configuration Change | Documented approvals |
| **FedRAMP** | CM-3, CM-4 Impact Analysis | Sandbox validation |

---

## Configuring HITL Policies

### Via the Python Service

The REST router for policies (`src/api/autonomy_endpoints.py`, prefix `/api/v1/autonomy`) is not mounted in the API yet, so policies are managed through the service directly:

```python
from src.services.autonomy_policy_service import (
    AutonomyLevel,
    create_autonomy_policy_service,
)

policy_service = create_autonomy_policy_service()

# Create a new policy
policy = policy_service.create_policy(
    organization_id="org-acme-corp",
    default_level=AutonomyLevel.CRITICAL_HITL,
    hitl_enabled=True,
)

# Add overrides
policy_service.add_override(
    policy.policy_id, "severity", "LOW", AutonomyLevel.FULL_AUTONOMOUS
)
policy_service.add_override(
    policy.policy_id, "repository", "payment-gateway", AutonomyLevel.FULL_HITL
)

# Check if HITL is required for a specific operation
requires_approval = policy_service.requires_hitl_approval(
    policy_id=policy.policy_id,
    severity="HIGH",
    operation="security_patch",
    repository="main-app",
)
# Returns: True (CRITICAL_HITL requires approval for HIGH severity)
```

The service stores policies in memory unless DynamoDB mode is configured.

### Via Dashboard

The Aura Dashboard includes an **Autonomy Policies** tab in Settings. Because the autonomy API is not mounted yet, the tab cannot load or save policies and falls back to a default policy; the steps below describe the intended flow:

1. Navigate to **Settings** > **Autonomy Policies**
2. Select your organization
3. Choose a preset or configure custom levels
4. Add repository and severity overrides as needed
5. Configure approver roles and escalation paths
6. Save and activate the policy

---

## Key Takeaways

> **HITL is designed to be configurable.** Policies and presets exist in the policy service; applying them to the remediation pipeline is planned. Today every patch goes to a human.

> **Guardrails are absolute in policy evaluation.** Production deployments and credential changes are hard-coded to require approval; three more operations are in every default policy.

> **Presets simplify compliance.** Seven industry-specific presets cover common compliance frameworks (CMMC, SOX, HIPAA, etc.) out of the box.

> **Every decision is audited.** Approval decisions are written to the audit log (90-day retention today; 7-year retention planned).

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

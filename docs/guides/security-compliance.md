# Security and Compliance Guide

This guide explains how Aura Platform helps you meet security requirements and compliance obligations through configurable controls, audit logging, and approval workflows.

---

## Security Architecture Overview

Aura implements a defense-in-depth approach with multiple security layers:

```
                    +------------------------------------------+
                    |          External Boundary               |
                    |  WAF | Rate Limiting | Authentication    |
                    +---------------------|--------------------+
                                          |
                    +---------------------|--------------------+
                    |           API Layer                      |
                    |  Input Validation | Injection Detection  |
                    +---------------------|--------------------+
                                          |
                    +---------------------|--------------------+
                    |          Agent Layer                     |
                    |  A2AS Security | Guardrails | HITL       |
                    +---------------------|--------------------+
                                          |
                    +---------------------|--------------------+
                    |         Data Layer                       |
                    |  Encryption | Audit Logs | Isolation     |
                    +------------------------------------------+
```

---

## Human-in-the-Loop (HITL) Workflows

HITL ensures that humans maintain control over critical operations.

### Understanding HITL

HITL is a workflow pattern where AI-generated recommendations require human approval before execution. This is essential for:

- Maintaining compliance with security frameworks
- Preventing unauthorized changes to production systems
- Providing audit trails for regulatory requirements

### Configurable Autonomy Levels

Your organization can choose from four autonomy levels:

| Level | HITL Required | Best For |
|-------|---------------|----------|
| **Full HITL** | All operations | Defense, healthcare, financial services |
| **Critical HITL** | HIGH/CRITICAL severity only | Enterprise standard |
| **Audit Only** | None (logged only) | Internal tools |
| **Full Autonomous** | None | Development/test environments |

### Guardrails (Always Require Approval)

Regardless of your autonomy level, these operations **always** require human approval:

| Operation | Why It Matters |
|-----------|----------------|
| **Production Deployment** | Protects live systems from unverified changes |
| **Credential Modification** | API keys, secrets, and passwords |
| **Access Control Changes** | IAM policies, RBAC, permissions |
| **Database Migration** | Schema changes, data migrations |
| **Infrastructure Changes** | Cloud resource modifications |

### Approval Workflow

```
Agent Generates Recommendation
            |
            v
    Sandbox Testing
            |
            v
    +-------+-------+
    |               |
    v               v
Auto-Approve    Human Review
(Low Severity)  (High Severity)
    |               |
    v               v
    +-------+-------+
            |
            v
    Final Approval
            |
            v
    Deployment
```

### Configuring HITL Settings

Navigate to **Settings > HITL Settings** to configure:

| Setting | Description | Default |
|---------|-------------|---------|
| Require approval for patches | All patches need human approval | Yes |
| Require approval for deployments | All deployments need approval | Yes |
| Auto-approve minor patches | Low-severity auto-approved after testing | No |
| Approval timeout | Hours before request expires | 24 |
| Minimum approvers | Required approvals for critical | 1 |

---

## Compliance Frameworks

Aura supports multiple compliance frameworks with configurable profiles.

### Supported Frameworks

| Framework | Status | Key Requirements |
|-----------|--------|------------------|
| **CMMC Level 2** | Supported | 90-day log retention, access controls |
| **CMMC Level 3** | Supported | 365-day logs, air-gap deployment |
| **SOX** | Supported | Audit trails, change management |
| **NIST 800-53** | Supported | Security controls, monitoring |
| **FedRAMP High** | Ready | Full isolation, GovCloud deployment |
| **HIPAA** | Supported | PHI protection, audit logs |
| **PCI-DSS** | Supported | Cardholder data protection |

### Compliance Profiles

Select a pre-configured compliance profile to automatically apply appropriate settings:

| Profile | Log Retention | KMS Mode | Integration Mode |
|---------|---------------|----------|------------------|
| **Commercial** | 30 days | AWS Managed | Enterprise |
| **CMMC Level 1** | 30 days | AWS Managed | Hybrid |
| **CMMC Level 2** | 90 days | Customer Managed | Hybrid |
| **GovCloud** | 365 days | Customer Managed | Defense |

### Applying a Compliance Profile

1. Navigate to **Settings > Compliance**
2. Select your target compliance profile
3. Review the settings that will be applied
4. Click **Apply Profile**

The system will:
- Update log retention policies
- Configure encryption settings
- Adjust security controls
- Trigger any necessary infrastructure updates

---

## Security Settings

### Log Retention

Audit logs are essential for compliance and incident investigation.

| Retention Period | Compliance Level |
|------------------|------------------|
| 30 days | Below CMMC minimum |
| 60 days | Below CMMC minimum |
| 90 days | CMMC Level 2 compliant |
| 180 days | Enhanced compliance |
| 365 days | GovCloud/FedRAMP recommended |

**How to Configure**:
1. Go to **Settings > Security**
2. Select your desired retention period
3. The system displays compliance status for your selection

### Encryption

All data is encrypted at rest and in transit:

| Data Type | Encryption | Key Management |
|-----------|------------|----------------|
| Database (Neptune) | AES-256 | KMS Customer Managed |
| Vector Store (OpenSearch) | AES-256 | KMS |
| Object Storage (S3) | SSE-KMS | Customer Managed |
| API Traffic | TLS 1.3 | ACM Certificates |

### Sandbox Isolation

Patches are tested in isolated sandbox environments:

| Isolation Level | Description | Use Case |
|-----------------|-------------|----------|
| **Container** | Isolated container | Quick tests |
| **VPC** | Dedicated VPC | Standard testing |
| **Full** | Complete isolation | Compliance testing |

---

## Security Services

Aura includes five integrated security services:

### Input Validation Service

Protects against injection attacks:

| Threat | Detection Method |
|--------|------------------|
| SQL Injection | Pattern matching, parameterization check |
| XSS | HTML/script tag detection |
| Command Injection | Shell metacharacter detection |
| SSRF | URL validation, allowlist check |
| Prompt Injection | LLM-specific pattern detection |

### Secrets Detection Service

Scans for exposed credentials:

- API keys (AWS, Azure, GCP, GitHub, etc.)
- Database credentials
- Private keys (RSA, SSH, PGP)
- OAuth tokens
- Entropy-based unknown secret detection

### Security Audit Service

Logs all security-relevant events:

```
Event Types:
- Authentication attempts
- Authorization decisions
- Configuration changes
- Agent operations
- HITL approvals/rejections
```

### Security Alerts Service

Priority-based alerting:

| Priority | Response Time | Example |
|----------|---------------|---------|
| P1 - Critical | Immediate | Active breach detected |
| P2 - High | < 1 hour | Credential exposure |
| P3 - Medium | < 4 hours | Suspicious pattern |
| P4 - Low | < 24 hours | Policy violation |
| P5 - Info | Best effort | Informational |

### A2AS Security Framework

Agent-to-Agent Security with four-layer defense:

1. **Injection Filter**: Blocks malicious inputs
2. **Command Verifier**: HMAC-signed command validation
3. **Sandbox Enforcer**: Runtime restrictions
4. **Behavioral Analysis**: Anomaly detection

---

## Integration Mode Security

### Defense Mode

Maximum security posture for regulated environments:

| Feature | Status |
|---------|--------|
| External network calls | Blocked |
| MCP Gateway | Disabled |
| External tools | Unavailable |
| Air-gap deployment | Supported |

**Compliance**: CMMC Level 3, NIST 800-53, FedRAMP High

### Enterprise Mode

Balanced security with productivity features:

| Feature | Status |
|---------|--------|
| External integrations | Enabled |
| MCP Gateway | Available |
| Slack/Jira/GitHub | Supported |
| Budget controls | Configurable |

**Compliance**: SOX, CMMC Level 2

### Hybrid Mode

Selective integrations with approval controls:

| Feature | Status |
|---------|--------|
| Tool allowlist | Configurable |
| Per-tool HITL | Available |
| Budget limits | Per-integration |
| Audit trail | Comprehensive |

---

## Audit and Reporting

### Audit Log Contents

Every action is logged with:

| Field | Description |
|-------|-------------|
| Timestamp | When the action occurred |
| User | Who performed the action |
| Action | What was done |
| Resource | What was affected |
| Result | Success/failure |
| Context | Additional details |

### Generating Reports

1. Navigate to the **Chat Assistant**
2. Request a report:
   - "Generate a security report for last week"
   - "Show HITL approval statistics for this month"
   - "List all credential-related alerts"

### Compliance Dashboards

The Security Alerts panel shows:

- Active alerts by priority
- Alert trends over time
- Resolution statistics
- Compliance posture summary

---

## Best Practices

### For Defense/Government Users

1. **Enable Defense Mode** - No external dependencies
2. **Use Full HITL** - All operations require approval
3. **Set 365-day retention** - FedRAMP requirement
4. **Enable full sandbox isolation** - Maximum protection
5. **Use customer-managed KMS keys** - Control your encryption

### For Commercial Enterprises

1. **Use Enterprise or Hybrid Mode** - Balance security and productivity
2. **Enable Critical HITL** - Human review for high-severity only
3. **Set 90-day retention** - CMMC Level 2 compliant
4. **Configure budget controls** - Limit MCP costs
5. **Enable notifications** - Stay informed of approvals

### For Development Teams

1. **Consider Audit Only mode** - Monitor without blocking
2. **Use sandbox testing** - Validate before deployment
3. **Enable auto-approve for minor patches** - Speed up low-risk changes
4. **Configure tool allowlists** - Control external access

---

## Incident Response

### When a Security Alert Fires

1. **Acknowledge** the alert in the Security Alerts panel
2. **Review** the details and affected resources
3. **Assign** to the appropriate team member
4. **Investigate** using audit logs and agent history
5. **Resolve** with documented remediation steps

### Escalation Path

```
P1/P2 Alert --> Security Team --> Incident Commander --> Executive (if needed)
P3/P4 Alert --> Security Team --> Resolution
P5 Alert --> Regular Review Queue
```

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Configuration Guide](./configuration.md) | Detailed settings reference |
| [Agent System Guide](./agent-system.md) | How agents enforce security |
| [Troubleshooting Guide](./troubleshooting.md) | Security issue resolution |

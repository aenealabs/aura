# Audit Logging

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

Project Aura provides comprehensive audit logging to support compliance requirements, security monitoring, and incident investigation. All security-relevant events are captured with detailed context, enabling organizations to maintain complete visibility into platform activity.

This document describes audit event types, log retention policies, integration options, and compliance reporting capabilities.

---

## Audit Event Categories

### Event Type Hierarchy

Project Aura captures audit events across five primary categories:

```
AUDIT EVENTS
|
+-- USER ACTIONS
|   +-- Authentication (login, logout, MFA)
|   +-- Authorization (role changes, permission grants)
|   +-- Data Access (repository access, vulnerability views)
|   +-- Configuration (settings changes, policy updates)
|
+-- AGENT ACTIONS
|   +-- Detection (vulnerability identified)
|   +-- Analysis (code analysis, context retrieval)
|   +-- Remediation (patch generation, validation)
|   +-- Decision (confidence scores, recommendations)
|
+-- APPROVAL WORKFLOW
|   +-- Request (patch submitted for review)
|   +-- Review (reviewer assignment, comments)
|   +-- Decision (approve, reject, defer)
|   +-- Deployment (patch applied, rollback)
|
+-- SYSTEM EVENTS
|   +-- Infrastructure (scaling, failover)
|   +-- Security (threat detection, alerts)
|   +-- Integration (webhook delivery, API calls)
|   +-- Maintenance (backup, rotation)
|
+-- COMPLIANCE EVENTS
|   +-- Policy (policy evaluation, violations)
|   +-- Report (report generation, export)
|   +-- Certification (evidence collection)
```

---

## Event Types Reference

### User Action Events

| Event Type | Description | Logged Attributes |
|------------|-------------|-------------------|
| `user.login` | User authentication | email, ip, user_agent, mfa_used |
| `user.logout` | User session end | email, session_duration |
| `user.login_failed` | Failed authentication | email, ip, failure_reason |
| `user.mfa_enrolled` | MFA setup completed | email, mfa_method |
| `user.password_changed` | Password update | email, initiated_by |
| `user.role_changed` | Role assignment | email, old_role, new_role, changed_by |
| `user.api_key_created` | API key generated | email, key_name, permissions |
| `user.api_key_revoked` | API key deleted | email, key_name, reason |

### Agent Action Events

| Event Type | Description | Logged Attributes |
|------------|-------------|-------------------|
| `agent.vulnerability_detected` | Vulnerability identified | vuln_id, severity, cve, repository |
| `agent.context_retrieved` | Code context gathered | vuln_id, context_tokens, retrieval_method |
| `agent.patch_generated` | Patch created | patch_id, vuln_id, confidence_score |
| `agent.patch_validated` | Sandbox validation | patch_id, test_results, validation_time |
| `agent.patch_rejected` | Patch failed validation | patch_id, failure_reason |
| `agent.decision_made` | Agent recommendation | vuln_id, decision, reasoning |
| `agent.llm_invocation` | LLM API call | model, tokens_in, tokens_out, latency |
| `agent.error` | Agent error occurred | agent_type, error_code, error_message |

### Approval Workflow Events

| Event Type | Description | Logged Attributes |
|------------|-------------|-------------------|
| `approval.requested` | Patch submitted for review | patch_id, severity, requester |
| `approval.assigned` | Reviewer assigned | patch_id, reviewer_email |
| `approval.comment` | Review comment added | patch_id, commenter, comment_text |
| `approval.approved` | Patch approved | patch_id, approver, approval_notes |
| `approval.rejected` | Patch rejected | patch_id, rejecter, rejection_reason |
| `approval.escalated` | Review escalated | patch_id, escalation_reason, escalated_to |
| `approval.deployed` | Patch deployed | patch_id, deployer, target_branch |
| `approval.rollback` | Patch rolled back | patch_id, rollback_reason |
| `approval.sla_warning` | SLA threshold approaching | patch_id, sla_hours_remaining |
| `approval.sla_breach` | SLA exceeded | patch_id, sla_hours_overdue |

### System Events

| Event Type | Description | Logged Attributes |
|------------|-------------|-------------------|
| `system.scaling` | Auto-scaling event | service, old_count, new_count |
| `system.health_check` | Service health status | service, status, latency |
| `system.backup_completed` | Backup successful | backup_type, size_bytes, duration |
| `system.backup_failed` | Backup unsuccessful | backup_type, error_message |
| `system.secret_rotated` | Secret rotation | secret_name, rotation_type |
| `system.certificate_renewed` | TLS certificate renewal | domain, expiry_date |
| `security.threat_detected` | GuardDuty finding | finding_id, severity, threat_type |
| `security.alert_triggered` | CloudWatch alarm | alarm_name, metric, threshold |
| `security.config_drift` | Configuration drift | resource_type, resource_id, drift_details |

### Compliance Events

| Event Type | Description | Logged Attributes |
|------------|-------------|-------------------|
| `compliance.policy_evaluated` | Policy check executed | policy_name, result, details |
| `compliance.violation_detected` | Policy violation | policy_name, violation_details |
| `compliance.report_generated` | Compliance report created | report_type, period, format |
| `compliance.evidence_collected` | Audit evidence gathered | evidence_type, control_id |
| `compliance.audit_started` | External audit begins | audit_type, auditor |
| `compliance.audit_completed` | External audit ends | audit_type, findings_count |

---

## Log Format

### Standard Log Structure

All audit events follow a consistent JSON structure:

```json
{
  "timestamp": "2026-01-23T14:30:00.000Z",
  "event_id": "evt-550e8400-e29b-41d4-a716-446655440000",
  "event_type": "approval.approved",
  "event_version": "1.0",
  "source": "aura-platform",
  "severity": "INFO",
  "actor": {
    "type": "user",
    "user_id": "usr-12345",
    "email": "security@customer.com",
    "ip_address": "203.0.113.50",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "session_id": "sess-abc123"
  },
  "resource": {
    "type": "patch",
    "id": "patch-67890",
    "attributes": {
      "vulnerability_id": "vuln-12345",
      "repository": "acme/web-app",
      "severity": "HIGH"
    }
  },
  "action": {
    "type": "approve",
    "result": "success",
    "details": {
      "approval_notes": "Reviewed and approved for production",
      "deploy_requested": true
    }
  },
  "context": {
    "organization_id": "org-xyz789",
    "request_id": "req-def456",
    "trace_id": "trace-ghi789",
    "environment": "production"
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | Event occurrence time (UTC) |
| `event_id` | UUID | Unique event identifier |
| `event_type` | String | Event category and action |
| `event_version` | String | Schema version for parsing |
| `source` | String | Originating service |
| `severity` | Enum | INFO, WARN, ERROR, CRITICAL |
| `actor` | Object | Who performed the action |
| `resource` | Object | What was acted upon |
| `action` | Object | What was done and result |
| `context` | Object | Additional context for correlation |

---

## Log Retention

### Retention Policies

| Log Category | Production | Development | Compliance Override |
|--------------|------------|-------------|---------------------|
| User Authentication | 365 days | 90 days | 7 years (SOX) |
| Agent Actions | 365 days | 90 days | 7 years (SOX) |
| Approval Workflow | 365 days | 90 days | 7 years (SOX) |
| System Events | 90 days | 30 days | 1 year |
| Security Events | 365 days | 90 days | 7 years (FedRAMP) |
| Compliance Events | 365 days | 90 days | 7 years (SOX) |
| VPC Flow Logs | 365 days | 90 days | 365 days |
| CloudTrail | 365 days | 90 days | 7 years (SOX) |

### Retention Configuration

Retention policies are configured per organization in Settings > Security > Log Retention.

**Available Options:**
- 90 days (minimum)
- 1 year (default)
- 3 years
- 7 years (SOX/financial compliance)
- Custom (enterprise only)

### Archive and Retrieval

Logs beyond the active retention period are archived to cold storage:

| Age | Storage Tier | Retrieval Time | Cost |
|-----|--------------|----------------|------|
| 0-90 days | CloudWatch Logs | Immediate | Included |
| 90-365 days | S3 Standard-IA | Immediate | +10% |
| 1-3 years | S3 Glacier | 3-5 hours | +5% |
| 3-7 years | S3 Glacier Deep Archive | 12-48 hours | +2% |

**Archive Retrieval Process:**
1. Navigate to Settings > Security > Log Archive
2. Select date range and log categories
3. Submit retrieval request
4. Receive notification when logs are available
5. Download within 7 days (link expires)

---

## CloudWatch Integration

### Log Groups

Project Aura creates dedicated CloudWatch Log Groups:

| Log Group | Content | Retention |
|-----------|---------|-----------|
| `/aura/audit/user-actions` | User authentication and authorization | 365 days |
| `/aura/audit/agent-actions` | AI agent operations | 365 days |
| `/aura/audit/approvals` | Approval workflow events | 365 days |
| `/aura/security/threats` | Security threats and alerts | 365 days |
| `/aura/security/compliance` | Compliance events | 365 days |
| `/aura/application/errors` | Application errors | 90 days |
| `/aura/application/performance` | Performance metrics | 90 days |

### CloudWatch Insights Queries

**Find all failed login attempts:**
```
fields @timestamp, actor.email, actor.ip_address, action.details.failure_reason
| filter event_type = "user.login_failed"
| sort @timestamp desc
| limit 100
```

**Find all high-severity vulnerability detections:**
```
fields @timestamp, resource.attributes.repository, resource.attributes.cve, resource.attributes.severity
| filter event_type = "agent.vulnerability_detected"
| filter resource.attributes.severity = "CRITICAL" or resource.attributes.severity = "HIGH"
| sort @timestamp desc
```

**Track patch approval times:**
```
fields @timestamp, resource.id, action.type, actor.email
| filter event_type like /^approval\./
| sort resource.id, @timestamp
```

### CloudWatch Alarms

Pre-configured security alarms included with deployment:

| Alarm Name | Condition | Action |
|------------|-----------|--------|
| `aura-injection-attempts` | Input validation failures > 10/min | SNS notification |
| `aura-secrets-exposure` | Secret detection in logs > 0 | SNS + PagerDuty |
| `aura-prompt-injection` | LLM prompt injection attempts > 5/min | SNS notification |
| `aura-rate-limit-exceeded` | API rate limit violations > 100/hour | SNS notification |
| `aura-high-severity-events` | Security event severity = CRITICAL | SNS + PagerDuty |
| `aura-llm-security-misuse` | LLM guardrail violations > 10/hour | SNS notification |
| `aura-security-build-failures` | Security build failures > 0 | SNS notification |

---

## SIEM Integration

### Supported SIEM Platforms

Project Aura integrates with major SIEM platforms for centralized security monitoring.

| Platform | Integration Method | Data Format |
|----------|-------------------|-------------|
| **Splunk** | HTTP Event Collector, S3 | JSON, CEF |
| **Datadog** | AWS Integration, API | JSON |
| **Sumo Logic** | AWS Integration, HTTP | JSON |
| **Microsoft Sentinel** | Azure Event Hub, S3 | CEF, JSON |
| **AWS Security Hub** | Native integration | ASFF |
| **Elastic Security** | Filebeat, S3 | JSON, ECS |
| **IBM QRadar** | S3, Syslog | LEEF, CEF |

### Splunk Integration

**Prerequisites:**
- Splunk HTTP Event Collector enabled
- HEC token with appropriate index

**Configuration:**

1. Navigate to Settings > Integrations > SIEM
2. Select Splunk
3. Enter HEC endpoint URL
4. Provide HEC token
5. Select event categories to forward
6. Test connection
7. Enable integration

**Sample Splunk Configuration:**
```json
{
  "siem_type": "splunk",
  "endpoint": "https://splunk.customer.com:8088/services/collector/event",
  "token": "********",
  "index": "aura_security",
  "sourcetype": "aura:audit",
  "event_categories": [
    "user.login",
    "user.login_failed",
    "approval.*",
    "security.*"
  ],
  "batch_size": 100,
  "flush_interval_seconds": 30
}
```

### Datadog Integration

**Prerequisites:**
- Datadog account with Logs enabled
- API key with logs write permission

**Configuration:**

1. Navigate to Settings > Integrations > SIEM
2. Select Datadog
3. Enter API key and region
4. Select event categories to forward
5. Configure tags (optional)
6. Test connection
7. Enable integration

### AWS Security Hub Integration

Project Aura natively integrates with AWS Security Hub for centralized security findings.

**Findings Published:**
- Vulnerability detections (mapped to ASFF)
- Security configuration issues
- Compliance violations
- Threat detections from GuardDuty

**Enable Integration:**
1. Ensure Security Hub is enabled in your AWS account
2. Navigate to Settings > Integrations > AWS Security Hub
3. Grant cross-account access (if Aura runs in different account)
4. Enable findings publication

---

## Compliance Reporting

### Standard Reports

Project Aura provides pre-built compliance reports for common frameworks.

| Report | Description | Frequency | Formats |
|--------|-------------|-----------|---------|
| User Access Report | All user access events | Weekly, Monthly | PDF, CSV, JSON |
| Privileged Action Report | Admin and elevated actions | Daily, Weekly | PDF, CSV, JSON |
| Vulnerability Report | Detection and remediation status | Daily, Weekly, Monthly | PDF, CSV, JSON |
| Patch Approval Report | Approval workflow summary | Weekly, Monthly | PDF, CSV, JSON |
| Security Incident Report | Security events and responses | Daily, Weekly | PDF, CSV, JSON |
| Compliance Posture Report | Control status summary | Weekly, Monthly | PDF, CSV, JSON |

### Automated Report Generation

Configure scheduled reports:

1. Navigate to Settings > Reports > Scheduled Reports
2. Select report type
3. Choose frequency (daily, weekly, monthly)
4. Select delivery method (email, S3, webhook)
5. Configure recipients
6. Enable schedule

### Custom Report Builder

Enterprise customers can build custom reports using the Report Builder:

**Available Fields:**
- All audit event attributes
- User and organization metadata
- Vulnerability and patch data
- Time-based aggregations
- Cross-reference lookups

**Export Options:**
- PDF with charts
- CSV for analysis
- JSON for automation
- Excel (XLSX)

### Compliance Dashboards

Pre-built dashboards for compliance frameworks:

| Dashboard | Metrics Included |
|-----------|------------------|
| SOX Compliance | Change management, access reviews, segregation of duties |
| CMMC Readiness | Control implementation status, evidence coverage |
| FedRAMP Monitoring | Continuous monitoring metrics, POA&M status |
| HIPAA Security | PHI access logs, security incidents, training status |

---

## Evidence Collection

### Automated Evidence Generation

Project Aura automatically generates audit evidence for common compliance controls.

| Control Area | Evidence Type | Generation |
|--------------|---------------|------------|
| Access Control | User access reports, RBAC configuration | Daily |
| Change Management | Approval workflow logs, deployment history | Continuous |
| Audit Logging | Log configuration, retention verification | Weekly |
| Encryption | KMS key inventory, encryption status | Daily |
| Vulnerability Management | Scan results, remediation timelines | Daily |
| Incident Response | Security event logs, response actions | Continuous |

### Evidence Export

Export evidence packages for external auditors:

1. Navigate to Settings > Compliance > Evidence Export
2. Select compliance framework
3. Choose date range
4. Select control categories
5. Generate package
6. Download encrypted ZIP

**Package Contents:**
- Control implementation summaries
- Configuration screenshots
- Log excerpts
- Policy documents
- Test results

### Auditor Access

Provide read-only access for external auditors:

1. Navigate to Settings > Users > Invite User
2. Select "Auditor" role
3. Configure access scope (organization, repositories)
4. Set access expiration date
5. Send invitation

**Auditor Permissions:**
- Read access to audit logs
- View compliance reports
- Export evidence packages
- No access to source code (unless explicitly granted)

---

## Log Integrity

### Tamper Evidence

Audit logs are protected against tampering:

| Control | Implementation |
|---------|----------------|
| Immutable storage | S3 Object Lock (compliance mode) |
| Hash chains | SHA-256 hash linking between log entries |
| Timestamp verification | AWS timestamp with cryptographic signature |
| Access logging | CloudTrail logging of log access |
| Deletion protection | Require MFA for log deletion |

### Verification

Verify log integrity using the provided verification tool:

```bash
# Verify log chain integrity
aura-cli logs verify --start 2026-01-01 --end 2026-01-31

# Output:
# Verified 1,247,893 log entries
# Hash chain: VALID
# Timestamps: VALID
# No gaps detected
# Integrity: CONFIRMED
```

### Legal Hold

Apply legal hold to preserve logs for litigation or investigation:

1. Navigate to Settings > Security > Legal Hold
2. Select date range
3. Select log categories
4. Provide justification
5. Set hold expiration (or indefinite)
6. Apply hold

**Legal Hold Effects:**
- Prevents automatic deletion
- Prevents modification
- Excludes from purge requests
- Requires elevated permission to release

---

## Best Practices

### Log Review Cadence

| Review Type | Frequency | Responsibility |
|-------------|-----------|----------------|
| Failed login attempts | Daily | Security Operations |
| Privileged actions | Daily | Security Operations |
| Approval workflow anomalies | Weekly | Security Management |
| Agent error rates | Weekly | Platform Engineering |
| Compliance posture | Monthly | Compliance Team |
| Full audit review | Quarterly | Internal Audit |

### Alert Tuning

Recommended thresholds for common alerts:

| Alert | Development | Production |
|-------|-------------|------------|
| Failed logins | 20/hour | 10/hour |
| Privileged actions | 100/hour | 50/hour |
| Agent errors | 10/hour | 5/hour |
| API rate limits | 1000/hour | 500/hour |
| Security events | 50/hour | 20/hour |

### Retention Optimization

Balance compliance requirements with cost:

- **High-value logs:** Authentication, approvals, security events - maximize retention
- **Medium-value logs:** Agent actions, system events - standard retention
- **Low-value logs:** Debug, performance - minimum retention

---

## Related Documentation

- [Security & Compliance Overview](./index.md)
- [Compliance Certifications](./compliance-certifications.md)
- [Data Handling](./data-handling.md)
- [GovCloud Guide](./govcloud-guide.md)
- [Monitoring Operations](../../support/operations/monitoring.md)
- [Logging Operations](../../support/operations/logging.md)

---

*Last updated: January 2026 | Version 1.0*

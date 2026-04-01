# ADR-016: HITL Approval Auto-Escalation Strategy

**Status:** Deployed
**Date:** 2025-12-02
**Decision Makers:** Project Aura Team

## Context

Project Aura's HITL (Human-in-the-Loop) approval workflow (ADR-005) requires human approval for AI-generated security patches before production deployment. However, the original design had a gap: **what happens when approval requests expire without a decision?**

The original implementation simply auto-rejected expired requests after 24 hours. This created a critical problem:

1. **Security vulnerabilities remain unpatched** - High-severity issues blocked indefinitely
2. **No differentiation by severity** - CRITICAL vulnerabilities treated same as LOW
3. **Reviewer unavailability** - Weekends, holidays, or PTO cause backlogs
4. **No proactive monitoring** - Only checked expiration when new requests created
5. **Lost context** - Expired requests required re-discovery and re-generation

The question: **How should we handle expired HITL approval requests to ensure critical vulnerabilities don't remain unpatched indefinitely?**

## Decision

We chose a **severity-based auto-escalation strategy** with proactive scheduled processing.

### Escalation Logic

| Severity | Action on Expiration | Rationale |
|----------|---------------------|-----------|
| **CRITICAL** | Escalate to backup reviewers | Cannot leave critical vulnerabilities unpatched |
| **HIGH** | Escalate to backup reviewers | Security risk too significant to ignore |
| **MEDIUM** | Mark as EXPIRED and re-queue | Can wait for next review cycle |
| **LOW** | Mark as EXPIRED and re-queue | Lower priority, can be batch-processed |

### Implementation Components

1. **Scheduled Lambda Function** (`src/lambda/expiration_processor.py`)
   - Triggered hourly by EventBridge rule
   - Scans all PENDING approval requests
   - Determines appropriate action based on severity and age

2. **Expiration Warning System**
   - At 75% of timeout period, sends warning notification
   - Gives original reviewer time to respond
   - Warning logged for audit trail

3. **Escalation Mechanism**
   - CRITICAL/HIGH: Assigns to backup reviewer, resets timeout clock
   - Maximum 2 escalations before final expiration
   - Each escalation uses shorter timeout (configurable)

4. **Notification Integration**
   - `send_escalation_notification()` - Notifies new reviewer
   - `send_expiration_notification()` - Notifies team of expired request
   - All notifications include severity, vulnerability details, audit ID

### Key Design Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TIMEOUT_HOURS` | 24 | Hours before approval request expires |
| `ESCALATION_TIMEOUT_HOURS` | 12 | Timeout for escalated requests (shorter) |
| `WARNING_THRESHOLD_PERCENT` | 0.75 | Send warning at 75% of timeout |
| `MAX_ESCALATIONS` | 2 | Maximum escalation attempts before expiration |
| `BACKUP_REVIEWERS` | Configurable | Comma-separated list of backup reviewer emails |

### State Transitions

```
PENDING ─────────────────────────────────────────────────────┐
   │                                                         │
   │ [75% timeout reached, severity=any]                     │
   ├──> Send warning notification ──────────────────────────┤
   │                                                         │
   │ [100% timeout reached]                                  │
   │                                                         │
   ├─[CRITICAL/HIGH]──> ESCALATED ──┐                       │
   │                                 │                       │
   │                    [escalation_count < MAX]             │
   │                                 │                       │
   │                    ├──> Assign to backup ──────────────┤
   │                    │    Reset timeout clock             │
   │                    │                                    │
   │                    │ [escalation_count >= MAX]          │
   │                    └──> EXPIRED                         │
   │                                                         │
   └─[MEDIUM/LOW]─────> EXPIRED ────────────────────────────┘
```

## Alternatives Considered

### Alternative 1: Auto-Reject All Expired Requests

Original behavior: Simply mark all expired requests as REJECTED regardless of severity.

**Pros:**
- Simple implementation
- No additional infrastructure needed
- Clear timeout policy

**Cons:**
- Critical vulnerabilities left unpatched
- No differentiation by severity
- Requires manual re-initiation
- Lost work (patch generation, sandbox testing)

### Alternative 2: Auto-Approve Expired Requests

Automatically approve patches that pass sandbox testing after timeout.

**Pros:**
- Vulnerabilities get patched quickly
- No human bottleneck
- Sandbox testing provides safety net

**Cons:**
- **Violates compliance requirements** (SOX, CMMC mandate human approval)
- Removes human oversight entirely
- Single point of failure if AI generates incorrect patch
- Not acceptable for security-critical changes

### Alternative 3: Re-queue with Same Reviewer

Keep re-queuing to the same reviewer with new notifications.

**Pros:**
- Simple implementation
- Original reviewer retains context
- No need for backup reviewer list

**Cons:**
- Doesn't solve unavailable reviewer problem
- Could spam same person indefinitely
- No escalation path
- Weekend/PTO issues remain

### Alternative 4: Manual Escalation Only

Require manager intervention to reassign expired requests.

**Pros:**
- Human judgment on escalation
- Manager visibility into backlog
- Flexible assignment

**Cons:**
- Adds another human bottleneck
- Delays critical patches further
- Manager may also be unavailable
- Not automated or proactive

## Consequences

### Positive

1. **Security**
   - Critical vulnerabilities escalated automatically
   - Reduced window of exposure for high-severity issues
   - Backup reviewers ensure coverage during unavailability

2. **Compliance**
   - Maintains human approval requirement (escalated, not bypassed)
   - Full audit trail of all escalations and expirations
   - Every state transition logged with timestamp and reason

3. **Operational Efficiency**
   - Proactive scheduled processing (hourly)
   - Warning notifications prevent surprise expirations
   - Automatic escalation reduces manual intervention

4. **Reliability**
   - Lambda with EventBridge provides durable scheduling
   - DynamoDB persistence survives service restarts
   - Mock mode enables comprehensive testing

### Negative

1. **Infrastructure Cost**
   - Lambda invocation: ~$0.01/month (hourly, ~730 invocations)
   - EventBridge rule: Free tier covers this
   - Additional SNS/SES notifications

2. **Complexity**
   - More notification types to maintain
   - Backup reviewer list management
   - Escalation state tracking

3. **Potential for Confusion**
   - Original reviewer may not know request was escalated
   - Multiple people could work on same request (mitigated by status checks)

### Mitigation

- **Cost:** Minimal Lambda costs, well within free tier
- **Complexity:** Comprehensive test suite (17 tests) covers all scenarios
- **Confusion:** Notifications include clear escalation context

## Infrastructure

### CloudFormation Resources

**File:** `deploy/cloudformation/hitl-scheduler.yaml`

| Resource | Type | Purpose |
|----------|------|---------|
| `ExpirationProcessorFunction` | Lambda | Processes expired approvals |
| `ExpirationScheduleRule` | Events::Rule | Hourly trigger (EventBridge) |
| `ExpirationProcessorRole` | IAM::Role | DynamoDB, SNS, SES permissions |
| `ExpirationProcessorLogGroup` | Logs::LogGroup | 365 days (prod) / 90 days (dev) |
| `ExpirationProcessorErrorAlarm` | CloudWatch::Alarm | Alert on Lambda errors |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `HITL_TABLE_NAME` | DynamoDB table for approval requests |
| `HITL_SNS_TOPIC_ARN` | SNS topic for notifications |
| `TIMEOUT_HOURS` | Primary timeout period |
| `ESCALATION_TIMEOUT_HOURS` | Escalated request timeout |
| `BACKUP_REVIEWERS` | Comma-separated reviewer emails |
| `USE_MOCK` | Enable mock mode for testing |

## Monitoring

### CloudWatch Metrics

| Metric | Description | Alarm Threshold |
|--------|-------------|-----------------|
| `Lambda Errors` | Expiration processor failures | >= 1 in 10 minutes |
| `Escalations` | Count of escalated requests | Dashboard only |
| `Expirations` | Count of expired requests | Dashboard only |

### Audit Log Events

All events logged to CloudWatch with structured JSON:

```json
{
  "event_type": "APPROVAL_ESCALATED",
  "approval_id": "approval-2025-12-02-abc123",
  "timestamp": "2025-12-02T14:30:00Z",
  "severity": "CRITICAL",
  "escalation_count": 1,
  "escalated_to": "backup-reviewer@company.com",
  "reason": "Primary reviewer did not respond within 24 hours"
}
```

## References

- **ADR-005:** `docs/architecture-decisions/ADR-005-hitl-sandbox-architecture.md` - Original HITL architecture
- **HITL Architecture:** `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Full specification
- **Lambda Handler:** `src/lambda/expiration_processor.py` - Scheduled processor
- **CloudFormation:** `deploy/cloudformation/hitl-scheduler.yaml` - Infrastructure
- **Service Implementation:** `src/services/hitl_approval_service.py` - Core logic
- **Notification Service:** `src/services/notification_service.py` - SNS/SES integration
- **Test Suite:** `tests/test_hitl_services.py` - 63 tests including 17 for expiration processing

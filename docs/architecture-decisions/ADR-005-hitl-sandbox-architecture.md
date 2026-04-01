# ADR-005: Human-in-the-Loop Sandbox Testing for Autonomous Remediation

**Status:** Deployed
**Date:** 2025-11-28
**Decision Makers:** Project Aura Team

## Context

Project Aura's autonomous vulnerability remediation system generates AI-generated security patches. Before deploying these patches to production, we must:

1. Validate patches work correctly (no breaking changes)
2. Ensure patches don't introduce new vulnerabilities
3. Obtain human approval for security-critical changes
4. Maintain compliance audit trails (SOX, CMMC)

The question: **Should AI-generated patches be deployed directly, or require human approval?**

This decision impacts:
- Security risk (untested AI code in production)
- Compliance requirements (change management approval)
- Remediation speed (autonomous vs. gated deployment)
- Operational workflow (engineer review burden)

## Decision

We chose a **mandatory Human-in-the-Loop (HITL) approval workflow** with isolated sandbox testing before production deployment.

**Workflow Stages:**
1. **Detection & Generation** - Reviewer Agent detects vulnerability, Coder Agent generates patch
2. **Sandbox Provisioning** - Isolated ECS/Fargate environment created
3. **Sandbox Testing** - Comprehensive test suite (unit, integration, security, performance)
4. **HITL Notification** - SNS/SES alert to security team with patch details
5. **Human Approval** - Senior engineer reviews and approves/rejects via dashboard
6. **Production Deployment** - Gated CI/CD deployment only after approval
7. **Post-Deployment Verification** - 24-hour monitoring period

**Key Design Decisions:**
- 24-hour approval timeout (auto-reject if no response)
- Sandbox isolation: no production data access, no VPC peering
- Test requirements: all tests must pass before approval request
- Audit trail: every decision logged to CloudWatch/S3 with 7-year retention

## Alternatives Considered

### Alternative 1: Fully Autonomous Deployment

AI-generated patches deploy directly to production after automated testing.

**Pros:**
- Fastest remediation time (minutes instead of hours)
- No human bottleneck
- Works 24/7 including weekends/holidays

**Cons:**
- High risk: untested AI code in production
- SOX non-compliant (no change approval)
- CMMC non-compliant (no human oversight)
- Single AI failure could cause outage
- No accountability for AI errors

### Alternative 2: Human Review Only (No Sandbox)

Patches reviewed by humans but not tested in isolated environment.

**Pros:**
- Human oversight maintained
- Lower infrastructure cost (no sandbox resources)
- Faster than full sandbox approach

**Cons:**
- Human reviewers can miss subtle bugs
- No integration testing before production
- Harder to verify security patches work correctly
- Risk of deploying broken patches

### Alternative 3: Staged Rollout (Canary)

Deploy to small percentage of production, monitor, then expand.

**Pros:**
- Real-world testing
- Limits blast radius of failures
- Works for gradual rollouts

**Cons:**
- Exposes production users to untested code
- Security patches shouldn't be gradual (vulnerability window)
- Complex rollback requirements
- Not suitable for compliance-critical patches

## Consequences

### Positive

1. **Security**
   - Patches validated in isolated environment before production
   - No production data exposure during testing
   - Security scans run on patched code
   - Human review catches AI errors

2. **Compliance**
   - SOX: Change management approval documented
   - CMMC: Human oversight for security changes
   - Audit trail: 7-year retention of all decisions
   - Evidence: Test results, approver identity, timestamps

3. **Quality**
   - Integration tests catch breaking changes
   - Performance benchmarks prevent regressions
   - Unit tests verify syntax correctness
   - SAST/SCA on patched code

4. **Accountability**
   - Approver name and comments recorded
   - Rejection reasons documented
   - Clear ownership of deployment decisions

### Negative

1. **Remediation Delay**
   - Average 4 hours to approval (target SLA)
   - Maximum 24 hours before auto-reject
   - Not suitable for zero-day emergencies

2. **Human Bottleneck**
   - Requires available security engineer
   - Timeout if approvers unavailable
   - Weekend/holiday coverage needed

3. **Infrastructure Cost**
   - Sandbox resources: ~$0.03/patch
   - Monthly estimate: $3-5 for 100 patches
   - Additional DynamoDB/SNS costs

### Mitigation

- **Emergency bypass:** CISO can approve urgent patches via direct API
- **On-call rotation:** 24/7 security engineer availability
- **Auto-escalation:** If primary approver doesn't respond in 4 hours, escalate
- **Cost optimization:** Fargate Spot for sandbox, auto-teardown after 2 hours

## Sandbox Isolation Requirements

| Requirement | Implementation |
|-------------|----------------|
| **Network Isolation** | Separate VPC, no peering, no transit gateway |
| **Data Isolation** | Synthetic/mock data only, no production DB access |
| **Compute Isolation** | Dedicated ECS cluster, no shared task execution |
| **Time Limits** | Auto-terminate after 2 hours |
| **Resource Quotas** | CPU/memory limits, prevent resource exhaustion |

## Approval Roles

| Role | IAM Role Name | Permissions |
|------|---------------|-------------|
| Senior Security Engineer | `AuraPatchApprover` | Approve/Reject/Request Changes |
| Security Operations Manager | `AuraSecurityManager` | All above + timeout overrides |
| CISO | `AuraCISO` | All above + emergency bypass |

## SLA Targets

| Metric | Target |
|--------|--------|
| Sandbox provisioning | < 5 minutes |
| Test execution | < 10 minutes |
| Notification delivery | < 1 minute |
| Human approval | < 24 hours (4 hours recommended) |
| Production deployment | < 30 minutes (post-approval) |

## References

- `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Full architecture specification
- `src/agents/sandbox_orchestrator.py` - Sandbox provisioning agent (future)
- `src/services/hitl_approval_service.py` - Approval workflow service (future)
- `agent-config/agents/security-code-reviewer.md` - Security review patterns

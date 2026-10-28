# ADR-005: Human-in-the-Loop Sandbox Testing for Autonomous Remediation

**Status:** Deployed (core HITL path; dedicated sandbox VPC, IAM approver roles and emergency bypass not built -- see status notes)

> **Status note (2026-10-26).** The 2026-08-28 and 2026-10-14 notes below are still accurate. Since then, a failed sandbox run first goes back to the coder for up to `max_sandbox_repairs` repair runs (default 1, `src/agents/agent_orchestrator.py:473`) before the approval request is blocked, and the job server calls the HITL workflow (`src/agents/orchestrator_server.py:342`). The IAM roles in the Approval Roles table (`AuraPatchApprover`, `AuraSecurityManager`, `AuraCISO`) are not in any template; approval rights come from the application roles `security-engineer` and `admin` (`src/api/approval_endpoints.py:68`). The CISO emergency bypass is not implemented, and sandbox tasks default to a 3600-second limit (`src/services/sandbox_network_service.py:701`), not 2 hours.

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

> **Status note (2026-08-28) -- the Network Isolation row is a requirement, not
> a shipped implementation.** No dedicated sandbox VPC exists.
> `deploy/cloudformation/sandbox.yaml` imports `VpcId` / `PrivateSubnetIds` from
> the networking stack, so sandbox tasks run in the platform VPC's private
> subnets. `ENFORCED_ISOLATION_LEVELS`
> (`src/services/sandbox_network_service.py:79`) restricts the provisioning path
> to `none` and `container`; requesting `vpc` or `full` now raises
> `UnsupportedIsolationLevelError` rather than returning success on
> container-level networking. What is enforced: no inbound security-group rules,
> `assignPublicIp: DISABLED`, egress limited to UDP 53 and TCP 443, and a
> least-privilege task role. The remaining rows in this table are accurate. The
> decision rationale below is preserved unchanged.

| Requirement | Implementation |
|-------------|----------------|
| **Network Isolation** | Separate VPC, no peering, no transit gateway (**not implemented** -- see status note) |
| **Data Isolation** | Synthetic/mock data only, no production DB access |
| **Compute Isolation** | Dedicated ECS cluster, no shared task execution |
| **Time Limits** | Auto-terminate after 2 hours |
| **Resource Quotas** | CPU/memory limits, prevent resource exhaustion |

## Approval Roles

> **Status note (2026-10-14) -- approval path hardening.** The approval API
> previously accepted approve/reject/cancel calls without authentication and
> took the reviewer identity from the request body. All routes in
> `src/api/approval_endpoints.py` now require an authenticated user; decisions
> require the `security-engineer` or `admin` role, the recorded reviewer comes
> from the token, a mismatched `reviewer_email` in the body is rejected, and a
> route-guard test fails if any state-changing route lacks an auth dependency.
> The HITL path in `src/agents/agent_orchestrator.py`
> (`execute_request_with_hitl`) previously simulated the sandbox step from
> static validation results; it now calls `ValidatorAgent.validate_in_sandbox`.
> When no sandbox orchestrator is configured the approval request records the
> sandbox as `SKIPPED` with no test counts, so an approver can see the patch
> was not runtime-tested. A failed sandbox run blocks the approval request.

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
- `src/services/sandbox_network_service.py` - Sandbox provisioning (`FargateSandboxOrchestrator`; the `src/agents/sandbox_orchestrator.py` path named in the original draft was never created)
- `src/agents/validator_agent.py` - `validate_in_sandbox`, the sandbox validation step used by the HITL path
- `src/services/hitl_approval_service.py` - Approval workflow service
- `src/api/approval_endpoints.py` - Approval API (authenticated; approve/reject/cancel restricted to `security-engineer` and `admin`)
- `agent-config/agents/security-code-reviewer.md` - Security review patterns

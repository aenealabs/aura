# ADR-092: CloudFormation Deploy Role Wildcard Scoping

## Status

**Proposed** | May 12, 2026

## Context

### Audit finding

The May 10, 2026 GTM-readiness audit (issue #163) flagged the `CloudFormationServiceRole` in `deploy/cloudformation/iam.yaml:320-341`:

> Unscoped `ec2:*` / `s3:*` / `kms:*` and 13 other `<service>:*` actions on `Resource: '*'` for the CFN deploy role. Region-scoped via `aws:RequestedRegion`; still account-wide for those services on role compromise. Document and accept or scope to `${ProjectName}-*` where the API permits.

(The audit's mention of `iam:*` was inaccurate — `iam:` is already scoped to `arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-*` at lines 343–367. Same for `cloudformation:` at lines 371–384 and `sts:` further down. The remaining 16 services genuinely have unscoped `Resource: '*'`.)

### Current state — the block in question

```yaml
# iam.yaml:319-341
- Effect: Allow
  Action:
    - ec2:*
    - eks:*
    - rds:*  # Neptune uses RDS service namespace
    - es:*  # OpenSearch uses 'es' service prefix
    - dynamodb:*
    - s3:*
    - kms:*
    - logs:*
    - cloudwatch:*
    - elasticloadbalancing:*
    - autoscaling:*
    - ecs:*
    - ecr:*
    - elasticfilesystem:*
    - rds:*
    - servicediscovery:*
  Resource: '*'
  Condition:
    StringEquals:
      'aws:RequestedRegion': !Ref AWS::Region
```

16 service namespaces, action-wildcarded, resource-wildcarded, region-scoped via `aws:RequestedRegion`. The role is assumed by `cloudformation.amazonaws.com` to deploy every layer of the platform.

### Threat model

If the CFN role were assumed by an attacker (e.g., via a compromised CodeBuild project, a manipulated buildspec, or a misconfigured trust policy), they would gain:

- **In-region:** Full read/write/delete on every resource in the 16 services across the entire account.
- **Out-of-region:** Nothing — the `aws:RequestedRegion` condition holds.
- **Out-of-service-namespace:** Nothing — IAM, CloudFormation, STS are already scoped to `${ProjectName}-*` or read-only.

Worst-case in-region blast radius:
- Read/exfiltrate every S3 bucket and DynamoDB table in the account (not just project ones)
- Decrypt every KMS-encrypted resource in the account
- Delete every EBS volume, EC2 instance, RDS database, EKS cluster, ECS service, ECR repository in the account
- Read CloudWatch metrics and logs for every service in the account

### Why the audit's "accept and document or scope" framing is correct

There is no single right answer because the trade-off varies per service:

- Some services (S3, DynamoDB, KMS, ECR, EKS, ECS, RDS) **fully support** resource-level IAM. Scoping to `arn:${partition}:<service>:*:${account}:*/${ProjectName}-*` is achievable.
- Some services (EC2) have **dozens of resource-less control-plane actions** (`ec2:DescribeImages`, `ec2:DescribeAvailabilityZones`, etc.) that AWS requires `Resource: '*'` for. Splitting the policy into "scoped actions" + "list-only on `*`" is achievable but verbose.
- Some services (CloudWatch metrics, certain `logs` actions) require `Resource: '*'` for the API to function — these are the case ADR-041 already covers.

ADR-041 (December 2025) accepted AWS-required wildcards and documented compensating controls. The CFN deploy role block was not specifically addressed there because it was already region-scoped, but the May 2026 audit re-raised it as a residual risk.

## Decision

**Take the hybrid path: scope what AWS supports, keep wildcards where AWS requires them, and document each retained wildcard inline.**

Concretely, the single 16-service wildcard statement becomes a 3-statement structure:

1. **Scoped statement** — services that fully support resource ARNs and project naming. List each action that the role actually uses (CFN deploy + drift detection + rollback paths), scope to `arn:${partition}:<service>:*:${account}:.../${ProjectName}-*` (or service-equivalent — e.g., S3 uses `arn:${partition}:s3:::${ProjectName}-*`).
2. **Read-only/list statement** — `*:Describe*`, `*:List*`, `*:Get*` actions that AWS requires `Resource: '*'` for. These are inventory operations; they can read but not mutate. Add explicit `aws:RequestedRegion` condition (already present).
3. **Compensating-control statement** — explicit `Deny` block for production-tier resource patterns (mirrors ADR-041 §65–74). Provides containment even if a scoped statement is misconfigured.

This is **stronger than ADR-041's "accept and document"** because it actually narrows the scoped set, and **safer than full "scope everything"** because EC2 list/describe wildcards stay legal but the destructive scope is narrowed.

### What stays wildcarded and why

| Service | Decision | Reason |
|---|---|---|
| `ec2:` | Split: scoped mutate, wildcarded describe/list | EC2 has ~50 resource-less `Describe*`/`Get*` APIs that AWS doesn't support resource conditions on. Mutate actions (RunInstances, TerminateInstances, etc.) accept resource ARNs. |
| `cloudwatch:PutMetricData` | Keep wildcarded + namespace condition | Same as ADR-041 §16. Metrics API is namespace-level, not resource. Already conditional in some templates. |
| `logs:CreateLogDelivery` | Keep wildcarded | AWS requires `Resource: '*'` for the log-delivery configuration API. |
| `autoscaling:Describe*` | Keep wildcarded | Auto Scaling describe-tier APIs operate on the account, not resource. Mutate actions scope correctly. |

### What gets scoped

| Service | New Resource pattern |
|---|---|
| `s3:` | `arn:${AWS::Partition}:s3:::${ProjectName}-*` and `arn:${AWS::Partition}:s3:::${ProjectName}-*/*` |
| `dynamodb:` | `arn:${AWS::Partition}:dynamodb:*:${AWS::AccountId}:table/${ProjectName}-*` |
| `kms:` | `arn:${AWS::Partition}:kms:*:${AWS::AccountId}:key/*` with `kms:ResourceAliases` condition matching `alias/${ProjectName}-*`, plus `Resource: '*'` for `kms:GenerateDataKey*` calls inside service integrations |
| `eks:` | `arn:${AWS::Partition}:eks:*:${AWS::AccountId}:cluster/${ProjectName}-*` (mutate); `Resource: '*'` retained for `eks:ListClusters` |
| `ecs:` | `arn:${AWS::Partition}:ecs:*:${AWS::AccountId}:cluster/${ProjectName}-*` and `task-definition/${ProjectName}-*:*` |
| `ecr:` | `arn:${AWS::Partition}:ecr:*:${AWS::AccountId}:repository/aura-*` (already private-ECR per ADR root CLAUDE.md) |
| `rds:` | `arn:${AWS::Partition}:rds:*:${AWS::AccountId}:db:${ProjectName}-*` and `cluster:${ProjectName}-*` |
| `es:` (OpenSearch) | `arn:${AWS::Partition}:es:*:${AWS::AccountId}:domain/${ProjectName}-*` |
| `elasticloadbalancing:` | `arn:${AWS::Partition}:elasticloadbalancing:*:${AWS::AccountId}:loadbalancer/*/${ProjectName}-*/*` |
| `elasticfilesystem:` | `arn:${AWS::Partition}:elasticfilesystem:*:${AWS::AccountId}:file-system/*` with name-tag condition |
| `servicediscovery:` | `arn:${AWS::Partition}:servicediscovery:*:${AWS::AccountId}:namespace/*` with name condition |
| `autoscaling:` mutate | `arn:${AWS::Partition}:autoscaling:*:${AWS::AccountId}:autoScalingGroup:*:autoScalingGroupName/${ProjectName}-*` |
| `logs:` mutate | `arn:${AWS::Partition}:logs:*:${AWS::AccountId}:log-group:/aws/${ProjectName}/*` |

## Alternatives Considered

### Option A — "Accept and document" (extension of ADR-041)

Add a row to ADR-041's "Affected Templates" table for `iam.yaml:320-341`, document that the region-scoping is the compensating control, and update root `CLAUDE.md` to acknowledge the trade-off. No code change.

**Pros:** Zero migration risk. ADR-041 precedent already exists. Region-scoping is a real (if narrow) compensating control.

**Cons:** Doesn't actually reduce blast radius. The audit was correct that "account-wide on role compromise" is a real exposure that *can* be narrowed. Punts the problem.

**When to pick:** If migration risk is unacceptable (e.g., immediately before a customer ship date) and the audit is willing to accept the residual.

### Option B — Full scope-everything (strict least-privilege)

Replace the wildcard block with ~120 explicit action statements (one per `CreateX`/`DeleteX`/`UpdateX` action across 16 services), each scoped to `${ProjectName}-*`. Inline `Describe*`/`List*`/`Get*` actions on `Resource: '*'`.

**Pros:** Tightest possible blast radius. Every action accounted for. Compliance auditor catnip.

**Cons:**
- IAM policy size limit (10,240 bytes inline). 16 services × 8 actions × ARN size = exceeds limit. Would force the policy into a managed policy split, adding deployment complexity.
- High maintenance: every new CloudFormation resource type added to the platform requires a corresponding action addition.
- High breakage risk: each missed action breaks deployments in non-obvious ways (CloudFormation rollback failures often surface as cryptic timeout errors, not access-denied).
- 1–2 week migration with full E2E redeploy required.

**When to pick:** If a security audit explicitly requires demonstrable least-privilege at the action level.

### Option C — Hybrid (RECOMMENDED)

Scope the 13 services that genuinely support resource-level IAM; keep the 3 services (`ec2:Describe*`, `cloudwatch:PutMetricData`, `logs:CreateLogDelivery`-class) wildcarded with conditions and inline documentation. Add an explicit `Deny` for production-tier patterns.

**Pros:**
- Reduces blast radius meaningfully (most exfiltration paths go through scoped services).
- Stays inside the IAM 10KB inline limit (estimate: ~6.5KB after rewrite vs current ~1.2KB).
- Maintenance burden is bounded (only the documented-wildcard subset evolves).
- Aligned with ADR-041's pattern.

**Cons:**
- Migration requires careful E2E deploy validation. Every CodeBuild project that triggers a CFN stack deployment needs to be re-run against the new role to surface any missing actions.
- 1-week scoped migration (smaller than Option B).

## Migration Plan (if Option C is chosen)

### Phase 1 — Inventory (1 day)
- Enable CloudTrail trail filtering for `userIdentity.sessionContext.sessionIssuer.userName == ${ProjectName}-cfn-role-${Environment}` over the last 30 days (CloudTrail Lake query).
- Compile per-service action set actually used. Likely 40–60 distinct actions total, not 16 wildcards.
- Cross-check against the 170 CloudFormation templates' resource declarations to catch deploy-time actions not in the 30-day window.

### Phase 2 — Implement in dev (2 days)
- Rewrite `CloudFormationServiceRole` policy in `iam.yaml` with the 3-statement structure.
- Deploy to dev. Trigger every parent-layer CodeBuild project (`aura-foundation-deploy-dev` through `aura-security-deploy-dev`). Capture `AccessDenied` errors.
- Iterate: add missing actions to the scoped statement, redeploy, re-run.

### Phase 3 — Validate in QA (1 day)
- Deploy the new role to QA. Re-run the full deployment pipeline end-to-end.
- Confirm zero `AccessDenied` events in CloudTrail for the CFN role for 24h.

### Phase 4 — Production rollout (1 day, gated by HITL)
- Deploy to production behind ADR-032 HITL approval gate (this is a credential-modification scope per ADR-086 `IMMUTABLE_GUARDRAILS`).
- Monitor CloudTrail for 72h post-deploy. Roll back if any `AccessDenied` surfaces.

### Phase 5 — Documentation
- Update root `CLAUDE.md` "IAM wildcards" section to reference this ADR.
- Update ADR-041's "Affected Templates" table to point at this ADR for the deploy role.
- Close `#182` IAM-wildcards line item.

## Compensating Controls

This ADR's controls are **additive** to ADR-041. The full layered defense remains:

1. **Permission boundaries** (ADR-041 §47) — unchanged.
2. **VPC endpoint policies** (ADR-041 §53) — unchanged.
3. **Region condition** (`aws:RequestedRegion` at line 339-341) — retained.
4. **NEW: Resource ARN scoping** for the 13 services that support it.
5. **NEW: Explicit Deny block** for production-tier resource patterns inside the CFN deploy role policy itself:
   ```yaml
   - Sid: DenyProductionPatternsOutsideTargetEnv
     Effect: Deny
     Action: '*'
     Resource:
       - !Sub 'arn:${AWS::Partition}:dynamodb:*:*:table/${ProjectName}-*-prod*'
       - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod*'
       - !Sub 'arn:${AWS::Partition}:rds:*:*:db:${ProjectName}-*-prod*'
     Condition:
       StringNotEquals:
         'aws:ResourceTag/Environment': !Ref Environment
   ```
   (Only applies when the deploy role tries to act on prod-named resources while running in dev/qa — guards against name-collision misconfig.)
6. **CloudTrail audit** (ADR-041 §86) — unchanged.
7. **GuardDuty threat detection** (ADR-041 §92) — unchanged.

## Affected Templates

| Template | Lines | Change |
|---|---|---|
| `iam.yaml` | 319–341 (current); ~319–390 (after) | Replace single 16-service wildcard statement with 3-statement scoped structure |
| `CLAUDE.md` (root) | "IAM wildcards" subsection | Add reference to ADR-092 |
| `ADR-041` | "Affected Templates" table | Update `iam.yaml` row to point at ADR-092 for the deploy role |

No other templates touched.

## Compliance Mapping

| Framework | Control | Before (ADR-041 only) | After (this ADR) |
|---|---|---|---|
| CMMC AC.L2-3.1.3 | Control information flow | Compensated | Compensated + scoped |
| NIST AC-3 | Access enforcement | Compensated | **Enforced (resource-level)** |
| NIST AC-6 | Least privilege | Partial | **Substantially compliant** (13 of 16 services scoped) |
| SOC 2 CC6.1 | Logical access | Compensated | Compensated + scoped |
| ISO 27001 A.9.4.1 | Access restriction | Partial | Substantially compliant |

## Consequences

### Positive
- Account-wide blast radius narrows to ~3 services for describe/list actions (was 16 services full read/write/delete).
- Compliance posture upgrades on NIST AC-3 and AC-6 from "compensated" to "enforced/substantially compliant".
- Each retained wildcard is inline-documented with rationale (ADR-041 pattern).
- Explicit `Deny` block adds a defense-in-depth layer that catches name-collision deployment misconfig.

### Negative
- 1-week migration with phased rollout (dev → qa → prod).
- IAM policy size grows from ~1.2KB to ~6.5KB inline. Stays under 10KB limit per `deploy/cloudformation/CLAUDE.md` rules.
- Each new CFN resource type added to the platform requires checking whether its actions are in the scoped or wildcarded set; missing actions will surface as `AccessDenied` during deploy.
- Slightly higher operational overhead — incidents involving deploy failures will need to confirm whether the role has the required action before pursuing other root causes.

### Rollback

If the new role causes deployment failures in production that can't be diagnosed in the 72-hour validation window, revert via stack policy update:
```bash
aws cloudformation deploy \
  --stack-name aura-foundation-iam-prod \
  --template-file deploy/cloudformation/iam.yaml \
  --parameter-overrides UseLegacyDeployRole=true \
  --capabilities CAPABILITY_NAMED_IAM
```
(Implementation note: add a `UseLegacyDeployRole` parameter conditioned on the legacy block during Phase 2 so rollback is single-stack and reversible.)

## References

- **Issue:** [#182](https://github.com/aenealabs/aura/issues/182) — tech-debt: lower-value cleanup tracker
- **Audit source:** Issue #163 (closed), GTM-readiness 8-lane audit, May 10, 2026
- **Precedent:** ADR-041 — AWS-Required Wildcards with Defense-in-Depth Compensating Controls
- **Related:** ADR-086 (Agentic Identity Lifecycle) — `IMMUTABLE_GUARDRAILS` requires HITL on credential-modification scope
- **AWS docs:**
  - [Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/) — per-service resource-ARN support matrix
  - [IAM JSON Policy Element: Condition Operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html)
  - [aws:RequestedRegion condition key](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-requestedregion)

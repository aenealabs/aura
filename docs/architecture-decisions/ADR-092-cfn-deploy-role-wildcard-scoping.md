# ADR-092: CloudFormation Deploy Role Wildcard Scoping

## Status

**Accepted (v2)** | May 12, 2026

### Revision history

- **v1** (May 12, 2026) — Initial draft. Three options (A/B/C) with C recommended. Drafted in response to issue #182 IAM-wildcards line item.
- **v2** (May 12, 2026) — Revised after three independent expert reviews (AWS/IAM architect, cybersecurity analyst, senior code reviewer). Material corrections to the per-service scoping table, added Self-Broadening Deny and `iam:PassedToService` constraint, re-labeled prod-pattern Deny as a safety control with a separate security Deny added, expanded to 8-statement structure, planned managed-policy split from day one, expanded Phase 1 inventory beyond CloudTrail-only, replaced inline `!If` rollback with dual-managed-policy or separate-template pattern.
- **Accepted** (May 12, 2026) — Owner accepted v2 unmodified. Phase 2 (code change) committed in the same change set. Phase 1 (CloudTrail inventory) and Phases 3–5 (deploy + rollback exercise + production + docs) pending live AWS access.

## Context

### Audit finding

The May 10, 2026 GTM-readiness audit (issue #163) flagged the `CloudFormationServiceRole` in `deploy/cloudformation/iam.yaml:319-341`:

> Unscoped `ec2:*` / `s3:*` / `kms:*` and 13 other `<service>:*` actions on `Resource: '*'` for the CFN deploy role. Region-scoped via `aws:RequestedRegion`; still account-wide for those services on role compromise. Document and accept or scope to `${ProjectName}-*` where the API permits.

The audit's mention of `iam:*` as unscoped was inaccurate — `iam:` is already scoped at lines 343–367. Same for `cloudformation:` (lines 371–384) and `sts:`. The actual residual is 16 service namespaces:

`ec2`, `eks`, `rds` (listed twice — duplicate to clean up during rewrite), `es`, `dynamodb`, `s3`, `kms`, `logs`, `cloudwatch`, `elasticloadbalancing`, `autoscaling`, `ecs`, `ecr`, `elasticfilesystem`, `servicediscovery`.

### Current state — the block in question

```yaml
# iam.yaml:319-341
- Effect: Allow
  Action:
    - ec2:*
    - eks:*
    - rds:*  # Neptune uses RDS service namespace
    - es:*
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
    - rds:*                  # DUPLICATE - drop during rewrite
    - servicediscovery:*
  Resource: '*'
  Condition:
    StringEquals:
      'aws:RequestedRegion': !Ref AWS::Region
```

16 service namespaces, action-wildcarded, resource-wildcarded, region-scoped. Assumed by `cloudformation.amazonaws.com` to deploy every layer of the platform.

### Threat model (expanded after v2 review)

Worst-case in-region blast radius on role compromise:

- Read/exfiltrate every S3 bucket + DynamoDB table in the account
- Decrypt every KMS-encrypted resource
- Delete every EBS/EC2/RDS/EKS/ECS/ECR resource
- Read CloudWatch metrics and logs across the account

**Additional paths the v1 threat model missed (added in v2 per Sally's review):**

| MITRE technique | Path | Status in current policy |
|---|---|---|
| **T1098.001 (Additional Cloud Roles)** | The role can `iam:UpdateAssumeRolePolicy` on its own ARN because `${ProjectName}-cfn-role-${Environment}` matches the `${ProjectName}-*` scope at line 365. **Attacker assuming the role can broaden its own trust policy to any external principal.** | **Unmitigated.** New explicit Deny required (see Decision §3.1). |
| **T1098.003 (Additional Cloud Credentials)** | The role can call `iam:CreateAccessKey`, `iam:CreateLoginProfile` on any `${ProjectName}-*` role/user. | Partially mitigated by existing scope; v2 adds explicit constraint. |
| **T1078.004 (Valid Accounts: Cloud Accounts)** | `iam:PassRole` is resource-scoped to `${ProjectName}-*`, which includes the ADR-043 IRSA roles (Bedrock, Neptune, OpenSearch, DDB access). Attacker can `RunInstances` or `CreateService` with an IRSA role attached and call APIs as that role — **sidesteps the 16-service policy entirely.** | **Unmitigated.** Requires `iam:PassedToService` condition (see Decision §3.2). |
| **T1213.003 (Data from Cloud Storage)** | In-region S3/DynamoDB/Neptune/OpenSearch read on account-wide scope. | Mitigated only by region condition. Narrowed by Option C resource scoping. |
| **T1485/T1486 (Data Destruction / Encrypted for Impact)** | `kms:*` + `s3:*` + `dynamodb:*` + delete actions. | Mitigated only by region condition. Narrowed by Option C resource scoping. |

**Region condition caveats (added in v2 per Sally):**

`aws:RequestedRegion` is a **regional-API jail, not a hard region jail**. The condition is evaluated per call against the *signing region of the API call*. Global APIs (IAM, Route 53, Organizations reads, `s3:CreateBucket` global endpoint, `kms:ReplicateKey` for multi-region keys) are region-less or have per-API treatment of `RequestedRegion` that varies. In practice this means the condition prevents *creating regional resources in another region* but does not prevent cross-region pivots through global control planes.

### Why the audit's "accept and document or scope" framing is correct

The trade-off varies per service:

- Some services (S3, DynamoDB, KMS, ECR, EKS, ECS, RDS) fully support resource-level IAM. Scoping is achievable.
- Some services (EC2) have ~50 resource-less control-plane actions (`ec2:DescribeImages`, `ec2:DescribeAvailabilityZones`, etc.) that AWS requires `Resource: '*'` for.
- Some services (CloudWatch metrics, certain `logs` actions) require `Resource: '*'` for the API to function — these are the cases ADR-041 already covers.
- Some services (EFS, ServiceDiscovery) have server-generated IDs that cannot be ARN-prefix-scoped; tag-based conditions are the only option.

ADR-041 (December 2025) accepted AWS-required wildcards and documented compensating controls. The CFN deploy role block was not specifically addressed there because it was already region-scoped, but the May 2026 audit re-raised it as a residual risk worth narrowing.

## Decision

**Take the hybrid path: scope what AWS supports via ARNs, use tag conditions for services with server-generated IDs, keep wildcards where AWS API design requires them, and document each retained wildcard inline.**

The single 16-service wildcard statement becomes an **8-statement structure** (revised from 3 in v1 per Jake's review). Statement ordering does not affect IAM evaluation (explicit Deny always wins regardless of position) — grouping is for readability and per-purpose review.

### Statement structure

```
Statement 1: Scoped mutate (ARN-supported services)
  s3, dynamodb, ecr, eks, ecs, rds, es, elasticloadbalancing, autoscaling

Statement 2: Tag-conditioned mutate (server-generated-ID services)
  elasticfilesystem (create + operate), servicediscovery (create + operate)

Statement 3: EC2 split
  - Mutate actions tag-conditioned on Project tag
  - Describe/List/Get actions on Resource: '*'

Statement 4: KMS bootstrap + operate split
  - kms:CreateKey on Resource: '*' with aws:RequestTag/Project condition
  - kms:* operate-tier on Resource: '*' with kms:ResourceAliases matching alias/${ProjectName}-*

Statement 5: CloudWatch PutMetricData wildcarded + cloudwatch:namespace condition
  (ADR-041 §44 precedent)

Statement 6: Logs CreateLogDelivery wildcarded (AWS-required) + inline rationale
  (ADR-041 §44 precedent)

Statement 7: Read-only wildcards (account-wide describe/list/get for inventory)
  *:Describe*, *:List*, *:Get*

Statement 8: Explicit Denies (safety + security, combined)
  - Safety: deny ${ProjectName}-*-prod* resources when role's Environment != prod
  - Security: deny mutate actions on resources lacking Project=${ProjectName} tag
  - Security: deny self-broadening (iam:UpdateAssumeRolePolicy on own ARN)
  - Security: deny iam:PassRole except to allowed service principals
```

### Revised "What gets scoped" matrix (v2 corrections from Jake + Tara)

| Service | Mutate scope (Statement 1 or 2 or 3) | Read scope (Statement 7) | Notes |
|---|---|---|---|
| `s3` | `arn:${AWS::Partition}:s3:::${ProjectName}-*` (bucket) **and** `arn:${AWS::Partition}:s3:::${ProjectName}-*/*` (objects) | `*` | Both bucket and object ARNs required. Verified correct. |
| `dynamodb` | `table/${ProjectName}-*` **plus** `table/${ProjectName}-*/index/*` **plus** `table/${ProjectName}-*/stream/*` **plus** `table/${ProjectName}-*/backup/*` **plus** `backup/*` | `*` | v2 fix: added GSI, stream, backup ARN patterns Jake flagged. |
| `kms` | **Split:** Statement 4 bootstrap = `Resource: '*'` for `kms:CreateKey` with `aws:RequestTag/Project=${ProjectName}` condition; Statement 4 operate = `Resource: '*'` for `kms:*` other actions with `kms:ResourceAliases` matching `alias/${ProjectName}-*` | `*` | v2 fix: bootstrap and operate split. `kms:CreateKey` cannot use `kms:ResourceAliases` because no alias exists yet. Per Tara's review. |
| `eks` | `cluster/${ProjectName}-*` **plus** `nodegroup/${ProjectName}-*/*/*` **plus** `fargateprofile/${ProjectName}-*/*` **plus** `addon/${ProjectName}-*/*/*` | `*` | v2 fix: added nodegroup/fargateprofile/addon ARN patterns. Required for `CreateNodegroup`/`CreateFargateProfile`/`CreateAddon`. |
| `ecs` | `cluster/${ProjectName}-*` **plus** `service/${ProjectName}-*/*` **plus** `task-definition/${ProjectName}-*:*` **plus** `task-set/${ProjectName}-*/*/*` | `*` | v2 fix: added service and task-set ARNs. Required for blue/green deploys. |
| `ecr` | `repository/aura-*` | `*` | **Intentional naming deviation per ADR-049:** ECR repos use `aura-*` prefix (private base images convention), not `${ProjectName}-*`. Called out explicitly so future renames don't break. |
| `rds` (incl. Neptune) | `db:${ProjectName}-*` **plus** `cluster:${ProjectName}-*` **plus** `subgrp:${ProjectName}-*` **plus** `pg:${ProjectName}-*` **plus** `og:${ProjectName}-*` **plus** `snapshot:${ProjectName}-*` **plus** `cluster-snapshot:${ProjectName}-*` **plus** `cluster-pg:${ProjectName}-*` | `*` | v2 fix: added subnet-group, parameter-group, option-group, snapshot ARNs. Required because CFN deploys create all of these. |
| `es` (OpenSearch) | `domain/${ProjectName}-*` | `*` | Correct as drafted. |
| `elasticloadbalancing` | `loadbalancer/app/${ProjectName}-*/*` **plus** `loadbalancer/net/${ProjectName}-*/*` **plus** `targetgroup/${ProjectName}-*/*` **plus** `listener/app/${ProjectName}-*/*/*` **plus** `listener-rule/app/${ProjectName}-*/*/*/*` | `*` | v2 fix: original ALBv2-only pattern was incomplete. Added explicit ALB+NLB load balancer ARNs and the targetgroup/listener/listener-rule ARNs that `CreateTargetGroup`/`ModifyListener` require. Classic ELB is not used in this codebase (verified). |
| `elasticfilesystem` | **Statement 2 tag-conditioned:** `Resource: '*'` for `efs:CreateFileSystem` with `aws:RequestTag/Project=${ProjectName}` condition; `file-system/*` for operate actions with `aws:ResourceTag/Project=${ProjectName}` condition | `*` | v2 fix: EFS IDs are server-generated (`fs-xxxxx`), no ARN-prefix scoping possible. Tag-based create + operate split per Tara's review. |
| `servicediscovery` | **Statement 2 tag-conditioned:** `Resource: '*'` for `CreatePrivateDnsNamespace`/`CreatePublicDnsNamespace` with `servicediscovery:NamespaceName` StringLike `${ProjectName}-*`; `namespace/*` and `service/*` for operate with `aws:ResourceTag/Project` condition | `*` | v2 fix: namespace/service IDs are server-generated. Name-based create + tag-based operate. Per Tara's review. |
| `autoscaling` | `autoScalingGroup:*:autoScalingGroupName/${ProjectName}-*` (mutate) | `*` | Format verified correct. Launch templates/configurations not covered here — they live under `ec2:` (Statement 3). |
| `logs` (CreateLogDelivery class) | **Wildcarded (AWS-required):** Statement 6 with `Resource: '*'` and inline rationale | `*` | AWS requires `Resource: '*'` for `logs:CreateLogDelivery`, `logs:GetLogDelivery`, `logs:UpdateLogDelivery`, `logs:DeleteLogDelivery`, `logs:ListLogDeliveries`. Per ADR-041 precedent. |
| `logs` (other mutate) | Account-wide actual log-group patterns: `log-group:/aws/lambda/${ProjectName}-*:*` **plus** `log-group:/aws/codebuild/${ProjectName}-*:*` **plus** `log-group:/aws/eks/${ProjectName}-*:*` **plus** `log-group:/aws/ecs/${ProjectName}-*:*` **plus** `log-group:/aws/${ProjectName}-*:*` | `*` | v2 fix: original `/aws/${ProjectName}/*` pattern was wrong — actual log groups use service-prefixed paths (`/aws/lambda/`, `/aws/codebuild/`, etc.). Trailing `:*` required for `PutLogEvents` to access log streams within the group. Per Jake's review. |
| `cloudwatch:PutMetricData` | **Wildcarded (AWS-required):** Statement 5 with `Resource: '*'` and `cloudwatch:namespace` StringEquals `${ProjectName}/*` condition | n/a | Per ADR-041 §59 precedent. Already used elsewhere in the codebase. |
| `ec2:` mutate | **Statement 3:** `Resource: '*'` with `aws:RequestTag/Project=${ProjectName}` on create actions; `aws:ResourceTag/Project=${ProjectName}` on operate actions | n/a | EC2 has too many resource types (VPC, subnet, IGW, NAT-GW, route table, SG, EBS volume, instance, AMI, snapshot, launch template, etc.) to enumerate by ARN. Tag-based scoping is the standard pattern. |
| `ec2:` describe/list/get | **Statement 7:** `Resource: '*'` (AWS-required) | `*` | ~50 EC2 Describe/Get APIs have no resource ARN support. |

### Statement 8: Explicit Denies (revised in v2)

The v1 prod-pattern Deny was a single block; v2 separates **safety** from **security** controls per Sally + Jake's findings.

#### 8.1 Safety Deny — production resource patterns (re-labeled)

```yaml
- Sid: SafetyDenyProductionPatternsInNonProdDeploys
  Effect: Deny
  Action: '*'
  Resource:
    - !Sub 'arn:${AWS::Partition}:dynamodb:*:*:table/${ProjectName}-*-prod*'
    - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod*'
    - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod*/*'
    - !Sub 'arn:${AWS::Partition}:rds:*:*:db:${ProjectName}-*-prod*'
    - !Sub 'arn:${AWS::Partition}:rds:*:*:cluster:${ProjectName}-*-prod*'
  Condition:
    StringNotEquals:
      'aws:PrincipalTag/Environment': !Ref Environment
```

**Re-labeled as a SAFETY control, not a security control.** The control catches name-collision misconfig (e.g., dev deploy accidentally targeting `aura-foo-prod-bucket`). It does NOT defend against an attacker because:

- It only fires on resources whose name matches `*-prod*` (an attacker creating new untagged resources is unaffected)
- It uses `aws:PrincipalTag/Environment` (the deploy role's tag) rather than the resource's tag, which is the correct check for "wrong-environment deploy" semantics but is irrelevant to lateral movement

Per Sally's finding. The block is kept because it's a useful safety net, but labeled accurately.

#### 8.2 Security Deny — Self-broadening trust policy (NEW in v2, Sally finding #1)

```yaml
- Sid: SecurityDenySelfBroadening
  Effect: Deny
  Action:
    - iam:UpdateAssumeRolePolicy
    - iam:DeleteRolePermissionsBoundary
    - iam:PutRolePermissionsBoundary
    - iam:DeleteRolePolicy
    - iam:PutRolePolicy
    - iam:AttachRolePolicy
    - iam:DetachRolePolicy
  Resource:
    - !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-cfn-role-*'
```

**Closes MITRE T1098.001.** The CFN role's name matches `${ProjectName}-*`, so without this Deny it could modify its own trust policy and permissions boundary to escalate or persist. This Deny applies to **every** policy operation on the role's own ARN family, regardless of which Allow statement granted access.

#### 8.3 Security Deny — Project tag requirement (NEW in v2, Sally finding #4)

```yaml
- Sid: SecurityDenyResourcesMissingProjectTag
  Effect: Deny
  Action:
    - dynamodb:DeleteItem
    - dynamodb:DeleteTable
    - dynamodb:BatchWriteItem
    - dynamodb:UpdateItem
    - s3:DeleteBucket
    - s3:DeleteObject
    - s3:PutBucketPolicy
    - kms:ScheduleKeyDeletion
    - kms:DisableKey
    - rds:DeleteDBCluster
    - rds:DeleteDBInstance
  Resource: '*'
  Condition:
    StringNotEqualsIfExists:
      'aws:ResourceTag/Project': !Ref ProjectName
```

**Narrows exfiltration / destruction blast radius** on resources outside the project. Caveats per Sally + Jake review:

- `aws:ResourceTag` support varies per service per action. **S3 `GetObject` does NOT consult bucket tags by default** — this Deny will be a no-op for S3 read operations. Other unsupported pairs need explicit testing before relying on this block.
- `StringNotEqualsIfExists` is intentional: it denies when the tag is present with a wrong value but does NOT deny when the tag is absent (otherwise initial resource creation would be blocked since the tag doesn't exist pre-create). This is a known trade-off; the Project-Tag-Required SCP at the organization level is the complementary control.

#### 8.4 Security constraint — `iam:PassRole` `PassedToService` (NEW in v2, Sally finding #2)

Modify the existing IAM scope statement at `iam.yaml:343-367` to add a condition on `iam:PassRole`:

```yaml
- Effect: Allow
  Action:
    - iam:PassRole
  Resource:
    - !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-*'
    - !Sub 'arn:${AWS::Partition}:iam::*:role/aws-service-role/*'
  Condition:
    StringEquals:
      'iam:PassedToService':
        - cloudformation.amazonaws.com
        - ec2.amazonaws.com
        - ecs-tasks.amazonaws.com
        - eks.amazonaws.com
        - lambda.amazonaws.com
        - states.amazonaws.com
```

**Closes MITRE T1078.004.** Without this condition, `iam:PassRole` permits attaching `${ProjectName}-*` IRSA roles to any service principal, including ones the platform doesn't use (CodeBuild, Glue, SageMaker — all potential escalation paths). The condition limits to the actual consumer services.

### What stays wildcarded and why (v2 unchanged from v1)

| Service | Decision | Reason |
|---|---|---|
| `ec2:Describe*` family | Statement 7 wildcarded | ~50 resource-less control-plane actions. Tara confirmed via Service Authorization Reference. |
| `cloudwatch:PutMetricData` | Statement 5 wildcarded + namespace condition | Metrics API is namespace-level, not resource. ADR-041 §59. |
| `logs:CreateLogDelivery` family | Statement 6 wildcarded | AWS requires `Resource: '*'`. ADR-041 §44. |
| Read-only `*:Describe*` / `*:List*` / `*:Get*` for autoscaling, eks, ecs, etc. | Statement 7 wildcarded | Account-wide inventory operations. Service Authorization Reference confirms resource-less. |

## Alternatives Considered (unchanged from v1)

### Option A — "Accept and document" (extension of ADR-041)

Add a row to ADR-041's "Affected Templates" table for `iam.yaml:319-341`. No code change.

**Why rejected (v2 reasoning, Sally's compensating-controls analysis):** ADR-041's existing stack (permission boundaries on test-env roles, VPC endpoint policies, CloudTrail, GuardDuty) does **not** contain T1098.001 or T1078.004 on the CFN deploy role itself. Permission boundaries are on the roles the CFN role *creates*, not on the CFN role. CloudTrail is detective, not preventive. GuardDuty has documented lower precision on legitimate-credential-abuse for service roles with high baseline activity. The audit was correct that the residual *can* be narrowed.

### Option B — Full scope-everything (strict least-privilege at the action level)

~120 explicit action statements, each scoped to `${ProjectName}-*`.

**Why rejected:** Per Tara's review, maintenance burden compounds with the platform's 170-template growth rate. Per Jake's review, even the partial v1 plan was likely to exceed the 10KB inline limit; full Option B forces aggressive managed-policy splitting with cross-policy drift risk. Option C achieves substantial blast-radius reduction with ~70% less ongoing maintenance.

### Option C — Hybrid (RECOMMENDED, this ADR's decision)

Scope the 13 ARN-supporting services; tag-condition the 2 server-generated-ID services (EFS, ServiceDiscovery); retain wildcards for the 3 AWS-required cases (`ec2:Describe*`, `cloudwatch:PutMetricData`, `logs:CreateLogDelivery`); add the 4 new Deny/condition blocks above.

**Reviewer consensus (v2 review pass):** 3 of 3 reviewers (Tara, Sally, Jake) recommended C. Each surfaced different defects in the v1 draft that v2 corrects.

## Migration Plan (revised in v2)

### Phase 1 — Inventory (2 days, expanded from 1 in v1)

**1.1 CloudTrail Lake query** — Enable CloudTrail Lake event-data-store query for `userIdentity.sessionContext.sessionIssuer.userName = ${ProjectName}-cfn-role-${Environment}` over the last 30 days, with `eventName != AssumeRole` to drop the high-volume credential-assumption events. Compile per-service action set actually used.

**1.2 `cfn-policy-validator` against all 170 templates** (NEW in v2, Tara finding) — Run [aws-cloudformation/cfn-policy-validator](https://github.com/awslabs/aws-cloudformation-template-formatter) or AWS IAM Access Analyzer policy-generation feature to generate the theoretical action set from the resource declarations in all 170 templates. This catches actions that CFN deploys silently without ever surfacing them in CloudTrail (e.g., deletion paths during stack updates).

**1.3 Replay last quarterly DR test logs** (NEW in v2, Tara finding) — Disaster-recovery test runs exercise restore paths that don't fire in normal deploys. Replay the most-recent DR test trail and union the action set.

**1.4 Manual cold-path checklist** (NEW in v2, Tara provided concrete list) — Explicitly verify the following are in the scoped Allow set:

- Stack rollback: `ec2:CancelSpotInstanceRequests`, `autoscaling:CancelInstanceRefresh`, `cloudformation:ContinueUpdateRollback`
- DR restore: `rds:RestoreDBClusterFromSnapshot`, `rds:RestoreDBInstanceFromSnapshot`, `dynamodb:RestoreTableFromBackup`, `s3:RestoreObject` (Glacier)
- Drift remediation: `cloudformation:DetectStackDrift`, `cloudformation:DetectStackResourceDrift`
- Fresh-account bootstrap: `ec2:CreateDefaultVpc`, `kms:CreateGrant` (service-linked role binding)
- Cross-region replication: `s3:PutReplicationConfiguration`, `dynamodb:CreateGlobalTable` (per ADR-091 DR pattern)
- EKS edge: `iam:TagOpenIDConnectProvider`, `eks:UpdatePodIdentityAssociation`
- Neptune restore: `rds:RestoreDBClusterFromSnapshot` (Neptune uses `rds:` namespace), `rds:ModifyDBClusterSnapshotAttribute`

### Phase 2 — Implement in dev (2 days)

**2.1** Rewrite `CloudFormationServiceRole` policy in `iam.yaml` with the 8-statement structure (Statement 1: scoped mutate; Statement 2: tag-conditioned mutate; Statement 3: EC2 split; Statement 4: KMS bootstrap+operate; Statement 5: CloudWatch namespace; Statement 6: Logs CreateLogDelivery; Statement 7: Read-only wildcard; Statement 8: Denies).

**2.2 Plan for managed-policy split from day one** (NEW in v2, Tara + Jake findings) — Estimated final policy size is 8–10 KB inline, exceeding or close to the 10 KB inline limit. Pre-split design:

- Statements 1, 2, 3 (scoped + tag-conditioned mutate) → new `AWS::IAM::ManagedPolicy` named `${ProjectName}-cfn-role-mutate-policy-${Environment}`
- Statements 4–7 (KMS/CloudWatch/Logs/read-only) → second managed policy or inline (depending on size)
- Statement 8 (Denies) → inline on the role (Denies belong with the role for review clarity)

Pattern matches `deploy/cloudformation/CLAUDE.md` precedent (`codebuild-observability.yaml` managed policy split).

**2.3** Deploy to dev. Trigger every parent-layer CodeBuild project (`aura-foundation-deploy-dev` through `aura-security-deploy-dev`). Capture `AccessDenied` errors. Iterate: add missing actions to the scoped statement, redeploy, re-run.

### Phase 2.5 — Deliberate rollback exercise (1 day, NEW in v2, Jake finding)

Phase 2 only exercises green-path deploys. Phase 2.5 exercises rollback paths:

**2.5.1** Deliberately break a CFN template (e.g., introduce a circular dependency) in dev. Trigger a deploy. Confirm the rollback path succeeds with the new role — surfaces `Delete*` and `CancelUpdateStack`-class actions that don't fire on green deploys.

**2.5.2** Trigger drift detection across all stacks in dev. Surfaces per-resource `Describe*` actions that may be in Statement 7 but worth confirming.

### Phase 3 — Validate in QA (1 day)

**3.1** Deploy the new role to QA. Re-run the full deployment pipeline end-to-end.

**3.2** Confirm zero `AccessDenied` events in CloudTrail for the CFN role for 24 h.

**3.3** Run the cold-path checklist from Phase 1.4 explicitly in QA (deploy + delete a test DR stack, exercise a snapshot-restore path if a test snapshot exists).

### Phase 4 — Production rollout (1 day, gated by HITL)

**4.1** Deploy to production behind ADR-032 HITL approval gate. This change is a credential-modification scope per ADR-086 `IMMUTABLE_GUARDRAILS`.

**4.2** Monitor CloudTrail for 72 h post-deploy. Roll back if any `AccessDenied` surfaces.

**4.3** First production deploy after rollout: pick a low-risk stack (e.g., documentation site) rather than a critical-path layer.

### Phase 5 — Documentation

**5.1** Update root `CLAUDE.md` "IAM wildcards" section to reference this ADR.

**5.2** Update ADR-041's "Affected Templates" table — point the `iam.yaml` row at ADR-092 for the deploy role.

**5.3** Add an annual review item to the security calendar: re-confirm each retained wildcard in Statements 5, 6, 7 still has AWS-API justification, and re-confirm the `iam:PassedToService` allow-list still matches deployed services.

**5.4** Close #182's IAM-wildcards line item.

### Total estimate

7 days (was 5 in v1; +1 for Phase 1 expansion, +1 for Phase 2.5 rollback exercise).

## Compensating Controls (revised in v2)

The compensating controls are **additive** to ADR-041. The full layered defense:

1. **Permission boundaries** (ADR-041 §47) — unchanged. Applies to roles the CFN role *creates*, not the role itself.
2. **VPC endpoint policies** (ADR-041 §53) — unchanged.
3. **Region condition** (`aws:RequestedRegion`) — retained, but acknowledged as a regional-API jail rather than a hard region jail (see Context §3).
4. **NEW: Resource ARN scoping** for the 13 ARN-supporting services (Statements 1, 3 mutate, 4 operate, 7 mutate).
5. **NEW: Tag-conditioned scoping** for the 2 server-generated-ID services (Statement 2).
6. **NEW: Safety Deny** for prod-pattern resources in non-prod deploys (Statement 8.1) — re-labeled as safety control.
7. **NEW: Security Deny — Self-broadening** (Statement 8.2) — closes T1098.001.
8. **NEW: Security Deny — Project-tag requirement on mutate** (Statement 8.3) — narrows exfiltration scope.
9. **NEW: `iam:PassRole` `PassedToService` constraint** (Statement 8.4) — closes T1078.004.
10. **CloudTrail audit** (ADR-041 §86) — unchanged.
11. **GuardDuty threat detection** (ADR-041 §92) — unchanged.

### Rollback (revised in v2)

**v1's inline `!If` on `UseLegacyDeployRole` was rejected by Jake's review** because `RoleName` is immutable — flipping the parameter triggers role replacement, breaking every in-flight CodeBuild deploy and every IAM principal referencing the role ARN.

**v2 chooses:** **Two managed policies, conditionally attached** to the same role.

```yaml
CloudFormationServiceRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: !Sub '${ProjectName}-cfn-role-${Environment}'
    # ... unchanged trust policy ...
    ManagedPolicyArns:
      - !If
        - UseLegacyDeployRole
        - !Ref CloudFormationLegacyManagedPolicy
        - !Ref CloudFormationScopedManagedPolicy
    Policies:
      # Inline policy = Denies + read-only + IAM/CFN scoping that hasn't changed
      - PolicyName: CloudFormationDeploymentPolicyInline
        # ...
```

Switching `UseLegacyDeployRole` flips the managed policy reference without recreating the role. In-flight deploys finish under the policy that was attached at session-start; subsequent deploys pick up the new managed policy. Standard blue/green for IAM.

The legacy managed policy is retained as a CloudFormation resource for the first 30 days post-rollout, then deleted in Phase 5.

## Affected Templates

| Template | Lines | Change |
|---|---|---|
| `iam.yaml` | 319–341 (current); ~319–500+ (after) | Replace single 16-service wildcard statement with 8-statement structure. Add `CloudFormationScopedManagedPolicy` and `CloudFormationLegacyManagedPolicy` resources for blue/green rollback. |
| `iam.yaml` | 365 (current) | Add `iam:PassedToService` condition on `iam:PassRole` (Statement 8.4). |
| `CLAUDE.md` (root) | "IAM wildcards" subsection | Add reference to ADR-092. |
| `ADR-041` | "Affected Templates" table | Update `iam.yaml` row to point at ADR-092 for the deploy role. |

No other templates touched.

## Compliance Mapping (revised in v2 per Sally)

| Framework | Control | Before (ADR-041 only) | After (this ADR) | Caveat |
|---|---|---|---|---|
| CMMC AC.L2-3.1.3 | Control information flow | Compensated | Compensated + scoped | — |
| CMMC AC.L2-3.1.5 | Least privilege | Partial | **Substantially compliant** | Requires annual review (Phase 5.3) |
| NIST AC-3 | Access enforcement | Compensated | **Enforced (resource-level)** | — |
| NIST AC-6 | Least privilege | Partial | **Substantially compliant** | Requires each retained wildcard to have inline rationale + annual review |
| SOC 2 CC6.1 | Logical access | Compensated | Compensated + scoped | — |
| SOC 2 CC6.3 | Authorization | Partial | **Compliant** | Documented Deny semantics |
| ISO 27001 A.9.4.1 | Access restriction | Partial | Substantially compliant | — |

**Auditor expectation (Sally's note):** "AC-6 substantially compliant" language draws a question in audits. The defensible answer requires:

1. Each retained wildcard (Statements 5, 6, 7) has inline rationale citing AWS API constraints (e.g., comment block above `Resource: '*'` referencing the Service Authorization Reference)
2. Documented annual review confirming the retained-wildcard list hasn't grown
3. The `iam:PassedToService` allow-list matches the platform's deployed services

All three are addressed in Phase 5.

## Consequences

### Positive
- Account-wide blast radius narrows from 16 services to ~3 services for describe/list-class actions only (was 16 services full read/write/delete on `Resource: '*'`).
- Compliance posture upgrades: NIST AC-3 from "compensated" → "enforced"; AC-6 from "partial" → "substantially compliant".
- Each retained wildcard inline-documented with rationale (ADR-041 pattern).
- Self-broadening trust policy pivot (T1098.001) closed by Statement 8.2.
- IRSA chain via `iam:PassRole` (T1078.004) narrowed by Statement 8.4.
- Safety Deny catches name-collision deployment misconfig.

### Negative
- 7-day migration with phased rollout (dev → dev rollback exercise → qa → prod).
- Two new managed policies in `iam.yaml` (CFN deploy gains a managed-policy split).
- IAM policy size estimate revised to 8–10 KB pre-split. Stays under 10 KB inline limit *only* with the managed-policy split per `deploy/cloudformation/CLAUDE.md` rules.
- Each new CFN resource type added to the platform requires checking whether its actions are in the scoped set; missing actions surface as `AccessDenied` during deploy.
- `iam:PassedToService` allow-list (Statement 8.4) requires explicit update when a new consumer service is added.
- Slightly higher operational overhead — incidents involving deploy failures need to confirm the role has the required action before pursuing other root causes.

### Residual risks (after Option C + v2 additions, per Sally's read)

**Medium-low.** Primary remaining exposures:

1. The 3 documented wildcards (`ec2:Describe*` family, `cloudwatch:PutMetricData`, `logs:CreateLogDelivery` family) — reconnaissance-class, not exfiltration-class.
2. Global API bypass of `aws:RequestedRegion` for `iam:*` (already scoped), Route 53, Organizations reads, `s3:CreateBucket` global endpoint.
3. `aws:ResourceTag` is a no-op on some S3 read paths (S3 `GetObject` does not consult bucket tags by default) — narrows but does not eliminate cross-bucket read exposure within the project namespace.

Both #1 and #3 are appropriate for a NIST 800-53 aligned POA&M with quarterly review.

## References

- **Issue:** [#182](https://github.com/aenealabs/aura/issues/182) — tech-debt: lower-value cleanup tracker
- **Audit source:** Issue #163 (closed), GTM-readiness 8-lane audit, May 10, 2026
- **Precedent ADRs:**
  - ADR-041 — AWS-Required Wildcards with Defense-in-Depth Compensating Controls
  - ADR-043 — Repository Onboarding Wizard (IRSA roles in scope of `iam:PassRole`)
  - ADR-049 — Self-Hosted Deployment Strategy (ECR `aura-*` naming convention)
  - ADR-086 — Agentic Identity Lifecycle (`IMMUTABLE_GUARDRAILS` requires HITL on credential-modification scope)
- **Review credits (v2):** Three independent agent reviews on May 12, 2026 surfacing material corrections. Their analyses recommended Option C unanimously and are summarized in the GitHub issue #182 comment thread.
- **AWS docs:**
  - [Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/) — per-service resource-ARN support matrix
  - [IAM JSON Policy Element: Condition Operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html)
  - [aws:RequestedRegion condition key](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-requestedregion)
  - [iam:PassedToService condition key](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html#ck_PassedToService)
  - [aws:ResourceTag and tag-based service support matrix](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_tags.html)
- **MITRE ATT&CK techniques addressed:** T1098.001 (Statement 8.2), T1098.003 (existing IAM scope), T1078.004 (Statement 8.4), T1213.003 (Statements 1+3+7), T1485/T1486 (Statements 1+4+8.3).

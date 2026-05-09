# DR Compliance Controls Guide

**Last Updated:** 2026-05-09
**Tracked As:** DR-8 (#151), part of DR umbrella #143
**Owner:** Platform Engineering / Security
**Related Runbook:** `docs/runbooks/MULTI_REGION_DR_OPERATIONS.md` (DR-7)

---

## Purpose

Sally's review (NIST 800-53 CP-2 / CP-4(1) / CP-9 / CP-10) identified seven controls that must be in place for Aura's manual / semi-manual DR operations to be audit-defensible. Without these, the auditor's killer question -- *"show me the last successful end-to-end failover with measured RTO and approval chain"* -- has no acceptable answer.

This guide explains each control: what it does, where it's deployed, how to use it during a drill or incident, and how it generates audit evidence.

The seven controls map 1:1 to deployments in `deploy/cloudformation/dr-compliance-controls.yaml` (Layer 5.16) plus changes to `deploy/cloudformation/multi-region-pipeline.yaml` (Layer 6.22).

---

## Control 1: Two-Person Integrity (AC-3(2), AC-5)

**What it does:** No single IAM principal can advance the DR failover state machine past a HITL approval gate. Two distinct principals must independently invoke the `aura-dr-two-person-approval-{env}` Lambda for the same `approval_id` before `states:SendTaskSuccess` fires.

**Where deployed:**
- `aura-dr-two-person-approval-prod` Lambda (state-tracking + send-task-success caller)
- `aura-dr-two-person-approvals-prod` DynamoDB table (per-approval state with TTL)

**How to use during a failover gate:**

When the failover Step Functions pipeline pauses at a HITL gate, the row in `aura-hitl-approvals-prod` carries the task token. Both approvers invoke the two-person Lambda with their own caller identity:

```bash
APPROVAL_ID="failover-traffic-failover-20260509-143000"

# Get the task token from the HITL approvals row (operator runs this once)
TASK_TOKEN=$(aws dynamodb get-item \
    --table-name aura-hitl-approvals-prod \
    --key "{\"approval_id\": {\"S\": \"${APPROVAL_ID}\"}}" \
    --query 'Item.task_token.S' \
    --output text)

# Approver 1 invokes:
MY_ARN_1=$(aws sts get-caller-identity --query Arn --output text)

aws lambda invoke \
    --function-name aura-dr-two-person-approval-prod \
    --payload "$(jq -nc \
        --arg id "${APPROVAL_ID}" \
        --arg tt "${TASK_TOKEN}" \
        --arg arn "${MY_ARN_1}" \
        '{approval_id: $id, task_token: $tt, principal_arn: $arn, approval_payload: {approved: true}}')" \
    /tmp/approval-1.json

cat /tmp/approval-1.json
# Expected: {"status": "waiting_for_second_approver", ...}
```

After the FIRST invocation, the response is `waiting_for_second_approver`. Approver 2 (a different IAM principal) then runs the same command. The SECOND invocation triggers `SendTaskSuccess` and the state machine continues.

CloudTrail records both invocations independently (each with the invoker's caller ARN). A drill that produces an audit-defensible approval chain shows two distinct `lambda:Invoke` events for the same `approval_id`.

**Break-glass mode (emergency only):**

When a true 3am emergency makes two-person approval impossible, an operator with the `DR-BreakGlass=true` IAM tag can invoke with `break_glass: true`. The Lambda allows a single-principal `SendTaskSuccess` AND writes a high-severity audit record to `s3://aura-compliance-evidence-prod/break-glass/`. Per Sally: "solo deploys are not allowed except in genuine 3am emergencies, and those must produce an enhanced audit trail."

```bash
aws lambda invoke \
    --function-name aura-dr-two-person-approval-prod \
    --payload "$(jq -nc \
        --arg id "${APPROVAL_ID}" \
        --arg tt "${TASK_TOKEN}" \
        --arg arn "${MY_ARN_1}" \
        '{approval_id: $id, task_token: $tt, principal_arn: $arn, break_glass: true, approval_payload: {approved: true, justification: "primary region down, no second approver reachable"}}')" \
    /tmp/break-glass.json
```

Break-glass invocations are reviewed in the next post-incident report.

---

## Control 2: Pre-Signed Change-Sets

**What it does:** Separation of duties (SoD) between *authoring* a change-set and *executing* it. The release manager creates the change-set during business hours; the on-call only executes it during the actual failover.

**No infrastructure required** -- this is a deploy convention enforced by IAM policy + runbook discipline.

**How to use:**

```bash
# Release manager (business hours): create the change-set
aws cloudformation create-change-set \
    --stack-name aura-multi-region-pipeline-prod \
    --template-body file://deploy/cloudformation/multi-region-pipeline.yaml \
    --change-set-name "drill-prep-$(date -u +%Y%m%d)" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters ParameterKey=Environment,ParameterValue=prod \
    --region us-east-1

# Verify the change-set
aws cloudformation describe-change-set \
    --stack-name aura-multi-region-pipeline-prod \
    --change-set-name "drill-prep-$(date -u +%Y%m%d)" \
    --query 'Changes' \
    --output json

# On-call (failover time, separate IAM principal): execute the change-set
aws cloudformation execute-change-set \
    --stack-name aura-multi-region-pipeline-prod \
    --change-set-name "drill-prep-$(date -u +%Y%m%d)" \
    --region us-east-1
```

IAM enforcement (deploy policy):
- Release manager role: `cloudformation:CreateChangeSet` allowed; `cloudformation:ExecuteChangeSet` denied.
- On-call role: `cloudformation:ExecuteChangeSet` allowed; `cloudformation:CreateChangeSet` denied.

(IAM policy split is out of scope for the DR-8 template; track as a separate IAM hardening pass.)

---

## Control 3: Session Recording (AU-2 / AU-12)

**What it does:** All deploy commands during a DR event run inside an SSM Session Manager session whose stdin/stdout is captured to S3 + CloudTrail Data Events.

**Where deployed:**
- `aura-session-recording-{account}-prod` S3 bucket (1-year retention, AES-256)
- `aura-SessionManagerRunShell-DR-prod` SSM document (preferences with S3 logging enabled)

**One-time setup (after deploying dr-compliance-controls.yaml):**

The SSM document is deployed by CloudFormation, but setting it as the *account-level default* requires a one-time console action:

1. Open AWS Systems Manager console -> Session Manager -> Preferences -> Edit.
2. Under "Use default Session Manager preferences," select `aura-SessionManagerRunShell-DR-prod`.
3. Save.

Now every Session Manager session in the production account uses S3 logging by default. Ad-hoc sessions can override via the `--document-name` parameter, but the default is logged.

**How to use during a DR event:**

```bash
# Operator: start a session-recorded shell
aws ssm start-session \
    --target i-<bastion-instance-id> \
    --document-name aura-SessionManagerRunShell-DR-prod \
    --region us-east-1

# Inside the session, all commands are captured to:
#   s3://aura-session-recording-{account}-prod/sessions/prod/<session-id>/
```

Session output appears in S3 within ~1 minute of session end. CloudTrail's `StartSession` and `TerminateSession` events provide the timeline.

For DR drills: the runbook sequence (`MULTI_REGION_DR_OPERATIONS.md` steps 1-3) should be executed inside such a session. The evidence bundle includes the S3 session-output keys.

---

## Control 4: Lambda Code Signing

**What it does:** Failover Lambda code is signed by AWS Signer; deploy fails if the signature doesn't match. Hash drift = fail closed.

**Where deployed:**
- `DRSignerProfile` (AWS Signer profile, 5-year signature validity)
- `LambdaCodeSigningConfig` (Lambda code-signing config; `UntrustedArtifactOnDeployment: Enforce`)

**Current status: infrastructure only, not yet applied.**

The existing failover Lambdas (`UserSyncFunction`, `CognitoHydratorTriggerFunction`, `CognitoSSMCutoverFunction`, `DataPlaneSecretCutoverFunction`, `EvidencePackageFunction`, etc.) use inline code (`Code.ZipFile` in CloudFormation). AWS Signer requires S3-uploaded code; inline code cannot be signed.

**To activate code signing on a Lambda:**

1. Migrate the Lambda from `Code.ZipFile` to `Code.S3Bucket` + `Code.S3Key`.
2. Sign the artifact with `aws signer start-signing-job`.
3. Set `CodeSigningConfigArn` on the Lambda function:
   ```yaml
   MyFunction:
     Type: AWS::Lambda::Function
     Properties:
       CodeSigningConfigArn: !ImportValue aura-dr-lambda-code-signing-arn-prod
       Code:
         S3Bucket: aura-signed-lambda-artifacts-prod
         S3Key: my-function/v1.zip
       # ...
   ```
4. CloudFormation deploy validates the signature; mismatch -> deploy rejected.

**Tracked as a separate hardening pass.** Migrating ~6 inline failover Lambdas to signed S3 packages requires:
- A signed-artifact CI build step (add to `deploy/buildspecs/`)
- An `aura-signed-lambda-artifacts-prod` bucket
- Replacing each Lambda's `ZipFile` with an `S3Bucket` reference

The Signer profile is ready when those migrations land.

---

## Control 5: Cross-Region IAM Trust Scoping

**What it does:** Failover Lambda execution roles are scoped via `aws:RequestedRegion` so they cannot be assumed (or cannot pass-role) outside the DR context.

**Current status: documented but not yet enforced.**

The existing failover Lambda roles (e.g., `CognitoHydratorTriggerRole`) use the standard Lambda assume-role policy:

```yaml
AssumeRolePolicyDocument:
  Statement:
    - Effect: Allow
      Principal: {Service: lambda.amazonaws.com}
      Action: sts:AssumeRole
```

To enforce Sally's scope: add a Condition restricting `aws:RequestedRegion` to the primary or secondary region only:

```yaml
AssumeRolePolicyDocument:
  Statement:
    - Effect: Allow
      Principal: {Service: lambda.amazonaws.com}
      Action: sts:AssumeRole
      Condition:
        StringEquals:
          aws:RequestedRegion: [us-east-1, us-west-2]
```

For `iam:PassRole` denial during non-DR state: the failover Lambda roles are not currently passed via `iam:PassRole` from any other context (they're invoked directly by Step Functions / EventBridge). When that changes (e.g., if a future cross-account assume-role pattern is added), gate `iam:PassRole` with a custom condition keyed on a "DR active" SSM parameter.

**Tracked as a separate IAM hardening pass.** The existing IAM policies are functionally correct but have wider blast radius than Sally's review prefers.

---

## Control 6: Evidence-Package Generation

**What it does:** Every DR drill / incident produces an evidence package: state-machine ARN + execution name, approver IDs, start/end timestamps, RTO measurement, alarm states, full state-machine history. Stored under `s3://aura-compliance-evidence-{account}-prod/<quarter>/<execution-name>/` with Object Lock GOVERNANCE + ~7-year retention (SOX alignment).

**Where deployed:**
- `aura-compliance-evidence-{account}-prod` S3 bucket (Object Lock + lifecycle to STANDARD_IA at 90d / GLACIER at 365d)
- `aura-dr-evidence-package-prod` Lambda (manifest generator)
- Wired into `multi-region-pipeline.yaml`: `CaptureEvidenceSuccess`, `CaptureEvidenceRollback`, `CaptureEvidenceFailure` states are appended to each terminal of the failover state machine

**Automatic invocation:**

Every Step Functions execution of `aura-multi-region-failover-prod` calls the evidence Lambda before terminating. No operator action required for the standard case.

The evidence Lambda is fail-soft via Catch -- if dr-compliance-controls.yaml hasn't been deployed yet (the Lambda doesn't exist), the state machine catches the error and routes to `EvidenceSkipped` (Pass state). The execution still terminates cleanly.

**Manual invocation (post-hoc enrichment):**

After a drill, the operator captures the measured RTO + drill notes:

```bash
aws lambda invoke \
    --function-name aura-dr-evidence-package-prod \
    --payload "$(jq -nc \
        --arg arn "<execution-arn>" \
        --arg op "<your-name>" \
        --argjson rto 47.5 \
        --arg notes "Quarterly drill; Cognito hydration ran clean; Neptune restore took 38min" \
        '{execution_arn: $arn, kind: "drill", operator: $op, rto_minutes: $rto, notes: $notes}')" \
    /tmp/evidence.json

cat /tmp/evidence.json
# Returns: {"evidence_prefix": "s3://aura-compliance-evidence-...-prod/2026-Q2/.../", ...}
```

The package contents:
- `manifest.json` -- structured summary (operator, kind, timing, approver counts, RTO)
- `execution_history.json` -- full state-machine event history
- `hitl_approvals.json` -- HITL approval rows with task tokens (redacted) + timestamps
- `two_person_approvals.json` -- two-person approval state with distinct principal ARNs

Auditor query: *"Show me the last successful failover with the approval chain."*
Answer: `aws s3 ls s3://aura-compliance-evidence-{account}-prod/$(date -u '+%Y-Q%q')/` -> pick the most recent execution -> open `manifest.json`.

---

## Control 7: Drill-Cadence Enforcement

**What it does:** A weekly Lambda checks the evidence bucket for the most recent manifest.json. If older than 90 days, a CloudWatch alarm fires (and pages the on-call via the DR alert SNS topic). Quarterly drills land packages every ~90 days, so a missed drill surfaces immediately.

**Where deployed:**
- `aura-dr-drill-cadence-prod` Lambda (weekly invocation)
- `aura-dr-drill-cadence-schedule-prod` EventBridge rule (Mondays 14:00 UTC)
- `Aura/DR DrillStalenessDays` CloudWatch metric
- `aura-dr-drill-cadence-stale-prod` alarm (threshold = 90 days, configurable)

**No operator action required.** The schedule runs on its own. The alarm wires to the DR SNS topic if `DRAlertTopicArn` parameter is provided at deploy time.

**Manual check (anytime):**

```bash
aws lambda invoke \
    --function-name aura-dr-drill-cadence-prod \
    --payload '{}' \
    /tmp/cadence.json
cat /tmp/cadence.json
# {"age_days": 47, "threshold_days": 90, "alarm_state": "OK", ...}
```

If age_days > 90, schedule a drill before the alarm pages on-call.

---

## What's NOT in DR-8 scope

- IAM policy split for Control 2 (release-manager vs on-call). Tracked as a separate IAM hardening pass.
- S3-package migration for Control 4 (existing inline-code Lambdas can't be signed). Tracked as a separate Lambda-signing hardening pass.
- aws:RequestedRegion / aws:RequestedRegion-conditioned PassRole for Control 5. Tracked as a separate IAM hardening pass.
- One-time SSM Session Manager default-document selection (Control 3). Console action documented above; not codified.

These follow-ups are pre-decided as "infrastructure ready, enforcement is the next pass." The DR umbrella (#143) now closes; specific hardening tickets can be filed against the IAM and Lambda surfaces as standalone work.

---

## How drills produce audit evidence

Quarterly drill workflow:

1. Operator starts an SSM Session Manager session (Control 3).
2. Operator triggers `start-execution` on `aura-multi-region-failover-prod` (DR-7 runbook Step 1.1).
3. Pipeline pauses at HITL gates. Operators 1 + 2 each invoke the two-person approval Lambda (Control 1).
4. Pipeline runs to NotifyComplete (or NotifyRollback / NotifyFailure for off-nominal drills).
5. CaptureEvidence state automatically invokes the evidence Lambda (Control 6).
6. Operator post-hoc invokes the evidence Lambda again with the measured RTO + notes (Control 6).
7. Drill-cadence Lambda picks up the new package on the next Monday run (Control 7); CloudWatch metric refreshed.
8. Auditor receives `s3://...-evidence-.../<quarter>/<execution>/manifest.json` as the audit artifact.

End-to-end audit trail without a single ad-hoc spreadsheet.

---

## References

- DR umbrella: #143
- DR-8: #151 (this guide)
- `deploy/cloudformation/dr-compliance-controls.yaml` -- Layer 5.16
- `deploy/cloudformation/multi-region-pipeline.yaml` -- Layer 6.22 (evidence wiring)
- `docs/runbooks/MULTI_REGION_DR_OPERATIONS.md` -- DR-7 operations runbook (this guide layers compliance on top)
- NIST 800-53 controls referenced: AC-3(2), AC-5, AU-2, AU-12, CP-2, CP-4(1), CP-9, CP-10, IA-2(1)/(2), IA-5, IA-5(7), SC-12, SC-28

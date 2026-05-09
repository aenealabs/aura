# Cognito Cross-Region Failover Runbook

**Last Updated:** 2026-05-09
**Tracked As:** Tier 1 (RTO 1h / RPO 15m) per `docs/support/architecture/disaster-recovery.md`
**Owner:** Platform Engineering
**Sub-issue:** DR-2 (#145) closed via ADR-091 + this runbook
**ADR:** `docs/architecture-decisions/ADR-091-cognito-cross-region-disaster-recovery.md`
**DR umbrella:** #143

---

## Overview

This runbook covers Cognito user pool failover from the primary region (`us-east-1`) to the secondary region (`us-west-2`). It is the operational procedure that pairs with the infrastructure deployed by:

- `deploy/cloudformation/cognito.yaml` (Layer 4.4) -- primary user pool with PostConfirmation / PostAuthentication triggers
- `deploy/cloudformation/user-mirror-table.yaml` (Layer 2.22) -- DDB Global Table mirror
- `deploy/cloudformation/cognito-secondary.yaml` (Layer 4.14) -- standby user pool
- `deploy/cloudformation/cognito-dr-hydrator.yaml` (Layer 6.21) -- hydrator Lambda

**Why a runbook is unavoidable:** Cognito has no native cross-region replication, no AWS Backup support, and tokens are pool-bound -- a session in user-pool-A is not valid in user-pool-B even if the user record is mirrored. Failover requires the operator to (a) hydrate the standby pool from the mirror, (b) cut application traffic over to the standby pool, (c) communicate to users that they must reset their password and re-enroll MFA on first login. ADR-091 covers the design rationale.

## What's already in place

- **Primary user pool** (`us-east-1`) writes user state changes to the user-mirror Global Table on `PostConfirmation` (signup) and `PostAuthentication` (subsequent logins). Best-effort writes -- a mirror error never blocks the auth flow.
- **User-mirror Global Table** replicates `{sub, email, groups, mfa_enabled_flag, dr_eligible, timestamps}` to `us-west-2`. Sub-second replication typically; CloudWatch alarm at 60s lag.
- **Standby user pool** (`us-west-2`) is empty under normal operation; mirrors primary password policy / MFA / groups / app-client config.
- **Hydrator Lambda** (`us-west-2`) is deployed but its EventBridge schedule is `DISABLED` by default. A CloudWatch alarm fires if the hydrator is invoked.
- **Standby pool client ID + pool ID** are stored in SSM at `/aura/${env}/cognito-dr/standby-pool-id` and `/aura/${env}/cognito-dr/standby-client-id`.

## Failover decision criteria

Execute this procedure only when one of the following is true:

1. **Primary region declared unavailable** by AWS Health Dashboard or internal incident command.
2. **Cognito service in `us-east-1`** is in confirmed degraded state for > 30 minutes per AWS status page or successful auth rate < 50% in primary.
3. **Disaster recovery drill** scheduled per `docs/support/architecture/disaster-recovery.md` quarterly cadence.

## Pre-failover checklist

- [ ] Incident commander has declared failover.
- [ ] Mirror replication-lag alarm checked: `CloudWatch console -> Alarms -> aura-user-mirror-replication-lag-prod`. If alarming, document expected RPO exposure.
- [ ] Approximate user count in mirror table known: `aws dynamodb scan --table-name aura-user-mirror-prod --select COUNT --region us-west-2`. Hydration time is ~1 minute per 60 users.
- [ ] Customer-comms templates pre-staged in `s3://aura-compliance-evidence/dr-comms-templates/cognito-failover/`.
- [ ] Standby pool config drift check passes (`aws cognito-idp describe-user-pool --user-pool-id <standby-id> --region us-west-2` matches the primary pool's relevant fields).

## Failover procedure

### Step 1: Suppress the unauthorized-invocation alarm

The hydrator alarm fires whenever the Lambda is invoked. Suppress it for the duration of the failover so operators are not paged for expected activity.

```bash
ENV=prod
PROJECT=aura
SECONDARY_REGION=us-west-2

aws cloudwatch set-alarm-state \
    --alarm-name "${PROJECT}-cognito-dr-hydrator-invoked-${ENV}" \
    --state-value INSUFFICIENT_DATA \
    --state-reason "Active failover drill / incident -- invocation expected" \
    --region "${SECONDARY_REGION}"
```

### Step 2: Enable the hydrator schedule

```bash
aws events enable-rule \
    --name "${PROJECT}-cognito-dr-hydrator-schedule-${ENV}" \
    --region "${SECONDARY_REGION}"
```

The hydrator runs every 5 minutes. Each invocation processes up to `BATCH_SIZE` (default 25) users from the mirror table.

### Step 3: Monitor hydration progress

```bash
aws logs tail "/aws/lambda/${PROJECT}-cognito-dr-hydrator-${ENV}" \
    --since 5m \
    --follow \
    --region "${SECONDARY_REGION}"
```

Look for `hydrator-summary` log lines. When `has_more=False`, hydration is complete:

```json
{"processed": 12, "hydrated": 12, "skipped": 0, "errors": 0, "has_more": false}
```

If the scan paginates beyond a single invocation (`has_more=true`), the next scheduled invocation continues from `LastEvaluatedKey`. The hydrator is idempotent: `UsernameExistsException` is treated as success, so re-running across overlapping pages is safe.

### Step 4: Validate hydration

```bash
# User count in standby pool (should match mirror table count, minus dr_eligible=False)
aws cognito-idp list-users \
    --user-pool-id "$(aws ssm get-parameter --name /aura/${ENV}/cognito-dr/standby-pool-id --region ${SECONDARY_REGION} --query Parameter.Value --output text)" \
    --region "${SECONDARY_REGION}" \
    --query 'length(Users)' \
    --output text

# Spot-check: pick one mirror record and verify in standby pool
SAMPLE_EMAIL=$(aws dynamodb scan \
    --table-name "${PROJECT}-user-mirror-${ENV}" \
    --limit 1 \
    --region "${SECONDARY_REGION}" \
    --query 'Items[0].email.S' \
    --output text)

aws cognito-idp admin-get-user \
    --user-pool-id "$(aws ssm get-parameter --name /aura/${ENV}/cognito-dr/standby-pool-id --region ${SECONDARY_REGION} --query Parameter.Value --output text)" \
    --username "${SAMPLE_EMAIL}" \
    --region "${SECONDARY_REGION}"
```

Verify the user exists with `UserStatus=RESET_REQUIRED` (forced reset on first login).

### Step 5: Customer comms

Send the pre-staged failover-comms email to all affected users. Template is at `s3://aura-compliance-evidence/dr-comms-templates/cognito-failover/`. Key points:

- Password reset is required on next login.
- MFA re-enrollment is required for users who had MFA enabled (the application's auth UI enforces this based on `mfa_enabled_flag` in the mirror).
- Self-service password reset works against the standby pool's hosted UI (URL change is transparent to the customer if the application uses the SSM parameters).

### Step 6: Cut application traffic to the standby pool

The application reads Cognito pool ID and client ID from SSM at cold-start. Update those parameters to the standby values; restart the frontend / API workloads in the secondary region.

```bash
STANDBY_POOL_ID=$(aws ssm get-parameter --name /aura/${ENV}/cognito-dr/standby-pool-id --region ${SECONDARY_REGION} --query Parameter.Value --output text)
STANDBY_CLIENT_ID=$(aws ssm get-parameter --name /aura/${ENV}/cognito-dr/standby-client-id --region ${SECONDARY_REGION} --query Parameter.Value --output text)

# Update primary-region SSM (if reachable) so any surviving primary workloads
# also pick up the new pool. If primary SSM is unreachable, this can wait.
aws ssm put-parameter \
    --name /aura/${ENV}/cognito/user-pool-id \
    --value "${STANDBY_POOL_ID}" \
    --type String \
    --overwrite \
    --region us-east-1 || true

aws ssm put-parameter \
    --name /aura/${ENV}/cognito/client-id \
    --value "${STANDBY_CLIENT_ID}" \
    --type String \
    --overwrite \
    --region us-east-1 || true

# Update secondary region (these may not exist yet -- create if not)
aws ssm put-parameter \
    --name /aura/${ENV}/cognito/user-pool-id \
    --value "${STANDBY_POOL_ID}" \
    --type String \
    --overwrite \
    --region "${SECONDARY_REGION}"

aws ssm put-parameter \
    --name /aura/${ENV}/cognito/client-id \
    --value "${STANDBY_CLIENT_ID}" \
    --type String \
    --overwrite \
    --region "${SECONDARY_REGION}"
```

Application workloads in the secondary region must be restarted to pick up the new SSM values (cold-start re-reads SSM).

### Step 7: Validate authentication

Pick a known user, perform the password-reset flow against the standby Hosted UI:

```
https://aura-prod-${ACCOUNT_ID}-dr.auth.us-west-2.amazoncognito.com/login?client_id=${STANDBY_CLIENT_ID}&response_type=code&...
```

Confirm: forgot-password email arrives, password reset succeeds, MFA enrollment is forced (if `mfa_enabled_flag=true`), application JWT validates against the secondary pool's issuer URL.

### Step 8: Disable the hydrator schedule

After hydration completes (`has_more=false` for two consecutive invocations), disable the schedule to prevent unnecessary scans:

```bash
aws events disable-rule \
    --name "${PROJECT}-cognito-dr-hydrator-schedule-${ENV}" \
    --region "${SECONDARY_REGION}"
```

Re-arm the alarm (clear the suppressed state) so future unauthorized invocations are detected.

## Post-failover follow-up

- File an incident report capturing actual RTO + RPO measurements, hydration runtime, count of users who needed re-registration (RPO violations).
- Update `docs/support/architecture/disaster-recovery.md` if new operational details emerged.
- Plan reverse hydration when the primary region is restored. Approach: write a one-shot reverse-hydrator job that scans the secondary pool and the mirror table, and rebuilds the primary pool from the mirror. The reverse-hydrator is not currently codified as a Lambda -- this is a known follow-up tracked separately.
- Capture audit evidence per Sally's NIST review:
  - CloudTrail logs for every `AdminCreateUser`, `AdminAddUserToGroup`, `AdminResetUserPassword` invocation (auto-collected, no manual step).
  - Hydrator Lambda CloudWatch logs (365-day retention -- audit evidence per AC-6(9)).
  - Drift detection report for the standby pool config at the time of failover (DR-9 dr-monitoring.yaml output).

## Rollback (failover wasn't needed)

If you started the hydrator but later determined failover wasn't necessary:

```bash
# Disable the schedule
aws events disable-rule \
    --name "${PROJECT}-cognito-dr-hydrator-schedule-${ENV}" \
    --region "${SECONDARY_REGION}"

# Optionally, delete the partial hydration to keep the standby pool empty.
# DELETE-USER IS DESTRUCTIVE -- only run this if you're sure no traffic was
# cut over yet. Confirm SSM still points at the primary pool first:
aws ssm get-parameter --name /aura/${ENV}/cognito/user-pool-id --query Parameter.Value --output text

# If still primary, rebuild the empty standby state:
STANDBY_POOL_ID=$(aws ssm get-parameter --name /aura/${ENV}/cognito-dr/standby-pool-id --region ${SECONDARY_REGION} --query Parameter.Value --output text)

aws cognito-idp list-users \
    --user-pool-id "${STANDBY_POOL_ID}" \
    --region "${SECONDARY_REGION}" \
    --query 'Users[].Username' \
    --output text | tr '\t' '\n' | while read username; do
        aws cognito-idp admin-delete-user \
            --user-pool-id "${STANDBY_POOL_ID}" \
            --username "${username}" \
            --region "${SECONDARY_REGION}"
    done
```

## Drill cadence

Per `docs/support/architecture/disaster-recovery.md`:

- **Quarterly:** drill the hydrator (enable schedule, verify hydration, disable). Use a synthetic test mirror table or a separate drill-only standby pool.
- **Annual:** end-to-end failover drill including SSM cutover (carefully -- this affects real users).

Each drill should produce evidence per Sally's controls (DR-8 / #151 when that ships): timestamped logs, measured RTO, signed approval ticket. Until DR-8 lands, capture drill artifacts manually under `s3://aura-compliance-evidence/dr-drills/<quarter>/`.

## Known limitations (documented in ADR-091)

- **Forced password reset on first post-failover login.** Cognito does not expose password hashes; replication is impossible without exposing them. Compensating control: standard email-OTP forgot-password flow, new password meeting the 12-character policy.
- **Forced MFA re-enrollment for users with MFA enabled.** TOTP / WebAuthn secrets are pool-bound. The `mfa_enabled_flag` in the mirror drives application-level enforcement: the auth UI requires TOTP enrollment on first login when the flag is True.
- **In-flight new-user RPO exposure.** Users who signed up in the 0-15 minute window before primary failure whose `PostConfirmation` trigger had not yet replicated to the secondary mirror table will need to re-register, not just re-auth. Mitigated by sub-second Global Table replication (typically); CloudWatch alarm fires if lag exceeds 60s.
- **Hydrator IAM role is privileged.** Audit-logged per AC-6(9). Mitigated by alarm on every invocation.

## References

- ADR-091: `docs/architecture-decisions/ADR-091-cognito-cross-region-disaster-recovery.md`
- DR umbrella: #143; DR-2: #145
- `docs/runbooks/NEPTUNE_FAILOVER_RUNBOOK.md` -- companion runbook (DR-3 / #146)
- `docs/runbooks/OPENSEARCH_FAILOVER_RUNBOOK.md` -- companion runbook (DR-4 / #147)
- `docs/support/architecture/disaster-recovery.md` -- service tier definitions and RTO/RPO targets
- This runbook closes: DR-2 (#145)

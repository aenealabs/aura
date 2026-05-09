# ADR-091: Cognito Cross-Region Disaster Recovery

**Status:** Accepted
**Date:** 2026-05-09
**Tracked As:** DR-2 (#145) under DR umbrella #143
**Sub-issue note:** The DR-2 issue body explicitly recommended a design doc / mini-ADR before implementation. This ADR is that artifact.

---

## Context

Project Aura's customer-facing authentication uses AWS Cognito (`deploy/cloudformation/cognito.yaml`, Layer 4.4): email/password, optional MFA in production (TOTP only), 12-character password policy, 4 user groups (admin / security_engineer / security_analyst / viewer), hosted UI for OAuth/PKCE. Cognito is single-region; a primary-region failure leaves users unable to authenticate.

The DR-2 scope (#145) requires:

- Tier 1 commitment: RTO 1h / RPO 15m.
- Pattern alignment with DR-3 / DR-4: passive DR + failover runbook is acceptable when active replication is too costly or unsupported.
- NIST 800-53 alignment (no FedRAMP / CMMC certification pursued).

External IdPs (LDAP / OIDC / SAML / PingID) are out of scope -- their cross-region replication is the IdP's responsibility, not Aura's. Their credential templates are already covered by DR-1 (Global Tables for `IdPConfigurationsTable` and `OAuthConnectionsTable`).

## Constraints

Cognito-specific limitations that drove this decision:

1. **No native cross-region replication.** Cognito user pools cannot be replicated across regions natively.
2. **Not supported by AWS Backup.** The DR-3 / DR-4 pattern (AWS Backup hourly snapshot + cross-region copy + restore) does not apply.
3. **Tokens are pool-bound.** Tokens issued by user-pool-A do not validate against user-pool-B even if user records are mirrored. Failover unavoidably requires re-authentication.
4. **Password hashes are not exposed.** No Cognito API returns password hashes; Lambda triggers see plaintext passwords only at signup/reset events. The hash itself cannot be replicated.
5. **MFA secrets are pool-bound.** TOTP secrets and WebAuthn credentials are scoped to the issuing pool and cannot be replicated. This is also a security property (NIST IA-5(7): no embedded authenticators).

## Decision

**Approach: Lambda-based replication of user state to a DynamoDB Global Table + pre-deployed empty standby user pool in `us-west-2` + force re-auth (and MFA re-enrollment) on failover.**

Architecture:

- A new DynamoDB Global Table `${ProjectName}-user-mirror-${Environment}` (Layer 2.22, `user-mirror-table.yaml`) replicates user-state attributes between `us-east-1` and `us-west-2`. Per-replica Tags / PITR / top-level `StreamSpecification` (DR-1 pattern). Replicas in `us-east-1` and `us-west-2`. Production-only, gated on `IsProduction`.
- Per-region customer-managed KMS keys (NOT MRKs) for the user-mirror table -- consistent with DR-1.0 SC-12 guidance: `UserMirrorKMSKey` in `kms.yaml` (us-east-1) and `UserMirrorReplicaKey` in `kms-replica-secondary.yaml` (us-west-2).
- Cognito Lambda triggers in `cognito.yaml` (Layer 4.4): `PostConfirmation` (write user record) and `PostAuthentication` (refresh `last_modified` for active-user analytics + drift detection). Triggers run in primary region only; replication is via the Global Table.
- Empty pre-deployed standby user pool in `us-west-2` (Layer 4.14, `cognito-secondary.yaml`): same app-client config, groups, hosted-UI domain, MFA / password policy.
- Hydrator Lambda in `us-west-2` (Layer 6.21, `cognito-dr-hydrator.yaml`): scans the user-mirror table and creates corresponding users in the standby pool via `AdminCreateUser` (`MessageAction=SUPPRESS`) + `AdminAddUserToGroup`. EventBridge schedule **disabled by default**; enabled at failover time only.
- Forced password reset on first post-failover login: hydrator calls `AdminResetUserPassword` for every hydrated user. Users receive an email OTP, set a new password meeting the 12-character policy.
- MFA re-enrollment forced for users with `mfa_enabled_flag=true` in the mirror table.

Mirror table schema (minimal PII per Sally's NIST guidance):

```
PK: sub (UUID, Cognito user identifier)
Attributes:
  email             (string, required)
  groups            (string set: admin/security_engineer/security_analyst/viewer)
  created_at        (ISO 8601 timestamp)
  last_modified     (ISO 8601 timestamp)
  mfa_enabled_flag  (boolean -- IS MFA enabled, NOT the secret itself)
  dr_eligible       (boolean -- per-tenant gate for future regional-residency requirements)
```

Failover procedure (`docs/runbooks/COGNITO_FAILOVER_RUNBOOK.md`):

1. Incident commander declares failover.
2. Enable EventBridge schedule for hydrator Lambda in `us-west-2`.
3. Hydrator processes the mirror table -> `AdminCreateUser` + group assignments + `AdminResetUserPassword`.
4. Update SSM parameters with secondary pool ID + client IDs (the application reads these at cold-start).
5. Customer comms: "Password reset required. MFA re-enrollment required for users who had MFA enabled."
6. Validate authentication against secondary pool.

## Alternatives Considered

| Approach | Why rejected |
|----------|--------------|
| **Identity broker (Auth0 / Okta / FusionAuth)** | Routes customer auth through external processor. Expands NIST SC-7 boundary, creates new SA-9 dependency, breaks "Cognito is the customer-facing auth path" decision. Cost: ~$15K-50K+/yr. Not viable for a 1-week close. |
| **Periodic ListUsers export -> S3 -> CRR -> rehydrate** | `ListUsers` is rate-limited (~5 RPS effective) -- full pool export at scale exceeds 15-minute RPO. Creates CSV/JSON snapshot of user records on disk: unnecessary AU-9 / SC-28 attack surface. |
| **Pure force-re-auth with empty standby pool, no mirror** | Violates RPO 15m. New users who signed up between the last mirror sync and the primary-region failure have no record in the secondary -- they would have to re-register, not just re-auth. Unacceptable for a B2B SaaS where new-tenant signups are revenue events. |
| **Pursue AWS adding native Cognito cross-region replication** | Not in our control; DR commitment is now. Reassess if/when AWS ships native replication. |

## Consequences

### Positive

- Tier 1 RPO 15m is achievable: DynamoDB Global Tables typically replicate sub-second, so the mirror lag is far below the commitment window.
- Tier 1 RTO 1h is achievable: hydration runtime is bounded by `AdminCreateUser` throughput (~1 RPS effective per region), so a ~1000-user pool hydrates in ~15 minutes; remaining ~45 minutes covers SSM cutover + validation + customer comms.
- Annual cost ~$200-400 (Lambda invocations + DDB Global Table for the mirror; secondary pool itself is free until users exist).
- Stays in CFN-native passive-DR territory; matches the DR-3 / DR-4 pattern.
- Compliance posture: Sally's NIST review confirmed acceptable for IA-2, IA-5, AU-9, SC-12 with the documented compensating controls.

### Negative

- **Forced password reset on failover** is a UX cost. Documented and accepted; mitigated via in-product banner, email comms template, and the Cognito self-service ForgotPassword flow.
- **MFA re-enrollment required** for users with `mfa_enabled_flag=true`. Documented; the `mfa_enabled_flag` lets the hydrator enforce re-enrollment programmatically.
- **In-flight new users may be lost.** Users who signed up in the 0-15 minute window before primary failure whose `PostConfirmation` trigger had not yet replicated will need to re-register. Mitigated by sub-second Global Table replication, alarm at 60s replication lag, and Cognito self-service signup against the standby pool. This is the smallest exposure window achievable without active-active.
- **Hydrator IAM role is privileged.** `cognito-idp:AdminCreateUser`, `AdminAddUserToGroup`, `AdminResetUserPassword`. Mitigated per Sally: every invocation logged to CloudTrail + the audit pipeline; the role is gated behind a failover-only condition; treated as a Tier 1 audited identity under AC-6(9).

### Compliance Bake-Ins (per Sally's review)

- **IA-2(1)/(2):** MFA re-enrollment forced for users with MFA enabled. The `mfa_enabled_flag` drives the enforcement decision; the secret itself is never replicated.
- **IA-5:** Password reset via standard Cognito email-OTP flow. New password must meet the 12-character policy. Document as compensating control under "authenticators are re-established via out-of-band email channel during regional failover."
- **AU-9:** Hydrator IAM role is privileged and must be audited. Every `AdminCreateUser` / `AdminAddUserToGroup` / `AdminResetUserPassword` call is logged to CloudTrail; CloudTrail feeds the existing audit pipeline (DR-1.1).
- **SC-12:** Per-region CMKs (NOT MRKs) for the user-mirror table. Consistent with DR-1.0.
- **SC-28:** Mirror table encrypted at rest with the per-region CMK. Standby pool uses default Cognito KMS (per-region by AWS).
- **CP-2 / CP-4(1):** Failover runbook tested quarterly. Customer-comms templates pre-staged.

### Drift Mitigation

- Standby pool config drift detection: weekly comparison of the primary and secondary user-pool clients, password policies, MFA settings, group definitions. Drift detection extends DR-9's existing cross-region drift detection Lambda.
- The hydrator's EventBridge schedule defaults to disabled. CloudFormation deployments should preserve the disabled state; an alarm fires if the schedule is enabled outside of an active failover.

## Sub-Tasks Tracked Separately

- Pre-staged customer-communication templates for the failover scenario (out of scope; tracked under DR-7 orchestration).
- Per-tenant `dr_eligible` enforcement at the Lambda trigger: implemented as a no-op gate today (every record is mirrored); enforcement layer waits for the multi-tenant feature work.
- Reverse hydration after primary recovery: documented in the runbook as a Phase 2 follow-up; not blocking DR-2 closure.

## References

- DR initiative umbrella: #143
- DR-2 sub-issue: #145
- DR-1.0 (per-region CMK precedent): #153
- DR-3 / DR-4 (passive DR pattern precedent): #146 / #147
- DR-9 (drift detection): #152
- `deploy/cloudformation/cognito.yaml` -- existing primary user pool
- `deploy/cloudformation/cognito-secondary.yaml` -- new (this ADR)
- `deploy/cloudformation/user-mirror-table.yaml` -- new (this ADR)
- `deploy/cloudformation/cognito-dr-hydrator.yaml` -- new (this ADR)
- `docs/runbooks/COGNITO_FAILOVER_RUNBOOK.md` -- new (this ADR)
- `docs/support/architecture/disaster-recovery.md` -- updated for DR-2 closure

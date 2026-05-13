# Cost-Gate Deferred Work

**Last reviewed:** May 13, 2026 (added #180 residuals on close-out)
**Next review:** August 13, 2026 (quarterly)
**Owner of this registry:** Platform team

---

## Purpose

This file is the single, grep-able registry of every item paused pending an external condition -- most commonly the cost-gate (live-AWS budget restoration), occasionally other event-driven conditions like external-endpoint provisioning or review-capacity availability. It exists because:

* Open GitHub issues that sit for indeterminate periods erode signal-to-noise in the issue tracker.
* The deferral trigger is **event-driven**, not time-driven, so a cron / milestone is the wrong shape.
* On Day-1 budget restoration (or external-endpoint provisioning), the operator needs to walk a single canonical list of "what was paused and what's the re-engage condition" -- not grep through 90+ ADRs.

**Source of truth remains the ADR's phase tracker (for ADR-derived items) or the closing comment of the originating issue (for issue-derived items).** This file is the discovery index that points back to those.

---

## Operating model

* **Adding an entry:** when an ADR (or sub-phase) is accepted with deploy phases marked Deferred (Cost Gate), add a row below in the same PR that lands the ADR.
* **Removing an entry:** when the deferred phase ships (or is explicitly cancelled), delete the row in the same PR that closes it; mention this file in the commit body.
* **Quarterly review** (next: 2026-08-13): walk every row, confirm:
  1. The deferral is still relevant (sometimes the work is obviated by an alternate path).
  2. The re-engage-when condition is still accurate.
  3. The owner is still the right person.
  4. If the answer to any of the above is "no," update the row or remove it with a note in git history.
* **Day-1 budget restoration playbook:** open this file, walk the table top-to-bottom, schedule each entry against the live-AWS calendar based on its dependencies.

---

## Deferred items

| Item | ADR / source | Description | Re-engage when | Owner | Added |
|------|---|---|---|---|---|
| **ADR-092 Phase 1** | [ADR-092](architecture-decisions/ADR-092-cfn-deploy-role-wildcard-scoping.md) | CloudTrail Lake inventory + `cfn-policy-validator` + DR replay + cold-path checklist. **Offline substitute shipped:** `scripts/adr_092_static_action_scan.py` + `docs/assessments/ADR_092_STATIC_SCAN_REPORT.md`. | Live-AWS budget restored OR static substitute deemed sufficient | Platform team | 2026-05-12 |
| **ADR-092 Phase 3** | [ADR-092](architecture-decisions/ADR-092-cfn-deploy-role-wildcard-scoping.md) | Validate `iam.yaml` against dev with `UseLegacyDeployRole=false`; exercise every CodeBuild project; capture any AccessDenied. | Live-AWS budget restored | Platform team | 2026-05-12 |
| **ADR-092 Phase 3.5** | [ADR-092](architecture-decisions/ADR-092-cfn-deploy-role-wildcard-scoping.md) | Deliberately fail a deploy to exercise rollback path on the scoped policy. | Live-AWS budget restored | Platform team | 2026-05-12 |
| **ADR-092 Phase 4** | [ADR-092](architecture-decisions/ADR-092-cfn-deploy-role-wildcard-scoping.md) | Validate scoped role against QA; 24-h zero-AccessDenied watch. | Live-AWS budget restored AND ADR-092 Phase 3 green | Platform team | 2026-05-12 |
| **ADR-092 Phase 5** | [ADR-092](architecture-decisions/ADR-092-cfn-deploy-role-wildcard-scoping.md) | Production rollout behind ADR-032 HITL approval gate (credential-modification scope per ADR-086 `IMMUTABLE_GUARDRAILS`). | Live-AWS budget restored AND ADR-092 Phases 3 + 4 green | Platform team | 2026-05-12 |
| **ADR-092 Phase 6** | [ADR-092](architecture-decisions/ADR-092-cfn-deploy-role-wildcard-scoping.md) | Documentation update + annual-review commitment + close-out of #182 IAM line. | After ADR-092 Phase 5 succeeds (so docs reflect deployed reality) | Platform team | 2026-05-12 |
| **ADR-093 Phase 6** | [ADR-093](architecture-decisions/ADR-093-neptune-cross-file-taint-resolver.md) | First-prod-scan of Neptune-backed taint resolver against single test tenant; feature flag on, kill-switch hot-standby, all 5 alarms armed. | Live-AWS budget restored AND ADR-093 Phases 1–5 green (✅ as of 2026-05-13) | Scanner platform team | 2026-05-13 |
| **ADR-093 Phase 7** | [ADR-093](architecture-decisions/ADR-093-neptune-cross-file-taint-resolver.md) | GA flag-flip for enterprise tenants, tiered (T1 commercial → T2 dedicated cluster → T3 GovCloud VPC). | After ADR-093 Phase 6 validates against a real test tenant | Scanner platform team | 2026-05-13 |
| **#180 SNS subscriptions** | [#180 closing comment](https://github.com/aenealabs/aura/issues/180) | Provision `AWS::SNS::Subscription` resources on the `runtime-security-correlation.yaml` topics (and other documented PagerDuty/Slack routes referenced in `docs/support/operations/monitoring.md`). Code path is in place; topics exist; only the subscriptions are missing. Without them, ADR-086 self-mod sentinel + remediation alerts have no human recipient. | External endpoints provisioned (PagerDuty / Slack webhook URLs) AND live-AWS budget restored to add subscriptions via console / CFN | Ops team | 2026-05-13 |
| **#180 nightly-live-llm.yml** | [#180 closing comment](https://github.com/aenealabs/aura/issues/180) | Workflow has `startup_failure` on every scheduled run; likely missing `secrets.AURA_LIVE_LLM_ROLE_ARN`. Tied to live-Bedrock invocations so cost-gate-coupled. Workflow remains in-tree because `docs/runbooks/ADR090_LIVE_LLM_SMOKE_RUNBOOK.md` references it; removing would orphan operational documentation. | Live-AWS budget restored (Bedrock test budget specifically) AND GitHub repo secret `AURA_LIVE_LLM_ROLE_ARN` populated | Ops team | 2026-05-13 |
| **#180 Branch-protection PR-review enforcement** | [#180 closing comment](https://github.com/aenealabs/aura/issues/180) | Enable PR + ≥1 review requirement on the `main-protection` ruleset. Branch-protection is *enabled* (since Wave 1, #163); the open work is tightening enforcement strength. Not budget-gated -- gated on external-review-capacity availability. Operator handling separately. | External code-review capacity confirmed AND operator schedules the GitHub ruleset update | Owner (lavrut) | 2026-05-13 |

---

## Cost-gate context (inherited from ADR-092 §"Cost gate context")

The platform is self-funded; live-AWS validation is paused indefinitely. Code-complete work continues to ship offline -- every deferred item above has its code-side companion already merged or has an offline static-analysis substitute (`scripts/adr_092_static_action_scan.py`, `scripts/adr_093_taint_schema_static_scan.py`, `scripts/adr_093_taint_query_static_scan.py`). The deferred phases are the live-AWS-dependent gates only.

When the cost gate opens:

1. Re-validate every row above is still relevant.
2. Schedule the deferred phases against the live-AWS calendar in dependency order (the "Re-engage when" column gives the prerequisite chain).
3. Each ADR's phase tracker remains the operational source of truth; this file is just the discovery index.

---

## What this file is NOT

* **Not a substitute for the ADR phase tracker.** When you re-engage a phase, update the ADR's tracker; this file only tells you which ADR to open.
* **Not a tech-debt registry.** Tech-debt items (refactors, rename ergonomics, etc.) go to issue #182 or the relevant ADR's "Known issues" section.
* **Not an open-issues replacement.** Active work in progress lives in GitHub issues; this file is for paused-pending-external-condition work only.

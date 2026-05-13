# Dependency Risk Audit Reports

This directory holds the weekly dependency-risk audit reports, one per ISO week, committed via PR by the `.github/workflows/dependency-risk-audit.yml` workflow.

## Layout

```
docs/security/audits/
  README.md          (this file)
  YYYY-WNN.md        weekly report for ISO week WNN of year YYYY
                     (e.g. 2026-W20.md for the week of 2026-05-11)
```

ISO week numbering is what `date -u +%G-W%V` returns. Weeks start on Monday; this matches the cron schedule (Mon 14:00 UTC).

## Cadence

| When | What |
|---|---|
| **Mon 14:00 UTC** | `dependency-risk-audit.yml` runs on cron. Generates the report into `YYYY-WNN.md`, opens a PR titled `audit(deps): weekly report YYYY-WNN`. |
| **Manual** | `gh workflow run dependency-risk-audit.yml` produces an off-cycle report on a fresh PR for the current ISO week (or updates the existing PR if one is already open). |
| **PR-triggered** | When a PR touches Python/Frontend deps (or this workflow), the audit runs against that PR's deps and surfaces the result in the workflow's summary -- *not* committed as a file. Lets the reviewer see what the dep change means before merging. |

## PR labels

Every audit PR is labelled by the workflow:

- **`audit-green`** -- both `pip-audit` and `npm audit --audit-level=high` returned clean. Operator action is: review the report (10-second glance) and merge.
- **`audit-findings`** -- one or both tools reported high-severity issues. Operator action is: triage per `docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`, update the register if a tier change is warranted, commit register edits to the same PR, then merge.

## Merge policy

Operator merges; no bot auto-merge. This is deliberate so the merge step is an audit-trail event tied to a named human reviewer (consistent with the `main-protection` PR-review enforcement). Green-week merges should take seconds; findings weeks force triage.

## Why a file-per-week rather than issue-comments

Prior to 2026-05-13 the audit posted as comments on issue #138. The issue-as-tracker pattern was a category mismatch: GitHub Issues are designed for trackable work with a beginning and end, not for indefinite cron-bot threads.

This directory pattern:

- Puts the audit-trail in git history (durable; survives GitHub policy changes; greppable forever).
- Reuses the existing PR-review discipline -- audits are diff-able week-over-week.
- Frees the issue tracker for actual issues.
- Surfaces findings via standard PR labels rather than buried thread state.

Tracking note: see issue #138's closing comment for the migration story.

## Where the canonical state lives

Per-package tracking, tier changes, and Replacement-Decisions-Made history all live in [`docs/security/DEPENDENCY_RISK_REGISTER.md`](../DEPENDENCY_RISK_REGISTER.md). The audit reports here are *evidence*; the register is the *decisions*. When triaging findings, the PR should typically update both files in the same commit.

## Triage runbook

See [`docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`](../../runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md) for the decision tree (new CVE with fix / without fix / staleness / Replace-Now). The runbook is the authority on how to act on a report; this README is just the layout.

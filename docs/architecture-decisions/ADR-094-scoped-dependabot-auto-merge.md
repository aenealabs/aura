# ADR-094: Scoped Auto-Merge for Routine Dependabot Pull Requests

## Status

**Accepted** — September 28, 2026

## Context

Two existing controls previously stated, in comments, a deliberate "no bot
self-approval, no auto-merge" posture:

- `dependabot-triage.yml`: "This workflow NEVER merges, approves, or marks a
  pull request ready. Operator review and merge remain required."
- `dependency-risk-audit.yml`: "Operator review + merge is required; no bot
  self-approval, no auto-merge -- consistent with the main-protection
  PR-review enforcement."

That posture held while Dependabot PR volume was low. It stopped scaling: a
routine weekly batch now runs 15-20 PRs deep, and every one of them sits
`BLOCKED` on `main-protection`'s single required approval even when every
required status check (`Analyze (python)`, `Analyze (javascript-typescript)`,
`Analyze (actions)`, `Python Quality & Tests`) is green. On 2026-09-28, 19 open
PRs were checked: 14 were fully green and blocked on nothing but that one
approval, 4 formed the known `github/codeql-action` coupled family (see
`docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md`), and 1 was the release-please
PR (a product decision, out of scope here). Clicking "approve" on 14
mechanically-identical, low-risk PRs every week is not a security control
doing useful work; it is toil that a human will eventually start rubber-
stamping without reading, which is a worse outcome than automating the
rubber stamp under an explicit, auditable set of conditions.

## Decision

Auto-merge is now enabled, but only for the narrow case that was already the
toil: a single, non-coupled, semver-patch-or-minor Dependabot PR. See
`dependabot-auto-merge.yml` for the enforced conditions:

1. PR author is `dependabot[bot]`.
2. `dependabot/fetch-metadata` reports `version-update:semver-patch` or
   `version-update:semver-minor` — never major.
3. `scripts/security/dep_triage.py` — the same classifier
   `dependabot-triage.yml` already publishes for human review — classifies
   the PR `candidate`, not `coupled`.

When all three hold, the workflow submits the one approving review
`main-protection` requires and enables GitHub's native auto-merge. It does
not touch the ruleset itself, does not bypass the four required status
checks (those still have to pass on their own before auto-merge actually
lands the PR), and does not change anything about how human-authored PRs or
release PRs are handled — those still need a human's approval exactly as
before.

Everything that fails any of the three conditions above still requires a
human: major version bumps, anything `dep_triage` calls `coupled`, and by
construction anything not authored by Dependabot. The workflow leaves a
comment on skipped PRs stating why, so the reason isn't silent.

## Consequences

### Positive

- Removes recurring manual-approval toil for the majority of routine
  dependency PRs (14 of 19 in the batch that prompted this ADR) without
  weakening the check that actually catches problems (CI, and the coupling
  classifier).
- The coupled-family protection is unaffected and, if anything, now load-
  bearing in an automated path instead of only an advisory one: a coupled
  PR that reaches `dep_triage` mis-classified as `candidate` would now
  auto-merge instead of just being reported. This raises the cost of a bug
  in `dep_triage.py`'s classifier from "a human might miss the advisory" to
  "it merges automatically" — see Risks below.
- Major version bumps, which are the update type most likely to carry
  breaking changes worth a human's attention, are excluded unconditionally.

### Negative / risks accepted

- **Classifier correctness is now load-bearing, not advisory.** A false
  `candidate` verdict from `dep_triage.py` on an actually-coupled PR merges
  it alone instead of surfacing it for review. Mitigation: the classifier's
  test suite (`tests/scripts/test_dep_triage.py`) already exists and is
  fixture-driven from real captured coupling incidents per the runbook's
  "When You Disagree With The Report" procedure; that procedure now doubles
  as the process for hardening the auto-merge gate, not just the report.
- **A compromised or buggy `dependabot/fetch-metadata` release** could
  misreport update type. Mitigated by pinning the action to a specific
  commit SHA (not a floating tag), consistent with every other third-party
  action in this repo's workflows.
- **This is the first exception to "every merge to main gets a human
  review."** Scope is deliberately narrow (bot-authored, non-major,
  non-coupled) specifically so this doesn't become precedent for widening
  auto-merge to human-authored PRs or to security-relevant changes.

## References

- `dependabot-auto-merge.yml` — the enforcing workflow.
- `dependabot-triage.yml`, `dependency-risk-audit.yml` — updated comments
  reflecting this decision.
- `docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md` — coupled-family
  classification and consolidation procedure, unchanged, now consumed by
  both the human report and the auto-merge gate.
- `scripts/security/dep_triage.py` — classifier; source of truth for what
  counts as `candidate` vs `coupled`.

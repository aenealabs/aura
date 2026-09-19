# Dependabot Triage Automation -- Design

**Date:** 2026-09-19
**Status:** Approved design, pending implementation plan

## Purpose

Automate the *analysis* of open Dependabot pull requests without automating the
merge decision. Each weekly Dependabot batch currently requires manual
investigation to answer one question per PR: is this safe to merge on its own?
That investigation is mechanical, repeatable, and expensive in reviewer time --
but its conclusions are not obvious from the GitHub UI, because a fully green PR
can still be unsafe.

The automation classifies every open Dependabot PR with a stated reason, proves
the safe subset works *as a batch*, consolidates PR sets that cannot merge
individually, and publishes a weekly report. A human reads the report and
performs every merge.

## Non-Goals

- **No auto-merge.** `dependency-risk-audit.yml` records a deliberate policy:
  "Operator review + merge is required; no bot self-approval, no auto-merge --
  consistent with the main-protection PR-review enforcement." This design does
  not alter that posture, and does not touch the one-approval requirement in the
  `main-protection` ruleset.
- **No bot self-approval.** Nothing in this design approves a pull request.
- **No classification labels on Dependabot PRs.** A PR's classification is
  carried by the weekly report, not by label state on the PR itself. (The report
  PR that the workflow opens does carry the routine `dependencies` / `automated`
  labels; that is unrelated to classification.)

## Evidence Base

Every rule below traces to an observed failure in the 2026-09-19 batch of 21
open PRs, not to a hypothetical. The two most important cases were both
**fully green**:

| PR | Appearance | Reality |
|----|-----------|---------|
| #450 | All checks pass | One of a four-way `github/codeql-action` split. Green only because `upload-sarif` runs in a workflow with no paired `init`/`analyze` step. Merging alone leaves a version mismatch on `main`. |
| #443 | All checks pass | Bumps `@vitest/coverage-v8` to `^5.0.0` while leaving `vitest` at `^4.0.16` -- a peer conflict. Its partner #442 is red. |
| #386 | No failing checks | A Release Please PR, not a Dependabot PR. Has zero check runs, so "no failures" is vacuously true. |
| #442 | One red check | `trivy` installer died with exit code 35 (download failure); `trivy-results.sarif` never existed. Infrastructure flake, not a defect. |
| #452, #453, #454 | Four red checks each | Correct failure: "Not all workflow steps that use `github/codeql-action` actions use the same version." Resolves only when all four refs move together. |
| #439 + #446 | Both green | Each was green against a `main` lacking the other. `requirements.txt:40` warned that `pydantic` and `cfn-lint` must move in the same PR. The merged combination was never tested by CI. |

Commit `ad67a34` documents the same four-way `codeql-action` coupling from the
previous release cycle, making it a recurring pattern rather than a one-off.

## Structural Findings

Two repository properties make the "untested combination" class of failure
structural rather than accidental:

1. **`strict_required_status_checks_policy: false`** in the `main-protection`
   ruleset. PRs may merge without being up to date with `main`, so sibling
   updates are never tested together before landing.
2. **`code-quality.yml` is `pull_request`-only.** The workflow carries an
   explicit comment forbidding a `paths:` filter, because a required check that
   never runs reports as *missing* and deadlocks the PR. A consequence is that
   the test suite never runs on `main` after a merge.

Together these mean no automated check ever validates the merged result. The
batch proof in Section 4 is the compensating control.

## Architecture

Network access is confined to one module so the decision logic is pure and
unit-testable.

```text
collect.py  --(snapshot.json)-->  triage.py  --(decisions.json)-->  report.md
   |                                                  |
   | GitHub API, PyPI/npm release dates,              +--> batch proof job
   | risk-register tiers                              +--> consolidation job
```

### Components

| Component | Responsibility |
|-----------|----------------|
| `scripts/dependabot/collect.py` | All API access. Emits `snapshot.json`: PR metadata, check runs, required-check names, release dates, risk-register tiers. |
| `scripts/dependabot/triage.py` | Pure classifier and report renderer. `snapshot.json` to `decisions.json` plus Markdown. No network, no side effects. |
| `.github/workflows/dependabot-triage.yml` | Orchestration: collect, classify, prove, consolidate, report. |

### Trigger

`schedule` (Mondays 16:00 UTC, after Dependabot opens PRs and after the 14:00
risk audit) and `workflow_dispatch`.

Deliberately **not** `pull_request_target`. That trigger combined with a
checkout of PR head is remote code execution against a write-scoped token; the
design avoids the pattern entirely rather than mitigating it.

## Section 1 -- Classification Rules

Ordered; first match wins. Every PR carries its reason string into the report.

### Hard exclusions

- **R1** Author is not `dependabot[bot]` -> `excluded:non-dependabot`.
  Identity-based, not a title heuristic. Catches #386.
- **R2** Zero check runs -> `excluded:no-checks`. Independent second guard on
  #386, and the rule that closes the "no failing checks is vacuously true" hole.
- **R3** Touches a policy-sensitive path -> `held:policy-review`: Dockerfiles
  (private-ECR mandate), workflow `uses:` SHA changes, or the `pyproject.toml`
  coverage threshold.
- **R4** Target package is a deliberate hold (the `tree-sitter` `<0.26` DoS
  guard) or is **At-Risk** / **Replace-Now** in
  `docs/security/DEPENDENCY_RISK_REGISTER.md` -> `held:pinned-by-policy` or
  `held:risk-tier`. The register specifies "pin precisely" for At-Risk items, so
  automation must not bump them.

### Coupling -- evaluated before check results are read

- **R5** Group open PRs into update families by shared action namespace
  (`github/codeql-action/*`), declared peer relationship (`vitest` and
  `@vitest/*`), or the same manifest key family within one directory. Any family
  with more than one member -> `coupled:<family>`, and **no member is
  individually merge-safe regardless of its check status.**

  Rule order matters: this must precede check evaluation, because the failure
  mode is a *green* sibling (#450, #443).

### Check evaluation

- **R6** Any `failure` or `timed_out` -> `attention:failing`. If the failing
  step matches infrastructure-flake signatures (download failure, exit code 35,
  rate limiting) -> `attention:suspected-flake`, rerun once, then escalate.
  Covers #442.
- **R7** A *required* check absent from the run set -> `attention:missing-required`.
  An unrun check is never treated as a passing check. This generalises the #450
  lesson.
- **R8** Major semver bump -> `held:major-review`.
- **R9** Release age below cooldown -> `held:cooldown`.
- **R10** Otherwise -> `candidate`. A candidate becomes `merge-safe` only by
  passing the batch proof.

### Cooldown defaults

3 days for packages; 7 days for GitHub Actions, which are SHA-pinned
supply-chain surface. Single adjustable constant.

## Section 2 -- Batch Proof

1. Create ephemeral `dep-triage/candidate-<run_id>` from `main`.
2. Merge each `candidate` PR head in ascending PR-number order (deterministic
   and reproducible).
3. A merge conflict demotes that PR to `attention:conflict`; the proof continues
   with the remainder.
4. Run in order:
   - `pip install --dry-run --report` across **all** requirements files. This
     automates the resolver check performed manually for #439 + #446.
   - `npm ci` in each npm directory. This is what surfaces the #443 peer
     conflict.
   - `pytest`, then the frontend test suite.
5. Green as a unit -> every member is reported `merge-safe`. Red -> bisect by
   halves to isolate the offender, demote it, re-prove the remainder. Capped at
   3 rounds to bound CI cost.
6. The branch is a proof artifact. It is deleted afterward and never merged.

This job runs with a **read-only token**.

## Section 3 -- Coupled-Set Consolidation

For families whose union is mechanical (one version string across N refs):

1. Branch `dep-consolidate/<family>-<version>` from `main` and apply the union
   of member changes.
2. **Assert that the set of added lines equals the union of added lines across
   the member PRs** -- the verification performed by hand in `ad67a34`. Abort on
   mismatch rather than open a PR.
3. Open one PR whose body explains the coupling and links every member; comment
   on each member pointing to it.
4. **Members are not closed.** Dependabot retires them once the version lands,
   and leaving them open means a rejected consolidation does not destroy the
   originals.

This is the only job requiring `contents: write` and `pull-requests: write`, and
it is isolated from the proof job.

## Section 4 -- Delivery

- Write `docs/security/dep-triage/YYYY-WNN.md`, mirroring the
  `docs/security/audits/` layout.
- Report sections: merge-safe batch with proof-run link; coupled sets with
  consolidated-PR links; held items with reasons; needs-attention items with
  reasons; unwatched surfaces.
- Open the PR with plain `gh pr create`, matching
  `dependency-risk-audit.yml:224` rather than introducing
  `peter-evans/create-pull-request`.
- Labels: `dependencies`, `automated`.

The report is the durable audit artifact. A human reads it and performs every
merge.

## Section 5 -- Permissions

| Job | `contents` | `pull-requests` | Notes |
|-----|-----------|-----------------|-------|
| collect / classify | read | read | No write surface. |
| batch proof | read | read | Read-only; executes dependency resolution and tests. |
| consolidation | write | write | Isolated; opens consolidated PRs only. |
| report | write | write | Commits report file, opens report PR. Mirrors `dependency-risk-audit.yml`. |

## Section 6 -- Testing

`tests/dependabot/test_triage.py`, table-driven, with regression fixtures built
from the observed 2026-09-19 batch:

| Fixture | Asserts |
|---------|---------|
| #386 | `excluded:non-dependabot` and `excluded:no-checks` both fire |
| #450 | `coupled:codeql-action` despite all checks green |
| #443 | `coupled:vitest` despite all checks green |
| #442 | `attention:suspected-flake`, not `attention:failing` |
| #452-#454 | Same coupled family as #450; consolidation eligible |
| #439 + #446 | Both reach `candidate`; batch proof runs the resolver |
| #451 | Group PR of 9 treated as one indivisible unit |

Fixtures are derived from real observed states rather than invented ones. The
suite meets the 70% coverage floor in `pyproject.toml`, which must not be
lowered.

## Section 7 -- Adjacent Gap

`.github/dependabot.yml` scopes the pip ecosystem to `directory: "/"`, so
`deploy/docker/memory-service/requirements.txt` is watched by nothing and its
dependencies are never updated. Add that directory in the same change; it is the
same subject and a security-relevant omission.

## Deferred / Considered and Rejected

- **Enabling `strict_required_status_checks_policy: true`** would force PRs up
  to date with `main` and eliminate the untested-combination class at the
  source. Rejected for now because it serialises every merge and would make a
  20-PR batch impractical. The batch proof achieves the same guarantee without
  the serialisation cost. Worth revisiting if batch sizes shrink.
- **Running the test suite on pushes to `main`** would catch post-merge
  breakage, but `code-quality.yml` is `pull_request`-only by deliberate design.
  Changing it risks the required-check deadlock documented in that file.
- **PR labels for classification** -- dropped as unnecessary once the report
  exists.

## Open Question

`requirements.txt:40` carries a justification stating that `pydantic` is capped
by the `moto[all]` -> `cfn-lint` -> `aws-sam-translator` chain pinning
`pydantic~=2.12.5`. As of 2026-09-19 that chain no longer exists: `cfn-lint`
1.56.0 and 1.57.0 declare no dependency on `aws-sam-translator`, and
`aws-sam-translator` 1.113.0 pins `pydantic~=2.13.3`, which permits the
`>=2.13.5` now on `main`. A clean resolve of all three succeeds. The comment is
stale and will mislead the next reader; correcting it is out of scope for this
design but should be tracked.

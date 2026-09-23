# Dependabot Triage Automation -- Design

**Date:** 2026-09-19
**Status:** Implemented, with documented deltas -- see [As-built deltas](#as-built-deltas)
**Implementation:** `scripts/security/dep_triage*.py`, `.github/workflows/dependabot-triage.yml`
**Operating procedure:** `docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md`

> **Read this first.** The sections below are the design as reviewed and
> approved on 2026-09-19. They are preserved as written, because the reasoning
> is worth keeping even where the conclusion changed. Several of them no longer
> describe what was built. Every divergence is recorded in
> [As-built deltas](#as-built-deltas) at the end of this document; where the two
> disagree, the deltas section and the code are authoritative.

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
2. **`code-quality.yml` does not run the test suite on `main`.** *(Corrected
   2026-09-22 -- see "As-built deltas". The original text read "`code-quality.yml`
   is `pull_request`-only", which is factually wrong, and drew a conclusion
   broader than the evidence supports.)*

   The `pull_request` trigger deliberately carries no `paths:` filter, because a
   required check that never runs reports as *missing* and deadlocks the PR. The
   workflow **also** has a `push` trigger on `main`. What that push trigger does
   not do is run tests: `check-trigger` sets `run_full_tests=true` only for
   `pull_request` and `workflow_dispatch`, so a push to `main` runs the lint,
   type and security steps and skips the suite. The push trigger additionally
   filters on `src/`, `tests/`, `deploy/`, `frontend/` and `scripts/`, which
   excludes `requirements*.txt` -- the file a Python dependency merge actually
   changes -- so a dependency-only merge triggers nothing at all on `main`.

Restated conclusion, narrower and accurate: **the merged combination of two
sibling dependency PRs is validated by no automated check.** Post-merge lint,
Bandit and CodeQL do run for source changes, so "no automated check ever
validates the merged result" was overstated.

The case for the batch proof does not rest on this finding. It rests on Finding 1
-- `strict_required_status_checks_policy: false` means siblings are never tested
against each other before they land -- and on the observed #439 + #446 failure,
where each PR was green against a `main` lacking the other. Finding 2 only
removes the safety net that would have caught the result afterwards. The batch
proof is **Section 2** of this document; the original text pointed at Section 4,
which is Delivery.

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

---

## As-built deltas

Recorded 2026-09-22, after implementation and three specialist reviews; deltas
16 and 17 added 2026-09-23. Each row below states what this spec said, what was
built, and why it changed. Rulings and their stated cost-if-wrong come from the
execution ledger at
`.superpowers/sdd/2026-09-19-dependabot-triage/progress.md`.

This section is additive. Nothing above it has been rewritten except Structural
Finding 2, which was factually wrong and is corrected in place with a marker.

### 1. Module paths

**Spec:** `scripts/dependabot/collect.py`, `scripts/dependabot/triage.py`;
tests at `tests/dependabot/test_triage.py`.

**Built:** `scripts/security/dep_triage_collect.py`,
`scripts/security/dep_triage.py`, `scripts/security/dep_triage_consolidate.py`;
tests at `tests/scripts/test_dep_triage*.py`.

**Why:** pattern compliance. The sibling `scripts/security/dep_risk_audit.py`
already occupies exactly this role, and the repo's rule is to match an
established pattern rather than introduce a second one.

**Consequence, recorded deliberately:** the coverage gate in `pyproject.toml` is
`--cov=src` with a 70% floor, so these modules are measured only when coverage is
requested explicitly and nothing enforces it going forward. Measured at the time
of writing: `dep_triage.py` 98.37%, `dep_triage_collect.py` 96.00%. The
pre-existing `dep_risk_audit.py` sits in the same position, so this matches the
convention rather than introducing a gap. A narrowly scoped run of these three
test files with default `addopts` reports a coverage failure at ~0.12% because
`--cov=src` measures a tree they do not exercise; use `--no-cov`.

### 2. Delivery: rolling issue, not a committed weekly file

**Spec (Section 4):** write `docs/security/dep-triage/YYYY-WNN.md`, mirroring
`docs/security/audits/`, and open a PR with `gh pr create`.

**Built:** one long-lived GitHub issue titled `Dependabot triage`, labelled
`dependencies` + `automated`, rewritten in place every run. Located by listing
open issues with the `automated` label and matching the title client-side -- not
by `--search`, whose index is eventually consistent and would fork the rolling
issue into duplicates on a stale hit.

**Why:** a report PR needs review and merge every week (~52 per year) under the
one-approval rule, for a document that only offers advice. An issue needs no
approval to update.

**Cost if wrong, as ruled:** loses the git-committed weekly artifact and parity
with `dependency-risk-audit.yml`; the issue's comment history becomes the record.
Partially mitigated by the `triage` workflow artifact (`snapshot.json`,
`decisions.json`, `triage-report.md`) retained for 90 days -- an explicit value,
not the admin-changeable default, because it is the only durable record of the
state a `merge-safe` verdict was based on.

**Operator consequence:** the report has no history, so its timestamp is the only
freshness signal. The runbook's *Rules of Engagement* section covers this.

### 3. Consolidation is an operator command, not a workflow job

**Spec (Section 3, Section 5):** a `consolidation` job holding `contents: write`
and `pull-requests: write`, isolated from the proof job.

**Built:** `scripts/security/dep_triage_consolidate.py` is run locally by an
operator. The workflow has no consolidation job and no job holds `contents:
write`. Top-level `permissions: {}`.

**Why:** three reasons, two of them found only by live probe.

1. A pull request opened with `GITHUB_TOKEN` does not trigger workflow runs. A
   consolidated PR created by Actions could therefore never satisfy the four
   required contexts in `main-protection` and would sit blocked forever. A branch
   pushed by a human does trigger them. This is the decisive reason: the coupled
   family is the highest-risk class *and* is excluded from the batch proof by
   construction, so it would have received neither the proof nor any PR CI.
2. It would have been the only write-scoped job, running weekly for something
   that occurs roughly monthly.
3. Gating it on `workflow_dispatch` did not work either: the dispatch had no
   inputs, so any manual dispatch fired consolidation -- conflating "refresh my
   report" with "write to the repository".

Two specialist reviewers reached this recommendation independently.

**Known residual, parked rather than fixed:** the push uses `--force-with-lease`
with no explicit expected value, which checks against the local
`refs/remotes/origin/<branch>`. Operator commits pushed *before* the run's
checkout are already in that ref, so the lease passes and the force push discards
them. Only commits landing between checkout and push are protected. Closing this
properly needs a SHA-pinned lease or an authorship check -- a design change.
The runbook warns operators not to push onto a `dep-consolidate/*` branch.

### 4. No bisect on a failed batch proof

**Spec (Section 2, step 5):** red proof bisects by halves to isolate the
offender, demotes it, re-proves the remainder, capped at 3 rounds.

**Built:** absent. A red proof leaves every member at `candidate`; nothing is
promoted to `merge-safe`, so a failed proof is fail-safe but silent about which
PR caused it. The only automatic demotion is for merge conflicts, which become
`attention:conflict` and drop out while the proof continues with the remainder.

**Why:** CI cost and orchestration complexity against a procedure that is cheap
and infrequent to run by hand, and whose first step -- reading which proof step
failed -- usually identifies the offender with no narrowing at all.

**Cost if wrong:** an operator narrows manually on a failed batch. The manual
procedure is documented in the runbook's *When the batch proof fails* section,
along with the local reproduction commands.

### 5. R3 does not cover workflow `uses:` SHA changes

> **Superseded 2026-09-23 by [delta 16](#16-r8-removed-r3-narrowed-then-partly-restored).**
> The gap recorded below was closed: `rule_workflow_path` now holds on
> `.github/workflows/`. The text is preserved because delta 16 is the answer to
> it and reads better with the question in front of it.

**Spec (R3):** hold on Dockerfiles, **workflow `uses:` SHA changes**, and the
`pyproject.toml` coverage threshold.

**Built:** `POLICY_PATHS` covers `Dockerfile` and `pyproject.toml` only. Matching
is on the path's basename -- exact match, or the basename prefixed with
`<marker>.` -- after a review found that substring matching held unrelated files
such as `frontend/.../DockerfileViewer.jsx`.

**Why:** not deliberate. It is an unimplemented clause of the spec, and it is
worth stating as an open gap rather than a decision.

**Current mitigation:** Dependabot's `github-actions` PRs do change `uses:` SHAs
and are held by the 7-day Actions cooldown, and when a bump splits across
multiple refs they are held by R5 coupling. Neither is a policy hold on the path
itself, so a single-ref action bump older than 7 days can reach `candidate`
without a policy review.

### 6. The security-advisory fast path: added, built, removed

**Spec:** silent. The fast path was added mid-execution by ruling -- R9 would
have delayed CVE fixes by 3 days, and slow-walking security fixes is the wrong
default for a security platform. It was then built and removed.

**Why removed:** it had zero true positives and its false positives landed
exactly where the bypass was worth most.

- Detection read the PR body for a GHSA/CVE id. Real Dependabot security bodies
  are a one-line preamble followed by collapsible `<details>` blocks, and the id
  is cited **inside** the block. Detection truncates at the first `<details>`-ish
  tag -- a deliberate choice, because paired stripping cannot be made
  nesting-aware with a regex and every failure mode of the clever version widened
  scope. So the real cases were never matched.
- False positives fired on ordinary bumps whose embedded upstream release notes
  cite any historical CVE. Those cluster on `docker` and `github-actions` bumps,
  where the bypass stripped a *permanent* policy hold rather than a 3-day wait.

**Consequence:** there is no automated exemption from the cooldown today. That is
a deliberate SI-2 risk acceptance with a stated ceiling, a compensating control
and a manual override -- see
`docs/security/SI2_DEPENDENCY_COOLDOWN_RISK_ACCEPTANCE.md`.

**If the capability is wanted later**, the sound signal is
`gh api repos/{owner}/{repo}/dependabot/alerts` correlated to the PR by package
name and `fixed_in` version. That is authoritative rather than inferred.

### 7. The flake detector: specified, built, removed

**Spec (R6):** infrastructure-flake signatures (download failure, exit code 35,
rate limiting) produce `attention:suspected-flake`, rerun once, then escalate.
Covers #442.

**Built, then removed.** `CODE_SUSPECTED_FLAKE` no longer exists; every failed
check reads as genuine.

**Why:** signatures were matched against `CheckRun.failing_log_excerpt`, which
the collector filled from `gh pr checks --json description`. That field is empty
for every GitHub Actions check run, so no signature could ever match. The code
path was unreachable in production while advertising coverage the tool did not
have.

**Why it was not simply repointed at the log:** matching "rate limit" or
"429 Too Many Requests" against arbitrary program output lets a compromised
package print that string from its own test process and have the classifier
relabel its genuine test failure as "rerun once before escalating". That is
evidence tampering through a signal the adversary controls. A sound
reimplementation reads the check run's own failure annotation
(`gh api repos/{owner}/{repo}/check-runs/{id}/annotations`), which the runner
writes about the step rather than the step writing about itself.

### 8. The batch proof does not run the frontend test suite

**Spec (Section 2, step 4):** `pip install --dry-run --report` across all
requirements files, `npm ci` in each npm directory, then `pytest`, then the
frontend test suite.

**Built:** the resolver and `npm ci` legs are present; the test leg is
`pytest -q --no-cov -p no:cacheprovider --maxfail=1` only. No frontend test run.

**Why `--no-cov`:** bare `pytest` inherits `pyproject.toml`'s `--cov=src
--cov-fail-under=70`, which would make the proof's verdict depend on `src/`
coverage on the integration branch. A dependency bump that shifts which tests run
would then fail the proof for a reason unrelated to any dependency. This proof
answers one question: does the batch resolve and pass tests together. It is a
compatibility check, not a supply-chain integrity check -- a malicious package
makes its own tests pass too.

**Why the frontend suite is absent:** not deliberate. Recorded as a gap.

**Related weakening, recorded deliberately:** `npm ci` must use
`--legacy-peer-deps` in `frontend/`, which is mandatory rather than a shortcut --
the `eslint-plugin-react` peer cap on `eslint@^9.7` makes a plain `npm ci` fail
outright (see `frontend/CLAUDE.md` and `code-quality.yml`). The flag globally
silences peer conflicts, so the npm leg is weaker assurance than Section 2
implies and would **not** on its own have caught #443. R5 coupled-family
detection is the primary, deterministic control for that class, and it catches
#443 before the proof ever runs.

### 9. R1 accepts two author formats

**Spec (R1):** "Author is not `dependabot[bot]`".

**Built:** `DEPENDABOT_AUTHORS` accepts both `app/dependabot` and
`dependabot[bot]`.

**Why:** `gh` normalizes bot logins to `app/<slug>`; the GitHub API and webhooks
use `<slug>[bot]`. An equality test against a single form excluded **every**
Dependabot PR -- R1 is the first rule, so no other rule ever ran, no candidates
existed, the batch proof was skipped and the workflow went green while the
feature did nothing. Verified live against PR #454, whose `author.login` is
`app/dependabot`.

**Root cause, worth keeping:** the regression fixture was hand-authored. It
carried the observed format for the one PR that had been inspected and the
assumed format for the rest, and the test suite validated the assumption against
itself. Fixtures are now built from a live `gh` capture (`dep_triage_collect
--record`), which is what Section 6 of this spec always intended and did not get
until after this defect was found. Three other identity/free-text detectors
failed the same way and are covered in deltas 6, 7 and 10.

### 10. R2 is reachable; the collector survives a zero-check PR

**Spec (R2):** zero check runs -> `excluded:no-checks`, a second independent
guard on #386.

**Built and repaired.** `gh pr checks <n>` exits non-zero with "no checks
reported" *before* the `--json` exporter runs, so the collector originally
crashed on exactly the PR the rule exists to classify -- deterministically, every
Monday, with no report. The collector now treats that one message as a legitimate
empty result and still aborts on any other `gh` failure, because a partial
snapshot is a silently incomplete security report.

### 11. New rule: `attention:required-not-passing`

**Spec:** not present.

**Built:** R7b. A required check that is present but has not conclusively passed
-- still running, cancelled, timed out, errored -- is reported rather than
treated as a pass. Only `success`, `skipped` and `neutral` count as passing,
matching what branch protection itself accepts.

**Why:** the collector maps `gh`'s `bucket` field, and six non-passing states
(`TIMED_OUT`, `CANCELLED`, `ACTION_REQUIRED`, `STARTUP_FAILURE`, `STALE`,
`ERROR`) were indistinguishable from green. "All required checks still running"
is the most ordinary input at 16:00 on a Monday, minutes after Dependabot opens
its PRs, and it classified as `candidate` -- identical to genuinely green.

### 12. Cooldown is two constants, and holds on unknown age

**Spec (Cooldown defaults):** "Single adjustable constant."

**Built:** `PACKAGE_COOLDOWN_DAYS = 3` and `ACTION_COOLDOWN_DAYS = 7`. The rule
also holds when the release age is unknown, which is an abstention rather than a
finding: without it, an ecosystem with no stdlib-reachable release timestamp
would pass unexamined.

**Known imprecision:** the schedule makes the two windows behave identically --
a release is either already older than both at first triage or is held to the
next run. This was true of the weekly schedule and is more true of the monthly
one it became (delta 17). Documented in
`docs/security/SI2_DEPENDENCY_COOLDOWN_RISK_ACCEPTANCE.md`, which also restates
the 7-day remediation ceiling that the weekly cadence used to deliver on its
own.

### 13. Permissions differ from Section 5

**Spec (Section 5):** four jobs; `consolidation` and `report` hold `contents:
write` + `pull-requests: write`.

**Built:** three jobs, top-level `permissions: {}`.

| Job | Permissions |
|-----|-------------|
| `classify` | `contents: read`, `pull-requests: read`, `checks: read`, `statuses: read` |
| `batch-proof` | `contents: read` only, plus `persist-credentials: false` on checkout |
| `report` | `contents: read`, `issues: write` |

`checks: read` + `statuses: read` were added because `gh pr checks` reads the
status-check rollup those scopes gate. Without them every PR classifies as
`excluded:no-checks` and the report is vacuous while the job goes green -- a
plausible empty answer is worse than a crash. `persist-credentials: false` is on
the proof job because it installs and runs the batch's own dependency code and
merges untrusted PR branches; no credential should be sitting in `.git/config`
for that code to find.

### 14. Section 7 adjacent gap: delivered

`.github/dependabot.yml`'s pip ecosystem now uses `directories:` and includes
`/deploy/docker/memory-service`, which was previously watched by nothing. No
delta; recorded so it is not re-opened.

### 15. Open Question: still open

`requirements.txt:40`'s justification for the `pydantic` cap still cites the
`moto[all]` -> `cfn-lint` -> `aws-sam-translator` chain. As of 2026-09-22 the
comment is unchanged and, per the analysis in the Open Question above, stale.
Out of scope for this work; still worth tracking.

### 16. R8 removed, R3 narrowed, then partly restored

**Spec (R3):** hold on Dockerfiles, workflow `uses:` SHA changes, and the
`pyproject.toml` coverage threshold -> `held:policy-review`.
**Spec (R8):** major semver bump -> `held:major-review`.

**Built, as of 2026-09-23:** `held:major-review` does not exist.
`held:policy-review` fires on `.github/workflows/` only. Both displaced
observations survive as `Decision.notes` -- advisory text attached to whatever
classification the PR otherwise earns, rendered into the report's reason cell
after `**Note:**`.

| Was | Is now | Mechanism |
|-----|--------|-----------|
| `held:major-review` | Note | `note_major` |
| `held:policy-review` on `Dockerfile*` / `pyproject.toml` | Note | `note_policy_file`, keyed by `POLICY_PATHS` |
| `held:policy-review` on `.github/workflows/` | Still a hold | `rule_workflow_path`, keyed by `POLICY_DIRS` |

**Why, and the order it happened in.** The demotion came first and took all
three. The premise is that this report is advisory: it merges nothing, and
`main-protection` still requires one human approval plus four status checks, so a
hold does not block anything -- it only tells the operator to look. It therefore
earns its cost only when it states something the operator could not cheaply
derive from the PR in front of them. A major bump fails that test outright (the
integer is in the title). A `Dockerfile` or `pyproject.toml` change fails it too
(a self-evident one-file diff the required reviewer is reading anyway). What
those two diffs do *not* carry is the *rationale* -- private-ECR base images, the
70% coverage floor -- so the rationale is what survives, as note text.

**Then the workflow case was restored, and that is the part worth recording.** A
security review objected to demoting it and was right on the facts. A workflow
`uses:` diff is the one policy-sensitive diff that is genuinely illegible: the
reviewer sees `owner/action@<40 hex>` replaced by `@<40 other hex>`, which proves
the pin moved and reveals nothing about what the new pin points at -- the only
load-bearing fact. SHA pinning only helps if a human confirms the new SHA is the
one intended, and nothing in this module confirms it. It is also the most
credential-adjacent surface in the repository; the motivating batch contained an
`aws-actions/configure-aws-credentials` bump, the action that performs AWS
credential assumption. So the line landed between "the diff is legible" and "the
diff is a hex string", not between "policy-sensitive" and "not".

**Rule position is load-bearing.** `rule_workflow_path` runs *after*
`rule_coupled`. Every github-actions family touches a workflow file by
construction, so running it first would flip all four codeql PRs out of `coupled`
and delete the family key `dep_triage_consolidate` reads. A coupled member is
held for a human either way, so the coupled verdict loses nothing by winning.

**Measured effect on the captured 22-PR batch:** the Held pile went from 5 to 2 --
`#458` (`held:policy-review`, the AWS credentials action) and `#468`
(`held:risk-tier`, `gremlinpython` At-Risk in the register). That is the point of
the change rather than a side effect: a Held pile that is mostly restatement
trains the operator to skim it, and then the holds carrying genuinely non-obvious
information get skimmed too.

**Cost if wrong:** a major bump can now reach `candidate` and `merge-safe`, and
nothing in the classifier reviews breaking changes. That review moved entirely to
the human whose approval `main-protection` requires. Recorded honestly in
`docs/security/SI2_DEPENDENCY_COOLDOWN_RISK_ACCEPTANCE.md`, which used to cite
both holds and now cites one.

**Reversing either direction is a small edit.** To re-demote the workflow hold,
drop `rule_workflow_path` from `classify`'s chain and fold `POLICY_DIRS` into
`note_policy_file`. To promote a note back to a hold, give it a `CODE_*`
constant, a `_SECTIONS` entry, and a position in the chain after `rule_coupled`.

### 17. Trigger is monthly, not weekly

**Spec (Trigger):** `schedule` (Mondays 16:00 UTC, after Dependabot opens PRs and
after the 14:00 risk audit) and `workflow_dispatch`.

**Built:** `cron: '0 16 1 * *'` -- 16:00 UTC on the 1st of the month --
with `workflow_dispatch` retained. Changed 2026-09-23.

**Why:** coupled families arrive at codeql-action's release cadence, roughly
monthly, and Dependabot PRs accumulate harmlessly. A larger batch triaged less
often is less work for the same coverage. `workflow_dispatch` covers the case
where a sweep is actually planned.

**What this costs.** Two things, both recorded rather than mitigated:

- The sibling Dependency Risk Audit (`0 14 * * 1`) did **not** move and is still
  weekly. The two jobs coincide only when the 1st is a Monday, so the spec's
  "read in the same sitting" framing no longer holds. Detection stays weekly;
  only merge *advice* batches up, which is the reason the divergence is
  acceptable.
- The SI-2 document's 7-day remediation ceiling was justified by the weekly
  cadence -- a release held at one run was necessarily re-evaluated 7 days later.
  Under a monthly schedule the schedule alone delivers 28-31 days. The 7-day
  ceiling is now a procedural commitment discharged by `workflow_dispatch`, with
  the still-weekly audit as the trigger that surfaces the need. Restated in
  `docs/security/SI2_DEPENDENCY_COOLDOWN_RISK_ACCEPTANCE.md`.

### Not deltas, but worth knowing

- **R5's npm grouping requires an unscoped namesake.** Grouping by bare npm scope
  would mark `@types/react` + `@types/node` as coupled, which is an everyday
  batch shape -- the report would be confidently wrong about routine weeks. The
  real signal is a scoped package pinned to its unscoped namesake, as
  `@vitest/coverage-v8` is to `vitest`. Accepted limitation: a scoped cluster
  with no unscoped root in the batch is not detected, which costs nothing because
  either member alone is a singleton no grouping rule would have caught.
- **`verify_union` compares a flat set of added lines with file identity
  discarded, and does not consider deletions.** Its docstring's "no more, no
  less" is therefore stronger than what it checks: the same added text in a
  different file, or member additions accompanied by unrelated deletions, both
  pass. It does reliably catch a smuggled added line, including relocated and
  `++`-prefixed shapes that defeated three earlier implementations. Treat it as a
  guard against added content, not a full diff equivalence check.
- **`attention:failing` has no flake exemption** (delta 7), so the operator makes
  that call. The runbook says so at the point of use.

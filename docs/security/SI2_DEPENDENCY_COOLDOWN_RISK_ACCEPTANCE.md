# Risk Acceptance: Dependency Update Cooldown (NIST 800-53 SI-2)

**Last Updated:** 2026-09-23
**Control:** NIST 800-53 **SI-2 Flaw Remediation** (supporting: SI-2(2), SI-5, RA-5)
**Status:** Accepted
**Owner / Accepting authority:** Platform Engineering
**Implemented in:** `scripts/security/dep_triage.py` (`PACKAGE_COOLDOWN_DAYS`, `ACTION_COOLDOWN_DAYS`, `rule_cooldown`)
**Triage cadence:** Monthly — `0 16 1 * *`, 16:00 UTC on the 1st — plus `workflow_dispatch` on demand
**Operating procedure:** [`docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md`](../runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md)
**Review cadence:** Quarterly, with `docs/DEFERRED_WORK_REGISTRY.md`

---

## Why this is a separate document

This lives under `docs/security/` rather than inside the triage runbook because
its audience is different. The runbook is read on the morning of a triage run by
an operator with five minutes; this is read by an assessor, a customer security
questionnaire, or whoever has to explain why a known-published fix sat unmerged
while the report said "held". It also outlives the runbook's procedures — the ceiling and the
override path below remain the commitment even if the tooling is rewritten. The
runbook links here from its `held:cooldown` row; this links back.

## Statement

**Accepted risk:** Project Aura deliberately delays the merge recommendation for
freshly published dependency versions by **3 days for packages** and **7 days for
GitHub Actions**. A dependency update that remediates a published flaw may
therefore be recommended for merge later than it could have been.

**Scope:** The delay is applied by the Dependabot triage classifier, which is
**advisory only**. It merges nothing, approves nothing and blocks nothing; the
`main-protection` ruleset's one-human-approval requirement is the only merge
gate, unchanged. The latency is procedural — it exists to the extent operators
follow the report — not mechanical.

**There is no automated exemption today.** A security-advisory fast path that
would have let CVE/GHSA-citing PRs skip the cooldown was specified, built, and
then removed. It had zero true positives: real Dependabot security PR bodies cite
the advisory id inside a collapsible `<details>` block, which the detector did not
read. Its false positives were worse than its absence — ordinary bumps whose
embedded upstream release notes mentioned any historical CVE were treated as
security updates, and those landed disproportionately on `docker` and
`github-actions` bumps. At the time both carried a *permanent* policy hold, which
the bypass stripped outright rather than shortening a three-day wait. The `docker`
half of that hold has since been demoted to an advisory note and the
`github-actions` half has not — see *Deployed control set* below. A body-text
heuristic is the wrong primitive for a control that removes two guards. The manual
override in this document is the exemption path.

## Rationale for the latency

A freshly published release is the window in which a compromised version is still
undetected. Registry-level supply-chain compromises are typically discovered and
yanked within hours to days of publication by the ecosystem at large, so an
install that waits out that window is materially less likely to pull the
malicious artifact than one that installs on publication day.

**What this defends against:** the `event-stream`, `ua-parser-js` and `node-ipc`
class — a maintainer account compromise or a malicious maintainer publishing a
poisoned version that the wider ecosystem identifies within days.

**What this does not defend against, stated plainly:** slow-burn insider
compromise. The `xz-utils` backdoor was built over roughly two years by a trusted
contributor and would have passed a 3-day, 7-day or 90-day cooldown untouched.
The cooldown buys time against fast-detected compromise and nothing else. It is
not a code-review substitute, not a malware scan, and not a supply-chain
integrity control.

Actions get the longer window because they are SHA-pinned supply-chain surface
executed inside the repository's own CI with repository credentials — a
compromised action runs with more reach than a compromised library, and the
`tj-actions/changed-files` incident is the local precedent.

The rule also holds when the release age is **unknown**. That is an abstention,
not a finding: the collector could not obtain a publish timestamp, so the PR
queues for a human rather than passing unexamined.

## Deployed control set

The classifier's holds are the inventory this document should be held to. As of
2026-09-23:

| Hold | Fires on | Status |
|------|----------|--------|
| `held:cooldown` | Release younger than 3d (packages) / 7d (Actions) | Deployed — the subject of this document |
| `held:no-release-metadata` | No publish timestamp resolvable, so the cooldown could not be evaluated | Deployed — an abstention, not a finding |
| `held:risk-tier` | Package is At-Risk or Replace-Now in `DEPENDENCY_RISK_REGISTER.md` | Deployed |
| `held:pinned-by-policy` | Package carries a documented deliberate cap (`tree-sitter < 0.26`) | Deployed |
| `held:grouped-unparsed` | Grouped update whose members could not be parsed, so the per-package holds never ran | Deployed |
| `coupled` | Member of a multi-PR update family; no member is individually mergeable | Deployed |
| `held:policy-review` | Diff touches a file under `.github/workflows/` | Deployed, **narrowed** — see below |
| `held:major-review` | Major semver bump | **Removed.** No longer exists |

Above all of them, and unaffected by any of this: the `main-protection` ruleset
requires one human approval plus four passing status checks on every pull
request. That is the only actual merge gate, and it is what every argument in
this document ultimately rests on.

### Two holds were reduced in September 2026

This document previously cited both of them. It no longer claims either, and the
reasoning below is stated rather than the line simply deleted.

**`held:major-review` was removed outright.** A major semver bump is now an
advisory *note* attached to whatever classification the PR otherwise earns, so a
major bump can reach `candidate` and `merge-safe`. Nothing in the classifier
reviews breaking changes any more. The observation was demoted because its entire
content — the leading version integer went up — is written in the PR title the
reviewer is already reading, not because breaking changes stopped mattering.

**Effect on this risk acceptance, stated plainly:** the argument is weaker than it
was. A major bump used to be routed to a human by two independent mechanisms; it
is now routed by one, the `main-protection` approval. That remaining mechanism is
the stronger of the two — it blocks the merge, where the hold only printed a
sentence — but it depends on the reviewer reading the version numbers in the
title. No automated control substitutes for that, and this document does not
claim one.

**`held:policy-review` was narrowed to `.github/workflows/` only.** Dockerfile and
`pyproject.toml` changes became advisory notes on the same "the diff is legible"
reasoning. The workflow case was kept because it is not legible: a `uses:` diff
shows one opaque 40-hex SHA replacing another, which proves the pin moved and says
nothing about what the new pin points at. SHA pinning only helps if a human
confirms the new SHA is the one intended, and nothing in the classifier confirms
that. This is the most credential-adjacent surface in the repository — the batch
that motivated the work contained an `aws-actions/configure-aws-credentials` bump,
the action that performs AWS credential assumption — so the hold is what puts the
confirmation in front of someone.

**A hold that persists past 7 days is not a cooldown hold.** It is one of the
other classifications in the table above, or an `attention:*` code, each with its
own procedure in the runbook and its own tracking. Cooldown expiry is automatic
and requires no action.

## Remediation ceiling

**No security-relevant dependency update is held by this cooldown for more than
7 calendar days from the first triage run that holds it.** As of September 2026
this is a *procedural* commitment discharged by the operator, not a property the
schedule delivers by itself. Read the next two paragraphs before citing it.

Why 7:

- 7 days is the longest cooldown constant in the system, so no hold attributable
  to this rule can exceed it on its own terms.
- Anything longer would be a number we could not measure against, which is
  precisely what SI-2 requires us to be able to do.

**What the schedule alone delivers is one calendar month, not 7 days.** Triage
moved from weekly to monthly (`0 16 1 * *`) in September 2026. A release held at
one scheduled run is not re-evaluated by the schedule until the 1st of the
following month, so schedule-only worst-case latency on the *advice* is 28–31
days, not 7.

**How the 7-day ceiling is met anyway.** `workflow_dispatch` is retained and a
re-dispatch is one command (`gh workflow run "Dependabot Triage"`, per the
runbook). More importantly, the detection side did not change cadence: the
Dependency Risk Audit still runs **weekly**, so an unremediated flaw still
surfaces within 7 days, and the operator who reads it re-dispatches triage rather
than waiting for the 1st. The ceiling therefore rests on an operator acting on the
weekly audit. That is a weaker guarantee than the old weekly schedule produced
automatically, and it is recorded here as such.

**None of this gates a merge.** The cooldown is a sentence in an advisory report.
An operator who has decided to merge needs no triage run at all, and the override
procedure below is available at 0 days.

**Ceiling for actively exploited flaws: 0 days.** A CVE with known in-the-wild
exploitation, or any finding the weekly audit escalates as Critical/High without
an upstream fix, is overridden immediately by the procedure below. The cooldown
never applies to a flaw already being exploited, because the "still undetected"
premise it rests on is already false.

## Compensating control

The **Dependency Risk Audit** (`.github/workflows/dependency-risk-audit.yml`,
Mondays 14:00 UTC) still runs **weekly**. Triage moved to monthly; the audit did
not, and the divergence is deliberate — detection stays weekly while merge
*advice* batches up. The two now coincide only when the 1st of the month falls on
a Monday, so the audit is no longer a two-hour curtain-raiser for triage; it is
the standing weekly signal. It runs `pip-audit` across every
`requirements*.txt` and `npm audit` against `frontend/`, and diffs maintainer
staleness against `docs/security/DEPENDENCY_RISK_REGISTER.md`. Its output is
committed to `docs/security/audits/YYYY-WNN.md` via PR.

This is the measurement side of SI-2 and it is **not gated by the cooldown**. An
unremediated flaw stays on the audit report every week until the fix merges, so a
cooldown hold cannot hide a CVE — at worst it appears once more on the following
Monday's report, which is the fact the 7-day ceiling above depends on. When the
two jobs do land in the same morning the audit runs first by design, so the
operator reads known flaws before reading merge advice.

GitHub Dependabot security alerts are a second, continuous signal and are not
gated by anything in this system.

## Manual override procedure

**Merging the pull request directly is the override.** It is legitimate and
sufficient, and it is the documented path. The triage system merges nothing, so
there is nothing to bypass: the `main-protection` ruleset still requires one human
approval and all four required status checks, exactly as for any other change. A
cooldown hold is a sentence in a report, not a lock.

Do not override by editing `PACKAGE_COOLDOWN_DAYS` or `ACTION_COOLDOWN_DAYS`. That
changes the policy for every future PR in order to release one, and it is a change
to a security control that requires review under the runbook's escalation rules.

Procedure:

1. **Decide and record the trigger.** Which advisory, which package, which fixed
   version. Confirm the PR actually contains the fix — read the upstream release,
   not the PR title.
2. **Merge the PR** through the normal flow: one human approval, all four required
   contexts green.
3. **Log it in two places:**
   - A comment on the rolling **Dependabot triage** issue, naming the PR, the
     advisory id, and one line of reasoning. The issue body is rewritten each run;
     comments are not, so the comment is the durable record.
   - The commit, using the `security:` prefix with the advisory id in the body, so
     Release Please surfaces it in the **Security** section of `CHANGELOG.md`.
4. **If the package is At-Risk or Replace-Now in the register**, add a row to the
   register's *Replacement Decisions Made* table as well.

The audit trail an assessor will look for is therefore: the GitHub PR timeline
(who approved, when, which checks passed), the git commit, the `CHANGELOG.md`
Security entry, and the triage issue comment. No step of the override is
performed by automation, and no automation can perform it.

## Known imprecision

**The schedule makes the 3-day and 7-day windows behave identically.** This was
true under the old weekly schedule and is more true under the monthly one. A
release observed at a scheduled triage run is either already older than 7 days —
in which case neither constant has any effect — or it is younger, in which case it
is held to the next run a month later, by which time both windows have long since
elapsed. There is no scheduled run at which the 3-day window could expire and the
7-day one could not. The distinction between the two constants is therefore
theoretical on the schedule alone; both read as "held until the next run."

The constants become distinguishable only under `workflow_dispatch`, which is the
same mechanism the remediation ceiling above relies on: an operator re-dispatching
four days after a release sees the package window expired and the Actions window
not.

Recorded rather than fixed, because fixing it means a more frequent schedule —
more CI cost and more operator attention, for a system that produces advice — and
the on-demand re-dispatch already covers the case where latency actually matters.
Revisit if effective latency ever becomes the binding constraint on a real
remediation.

## References

- Operating procedure: [`docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md`](../runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md)
- Compensating control: [`docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`](../runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md)
- Register: [`docs/security/DEPENDENCY_RISK_REGISTER.md`](DEPENDENCY_RISK_REGISTER.md)
- Audit history: [`docs/security/audits/`](audits/)
- Design + as-built deltas: [`docs/superpowers/specs/2026-09-19-dependabot-triage-design.md`](../superpowers/specs/2026-09-19-dependabot-triage-design.md)
- Control identifier conventions: [`docs/security/CONTROL_REGISTRY.md`](CONTROL_REGISTRY.md) (no `AURA-CTL-###` is assigned here; this is an accepted risk, not an implemented infrastructure control)

# Risk Acceptance: Dependency Update Cooldown (NIST 800-53 SI-2)

**Last Updated:** 2026-09-22
**Control:** NIST 800-53 **SI-2 Flaw Remediation** (supporting: SI-2(2), SI-5, RA-5)
**Status:** Accepted
**Owner / Accepting authority:** Platform Engineering
**Implemented in:** `scripts/security/dep_triage.py` (`PACKAGE_COOLDOWN_DAYS`, `ACTION_COOLDOWN_DAYS`, `rule_cooldown`)
**Operating procedure:** [`docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md`](../runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md)
**Review cadence:** Quarterly, with `docs/DEFERRED_WORK_REGISTRY.md`

---

## Why this is a separate document

This lives under `docs/security/` rather than inside the triage runbook because
its audience is different. The runbook is read at 9am on a Monday by an operator
with five minutes; this is read by an assessor, a customer security
questionnaire, or whoever has to explain why a known-published fix sat unmerged
for four days. It also outlives the runbook's procedures — the ceiling and the
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
`github-actions` bumps, where the bypass stripped a *permanent* policy hold rather
than a three-day wait. A body-text heuristic is the wrong primitive for a control
that removes two guards. The manual override in this document is the exemption
path.

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

## Remediation ceiling

**No security-relevant dependency update is held by this cooldown for more than
7 calendar days from the first triage run that holds it.**

Why 7:

- 7 days is the longest cooldown constant in the system, so no hold attributable
  to this rule can exceed it on its own terms.
- The triage runs weekly (Mondays 16:00 UTC). A release held at one run is
  re-evaluated at the next, 7 days later, at which point both the 3-day and the
  7-day window have necessarily elapsed. 7 is therefore the true worst case for
  both ecosystems, not just for Actions.
- Anything longer would be a number we could not measure against, which is
  precisely what SI-2 requires us to be able to do.

**A hold that persists past 7 days is not a cooldown hold.** It is a different
classification — `held:major-review`, `held:policy-review`,
`held:pinned-by-policy`, `held:risk-tier`, `attention:*` — each of which has its
own procedure in the runbook and its own tracking. Cooldown expiry is automatic
and requires no action.

**Ceiling for actively exploited flaws: 0 days.** A CVE with known in-the-wild
exploitation, or any finding the weekly audit escalates as Critical/High without
an upstream fix, is overridden immediately by the procedure below. The cooldown
never applies to a flaw already being exploited, because the "still undetected"
premise it rests on is already false.

## Compensating control

The weekly **Dependency Risk Audit** (`.github/workflows/dependency-risk-audit.yml`,
Mondays 14:00 UTC, two hours before triage) runs `pip-audit` across every
`requirements*.txt` and `npm audit` against `frontend/`, and diffs maintainer
staleness against `docs/security/DEPENDENCY_RISK_REGISTER.md`. Its output is
committed to `docs/security/audits/YYYY-WNN.md` via PR.

This is the measurement side of SI-2 and it is **not gated by the cooldown**. An
unremediated flaw stays on the audit report every week until the fix merges, so a
cooldown hold cannot hide a CVE — at worst it appears once more on the following
Monday's report. The audit runs first by design: the operator reads known flaws
before reading merge advice.

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

**The weekly schedule makes the 3-day and 7-day windows behave identically.** A
release observed at a Monday 16:00 triage run is either already older than 3 days
— in which case the package cooldown has no effect at all — or it is younger, in
which case it is held to the next Monday, 7 days later. There is no run in between
at which a 3-day window could expire. The distinction between the two constants is
therefore currently theoretical; both behave as "held until next Monday."

Recorded rather than fixed, because fixing it means either a more frequent
schedule (more CI cost, more operator attention, for a system that produces
advice) or a mid-week re-dispatch by the operator — which is already available on
demand via `gh workflow run "Dependabot Triage"` when it matters. Revisit if the
effective latency ever becomes the binding constraint on a real remediation.

## References

- Operating procedure: [`docs/runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md`](../runbooks/DEPENDABOT_TRIAGE_RUNBOOK.md)
- Compensating control: [`docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`](../runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md)
- Register: [`docs/security/DEPENDENCY_RISK_REGISTER.md`](DEPENDENCY_RISK_REGISTER.md)
- Audit history: [`docs/security/audits/`](audits/)
- Design + as-built deltas: [`docs/superpowers/specs/2026-09-19-dependabot-triage-design.md`](../superpowers/specs/2026-09-19-dependabot-triage-design.md)
- Control identifier conventions: [`docs/security/CONTROL_REGISTRY.md`](CONTROL_REGISTRY.md) (no `AURA-CTL-###` is assigned here; this is an accepted risk, not an implemented infrastructure control)

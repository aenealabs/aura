# Dependabot Triage Runbook

**Last Updated:** 2026-09-25
**Workflow:** `.github/workflows/dependabot-triage.yml` (monthly -- 16:00 UTC on the 1st -- plus `workflow_dispatch`)
**Scripts:** `scripts/security/dep_triage_collect.py` (network I/O), `scripts/security/dep_triage.py` (classifier; its module docstring is the authority on what exists)
**Report:** rolling GitHub issue titled **Dependabot triage**, labelled `dependencies` + `automated`
**Owner:** Platform Engineering

## What It Does

Lists open Dependabot pull requests, detects **coupled families** -- sets of PRs
that cannot be merged individually -- and rewrites a rolling issue with the
result. It is read-only: it merges nothing, approves nothing, holds nothing, and
puts no labels on Dependabot PRs. The `main-protection` ruleset (one human
approval plus four required status checks) remains what gates every merge. This
job does the one thing that gate cannot: notice that a PR is **green and still
unsafe to merge on its own**.

Dispatch it by hand any time you are actually planning a dependency sweep;
waiting for the 1st is never required. The sibling
[`DEPENDENCY_RISK_AUDIT_RUNBOOK.md`](DEPENDENCY_RISK_AUDIT_RUNBOOK.md) (weekly,
Mondays 14:00 UTC) is the flaw-detection control and is independent of this job.

## The Three Classifications

Every open PR gets exactly one code. Source of truth is `CODE_*` in
`scripts/security/dep_triage.py`.

| Code | What it means | What you do |
|------|---------------|-------------|
| `candidate` | No objection found here. Not a safety verdict. | Review and merge normally. One approval and the four required checks still apply. |
| `coupled` | Member of a multi-PR update family, named by key (`github/codeql-action`, `npm:/frontend:vitest`). | **Never merge alone, even fully green.** Consolidate the family -- see below. |
| `excluded:non-dependabot` | Author is not a recognised Dependabot login. | Out of scope. Release Please and human PRs land here; review them normally. |

## Consolidating a Coupled Family

Manual procedure. When the report names a family, create **one** branch that
moves every member's change together and open a **single** PR.

Merging one member alone leaves the repository inconsistent. That is the entire
reason this tool exists. A four-way `github/codeql-action` split is the worked
example: CodeQL refuses to run when its sub-actions disagree on version, so three
of the four PRs failed their own CI and the fourth passed only because it ran in a
workflow with no paired `init`/`analyze` step. Read commit `ad67a34` -- its
message states the failure mode, the member PRs, and the ref change applied to
all four.

```bash
git fetch origin
git switch -c "dep-consolidate/<family>-<version>" origin/main
# apply every member's change in this one branch, then:
gh pr create --title "chore(deps): bump <family> to <version> across all refs"
```

Push from your own account, not from CI: a PR opened with `GITHUB_TOKEN` does not
trigger workflow runs, so it can never satisfy the required contexts in
`main-protection`. Leave the member PRs open and comment on them -- Dependabot
retires them once the version lands.

The report names the head commit each row was computed against. Dependabot
force-pushes on rebase, so confirm the heads still match before you build the
branch.

## Reading the Rolling Issue

One long-lived issue, rewritten in place every run. The workflow finds it by
listing **open** issues labelled `automated` and matching the exact title
`Dependabot triage`.

| Rule | Why |
|------|-----|
| **Never close it.** | The lookup finds nothing and opens a new issue on every run thereafter. |
| **Never remove the `automated` label.** | The label is the lookup key, not decoration. |
| **Never rename it.** | The title is matched exactly. |
| **Do not edit the body.** | The next run overwrites it. Put notes in a comment; comments survive. |

The timestamp in the first heading is the only freshness signal, and Dependabot
supersedes PRs continuously. **Do not act on a stale report** -- re-dispatch and
read the new one:

```bash
gh workflow run "Dependabot Triage"
```

Check the report's `Bump titles:` line. If it says a whole batch named no
package, Dependabot's title format has moved, no family can be detected, and the
job is reporting a clean batch while its one control is inert. Fix the parser
before trusting the report.

If duplicate issues appear, close all but the one with the longest comment
history. Verify exactly one remains:

```bash
gh issue list --state open --label automated --json number,title \
  --jq '[.[] | select(.title == "Dependabot triage")]'
```

## Kill Switch

```bash
gh workflow disable "Dependabot Triage"      # stops schedule and dispatch both
gh workflow enable  "Dependabot Triage"      # resume
gh workflow list --all | grep -i dependabot  # confirm state
```

Nothing degrades. The job produces advice, so its absence costs a manual triage,
not an outage. Comment on the rolling issue saying who disabled it and why, so
nobody reads a frozen report as current.

## When You Disagree With the Report

**Your judgement wins on the individual PR.** The report is advisory: it merges
nothing and blocks nothing. If it calls a PR coupled and you know it is fine,
merge it.

**But a disagreement is not resolved until the rule changes.** A one-off override
that leaves no fixture behind is how a classifier decays into something nobody
trusts and everybody re-checks by hand -- at which point the team pays for the
automation *and* the manual work.

1. **Act now** on your own judgement. Do not wait for a rule change.
2. **Then open a PR** adding a fixture built from the real observed case, and
   change the rule so the fixture classifies the way you decided. The
   `snapshot.json` in that run's `triage` artifact is the capture -- use it. Do
   not hand-write a fixture; every detector here that was validated against an
   invented one has been wrong in production at least once.
3. **Record it** in a comment on the rolling issue, linking the PR.

Arbiter is the owner named in the header block.

## References

- Weekly flaw-detection sibling: [`DEPENDENCY_RISK_AUDIT_RUNBOOK.md`](DEPENDENCY_RISK_AUDIT_RUNBOOK.md)
- Design record and as-built deltas: [`docs/superpowers/specs/2026-09-19-dependabot-triage-design.md`](../superpowers/specs/2026-09-19-dependabot-triage-design.md)
- Workflow: `.github/workflows/dependabot-triage.yml`

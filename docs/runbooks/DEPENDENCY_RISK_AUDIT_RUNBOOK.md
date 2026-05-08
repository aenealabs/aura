# Dependency Risk Audit Runbook

**Last Updated:** 2026-05-08
**Workflow:** `.github/workflows/dependency-risk-audit.yml`
**Script:** `scripts/security/dep_risk_audit.py`
**Register:** `docs/security/DEPENDENCY_RISK_REGISTER.md`
**Tracking Issue:** #138
**Owner:** Platform Engineering

---

## Overview

The dependency risk audit runs every Monday at 14:00 UTC and produces a markdown report covering:

1. **Python CVEs** via `pip-audit` against every `requirements*.txt` in the repo.
2. **Frontend CVEs** via `npm audit` against `frontend/`.
3. **Maintainer staleness** against the Watch / At-Risk tiers from the register, using `pip show` and `npm view` metadata.

The report is posted as a comment on tracking issue #138 and stored as a workflow artifact for 90 days.

## Triage Decision Tree

When the audit posts a new report, walk this list top to bottom.

### 1. Any Python or npm CVE listed?

For each new entry not already tracked:

- **Has a fix version?** -> Open a PR pinning to the fix version. Standard PR review.
- **No fix yet?** -> Decide whether to:
  - Pin to the unpatched version and accept the risk (document in the register's "At-Risk" table with a one-line rationale).
  - Replace the package (treat as Replace-Now; file an issue).
  - Vendor in-tree if the patch is small enough to apply locally.

Any CVE marked **critical** or **high** that lacks a fix should escalate to an issue tagged `security` within 24 hours of the audit run.

### 2. Any tracked package's last-release date older than 12 months?

For each:

- **Was the package recently deprecated by its maintainer?** Check the project README / GitHub repo. If yes -> move to **Replace-Now** in the register and file a remediation issue.
- **Is the project still alive but slow?** -> Stay in **At-Risk** but document the staleness signal in the register entry (e.g., "last release 2025-06; project alive on the dev branch but no releases").
- **Has a viable fork emerged?** -> Evaluate the fork. If healthier, move toward swap.

### 3. Has anything moved up a tier?

Sometimes a package gets compromised, deprecated, or formally announces end-of-life between audits. Cross-reference the news against the register:

- **Compromise / supply-chain incident** -> Replace-Now immediately. Audit usage in repo: `grep -rn "<package-name>" src/ frontend/`.
- **Maintainer EOL announcement** -> Move to At-Risk; file a swap-tracking issue.

### 4. New package added to the project since last audit?

Cross-reference `git diff <last-audit-sha>..HEAD -- requirements*.txt frontend/package.json`. Anything new should land in the register at the appropriate tier. The register PR should accompany the dep-add PR; if the register wasn't updated, file a follow-up to do so.

## Common Findings and Their Right Answers

### "py 1.11.0 -- PYSEC-2022-42969" or similar transitive-dep CVE

`py` is a transitive dep of `pytest` historically. The CVE is a ReDoS only triggered through SVN repository handling. Project Aura does not parse SVN repos; the practical risk is zero. Action:

- Document in the register's "At-Risk" table with `accept-and-monitor` as the mitigation.
- Re-evaluate when pytest cuts a release that drops `py`.

This is a template for "CVE with no exploit path in our usage": document the no-exploit reasoning in the register, accept, monitor.

### "npm audit -- N vulnerabilities, all in dev dependencies"

npm audit's default output includes dev-only deps. For a frontend that ships static assets:

- **Production-affecting** (in `dependencies`, not `devDependencies`) -> Same as a CVE: pin or swap.
- **Dev-only** -> Lower urgency; fix when cycling deps anyway. Don't open issues for these unless they affect the build pipeline.

### "Workflow failed: pip-audit exited 2"

pip-audit can fail on PyPI rate limits or network blips. Re-run the workflow once. Persistent failures indicate either a tool-version mismatch or a packaging issue in `requirements.txt`; investigate the audit script's stderr output in the run logs.

## Acting on a Replace-Now

When a dep moves to Replace-Now:

1. File an issue using the template:
   ```
   Title: Replace <package> -- <reason>
   Labels: security, dependencies, P1
   ```
2. The issue body must include:
   - Why it's Replace-Now (deprecated / compromised / EOL).
   - Where the package is used (`grep -rn "<package>"` output).
   - Proposed replacement and migration scope.
   - Acceptance criteria.
3. Update the register's "Replacement Decisions Made" table once the swap is merged.

## Manual Runs

```bash
# Run the audit locally against your venv. Skip the npm step if no
# Node setup, or the pip step if you don't have pip-audit installed.
python -m scripts.security.dep_risk_audit \
    --output /tmp/dep-audit.md

# Skip pip-audit (if you don't have it installed):
python -m scripts.security.dep_risk_audit \
    --output /tmp/dep-audit.md --skip-pip-audit

# Skip npm audit (if you don't have Node set up):
python -m scripts.security.dep_risk_audit \
    --output /tmp/dep-audit.md --skip-npm-audit
```

The script is stdlib + `pip-audit` + `npm` only -- no other Python imports or external API calls.

## When Not to Touch the Register

The register is the source of truth for tracked deps. Don't:

- Silence an audit alert by removing a dep entry from the register.
- Move a dep up a tier without updating the mitigation field.
- Mark something Healthy when you couldn't verify the backing yourself; leave it Watch and add a note.

The audit's value is the diff against the register. If the register is wrong or stale, the audit's signal is wrong too.

## Publishing a Security Advisory (the outbound bridge)

The audit detects. `SECURITY.md` describes how customers consume our advisories. This section is the connecting playbook: when a triaged finding warrants a customer-visible advisory, how do we publish it.

See the worked example: [`docs/security/SAMPLE_ADVISORY_TJ_ACTIONS.md`](../security/SAMPLE_ADVISORY_TJ_ACTIONS.md) (a backfilled GHSA for the `tj-actions/changed-files` swap, formatted exactly as a real advisory would read).

### When to publish

Publish a GHSA when **all** of the following are true:

1. The vulnerability affects a **shipped** Aura release (anything tagged on `main`). Findings against `main` HEAD that haven't shipped yet do not need an advisory; the patch lands before the release notes do.
2. The vulnerability is **reachable** in Aura's actual call paths. Most upstream CVEs are not. The audit's triage step (the runbook decision tree above) determines reachability.
3. The vulnerability is **actionable** by self-hosted operators. If the only mitigation is "wait for the next release we already shipped," there's no operator action required and the regular release notes are enough.

When in doubt: publish. A purely-informational advisory ("this CVE was reported upstream; not exploitable in Aura") still lets compliance teams at customer organizations close the loop with a citable reference.

### Who decides severity

Severity is the audit owner's call, with these defaults:

- **Upstream CVSS** is the starting point. Adjust *down* (not up) if Aura's usage of the affected code path is bounded (e.g., upstream RCE that we only exercise behind authenticated admin paths).
- **Critical / High** require a second reviewer (typically the security lead) before publishing.
- **Medium / Low** can be published by the audit owner unilaterally.

The qualitative severity must match the *Severity Classification* table in `SECURITY.md` so customers see a consistent vocabulary across inbound and outbound disclosures.

### Drafting and publishing

1. **Draft** in the GitHub Security Advisories UI: `https://github.com/aenealabs/aura/security/advisories/new`. Use the worked example linked above as the formatting template.
2. **Cross-link** the patched release in the advisory body. The patched release is whatever Release Please cuts after the `security:` commit lands.
3. **Tag the commit** that fixes the issue with a `security:` prefix so Release Please surfaces it in the **Security** section of `CHANGELOG.md`. Include the GHSA URL in the commit body.
4. **Approval gate**:
   - Critical / High: second reviewer signs off in the draft GHSA before clicking Publish.
   - Medium / Low: audit owner publishes directly.
5. **Request a CVE** during the GHSA flow if the vulnerability is in code we author and upstream hasn't already issued one. For third-party CVEs, just reference the upstream CVE ID; don't request a duplicate.
6. **Publish**. The GHSA hits the Atom feed and Dependabot scanners automatically.

### What goes in the advisory

The required fields, with our conventions:

| Field | Convention |
|---|---|
| Title | `<component> -- <one-line summary>` (e.g., `tj-actions/changed-files -- supply-chain compromise (CVE-2025-30066)`) |
| Affected versions | Aura release range (e.g., `<= v1.7.0`). Use semver ranges when the audit can determine a clean cutoff; otherwise list specific versions. |
| Patched versions | The first Aura release containing the fix. |
| CVE | Upstream CVE if one exists. Don't coin our own. |
| Severity / CVSS | Per *Who decides severity* above. |
| Description | What the upstream vulnerability is, how Aura uses (or doesn't use) the affected component, and the resulting impact on a self-hosted Aura operator. |
| Mitigation | Update path; any workaround for operators who cannot update immediately. |
| Acknowledgements | Upstream researcher / reporter (if known). |

### Post-publication

- Add a short note to the audit register entry in `docs/security/DEPENDENCY_RISK_REGISTER.md` (in the `Replacement Decisions Made` table) if this advisory was tied to a Replace-Now action.
- The recurring audit's next run will see the patched dep in `requirements*.txt` / `package-lock.json` and the previous CVE will drop from the report -- this is the normal closure signal.

## References

- Register: `docs/security/DEPENDENCY_RISK_REGISTER.md`
- Script: `scripts/security/dep_risk_audit.py`
- Workflow: `.github/workflows/dependency-risk-audit.yml`
- Disclosure policy (inbound + advisory consumer guidance): [`SECURITY.md`](../../SECURITY.md)
- Worked-example advisory (dry-run for `tj-actions/changed-files`): [`docs/security/SAMPLE_ADVISORY_TJ_ACTIONS.md`](../security/SAMPLE_ADVISORY_TJ_ACTIONS.md)
- Tracking issue (audit feed): [#138](https://github.com/aenealabs/aura/issues/138)
- Tracking issue (advisory pipeline): [#141](https://github.com/aenealabs/aura/issues/141)

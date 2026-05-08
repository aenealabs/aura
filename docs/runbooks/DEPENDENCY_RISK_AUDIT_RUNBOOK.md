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

## References

- Register: `docs/security/DEPENDENCY_RISK_REGISTER.md`
- Script: `scripts/security/dep_risk_audit.py`
- Workflow: `.github/workflows/dependency-risk-audit.yml`
- Tracking issue: [#138](https://github.com/aenealabs/aura/issues/138)

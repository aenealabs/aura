# Sample Security Advisory: `tj-actions/changed-files` (worked example)

This document is a **dry-run / backfill**. It shows what a GitHub Security Advisory for the `tj-actions/changed-files` situation (commit `a216ab4`, May 2026) would have looked like if the disclosure pipeline described in `SECURITY.md` and `docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md` had been in place at the time.

The fields below are formatted to match the GitHub Security Advisories submission UI. To file a real advisory:

1. Open `https://github.com/aenealabs/aura/security/advisories/new`.
2. Copy the field values below into the corresponding form inputs.
3. Adjust the **Affected products** and **Patched versions** ranges to whatever Aura releases are actually affected at the time of filing.
4. Follow the *Drafting and publishing* steps in `docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`.

This sample is intentionally not filed as a live draft GHSA — filing a real advisory (even draft state) creates entries in security feeds that scanners and watchers consume, and a placeholder dummy in that feed would cause confusion. Use this markdown as a template; file the real advisory only when an actual incident warrants one.

---

## Title

```
tj-actions/changed-files -- supply-chain compromise (CVE-2025-30066) -- not exploitable in Aura's pinned configuration
```

## Affected products

`aenealabs/aura` -- specifically the `aura-security-review` GitHub Actions workflow.

## Affected versions

`<= v1.6.x`

(All Aura releases prior to the swap commit `a216ab4`. The pin was always SHA-locked to a known-good commit, so the original attack vector was closed at the SHA layer; this advisory documents the remediation completion.)

## Patched versions

`>= v1.7.0` (the first release after `a216ab4` lands; substitute the actual cut release tag at filing time).

## CVE

[CVE-2025-30066](https://nvd.nist.gov/vuln/detail/CVE-2025-30066) -- assigned by upstream / NVD; we do not coin a separate CVE.

## Severity

**Informational** for Aura. The upstream CVSS is high (the underlying compromise allowed secret exfiltration from any workflow run that resolved the action by tag rather than SHA), but Aura's usage was always SHA-pinned to `9426d40962ed5378910ee2e21d5f8c6fcbf2dd96` -- a commit predating the compromise -- so the original attack vector did not affect any Aura release.

We are publishing this advisory because:

1. Operators tracking GHSA / Dependabot for the Aura repo will see the upstream CVE in their dependency graph; this advisory documents *our* posture, including SHA pin and remediation, so their compliance teams have a citable reference.
2. The remediation moved Aura off the single-maintainer compromised action entirely (replaced with a native `git diff` step), which removes a category of supply-chain risk going forward.

## Description

`tj-actions/changed-files` was compromised in March 2025 ([CVE-2025-30066](https://nvd.nist.gov/vuln/detail/CVE-2025-30066)). The maintainer's release tag was rewritten to publish a malicious version that exfiltrated secrets from any workflow run that referenced the action by tag (e.g., `@v47`) rather than by commit SHA.

### Aura's usage

Aura referenced this action only from `.github/workflows/aura-security-review.yml`, and only with a SHA pin:

```yaml
uses: tj-actions/changed-files@9426d40962ed5378910ee2e21d5f8c6fcbf2dd96 # v47.0.6
```

The pinned SHA predates the compromise, and GitHub Actions resolves SHA-pinned references against the immutable commit (not the rewritten tag), so the malicious version was never executed in any Aura workflow run. Audit logs of workflow runs from `aenealabs/aura` confirm no runs against the compromised tags.

### Why we're moving off the action anyway

Continuing to depend on a single-maintainer action with a documented compromise is a category of risk we don't need. The action's functionality (filter PR-changed files by glob) is ~15 lines of native bash using `git diff --name-only` against the PR's base/head SHAs. The native step has no external dependencies, no third-party action surface, and no maintainer-handover risk.

## Mitigation

For operators of past Aura releases (`<= v1.6.x`):

- **Verify your workflow runs**: SHA-pinning meant the original attack vector did not fire, but if you forked the workflow and unpinned, audit your past runs for unexpected secret exfiltration. The compromise window for the upstream tag rewrite was narrow and well-publicized.
- **No code change required on your end if you used the upstream Aura release verbatim.** The replacement lands automatically when you update to `>= v1.7.0`.

For operators of `>= v1.7.0`:

- No action required. The action has been replaced by a native `git diff` step in the same workflow.

## Resolution path in Aura

Tracked in [#139](https://github.com/aenealabs/aura/issues/139). Resolved by commit `a216ab4` (`fix(security): close both Replace-Now items from dependency risk register`).

The replacement step preserves the same outputs (`any_changed`, `all_changed_files`) so downstream workflow steps were not affected. Verified by running the bash filter against synthetic populated and empty diff inputs before the commit landed.

## Acknowledgements

- Upstream supply-chain compromise reported by the broader security community; CVE assigned via NVD.
- Internal detection: tracked through the dependency risk audit (`scripts/security/dep_risk_audit.py`) on its first triage pass.

## References

- Upstream CVE: [CVE-2025-30066](https://nvd.nist.gov/vuln/detail/CVE-2025-30066)
- Aura issue: [#139](https://github.com/aenealabs/aura/issues/139)
- Aura commit: `a216ab4`
- Disclosure policy: [`SECURITY.md`](../../SECURITY.md)
- Dependency risk register entry: [`docs/security/DEPENDENCY_RISK_REGISTER.md`](DEPENDENCY_RISK_REGISTER.md) -- `Replacement Decisions Made` table
- Audit runbook (publication playbook): [`docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`](../runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md) -- *Publishing a Security Advisory*

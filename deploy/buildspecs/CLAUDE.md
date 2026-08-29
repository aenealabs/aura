# Buildspec Development Guide

> Full CI/CD guide: `docs/deployment/CICD_SETUP_GUIDE.md` (563 lines)

---

## Critical Rules

1. **Single Source of Truth:** CodeBuild is the ONLY authoritative deployment method
2. **No Duplicate Builds:** Never trigger CodeBuild while another build is running
3. **No Manual Deployments:** Manual deploys break audit trail and IAM consistency
4. **Buildspec Runtime Budget (replaces the prior 600-line cap):** Each parent layer
   buildspec must have its `TimeoutInMinutes` set to at least `2 * p95(observed cold-start
   duration)`. Default `TimeoutInMinutes: 480` (CodeBuild's 8-hour max) is acceptable
   for any parent buildspec that runs >50 sequential `cloudformation deploy` calls. Line
   count is a poor proxy for risk -- `cloudformation deploy --no-fail-on-empty-changeset`
   is idempotent, so warm-state deploys finish in seconds regardless of the number of
   stacks. Cold-start risk is the only real concern, and a generous timeout addresses it
   directly. Documented under issue #131; rationale is in Tara's review.
5. **No Parent -> Sub-Layer CodeBuild Nesting:** The only `aws codebuild start-build`
   chain that is allowed is `bootstrap` -> parent layer projects (which is structurally
   unavoidable for fresh-account deploys). Parent layer buildspecs MUST do their work
   inline, not by invoking sub-layer CodeBuild projects via `start-build` and polling.
   When sub-layer indirection is genuinely required (different IAM scope, parallel
   execution, independent retry), invoke the sub-layer CodeBuild project from the
   Step Functions deployment pipeline (`deployment-pipeline.yaml`), NOT from a parent
   buildspec. The reference model is `codebuild-serverless-symbol-resolver.yaml`.

---

## Deployment Commands

```bash
# Trigger deployment
aws codebuild start-build --project-name aura-compute-deploy-dev

# Check for running builds first
aws codebuild list-builds-for-project --project-name {project} --max-items 1
```

**If you manually deployed:** Delete stack -> Redeploy via CodeBuild to restore single source of truth.

---

## CloudFormation Deploy Pattern

All buildspecs use the standard deploy command. Do not invent create/update branching logic:

```bash
aws cloudformation deploy --no-fail-on-empty-changeset
```

See `buildspec-data.yml` for the canonical pattern.

---

## Buildspec Naming Convention

Buildspecs follow the layer naming convention from the CloudFormation stack system. Each buildspec manages templates within its layer scope. See `deploy/cloudformation/CLAUDE.md` for the layer reference table.

---

## Validation

- cfn-lint is NOT for buildspec YAML files (buildspecs are not CloudFormation templates)
- Validate buildspec syntax with standard YAML linting only
- The pre-commit `check-yaml` hook covers buildspec syntax validation
- `.github/workflows/buildspec-validation.yml` validates changed buildspecs on the pull request

---

## What Gates a Pull Request (as of #415, 2026-08-29)

The repository has three PR quality gates, all in `.github/workflows/code-quality.yml`, plus the
separate `buildspec-validation.yml`. Which ones fire depends on which tree you touched:

| Changed tree | Gate |
|---|---|
| `deploy/buildspecs/**` | `Validate Changed Buildspecs` (`buildspec-validation.yml`) |
| `deploy/cloudformation/**` | cfn-lint step inside `Python Quality & Tests` (#406) |
| `frontend/**` | `Frontend Quality & Tests` (#415) |
| `src/`, `tests/`, Python config | Full Python steps in `Python Quality & Tests` |

The `src/` and `tests/` row keys on the **path prefix only**. The `python_changed` detector
(`code-quality.yml:132`) matches bare `^src/` and `^tests/` with no `.md` exclusion, so a
markdown-only edit under either tree runs the entire Python job. #420 changed one file,
`tests/CLAUDE.md`, and its `Python Quality & Tests` job ran 19m44s (run `33238518088`). Markdown
elsewhere, including `docs/`, costs nothing. The `pre-commit` step runs unconditionally and already
covers markdown, so the full run adds no signal -- but it is a required check, so it fails in the
safe direction. See `docs/deployment/GITHUB_ACTIONS_SETUP.md`.

Two consequences that matter when editing a buildspec:

1. **A buildspec change does not run cfn-lint.** The PR-level template gate added in #406 keys on
   `^deploy/cloudformation/.*\.(yaml|yml)$`. If you change a buildspec's `cloudformation deploy`
   call for a template you did not edit, nothing lints that template on this PR -- only the 02:00
   nightly job will, after merge.
2. **The `deploy/buildspecs/**` glob is not in `code-quality.yml`'s trigger paths.**
   `Python Quality & Tests`
   is a required status check in the `main-protection` ruleset, and a required check that never runs
   reports as *missing* rather than passing. A buildspec-only PR is therefore exposed to the same
   deadlock class #406 fixed for CloudFormation and #415 fixed for the frontend. Inferred from the
   path filters and the ruleset; **not verified against a live PR**. If you hit it, add the path to
   the trigger list and gate the expensive steps in the job body -- do not narrow the trigger.

---

## cfn-lint Exit Codes in Buildspecs -- Unresolved

122 call sites across `deploy/buildspecs/*.yml` invoke cfn-lint as
`cfn-lint template.yaml || echo "cfn-lint warnings (non-blocking)"`. That form makes **every** exit
code pass, including 2 / 6 / 8, which `deploy/cloudformation/CLAUDE.md` documents as "Fail build".
A template error in a deploy build is therefore swallowed today, while the PR gate and the nightly
job both use `scripts/cfn-lint-wrapper.sh` and fail correctly.

This divergence is flagged, not resolved: converting 122 sites could start failing deploy builds
that currently pass. See the "UNRESOLVED CONTRADICTION" note in
`deploy/cloudformation/CLAUDE.md` before changing either side.

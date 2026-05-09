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

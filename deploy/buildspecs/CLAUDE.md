# Buildspec Development Guide

> Full CI/CD guide: `docs/deployment/CICD_SETUP_GUIDE.md` (563 lines)

---

## Critical Rules

1. **Single Source of Truth:** CodeBuild is the ONLY authoritative deployment method
2. **No Duplicate Builds:** Never trigger CodeBuild while another build is running
3. **No Manual Deployments:** Manual deploys break audit trail and IAM consistency
4. **Buildspec Size Limit:** Max 600 lines per buildspec (`wc -l deploy/buildspecs/*.yml` to check)

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

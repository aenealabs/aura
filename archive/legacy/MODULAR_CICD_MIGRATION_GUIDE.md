# Modular CI/CD Migration Guide

## Overview

This guide outlines the migration from the monolithic `aura-infra-deploy-dev` CodeBuild project to the modular CI/CD architecture with separate CodeBuild projects per layer.

## Current State (As of Nov 25, 2025)

### ✅ What's Deployed

**CloudFormation Stacks:**
- Foundation Layer: `aura-networking-dev`, `aura-security-dev`, `aura-iam-dev` ✅
- Data Layer: `aura-neptune-dev`, `aura-dynamodb-dev`, `aura-s3-dev` ✅
- Compute Layer: `aura-eks-dev` ✅

**CodeBuild Projects:**
- `aura-codebuild-foundation-dev` - EXISTS (never executed)
- `aura-codebuild-data-dev` - EXISTS
- `aura-infra-deploy-dev` - EXISTS (old monolithic, failing)

### ❌ Problems Identified

1. **aura-foundation-deploy-dev** has no build logs (never executed)
2. **aura-infra-deploy-dev** has 10+ failed builds
3. **Foundation layer was NOT deployed via CI/CD** - deployed manually or via old monolithic project
4. **Modular architecture exists but is not being used**

---

## Root Cause Analysis

### Problem 1: aura-foundation-deploy-dev Never Executed

**Root Cause:**
- CodeBuild project was created via `deploy/cloudformation/codebuild-foundation.yaml`
- Project exists in AWS but was never triggered
- No GitHub webhook or manual trigger configured

**Evidence:**
```bash
$ aws codebuild list-builds-for-project --project-name aura-foundation-deploy-dev
[]
```

**Impact:**
- Foundation layer stacks exist in AWS (aura-networking-dev, aura-security-dev, aura-iam-dev)
- This means foundation was deployed outside the modular CI/CD pipeline
- Likely deployed manually via AWS CLI or through the old monolithic project

### Problem 2: aura-infra-deploy-dev Failing

**Root Cause:**
- Old monolithic project attempts to deploy ALL layers in one buildspec
- Uses `deploy/buildspec-modular.yml` which calls multiple deployment scripts
- BUILD phase fails (likely due to deploy-data.sh or deploy-compute.sh errors)
- Post-build smoke tests pass, indicating infrastructure is actually healthy

**Evidence:**
```bash
Latest Build: aura-infra-deploy-dev:4aa161ab-5b34-4225-9040-70d068cf425a
Status: FAILED
Failed Phase: BUILD (7 seconds)
Date: Nov 21, 2025 21:21 UTC
```

**Impact:**
- Creates noise with failed builds
- Confusing status (builds fail but infrastructure is deployed)
- Old architecture should be retired

---

## Migration Plan

### Phase 1: Clean Up Old Infrastructure ✅ READY

**Actions:**
1. Archive logs from `aura-infra-deploy-dev` for reference
2. Delete `aura-infra-deploy-dev` CodeBuild project
3. Delete `aura-codebuild-dev` CloudFormation stack (creates the old project)
4. Archive `deploy/buildspec-modular.yml` (move to `archive/legacy/`)

**Script:**
```bash
# Run the cleanup script
bash /tmp/cleanup-old-codebuild.sh
```

**Validation:**
```bash
# Verify deletion
aws codebuild list-projects --query 'projects' | grep -v "aura-infra-deploy-dev"

# Verify CloudFormation stack deleted
aws cloudformation describe-stacks --stack-name aura-codebuild-dev  # Should return error
```

---

### Phase 2: Configure Modular CI/CD Triggers

**Objective:** Set up proper triggers for each modular CodeBuild project

#### Option A: GitHub Webhooks (Recommended for Production)

**Prerequisites:**
- GitHub repository: `https://github.com/aenealabs/aura`
- GitHub personal access token with `repo` and `admin:repo_hook` permissions
- AWS CodeBuild GitHub OAuth connection

**Steps:**

1. **Create GitHub Connection (One-time setup):**
```bash
# Import GitHub source credentials
aws codebuild import-source-credentials \
  --server-type GITHUB \
  --auth-type PERSONAL_ACCESS_TOKEN \
  --token YOUR_GITHUB_PAT
```

2. **Update CodeBuild projects to enable webhooks:**

For each modular project, update the CloudFormation template:

```yaml
# Example for codebuild-foundation.yaml
Resources:
  FoundationCodeBuildProject:
    Type: AWS::CodeBuild::Project
    Properties:
      # ... existing properties ...
      Source:
        Type: GITHUB
        Location: https://github.com/aenealabs/aura
        BuildSpec: deploy/buildspecs/buildspec-foundation.yml
        GitCloneDepth: 1
      Triggers:
        Webhook: true
        FilterGroups:
          - - Type: EVENT
              Pattern: PUSH
            - Type: HEAD_REF
              Pattern: ^refs/heads/main$
            - Type: FILE_PATH
              Pattern: deploy/cloudformation/(networking|security|iam)\.yaml
```

3. **Redeploy CodeBuild CloudFormation stacks:**
```bash
# Foundation layer
aws cloudformation deploy \
  --stack-name aura-codebuild-foundation-dev \
  --template-file deploy/cloudformation/codebuild-foundation.yaml \
  --parameter-overrides \
    Environment=dev \
    ProjectName=aura \
    GitHubRepository=https://github.com/aenealabs/aura \
    GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM

# Repeat for data, compute, application, observability layers
```

#### Option B: Manual Triggers (Temporary / Development)

**Use Case:** Testing, one-off deployments, development

**Command:**
```bash
# Trigger foundation layer build
aws codebuild start-build --project-name aura-foundation-deploy-dev

# Trigger data layer build
aws codebuild start-build --project-name aura-data-deploy-dev

# Trigger compute layer build
aws codebuild start-build --project-name aura-compute-deploy-dev
```

#### Option C: EventBridge Scheduled Triggers

**Use Case:** Nightly deployments, drift detection, compliance checks

**Example:** Daily foundation layer validation at 2 AM UTC

```yaml
Resources:
  NightlyFoundationBuild:
    Type: AWS::Events::Rule
    Properties:
      ScheduleExpression: cron(0 2 * * ? *)
      Targets:
        - Arn: !GetAtt FoundationCodeBuildProject.Arn
          RoleArn: !GetAtt EventBridgeCodeBuildRole.Arn
          Id: FoundationNightlyBuild
```

---

### Phase 3: Test Modular Deployments

**Objective:** Verify each layer can be deployed independently

**Test Plan:**

1. **Foundation Layer Test:**
```bash
# Make a small change to networking.yaml (add a tag)
vim deploy/cloudformation/networking.yaml

# Commit and push to trigger webhook OR manually start build
git add deploy/cloudformation/networking.yaml
git commit -m "test: trigger foundation layer build"
git push origin main

# Monitor build
aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-dev \
  --max-items 1

# View logs
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow
```

2. **Data Layer Test:**
```bash
# Trigger data layer build manually
aws codebuild start-build --project-name aura-data-deploy-dev

# View logs
aws logs tail /aws/codebuild/aura-data-deploy-dev --follow
```

3. **Validate Outputs:**
```bash
# Check CloudFormation stack outputs
aws cloudformation describe-stacks \
  --stack-name aura-networking-dev \
  --query 'Stacks[0].Outputs' \
  --output table
```

---

### Phase 4: Establish Pipeline Standards

**Objective:** Ensure all future deployments follow the modular architecture

#### **Standard Operating Procedures:**

1. **Never deploy infrastructure manually** - Always use CodeBuild
2. **Each layer has a dedicated CodeBuild project**:
   - Foundation: `aura-foundation-deploy-dev`
   - Data: `aura-data-deploy-dev`
   - Compute: `aura-compute-deploy-dev`
   - Application: `aura-application-deploy-dev`
   - Observability: `aura-observability-deploy-dev`

3. **Layer Dependencies:**
   ```
   Foundation (networking, security, iam)
      ├── Data (neptune, opensearch, dynamodb, s3)
      ├── Compute (eks)
      └── Observability (secrets, monitoring)
           └── Application (bedrock infrastructure)
   ```

4. **Deployment Order:**
   - Deploy foundation layer FIRST
   - Wait for foundation to complete
   - Deploy data, compute, observability in parallel (they only depend on foundation)
   - Deploy application LAST (depends on all above)

5. **Change Detection:**
   - Use `deploy/scripts/detect_changes.py` to identify which layers changed
   - Only trigger builds for changed layers + their dependents

#### **Pipeline Guardrails:**

**Pre-deployment Gates:**
1. ✅ Smoke tests must pass (`tests/smoke/test_platform_smoke.py`)
2. ✅ CloudFormation templates must pass `cfn-lint` validation
3. ✅ AWS CloudFormation validate-template must succeed

**Post-deployment Validation:**
1. ✅ CloudFormation stacks must reach CREATE_COMPLETE or UPDATE_COMPLETE
2. ✅ Post-deployment smoke tests must pass
3. ✅ Stack outputs must be verified

**Example from buildspec-foundation.yml:**
```yaml
phases:
  pre_build:
    commands:
      # GATE 1: Validate templates
      - cfn-lint deploy/cloudformation/networking.yaml --ignore-checks W3002
      - aws cloudformation validate-template \
          --template-body file://deploy/cloudformation/networking.yaml

  build:
    commands:
      # Deploy and wait for completion
      - aws cloudformation create-stack --stack-name aura-networking-dev ...
      - aws cloudformation wait stack-create-complete --stack-name aura-networking-dev

  post_build:
    commands:
      # GATE 2: Verify outputs
      - aws cloudformation describe-stacks --stack-name aura-networking-dev
```

---

## Cleanup Checklist

Before running the cleanup script, verify:

- [ ] All foundation, data, and compute stacks are deployed and healthy
- [ ] You have archived recent build logs from `aura-infra-deploy-dev`
- [ ] You have tested manual triggers for modular CodeBuild projects
- [ ] You have a rollback plan if cleanup causes issues

**Cleanup Commands:**
```bash
# Step 1: Archive build logs (optional but recommended)
aws codebuild batch-get-builds \
  --ids $(aws codebuild list-builds-for-project --project-name aura-infra-deploy-dev --query 'ids[0]' --output text) \
  > archive/codebuild-logs/aura-infra-deploy-dev-final-build.json

# Step 2: Run cleanup script
bash /tmp/cleanup-old-codebuild.sh

# Step 3: Archive old buildspec
mkdir -p archive/legacy/buildspecs
git mv deploy/buildspec-modular.yml archive/legacy/buildspecs/
git commit -m "chore: archive old monolithic buildspec"
```

---

## Post-Migration Validation

After migration, verify:

1. **Old project is gone:**
```bash
aws codebuild list-projects --query 'projects' | grep "aura-infra-deploy-dev"
# Should return nothing
```

2. **Modular projects exist:**
```bash
aws codebuild list-projects --query 'projects' | grep "aura-.*-deploy-dev"
# Should show: foundation, data, compute, application, observability
```

3. **CloudFormation stacks are healthy:**
```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?starts_with(StackName, `aura-`)].{Name:StackName, Status:StackStatus}' \
  --output table
```

4. **Trigger a test build:**
```bash
aws codebuild start-build --project-name aura-foundation-deploy-dev
# Monitor logs to ensure it succeeds
```

---

## Troubleshooting

### "CodeBuild project not found" error after cleanup

**Cause:** Cleanup script deleted the project successfully

**Solution:** This is expected. Use modular projects instead.

### "No builds found for aura-foundation-deploy-dev"

**Cause:** Project has never been triggered

**Solution:**
```bash
# Manually trigger first build
aws codebuild start-build --project-name aura-foundation-deploy-dev
```

### "GitHub webhook not triggering builds"

**Cause:** Webhook not configured or GitHub token expired

**Solutions:**
1. Check webhook in GitHub repo settings
2. Verify CodeBuild has GitHub source credentials
3. Check filter groups in CodeBuild project configuration

---

## References

- **Modular Architecture Design:** `deploy/README.md`
- **Change Detection Script:** `deploy/scripts/detect_changes.py`
- **CodeBuild Templates:** `deploy/cloudformation/codebuild-*.yaml`
- **Buildspecs:** `deploy/buildspecs/buildspec-*.yml`
- **Deployment Scripts:** `deploy/scripts/deploy-*.sh`

---

## Next Steps

After completing this migration:

1. Set up GitHub webhooks for automatic deployments
2. Configure SNS notifications for build failures
3. Implement drift detection with scheduled builds
4. Document runbook for emergency manual deployments
5. Train team on new modular CI/CD workflow

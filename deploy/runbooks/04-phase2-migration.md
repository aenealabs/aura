# Runbook: Phase 2 Migration - Multi-Project Setup

**Purpose:** Migrate from single CodeBuild project to multiple team-owned projects

**Audience:** DevOps Engineers, Platform Team Lead, Engineering Managers

**Estimated Time:** 2-4 hours (planning + execution)

**Prerequisites:**
- Phase 1 operational for at least 2-4 weeks
- Team size 3+ people
- Clear ownership boundaries defined
- All stakeholders aligned

---

## Overview

Phase 2 splits the monolithic CodeBuild project into separate projects per infrastructure layer, enabling:
- **Team autonomy** - Each team deploys their layer independently
- **Parallel deployments** - Reduce total deployment time
- **Granular permissions** - IAM roles per team
- **Separate schedules** - Deploy on your team's timeline

## When to Migrate

✅ **Migrate when:**
- Team has grown to 3+ people
- Multiple teams own different infrastructure layers
- Need parallel deployments to speed up delivery
- Want layer-specific IAM permissions
- Teams need independent deployment schedules

❌ **Don't migrate if:**
- Team is still 1-2 people
- Single owner for all infrastructure
- Deployments are infrequent (< 1/week)
- Phase 1 working well and no pain points

---

## Pre-Migration Checklist

### 1. Define Ownership Model

Document which team owns which layer:

| Layer | Team | Primary Contact | Backup |
|-------|------|----------------|--------|
| Foundation | Platform Team | alice@example.com | bob@example.com |
| Data | Data Engineering | carol@example.com | dave@example.com |
| Compute | DevOps Team | eve@example.com | frank@example.com |
| Application | App Team | grace@example.com | heidi@example.com |
| Observability | SRE Team | ivan@example.com | judy@example.com |

### 2. Communication Plan

- [ ] Announce migration to all engineering teams
- [ ] Schedule migration during low-traffic period
- [ ] Notify stakeholders of potential brief disruption
- [ ] Prepare rollback plan
- [ ] Document new deployment procedures

### 3. Technical Prerequisites

- [ ] Phase 1 has been stable for 2+ weeks
- [ ] All builds passing consistently
- [ ] No pending infrastructure changes
- [ ] Backup of current configuration
- [ ] Test environments available for validation

### 4. Stakeholder Approval

- [ ] Engineering Manager approval
- [ ] DevOps Team approval
- [ ] Security Team review (IAM changes)
- [ ] Finance Team notified (potential cost changes)

---

## Migration Steps

## Step 1: Backup Current Configuration

### 1.1 Export Current CodeBuild Project

```bash
aws codebuild batch-get-projects \
  --names aura-infra-deploy-dev \
  --region us-east-1 > backup/codebuild-phase1-$(date +%Y%m%d).json
```

### 1.2 Backup CloudFormation Templates

```bash
# Create backup directory
mkdir -p backup/phase1-$(date +%Y%m%d)

# Copy all templates
cp -r deploy/cloudformation/ backup/phase1-$(date +%Y%m%d)/

# Create git tag
git tag -a phase1-final -m "Final Phase 1 configuration before Phase 2 migration"
git push origin phase1-final
```

### 1.3 Document Current State

```bash
# List all stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-')].{Name:StackName, Status:StackStatus}" \
  --output table > backup/stacks-pre-migration.txt
```

✅ **Checkpoint:** Backup completed and verified

---

## Step 2: Update CodeBuild CloudFormation Template

### 2.1 Uncomment Phase 2 Resources

Edit `deploy/cloudformation/codebuild.yaml`:

```bash
vim deploy/cloudformation/codebuild.yaml
```

Find lines 343-519 (Phase 2 resources) and uncomment them:

**Before:**
```yaml
  # # Foundation Layer CodeBuild Project (Platform Team)
  # FoundationCodeBuildProject:
  #   Type: AWS::CodeBuild::Project
```

**After:**
```yaml
  # Foundation Layer CodeBuild Project (Platform Team)
  FoundationCodeBuildProject:
    Type: AWS::CodeBuild::Project
```

**Repeat for all Phase 2 resources:**
- FoundationCodeBuildProject
- DataCodeBuildProject
- ComputeCodeBuildProject
- ObservabilityCodeBuildProject

### 2.2 Optional: Add Application Layer Project

If you have an application layer, add:

```yaml
  # Application Layer CodeBuild Project (App Team)
  ApplicationCodeBuildProject:
    Type: AWS::CodeBuild::Project
    Properties:
      Name: !Sub '${ProjectName}-application-deploy-${Environment}'
      Description: Deploy application layer (Bedrock infrastructure)
      ServiceRole: !GetAtt CodeBuildServiceRole.Arn
      Artifacts:
        Type: S3
        Location: !Ref BuildArtifactsBucket
        Name: application-artifacts
      Environment:
        Type: LINUX_CONTAINER
        ComputeType: BUILD_GENERAL1_SMALL
        Image: aws/codebuild/standard:7.0
        EnvironmentVariables:
          - Name: ENVIRONMENT
            Value: !Ref Environment
          - Name: PROJECT_NAME
            Value: !Ref ProjectName
          - Name: AWS_ACCOUNT_ID
            Value: !Ref AWS::AccountId
          - Name: AWS_DEFAULT_REGION
            Value: !Ref AWS::Region
      Source:
        Type: !If [HasGitHubRepo, GITHUB, NO_SOURCE]
        Location: !If [HasGitHubRepo, !Ref GitHubRepository, !Ref AWS::NoValue]
        BuildSpec: deploy/buildspecs/buildspec-application.yml
      Cache:
        Type: S3
        Location: !Sub '${BuildArtifactsBucket}/cache'
      LogsConfig:
        CloudWatchLogs:
          Status: ENABLED
          GroupName: !Sub '/aws/codebuild/${ProjectName}-application-${Environment}'
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment
        - Key: Layer
          Value: application
```

### 2.3 Add Outputs for New Projects

Add to Outputs section:

```yaml
Outputs:
  # Existing outputs...

  # Phase 2 Project Names
  FoundationProjectName:
    Description: Foundation layer CodeBuild project name
    Value: !Ref FoundationCodeBuildProject
    Export:
      Name: !Sub '${AWS::StackName}-FoundationProjectName'

  DataProjectName:
    Description: Data layer CodeBuild project name
    Value: !Ref DataCodeBuildProject
    Export:
      Name: !Sub '${AWS::StackName}-DataProjectName'

  ComputeProjectName:
    Description: Compute layer CodeBuild project name
    Value: !Ref ComputeCodeBuildProject
    Export:
      Name: !Sub '${AWS::StackName}-ComputeProjectName'

  ObservabilityProjectName:
    Description: Observability layer CodeBuild project name
    Value: !Ref ObservabilityCodeBuildProject
    Export:
      Name: !Sub '${AWS::StackName}-ObservabilityProjectName'
```

### 2.4 Validate Template

```bash
cfn-lint deploy/cloudformation/codebuild.yaml

aws cloudformation validate-template \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --region us-east-1
```

✅ **Checkpoint:** Template validation passes

---

## Step 3: Update CodeBuild Stack

### 3.1 Create Change Set

```bash
aws cloudformation create-change-set \
  --stack-name aura-codebuild-dev \
  --change-set-name phase2-migration \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=AlertEmail,ParameterValue=team@example.com \
    ParameterKey=GitHubRepository,ParameterValue=https://github.com/org/repo \
    ParameterKey=GitHubBranch,ParameterValue=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### 3.2 Review Change Set

```bash
aws cloudformation describe-change-set \
  --stack-name aura-codebuild-dev \
  --change-set-name phase2-migration \
  --query 'Changes[*].{Action:ResourceChange.Action,Resource:ResourceChange.LogicalResourceId,Type:ResourceChange.ResourceType}' \
  --output table \
  --region us-east-1
```

**Expected Changes:**
- Add: FoundationCodeBuildProject
- Add: DataCodeBuildProject
- Add: ComputeCodeBuildProject
- Add: ObservabilityCodeBuildProject
- No changes to existing project (aura-infra-deploy-dev)

✅ **Checkpoint:** Change set looks correct (4 new projects, no deletions)

### 3.3 Execute Change Set

```bash
aws cloudformation execute-change-set \
  --stack-name aura-codebuild-dev \
  --change-set-name phase2-migration \
  --region us-east-1

# Monitor progress
aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-dev \
  --region us-east-1

echo "Stack update completed!"
```

⏱️ **Expected Duration:** 5-10 minutes

### 3.4 Verify New Projects Created

```bash
# List all CodeBuild projects
aws codebuild list-projects \
  --query 'projects[?starts_with(@, `aura-`)]' \
  --output table \
  --region us-east-1
```

**Expected Output:**
```
-------------------------------------
|           ListProjects            |
+-----------------------------------+
|  aura-infra-deploy-dev           | ← Phase 1 (keep for now)
|  aura-foundation-deploy-dev      | ← NEW
|  aura-data-deploy-dev            | ← NEW
|  aura-compute-deploy-dev         | ← NEW
|  aura-observability-deploy-dev   | ← NEW
+-----------------------------------+
```

✅ **Checkpoint:** All 5 projects exist

---

## Step 4: Test Each Layer Project

### 4.1 Test Foundation Layer

```bash
# Trigger build
aws codebuild start-build \
  --project-name aura-foundation-deploy-dev \
  --region us-east-1

# Monitor logs
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow
```

**Expected Result:** Foundation layer deploys successfully

### 4.2 Test Data Layer

```bash
aws codebuild start-build \
  --project-name aura-data-deploy-dev \
  --region us-east-1

# Wait for completion
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-data-deploy-dev \
  --query 'ids[0]' \
  --output text)

aws codebuild wait build-complete --id $BUILD_ID
```

### 4.3 Test Compute Layer

```bash
aws codebuild start-build \
  --project-name aura-compute-deploy-dev
```

### 4.4 Test Observability Layer

```bash
aws codebuild start-build \
  --project-name aura-observability-deploy-dev
```

✅ **Checkpoint:** All layer projects build successfully

---

## Step 5: Configure GitHub Triggers (Optional)

### Path-Based Triggers

Each project can be triggered by changes to specific files.

#### 5.1 Create GitHub Actions Workflow

Create `.github/workflows/infra-deploy-phase2.yml`:

```yaml
name: Infrastructure Deployment (Phase 2)

on:
  push:
    branches: [main]

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      foundation: ${{ steps.filter.outputs.foundation }}
      data: ${{ steps.filter.outputs.data }}
      compute: ${{ steps.filter.outputs.compute }}
      observability: ${{ steps.filter.outputs.observability }}
    steps:
      - uses: actions/checkout@v3
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            foundation:
              - 'deploy/cloudformation/networking.yaml'
              - 'deploy/cloudformation/security.yaml'
              - 'deploy/cloudformation/iam.yaml'
            data:
              - 'deploy/cloudformation/neptune.yaml'
              - 'deploy/cloudformation/opensearch.yaml'
              - 'deploy/cloudformation/dynamodb.yaml'
              - 'deploy/cloudformation/s3.yaml'
            compute:
              - 'deploy/cloudformation/eks.yaml'
            observability:
              - 'deploy/cloudformation/secrets.yaml'
              - 'deploy/cloudformation/monitoring.yaml'
              - 'deploy/cloudformation/aura-cost-alerts.yaml'

  deploy-foundation:
    needs: detect-changes
    if: needs.detect-changes.outputs.foundation == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Trigger Foundation Build
        run: aws codebuild start-build --project-name aura-foundation-deploy-dev

  deploy-data:
    needs: [detect-changes, deploy-foundation]
    if: needs.detect-changes.outputs.data == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Trigger Data Build
        run: aws codebuild start-build --project-name aura-data-deploy-dev

  deploy-compute:
    needs: [detect-changes, deploy-foundation]
    if: needs.detect-changes.outputs.compute == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Trigger Compute Build
        run: aws codebuild start-build --project-name aura-compute-deploy-dev

  deploy-observability:
    needs: [detect-changes, deploy-foundation, deploy-data]
    if: needs.detect-changes.outputs.observability == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Trigger Observability Build
        run: aws codebuild start-build --project-name aura-observability-deploy-dev
```

#### 5.2 Add AWS Credentials to GitHub Secrets

1. Go to GitHub repo → Settings → Secrets and variables → Actions
2. Add secrets:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

**Security Note:** Use IAM user with minimal permissions or OIDC provider.

---

## Step 6: Update Team Documentation

### 6.1 Update Deployment Instructions

Create team-specific guides:

**For Platform Team:**
```markdown
# Platform Team: Foundation Layer Deployment

Your team owns: Networking, Security, IAM

## Manual Deployment
aws codebuild start-build --project-name aura-foundation-deploy-dev

## Automatic
Push changes to:
- deploy/cloudformation/networking.yaml
- deploy/cloudformation/security.yaml
- deploy/cloudformation/iam.yaml
```

**For Data Team:**
```markdown
# Data Team: Data Layer Deployment

Your team owns: Neptune, OpenSearch, DynamoDB, S3

## Manual Deployment
aws codebuild start-build --project-name aura-data-deploy-dev

## Automatic
Push changes to:
- deploy/cloudformation/neptune.yaml
- deploy/cloudformation/opensearch.yaml
- deploy/cloudformation/dynamodb.yaml
- deploy/cloudformation/s3.yaml
```

### 6.2 Update README

```bash
vim deploy/README.md
```

Add Phase 2 section:

```markdown
## Phase 2: Team-Based Deployment (ACTIVE)

We've migrated to separate CodeBuild projects per layer:

| Layer | Project | Team |
|-------|---------|------|
| Foundation | aura-foundation-deploy-dev | Platform Team |
| Data | aura-data-deploy-dev | Data Team |
| Compute | aura-compute-deploy-dev | DevOps Team |
| Observability | aura-observability-deploy-dev | SRE Team |

See [04-phase2-migration.md](./runbooks/04-phase2-migration.md) for details.
```

---

## Step 7: (Optional) Create Team-Specific IAM Roles

For enhanced security, create separate IAM roles per team.

### 7.1 Create Foundation Team Role

```yaml
# In codebuild.yaml, add:
FoundationTeamRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: !Sub '${ProjectName}-foundation-team-role-${Environment}'
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: codebuild.amazonaws.com
          Action: sts:AssumeRole
    Policies:
      - PolicyName: FoundationTeamPolicy
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            # CloudFormation
            - Effect: Allow
              Action: cloudformation:*
              Resource:
                - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-networking-*'
                - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-security-*'
                - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-iam-*'
            # VPC/EC2
            - Effect: Allow
              Action:
                - ec2:*
              Resource: '*'
            # IAM (limited)
            - Effect: Allow
              Action:
                - iam:CreateRole
                - iam:DeleteRole
                - iam:GetRole
                - iam:PassRole
                - iam:AttachRolePolicy
                - iam:DetachRolePolicy
              Resource: !Sub 'arn:aws:iam::${AWS::AccountId}:role/${ProjectName}-*'
```

### 7.2 Update Foundation Project to Use New Role

```yaml
FoundationCodeBuildProject:
  Properties:
    ServiceRole: !GetAtt FoundationTeamRole.Arn  # Change from CodeBuildServiceRole
```

Repeat for other teams with appropriate permissions.

---

## Step 8: Decommission Phase 1 Project (Optional)

After Phase 2 is stable for 2-4 weeks:

### 8.1 Verify Phase 2 Stability

```bash
# Check build success rate
aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-dev \
  --max-items 20 | \
  jq '.ids[]' | \
  xargs -I {} aws codebuild batch-get-builds --ids {} | \
  jq '.builds[] | {status: .buildStatus}' | \
  grep -c SUCCEEDED
```

✅ **Checkpoint:** 90%+ success rate over 2 weeks

### 8.2 Delete Phase 1 Project

**CAUTION:** This is irreversible!

```bash
# Backup one last time
aws codebuild batch-get-projects \
  --names aura-infra-deploy-dev \
  --region us-east-1 > backup/phase1-final.json

# Delete project (removes from template)
# Comment out original project in codebuild.yaml
vim deploy/cloudformation/codebuild.yaml

# Update stack
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## Rollback Procedure

If Phase 2 causes issues:

### Option 1: Keep Both (Recommended)

Keep Phase 1 project as backup:
```bash
# Just continue using Phase 1
aws codebuild start-build --project-name aura-infra-deploy-dev
```

### Option 2: Delete Phase 2 Projects

```bash
# Re-comment Phase 2 resources in codebuild.yaml
vim deploy/cloudformation/codebuild.yaml

# Update stack (deletes Phase 2 projects)
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

### Option 3: Full Rollback

```bash
# Restore from backup
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://backup/phase1-$(date +%Y%m%d)/codebuild.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# Restore git tag
git checkout phase1-final
git push origin main --force
```

---

## Post-Migration Checklist

- [ ] All 4-5 new CodeBuild projects created
- [ ] Each project tested successfully
- [ ] GitHub triggers configured (if using)
- [ ] Team documentation updated
- [ ] Team members trained
- [ ] IAM roles configured (if using team-specific roles)
- [ ] Monitoring and alerts verified
- [ ] Phase 1 project retained as backup
- [ ] Migration announced to all teams

---

## Success Metrics

Track these metrics post-migration:

### Deployment Speed
```bash
# Average build duration per layer (should be faster)
aws codebuild list-builds-for-project \
  --project-name aura-data-deploy-dev \
  --max-items 20 | \
  jq '.ids[]' | \
  xargs -I {} aws codebuild batch-get-builds --ids {} | \
  jq '.builds[].phases[] | select(.phaseType=="BUILD") | .durationInSeconds' | \
  awk '{sum+=$1; count++} END {print sum/count}'
```

### Deployment Frequency
- Track builds per week per team
- Target: Increase in deployment frequency

### Team Satisfaction
- Survey teams on deployment experience
- Collect feedback on autonomy and speed

---

## Troubleshooting

### Issue: New Projects Not Triggering

**Solution:** Verify GitHub webhook or GitHub Actions configuration

### Issue: Permission Errors in Team-Specific Roles

**Solution:** Add missing permissions to team role

### Issue: Parallel Deployments Conflict

**Solution:** Ensure proper dependency ordering (Foundation before Data/Compute)

---

## Related Documentation

- [MODULAR_DEPLOYMENT.md](../MODULAR_DEPLOYMENT.md) - Architecture overview
- [02-routine-deployments.md](./02-routine-deployments.md) - Day-to-day operations
- [03-troubleshooting.md](./03-troubleshooting.md) - Problem resolution

---

**Document Version:** 1.0
**Last Updated:** 2025-11-11
**Maintained By:** Platform Engineering Team

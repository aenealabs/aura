# Runbook: CodeConnections GitHub Access Errors (OAuthProviderException)

**Purpose:** Resolve CodeBuild project creation and execution failures caused by CodeConnections/codestar-connections IAM permission issues

**Audience:** DevOps Engineers, Platform Team

**Estimated Time:** 20-45 minutes

**Last Updated:** Dec 11, 2025

---

## Problem Description

CloudFormation stack operations or CodeBuild executions fail with `OAuthProviderException` when:
- Creating new CodeBuild projects that reference GitHub via CodeConnections
- Running CodeBuild projects that need to clone repositories from GitHub
- IAM roles are missing the dual-namespace CodeConnections permissions

### Symptoms

**CloudFormation Stack Creation Failure:**
```
OAuthProviderException: User is not authorized to access connection
arn:aws:codeconnections:us-east-1:123456789012:connection/87747688-215a-44f9-b350-e26c52282c6e
```

**CloudFormation Stack Status:**
```
ROLLBACK_COMPLETE
```

**CodeBuild DOWNLOAD_SOURCE Phase Failure:**
```
Phase is DOWNLOAD_SOURCE
OAuthProviderException: User is not authorized to access connection...
```

### Root Cause

AWS uses **two IAM permission namespaces** for CodeConnections:
1. **`codeconnections:`** - The current namespace
2. **`codestar-connections:`** - The legacy namespace (still used by some AWS APIs)

Both namespaces are required because:
- CloudFormation CREATE operations may use one namespace
- CodeBuild runtime DOWNLOAD_SOURCE may use the other
- AWS SDK versions and API endpoints vary in which namespace they check

**Key Permission: `PassConnection`**
- Required to CREATE CodeBuild projects that reference a CodeConnection
- Without it, CloudFormation cannot pass the connection to the new CodeBuild project

---

## Quick Resolution

### Step 1: Identify the Affected Stack and Role

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-runbook-agent-dev \
  --query 'Stacks[0].StackStatus' \
  --output text

# Check stack events for error details
aws cloudformation describe-stack-events \
  --stack-name aura-codebuild-runbook-agent-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

### Step 2: Add Dual-Namespace CodeConnections Permissions

Edit the relevant IAM role in the CloudFormation template. Add **both** namespaces:

```yaml
# CodeConnections - GitHub access
# Note: Both 'codeconnections' and legacy 'codestar-connections' namespaces needed
# because AWS APIs may use either depending on the operation and SDK version
- Effect: Allow
  Action:
    - codeconnections:UseConnection
    - codeconnections:GetConnectionToken
    - codeconnections:GetConnection
    - codeconnections:PassConnection      # Required for CloudFormation to create CodeBuild projects
    - codestar-connections:UseConnection
    - codestar-connections:GetConnectionToken
    - codestar-connections:GetConnection
    - codestar-connections:PassConnection # Required for CloudFormation to create CodeBuild projects
  Resource:
    - '{{resolve:ssm:/aura/global/codeconnections-arn}}'
```

### Step 3: Deploy the Fix

**If stack is ROLLBACK_COMPLETE (must delete first):**
```bash
# Delete the failed stack
aws cloudformation delete-stack \
  --stack-name aura-codebuild-runbook-agent-dev

aws cloudformation wait stack-delete-complete \
  --stack-name aura-codebuild-runbook-agent-dev

# Create fresh stack with fixed template
aws cloudformation create-stack \
  --stack-name aura-codebuild-runbook-agent-dev \
  --template-body file://deploy/cloudformation/codebuild-runbook-agent.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=GitHubRepository,ParameterValue=https://github.com/aenealabs/aura \
    ParameterKey=GitHubBranch,ParameterValue=main \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation wait stack-create-complete \
  --stack-name aura-codebuild-runbook-agent-dev
```

**If stack exists and can be updated:**
```bash
aws cloudformation update-stack \
  --stack-name aura-codebuild-runbook-agent-dev \
  --template-body file://deploy/cloudformation/codebuild-runbook-agent.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=GitHubRepository,ParameterValue=https://github.com/aenealabs/aura \
    ParameterKey=GitHubBranch,ParameterValue=main \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-runbook-agent-dev
```

### Step 4: Verify CodeBuild Execution

```bash
# Trigger a build
BUILD_ID=$(aws codebuild start-build \
  --project-name aura-runbook-agent-dev \
  --query 'build.id' \
  --output text)

echo "Build started: $BUILD_ID"

# Wait and check status
sleep 45
aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --query 'builds[0].{status:buildStatus,currentPhase:currentPhase}' \
  --output json
```

---

## Permission Reference

### Roles That Require CodeConnections Permissions

| Role | Template | Needs PassConnection? |
|------|----------|----------------------|
| `aura-foundation-codebuild-role-dev` | `codebuild-foundation.yaml` | Yes (creates other CodeBuild projects) |
| `aura-cloudformation-role-dev` | `iam.yaml` | Yes (creates CodeBuild projects via CloudFormation) |
| `aura-runbook-agent-codebuild-role-dev` | `codebuild-runbook-agent.yaml` | No (only needs UseConnection for cloning) |
| `aura-application-codebuild-role-dev` | `codebuild-application.yaml` | No (only needs UseConnection for cloning) |

### Permission Breakdown

| Permission | Purpose |
|------------|---------|
| `UseConnection` | Clone repository during CodeBuild execution |
| `GetConnectionToken` | Authenticate with GitHub during clone |
| `GetConnection` | Retrieve connection metadata |
| `PassConnection` | Allow CloudFormation to assign connection to new CodeBuild projects |

---

## Related Issues

### CodeBuild Buildspec YAML Parsing Errors

If the CodeBuild project is created successfully but builds fail at DOWNLOAD_SOURCE with YAML errors:

**Symptom:**
```
YAML_FILE_ERROR: Expected Commands[3] to be of string type: found subkeys instead
at line 31, value of the key tag on line 30 might be empty
```

**Root Cause:** CodeBuild's YAML parser interprets `=` at the start of echo command values as YAML tags.

**Fix:** Avoid decorative echo commands with `=` characters:
```yaml
# BAD - causes YAML parsing error
- 'echo "=========================================="'
- 'echo "Title"'
- 'echo "=========================================="'

# GOOD - simple echo statements
- echo "Starting pre_build phase..."
- echo "Environment is $ENVIRONMENT"
```

### CodeBuild Report Group Permissions

If builds fail at UPLOAD_ARTIFACTS phase with report group errors:

**Symptom:**
```
AccessDeniedException: User is not authorized to perform: codebuild:CreateReportGroup
```

**Fix:** Add CodeBuild report permissions to the IAM role:
```yaml
- Effect: Allow
  Action:
    - codebuild:CreateReportGroup
    - codebuild:CreateReport
    - codebuild:UpdateReport
    - codebuild:BatchPutTestCases
    - codebuild:BatchPutCodeCoverages
  Resource:
    - !Sub 'arn:${AWS::Partition}:codebuild:${AWS::Region}:${AWS::AccountId}:report-group/${ProjectName}-*'
```

---

## Prevention

1. **Always use dual-namespace permissions** for any IAM role that interacts with CodeConnections
2. **Test buildspec YAML locally** with a YAML validator before pushing
3. **Include report group permissions** when defining CodeBuild reports in buildspec
4. **Use SSM Parameter Store** for CodeConnections ARN to avoid hardcoding

---

## References

- **AWS Documentation:** [Working with connections in CodeConnections](https://docs.aws.amazon.com/codepipeline/latest/userguide/connections.html)
- **SSM Parameter:** `/aura/global/codeconnections-arn`
- **Related ADR:** ADR-030 (CI/CD Architecture)

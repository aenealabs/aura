# Runbook: ECR Repository Conflicts (AlreadyExists Error)

**Purpose:** Resolve CloudFormation deployment failures when ECR repositories already exist outside of CloudFormation management

**Audience:** DevOps Engineers, Platform Team, On-call Engineers

**Estimated Time:** 10-20 minutes

**Last Updated:** Dec 11, 2025

---

## Problem Description

CloudFormation stack creation fails with `AlreadyExists` error when:
- An ECR repository was manually created via AWS Console or CLI
- A previous CloudFormation stack was deleted but the repository was retained
- Another CloudFormation stack manages the same repository name

### Symptoms

```
Resource handler returned message: "Resource of type 'AWS::ECR::Repository'
with identifier 'aura-api-dev' already exists."
(RequestToken: xxx, HandlerErrorCode: AlreadyExists)

Stack Status: ROLLBACK_COMPLETE
```

### Root Cause

CloudFormation cannot create a resource that already exists in AWS. Unlike some resources that support "import", ECR repositories created outside CloudFormation require special handling.

---

## Quick Resolution

### Option A: Use Existing Repository (Recommended)

The buildspec automatically detects existing repositories and skips CloudFormation creation:

```bash
# Verify the repository exists
aws ecr describe-repositories \
  --repository-names aura-api-dev \
  --query 'repositories[0].repositoryUri'

# Re-run CodeBuild - it will detect and use existing repo
aws codebuild start-build --project-name aura-application-deploy-dev
```

### Option B: Import into CloudFormation

Import the existing resource into a new CloudFormation stack:

```bash
# See Procedure 2 below for detailed steps
```

### Option C: Delete and Recreate (Data Loss Warning)

Only use if the repository is empty or images can be recreated:

```bash
# WARNING: This deletes all images in the repository!
aws ecr delete-repository \
  --repository-name aura-api-dev \
  --force

# Re-run CodeBuild
aws codebuild start-build --project-name aura-application-deploy-dev
```

---

## Detailed Diagnostic Steps

### Step 1: Identify the Conflicting Resource

```bash
# Check for failed CloudFormation stacks
aws cloudformation list-stacks \
  --stack-status-filter ROLLBACK_COMPLETE CREATE_FAILED \
  --query "StackSummaries[?contains(StackName, 'ecr')].{Name:StackName,Status:StackStatus}"

# Get the failure reason
STACK_NAME="aura-ecr-api-dev"
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" \
  --output table
```

### Step 2: Check if Repository Exists

```bash
# List all aura ECR repositories
aws ecr describe-repositories \
  --query "repositories[?contains(repositoryName, 'aura')].{Name:repositoryName,Uri:repositoryUri,Created:createdAt}" \
  --output table

# Check specific repository
aws ecr describe-repositories \
  --repository-names aura-api-dev \
  --query 'repositories[0]'
```

### Step 3: Check Repository Contents

```bash
# List images in the repository (check if it's safe to delete)
aws ecr list-images \
  --repository-name aura-api-dev \
  --query 'imageIds[*].imageTag'

# Get image count
aws ecr describe-images \
  --repository-name aura-api-dev \
  --query 'length(imageDetails)'
```

---

## Resolution Procedures

### Procedure 1: Clean Up Failed Stack and Use Existing Repo

This is the recommended approach when the repository should continue to exist:

```bash
# Step 1: Delete the failed CloudFormation stack
aws cloudformation delete-stack --stack-name aura-ecr-api-dev

# Step 2: Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name aura-ecr-api-dev

# Step 3: Verify repository still exists
aws ecr describe-repositories --repository-names aura-api-dev

# Step 4: Re-run CodeBuild (buildspec will detect existing repo)
aws codebuild start-build --project-name aura-application-deploy-dev
```

The buildspec includes logic to skip CloudFormation creation and auto-cleanup failed stacks:

```yaml
# From buildspec-application.yml
API_ECR_REPO_URI=$(aws ecr describe-repositories --repository-names $API_REPO_NAME \
  --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "")

if [[ -n "$API_ECR_REPO_URI" && "$API_ECR_REPO_URI" != "None" ]]; then
  echo "ECR repository already exists: $API_ECR_REPO_URI"
  echo "Skipping CloudFormation stack creation to avoid AlreadyExists error"

  # Auto-cleanup any failed CloudFormation stack for this repository
  STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $API_ECR_STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")
  if [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "CREATE_FAILED" ]]; then
    echo "Cleaning up failed CloudFormation stack ($STACK_STATUS)..."
    aws cloudformation delete-stack --stack-name $API_ECR_STACK
    aws cloudformation wait stack-delete-complete --stack-name $API_ECR_STACK
    echo "Failed stack cleaned up"
  fi
fi
```

**Note:** As of Dec 11, 2025, the buildspec automatically cleans up orphaned failed stacks. Manual cleanup is only needed if auto-cleanup fails.

### Procedure 2: Import Existing Repository into CloudFormation

Use CloudFormation resource import to bring the existing repository under stack management:

```bash
# Step 1: Delete the failed stack first
aws cloudformation delete-stack --stack-name aura-ecr-api-dev
aws cloudformation wait stack-delete-complete --stack-name aura-ecr-api-dev

# Step 2: Create an import template (resources-to-import.json)
cat > /tmp/resources-to-import.json << 'EOF'
[
  {
    "ResourceType": "AWS::ECR::Repository",
    "LogicalResourceId": "ApiRepository",
    "ResourceIdentifier": {
      "RepositoryName": "aura-api-dev"
    }
  }
]
EOF

# Step 3: Create change set for import
aws cloudformation create-change-set \
  --stack-name aura-ecr-api-dev \
  --change-set-name import-existing-repo \
  --change-set-type IMPORT \
  --resources-to-import file:///tmp/resources-to-import.json \
  --template-body file://deploy/cloudformation/ecr-api.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev \
               ParameterKey=ProjectName,ParameterValue=aura

# Step 4: Review the change set
aws cloudformation describe-change-set \
  --stack-name aura-ecr-api-dev \
  --change-set-name import-existing-repo

# Step 5: Execute the import
aws cloudformation execute-change-set \
  --stack-name aura-ecr-api-dev \
  --change-set-name import-existing-repo

# Step 6: Wait for completion
aws cloudformation wait stack-import-complete --stack-name aura-ecr-api-dev
```

### Procedure 3: Delete Repository and Recreate (Data Loss)

**WARNING:** Only use this if the repository is empty or all images can be rebuilt.

```bash
# Step 1: Verify repository contents
aws ecr list-images --repository-name aura-api-dev

# Step 2: Delete all images first (required before repo deletion)
aws ecr batch-delete-image \
  --repository-name aura-api-dev \
  --image-ids "$(aws ecr list-images --repository-name aura-api-dev --query 'imageIds' --output json)"

# Step 3: Delete the repository
aws ecr delete-repository --repository-name aura-api-dev

# Step 4: Delete the failed CloudFormation stack
aws cloudformation delete-stack --stack-name aura-ecr-api-dev
aws cloudformation wait stack-delete-complete --stack-name aura-ecr-api-dev

# Step 5: Re-run CodeBuild to recreate everything
aws codebuild start-build --project-name aura-application-deploy-dev
```

---

## Prevention

### 1. Buildspec Pre-check (Already Implemented)

The buildspec checks for existing repositories before attempting CloudFormation:

```yaml
# Check if repository already exists
API_ECR_REPO_URI=$(aws ecr describe-repositories --repository-names $API_REPO_NAME \
  --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "")

if [[ -n "$API_ECR_REPO_URI" && "$API_ECR_REPO_URI" != "None" ]]; then
  echo "ECR repository already exists, skipping CloudFormation"
else
  # Create via CloudFormation
fi
```

### 2. Use DeletionPolicy: Retain

Add `DeletionPolicy: Retain` to ECR repositories to prevent accidental deletion:

```yaml
ApiRepository:
  Type: AWS::ECR::Repository
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    RepositoryName: !Sub '${ProjectName}-api-${Environment}'
```

### 3. Naming Convention Enforcement

Use consistent naming to avoid conflicts:
- Format: `${ProjectName}-${Purpose}-${Environment}`
- Example: `aura-api-dev`, `aura-dnsmasq-dev`

### 4. Pre-deployment Validation Script

```bash
#!/bin/bash
# validate-ecr-resources.sh

REPOS=("aura-api-dev" "aura-dnsmasq-dev" "aura-frontend-dev")

for repo in "${REPOS[@]}"; do
  if aws ecr describe-repositories --repository-names $repo 2>/dev/null; then
    echo "WARNING: Repository $repo already exists outside CloudFormation"
    echo "  - Buildspec will use existing repository"
    echo "  - To import into CloudFormation, see ECR_REPOSITORY_CONFLICTS.md"
  fi
done
```

---

## Related Documentation

- [Application Buildspec](../../deploy/buildspecs/buildspec-application.yml)
- [ECR API CloudFormation Template](../../deploy/cloudformation/ecr-api.yaml)
- [ECR dnsmasq CloudFormation Template](../../deploy/cloudformation/ecr-dnsmasq.yaml)
- [AWS CloudFormation Resource Import](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resource-import.html)

---

## Appendix: Common ECR Repositories

| Repository Name | Purpose | CloudFormation Stack |
|-----------------|---------|---------------------|
| `aura-api-dev` | API service images | `aura-ecr-api-dev` |
| `aura-dnsmasq-dev` | DNS service images | `aura-ecr-dnsmasq-dev` |
| `aura-frontend-dev` | Frontend images | `aura-ecr-frontend-dev` |
| `aura-base-images/alpine` | Base Alpine image | `aura-ecr-base-images-dev` |
| `aura-base-images/node` | Base Node.js image | `aura-ecr-base-images-dev` |
| `aura-base-images/nginx` | Base Nginx image | `aura-ecr-base-images-dev` |

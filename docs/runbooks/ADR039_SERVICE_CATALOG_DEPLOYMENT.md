# ADR-039 Service Catalog Deployment Runbook

**Date Created:** 2025-12-15
**Last Updated:** 2025-12-15
**Author:** Platform Team
**Status:** Production

## Overview

This runbook documents the deployment issues encountered during ADR-039 Phase 2 (Service Catalog integration for self-service test environments) and their solutions. These issues primarily involve IAM permission gaps that were discovered iteratively during CloudFormation deployments.

## Architecture Summary

ADR-039 Phase 2 deploys the following components:

| Stack Name | Purpose | Key Resources |
|------------|---------|---------------|
| `aura-test-env-state-dev` | State management | DynamoDB table for environment state |
| `aura-test-env-iam-dev` | IAM roles | Permission boundary, Lambda roles, Step Functions role, Service Catalog launch role |
| `aura-test-env-catalog-dev` | Service Catalog | Portfolio, 5 product templates, principal associations, launch constraints |
| `aura-test-env-approval-dev` | HITL approval workflow | 4 Lambda functions, Step Functions state machine, API Gateway |

## Issues and Resolutions

### Issue 1: Service Catalog Constraint ARN Namespace

**Error Message:**
```
User: arn:aws:sts::ACCOUNT_ID:assumed-role/aura-sandbox-codebuild-role-dev/AWSCodeBuild-xxx
is not authorized to perform: servicecatalog:DeleteConstraint on resource:
arn:aws:servicecatalog:us-east-1:ACCOUNT_ID:...
```

**Root Cause:**
Service Catalog portfolios and products use `arn:aws:catalog:...` namespace, but **constraints** use `arn:aws:servicecatalog:...` namespace in IAM policies.

**Solution:**
Add both ARN namespaces to the IAM policy:

```yaml
# In deploy/cloudformation/codebuild-sandbox.yaml (TestEnvManagedPolicy)
Resource:
  - !Sub 'arn:${AWS::Partition}:catalog:${AWS::Region}:${AWS::AccountId}:portfolio/*'
  - !Sub 'arn:${AWS::Partition}:catalog:${AWS::Region}:${AWS::AccountId}:product/*'
  # Constraints use servicecatalog namespace (different from catalog for portfolios/products)
  - !Sub 'arn:${AWS::Partition}:servicecatalog:${AWS::Region}:${AWS::AccountId}:*'
```

**Reference:** Lines 87-91 in `deploy/cloudformation/codebuild-sandbox.yaml`

---

### Issue 2: CloudWatch Logs Pattern Mismatch

**Error Message:**
```
User: arn:aws:sts::ACCOUNT_ID:assumed-role/aura-sandbox-codebuild-role-dev/AWSCodeBuild-xxx
is not authorized to perform: logs:CreateLogGroup on resource:
arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/aws/aura/dev/test-env-approval:log-stream:
```

**Root Cause:**
The `test-env-approval.yaml` template creates a log group with pattern `/aws/${ProjectName}/${Environment}/test-env-approval`, but the CodeBuild IAM policy only allowed patterns like `/aws/lambda/${ProjectName}-test-env-*`.

**Solution:**
Add the custom log group pattern to the CloudWatch Logs permission:

```yaml
# In deploy/cloudformation/codebuild-sandbox.yaml (SandboxCodeBuildRole)
Resource:
  # ... existing patterns ...
  # Custom log groups for test environment approval workflow
  - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/${ProjectName}/${Environment}/*'
  # ... log stream patterns ...
  - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/${ProjectName}/${Environment}/*:*'
```

**Reference:** Lines 189-190 and 198 in `deploy/cloudformation/codebuild-sandbox.yaml`

---

### Issue 3: Lambda Cannot Assume Step Functions Role

**Error Message:**
```
Resource handler returned message: "The role defined for the function cannot be assumed by Lambda.
(Service: Lambda, Status Code: 400, Request ID: xxx)"
```

**Root Cause:**
The `test-env-approval.yaml` template uses `StepFunctionsRoleArn` as the execution role for Lambda functions. However, the `TestEnvStepFunctionsRole` in `test-env-iam.yaml` only allowed `states.amazonaws.com` in its trust policy, not `lambda.amazonaws.com`.

**Solution:**
Update the trust policy to allow both services:

```yaml
# In deploy/cloudformation/test-env-iam.yaml (TestEnvStepFunctionsRole)
AssumeRolePolicyDocument:
  Version: '2012-10-17'
  Statement:
    - Effect: Allow
      Principal:
        Service:
          - states.amazonaws.com
          - lambda.amazonaws.com  # Added for approval workflow Lambda functions
      Action: sts:AssumeRole
ManagedPolicyArns:
  # Lambda basic execution for CloudWatch Logs
  - !Sub 'arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
```

**Reference:** Lines 670-681 in `deploy/cloudformation/test-env-iam.yaml`

---

### Issue 4: Missing IAM UpdateRole Permissions

**Error Message:**
```
User: arn:aws:sts::ACCOUNT_ID:assumed-role/aura-sandbox-codebuild-role-dev/AWSCodeBuild-xxx
is not authorized to perform: iam:UpdateRoleDescription on resource:
role aura-test-env-stepfunctions-role-dev
```

**Root Cause:**
When modifying an IAM role's description or trust policy via CloudFormation, the following actions are required:
- `iam:UpdateRole`
- `iam:UpdateRoleDescription`
- `iam:UpdateAssumeRolePolicy`

The CodeBuild role only had create/delete/get permissions.

**Solution:**
Add update permissions to the IAM policy:

```yaml
# In deploy/cloudformation/codebuild-sandbox.yaml (TestEnvManagedPolicy)
Action:
  - iam:CreateRole
  - iam:DeleteRole
  - iam:GetRole
  - iam:UpdateRole              # Added
  - iam:UpdateRoleDescription   # Added
  - iam:UpdateAssumeRolePolicy  # Added
  - iam:PutRolePolicy
  # ... rest of actions ...
```

**Reference:** Lines 104-118 in `deploy/cloudformation/codebuild-sandbox.yaml`

---

## Handling Stack Failures

### ROLLBACK_COMPLETE State

When a stack is in `ROLLBACK_COMPLETE` state, you must delete it before redeploying:

```bash
# The buildspec handles this automatically, but for manual intervention:
aws cloudformation delete-stack --stack-name aura-test-env-approval-dev --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name aura-test-env-approval-dev --region us-east-1
```

### ROLLBACK_FAILED State

When a stack is in `ROLLBACK_FAILED` state (e.g., due to a resource that couldn't be deleted):

```bash
# Option 1: Delete the problematic resource manually, then continue rollback
aws logs delete-log-group --log-group-name "/aws/aura/dev/test-env-approval" --region us-east-1

# Option 2: Skip the resource and continue rollback
aws cloudformation continue-update-rollback \
  --stack-name aura-test-env-iam-dev \
  --resources-to-skip TestEnvStepFunctionsRole \
  --region us-east-1
```

### UPDATE_ROLLBACK_FAILED State

When a stack update fails and rollback also fails:

```bash
# Continue the rollback (may need to fix IAM permissions first)
aws cloudformation continue-update-rollback \
  --stack-name aura-test-env-iam-dev \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-update-rollback-complete \
  --stack-name aura-test-env-iam-dev \
  --region us-east-1
```

---

## Manual IAM Stack Updates

The sandbox buildspec (`buildspec-sandbox.yml`) does NOT update the `aura-codebuild-sandbox-dev` stack because modifying the CodeBuild role during the build that uses it can cause issues. When IAM permission changes are needed:

```bash
# Update the CodeBuild IAM stack manually
AWS_PROFILE=aura-admin aws cloudformation update-stack \
  --stack-name aura-codebuild-sandbox-dev \
  --template-body file://deploy/cloudformation/codebuild-sandbox.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters ParameterKey=Environment,ParameterValue=dev ParameterKey=ProjectName,ParameterValue=aura \
  --region us-east-1

# Wait for completion
AWS_PROFILE=aura-admin aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-sandbox-dev \
  --region us-east-1
```

---

## Verification Commands

After successful deployment, verify all components:

```bash
# 1. Check Service Catalog Portfolio
aws servicecatalog list-portfolios \
  --query "PortfolioDetails[?contains(DisplayName, 'aura')]" \
  --output table --region us-east-1

# 2. Check Service Catalog Products
PORTFOLIO_ID=$(aws servicecatalog list-portfolios \
  --query "PortfolioDetails[?contains(DisplayName, 'aura')].Id" \
  --output text --region us-east-1)
aws servicecatalog search-products-as-admin --portfolio-id "$PORTFOLIO_ID" \
  --query "ProductViewDetails[*].ProductViewSummary.[Name,Id]" \
  --output table --region us-east-1

# 3. Check Lambda Functions
aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'test-env')].[FunctionName,Runtime]" \
  --output table --region us-east-1

# 4. Check Step Functions
aws stepfunctions list-state-machines \
  --query "stateMachines[?contains(name, 'test-env')].[name,type]" \
  --output table --region us-east-1

# 5. Check API Gateway
aws apigateway get-rest-apis \
  --query "items[?contains(name, 'test-env')].[name,id]" \
  --output table --region us-east-1

# 6. Check All Stack Status
for stack in aura-test-env-state-dev aura-test-env-iam-dev aura-test-env-catalog-dev aura-test-env-approval-dev; do
  echo -n "$stack: "
  aws cloudformation describe-stacks --stack-name $stack \
    --query "Stacks[0].StackStatus" --output text --region us-east-1 2>/dev/null || echo "NOT_FOUND"
done
```

---

## Lessons Learned

### 1. AWS Service Namespaces Vary

Different AWS services use different ARN namespaces for different resource types:
- Service Catalog portfolios/products: `arn:aws:catalog:...`
- Service Catalog constraints: `arn:aws:servicecatalog:...`

Always check the [IAM Actions, Resources, and Condition Keys](https://docs.aws.amazon.com/service-authorization/latest/reference/reference.html) documentation for the correct ARN format.

### 2. Shared Roles Need Multiple Trust Principals

When a role is used by multiple AWS services (e.g., both Step Functions and Lambda), the trust policy must include all services:

```yaml
Principal:
  Service:
    - states.amazonaws.com
    - lambda.amazonaws.com
```

### 3. IAM Update Actions Are Separate

Creating and deleting IAM roles requires different permissions than updating them:
- Create: `iam:CreateRole`
- Delete: `iam:DeleteRole`
- Update: `iam:UpdateRole`, `iam:UpdateRoleDescription`, `iam:UpdateAssumeRolePolicy`

### 4. Test IAM Permissions Comprehensively

Before deploying, validate that the CodeBuild role has permissions for ALL operations the CloudFormation template will perform:
- Create resources
- Update resources (including descriptions, tags, policies)
- Delete resources (for rollback scenarios)

### 5. CodeBuild Self-Referential Stack Updates

Never have a CodeBuild project update its own IAM role stack during a build. The buildspec should skip the codebuild stack and require manual updates for IAM changes.

---

## Related Documentation

- [ADR-039: Self-Service Test Environments](../architecture-decisions/ADR-039-SELF-SERVICE-TEST-ENVIRONMENTS.md)
- [Layer 7 Sandbox Runbook](./LAYER7_SANDBOX_RUNBOOK.md)
- [CloudFormation IAM Permissions Runbook](./CLOUDFORMATION_IAM_PERMISSIONS.md)
- [CI/CD Setup Guide](../deployment/CICD_SETUP_GUIDE.md)

---

## Appendix: Complete IAM Policy Reference

### TestEnvManagedPolicy (Service Catalog Permissions)

```yaml
# Required for Service Catalog management
servicecatalog:CreatePortfolio
servicecatalog:DeletePortfolio
servicecatalog:UpdatePortfolio
servicecatalog:DescribePortfolio
servicecatalog:ListPortfolios
servicecatalog:CreateProduct
servicecatalog:DeleteProduct
servicecatalog:UpdateProduct
servicecatalog:DescribeProduct
servicecatalog:DescribeProductAsAdmin
servicecatalog:ListProvisioningArtifacts
servicecatalog:AssociateProductWithPortfolio
servicecatalog:DisassociateProductFromPortfolio
servicecatalog:AssociatePrincipalWithPortfolio
servicecatalog:DisassociatePrincipalFromPortfolio
servicecatalog:CreateConstraint
servicecatalog:DeleteConstraint
servicecatalog:UpdateConstraint
servicecatalog:DescribeConstraint
servicecatalog:ListConstraintsForPortfolio
servicecatalog:CreateProvisioningArtifact
servicecatalog:DeleteProvisioningArtifact
servicecatalog:UpdateProvisioningArtifact
servicecatalog:TagResource
servicecatalog:UntagResource
```

### IAM Role Management Permissions

```yaml
# Required for IAM role lifecycle management
iam:CreateRole
iam:DeleteRole
iam:GetRole
iam:UpdateRole
iam:UpdateRoleDescription
iam:UpdateAssumeRolePolicy
iam:PutRolePolicy
iam:DeleteRolePolicy
iam:GetRolePolicy
iam:AttachRolePolicy
iam:DetachRolePolicy
iam:TagRole
iam:UntagRole
iam:ListAttachedRolePolicies
iam:ListRolePolicies
iam:PassRole  # With service condition
```

### CloudWatch Logs Patterns

```yaml
# Required log group patterns for test environment resources
/aws/codebuild/${ProjectName}-sandbox-*
/ecs/sandboxes-${Environment}
/ecs/${ProjectName}-sandbox-*
/aws/states/${ProjectName}-hitl-*
/aws/states/${ProjectName}-test-env-*
/aws/lambda/${ProjectName}-test-env-*
/aws/${ProjectName}/${Environment}/*  # Custom approval workflow log group
```

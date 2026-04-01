# Lambda Configuration Standards Runbook

**Last Updated:** 2025-12-12
**Author:** Platform Engineering Team
**Scope:** Standards and validation for AWS Lambda function configurations

---

## Overview

This runbook documents the required configuration standards for all AWS Lambda functions in Project Aura. All Lambda functions must have consistent configurations to ensure operational visibility, compliance, and maintainability.

---

## Required Configuration Properties

### 1. Description (Required)

Every Lambda function MUST have a `Description` property that:
- Starts with a verb (e.g., "Processes", "Handles", "Generates", "Calculates")
- Is concise (under 256 characters)
- Clearly explains the function's purpose
- Does not include environment names (use function name suffix instead)

**Good Examples:**
| Function | Description |
|----------|-------------|
| `aura-chat-handler-dev` | Processes chat messages via Bedrock Claude with tool use |
| `aura-calculate-threshold-dev` | Calculates budget threshold percentages for AWS cost alert notifications |
| `aura-drift-detector-dev` | Detects CloudFormation drift for aura stacks in dev |
| `aura-orchestrator-dispatcher-dev` | Dispatches SQS messages to EKS MetaOrchestrator Jobs |

**Bad Examples:**
| Description | Issue |
|-------------|-------|
| `Lambda function for chat` | Too vague, doesn't start with verb |
| `aura-chat-handler-dev function` | Repeats function name |
| `Handles stuff` | Non-descriptive |
| (empty) | Missing entirely |

### 2. Function Name (Required)

Function names MUST follow the pattern:
```
{project}-{purpose}-{environment}
```

**Pattern:** `aura-{descriptive-name}-{env}`

**Examples:**
- `aura-chat-handler-dev`
- `aura-approval-callback-dev`
- `aura-drift-detector-dev`

### 3. Runtime (Required)

Use the latest supported LTS runtime:
- **Python:** `python3.11` (preferred) or `python3.12`
- **Node.js:** `nodejs20.x` or `nodejs18.x`

### 4. Timeout (Required)

Set appropriate timeouts based on function type:

| Function Type | Recommended Timeout |
|--------------|---------------------|
| API handlers | 30 seconds |
| Event processors | 60 seconds |
| Data pipelines | 300 seconds |
| Long-running tasks | 900 seconds (max) |

### 5. Memory (Required)

Size appropriately for the workload:

| Function Type | Recommended Memory |
|--------------|-------------------|
| Simple handlers | 128-256 MB |
| API with dependencies | 256-512 MB |
| ML/AI processing | 512-1024 MB |
| Heavy compute | 1024-3008 MB |

---

## Current Lambda Inventory

All Project Aura Lambda functions with their descriptions:

| Function Name | Description | Layer |
|--------------|-------------|-------|
| `aura-approval-callback-dev` | Processes approval decisions and sends Step Functions callbacks | Serverless |
| `aura-blocklist-updater-dev` | Generates DNS blocklists from threat intelligence feeds | Security |
| `aura-calculate-threshold-dev` | Calculates budget threshold percentages for AWS cost alert notifications | Observability |
| `aura-chat-handler-dev` | Processes chat messages via Bedrock Claude with tool use | Application |
| `aura-chat-ws-connect-dev` | Handles WebSocket connection establishment | Application |
| `aura-chat-ws-disconnect-dev` | Handles WebSocket disconnection cleanup | Application |
| `aura-chat-ws-message-dev` | Handles incoming WebSocket messages for streaming | Application |
| `aura-deployment-recorder-dev` | Records ArgoCD deployment events to DynamoDB | Application |
| `aura-drift-detector-dev` | Detects CloudFormation drift for aura stacks in dev | Security |
| `aura-expiration-processor-dev` | Processes expired HITL approval requests with auto-escalation | Serverless |
| `aura-orchestrator-dispatcher-dev` | Dispatches SQS messages to EKS MetaOrchestrator Jobs | Serverless |
| `aura-orchestrator-trigger-dev` | Triggers MetaOrchestrator for autonomous remediation of critical security events | Application |
| `aura-threat-intel-processor-dev` | Daily threat intelligence pipeline - gathers CVE/CISA/GitHub advisories | Serverless |

---

## Validation Commands

### Check All Lambda Descriptions

```bash
# List all aura Lambda functions with descriptions
AWS_PROFILE=aura-admin aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `aura-`)].{Name: FunctionName, Description: Description}' \
  --output table --region us-east-1
```

### Find Lambdas Missing Descriptions

```bash
# Find functions with empty or missing descriptions
AWS_PROFILE=aura-admin aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `aura-`) && (Description==`` || Description==`null`)].FunctionName' \
  --output text --region us-east-1
```

### Validate Single Lambda Configuration

```bash
# Get full configuration for a specific Lambda
AWS_PROFILE=aura-admin aws lambda get-function-configuration \
  --function-name aura-chat-handler-dev \
  --query '{Name: FunctionName, Description: Description, Runtime: Runtime, Timeout: Timeout, Memory: MemorySize}' \
  --output json --region us-east-1
```

---

## CloudFormation Template Standards

### Required Properties

Every `AWS::Lambda::Function` resource MUST include:

```yaml
MyLambdaFunction:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub '${ProjectName}-function-name-${Environment}'
    Description: Verb-starting description of what the function does
    Runtime: python3.11
    Handler: index.handler
    Timeout: 30
    MemorySize: 256
    Role: !GetAtt LambdaExecutionRole.Arn
    Code:
      S3Bucket: !Ref LambdaBucket
      S3Key: !Ref LambdaS3Key
    Tags:
      - Key: Project
        Value: !Ref ProjectName
      - Key: Environment
        Value: !Ref Environment
```

### Template Validation

Before committing CloudFormation templates with Lambda functions:

1. **Check for Description property:**
```bash
grep -A 10 "Type: AWS::Lambda::Function" deploy/cloudformation/*.yaml | grep -B 5 -A 5 "Description:"
```

2. **Find Lambda functions missing Description:**
```bash
# Find Lambda resources without Description property
for file in deploy/cloudformation/*.yaml; do
  if grep -q "AWS::Lambda::Function" "$file"; then
    echo "=== $file ==="
    grep -A 15 "Type: AWS::Lambda::Function" "$file" | grep -E "(FunctionName|Description):"
  fi
done
```

---

## Remediation Process

### Adding Missing Description

1. **Identify the CloudFormation template:**
```bash
grep -l "FunctionName.*function-name" deploy/cloudformation/*.yaml
```

2. **Add Description property:**
```yaml
Properties:
  FunctionName: !Sub '${ProjectName}-function-name-${Environment}'
  Description: Clear description starting with a verb
  Runtime: python3.11
```

3. **Commit and deploy:**
```bash
git add deploy/cloudformation/template-name.yaml
git commit -m "fix(lambda): Add missing description to function-name Lambda"
git push

# Deploy via appropriate layer
aws codebuild start-build --project-name aura-{layer}-deploy-dev --region us-east-1
```

4. **Verify deployment:**
```bash
AWS_PROFILE=aura-admin aws lambda get-function-configuration \
  --function-name aura-function-name-dev \
  --query '{FunctionName: FunctionName, Description: Description}' \
  --output json --region us-east-1
```

---

## Historical Fixes

### 2025-12-12: aura-calculate-threshold-dev

**Issue:** Lambda function `aura-calculate-threshold-dev` was deployed without a Description property.

**Root Cause:** The `CalculateThresholdFunction` in `deploy/cloudformation/aura-cost-alerts.yaml` was defined as a CloudFormation custom resource but the Description property was omitted.

**Resolution:**
1. Added Description property: `Calculates budget threshold percentages for AWS cost alert notifications`
2. Deployed via `aura-observability-deploy-dev` CodeBuild
3. Verified description applied to Lambda function

**Template Location:** `deploy/cloudformation/aura-cost-alerts.yaml:248`

---

## Related Documentation

- [Serverless Deployment Runbook](./SERVERLESS_DEPLOYMENT_RUNBOOK.md)
- [CI/CD Setup Guide](../CICD_SETUP_GUIDE.md)
- [AWS Naming Standards](../AWS_NAMING_AND_TAGGING_STANDARDS.md)

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-12 | Platform Engineering | Initial creation documenting Lambda configuration standards |

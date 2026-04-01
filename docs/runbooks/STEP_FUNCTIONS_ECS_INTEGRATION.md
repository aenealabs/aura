# Runbook: Step Functions ECS Integration Troubleshooting

**Purpose:** Diagnose and resolve Step Functions workflow failures when integrating with ECS tasks, particularly JSONPath errors in Choice states

**Audience:** DevOps Engineers, Platform Team, On-call Engineers

**Estimated Time:** 15-45 minutes

**Last Updated:** Jan 2, 2026

---

## Problem Description

Step Functions workflows integrating with ECS `ecs:runTask` may fail at Choice states due to incorrect JSONPath expressions referencing ECS task output. The ECS integration has two modes with different output structures.

### Symptoms

**Choice State Error:**
```
Invalid path '$.solving_result.Tasks[0].Containers[0].ExitCode'
```

**Execution History Shows:**
- `RunTask` state completes successfully
- `CheckResult` Choice state fails immediately
- Error type: `States.Runtime`

### Root Causes

1. **Sync vs Async Integration:** The `ecs:runTask.sync` integration returns task output directly, NOT wrapped in a `Tasks[]` array
2. **Wrong CodeBuild Project:** Deploying CloudFormation via the wrong CodeBuild project (e.g., `serverless` instead of `ssr`) causes the state machine definition to not update
3. **Outdated State Machine:** CloudFormation reports success but the deployed state machine still has the old definition

---

## Quick Resolution

### Fix 1: Correct JSONPath for Sync Integration

For `ecs:runTask.sync` integration, change JSONPath from:
```
$.result.Tasks[0].Containers[0].ExitCode
```

To:
```
$.result.Containers[0].ExitCode
```

### Fix 2: Deploy via Correct CodeBuild Project

Identify which CodeBuild project deploys your CloudFormation template:

```bash
# Find the buildspec that deploys your template
grep -r "ssr-training-pipeline.yaml" deploy/buildspecs/

# Trigger the correct CodeBuild project
aws codebuild start-build --project-name aura-ssr-deploy-dev
```

---

## Detailed Diagnostic Steps

### Step 1: Check Step Functions Execution History

```bash
# Get recent executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT:stateMachine:aura-ssr-training-workflow-dev \
  --status-filter FAILED \
  --max-items 5

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:ACCOUNT:execution:aura-ssr-training-workflow-dev:EXECUTION_ID

# Get execution history (shows exact error location)
aws stepfunctions get-execution-history \
  --execution-arn arn:aws:states:us-east-1:ACCOUNT:execution:aura-ssr-training-workflow-dev:EXECUTION_ID \
  --query 'events[?type==`ChoiceStateEntered` || type==`ExecutionFailed`]'
```

### Step 2: Examine ECS Task Output Structure

Start a test execution and examine the RunTask output:

```bash
# Get output from a successful RunTask state
aws stepfunctions get-execution-history \
  --execution-arn $EXECUTION_ARN \
  --query 'events[?type==`TaskSucceeded`].taskSucceededEventDetails.output' \
  --output text | jq .
```

**Sync Integration Output (`ecs:runTask.sync`):**
```json
{
  "Containers": [
    {
      "ContainerArn": "arn:aws:ecs:...",
      "ExitCode": 0,
      "Name": "bug-solving"
    }
  ],
  "TaskArn": "arn:aws:ecs:...",
  "StoppedReason": "Essential container exited"
}
```

**Async Integration Output (`ecs:runTask`):**
```json
{
  "Tasks": [
    {
      "Containers": [...],
      "TaskArn": "..."
    }
  ],
  "Failures": []
}
```

### Step 3: Verify State Machine Definition

Check if CloudFormation actually updated the state machine:

```bash
# Get current state machine definition
aws stepfunctions describe-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT:stateMachine:aura-ssr-training-workflow-dev \
  --query 'definition' --output text | jq .

# Compare against CloudFormation template
grep -A 50 "CheckSolvingResult" deploy/cloudformation/ssr-training-pipeline.yaml
```

### Step 4: Verify Correct CodeBuild Project

```bash
# Check which buildspec references your template
grep -l "ssr-training-pipeline" deploy/buildspecs/*.yml

# Verify the CodeBuild project that uses that buildspec
aws codebuild batch-get-projects \
  --names aura-ssr-deploy-dev aura-serverless-deploy-dev \
  --query 'projects[*].[name,source.buildspec]'
```

---

## Resolution Procedures

### Procedure 1: Fix JSONPath in CloudFormation

Edit the CloudFormation template to use the correct path:

```yaml
# Before (WRONG for sync integration)
CheckSolvingResult:
  Type: Choice
  Choices:
    - Variable: "$.solving_result.Tasks[0].Containers[0].ExitCode"
      NumericEquals: 0
      Next: RecordSuccess

# After (CORRECT for sync integration)
CheckSolvingResult:
  Type: Choice
  Choices:
    - Variable: "$.solving_result.Containers[0].ExitCode"
      NumericEquals: 0
      Next: RecordSuccess
```

### Procedure 2: Deploy via Correct CodeBuild

```bash
# 1. Identify correct project
CORRECT_PROJECT="aura-ssr-deploy-dev"

# 2. Check for running builds
aws codebuild list-builds-for-project \
  --project-name $CORRECT_PROJECT \
  --query 'ids[0]'

# 3. Trigger deployment
aws codebuild start-build --project-name $CORRECT_PROJECT

# 4. Monitor build progress
aws codebuild batch-get-builds --ids $(aws codebuild list-builds-for-project \
  --project-name $CORRECT_PROJECT --query 'ids[0]' --output text)
```

### Procedure 3: Force State Machine Update

If CloudFormation shows no changes but state machine needs update:

```bash
# Option A: Touch a parameter to force update
aws cloudformation update-stack \
  --stack-name aura-ssr-training-pipeline-dev \
  --use-previous-template \
  --parameters ParameterKey=Environment,ParameterValue=dev

# Option B: Delete and redeploy (if no active executions)
aws stepfunctions list-executions \
  --state-machine-arn $STATE_MACHINE_ARN \
  --status-filter RUNNING

# If no running executions, trigger CodeBuild to redeploy
aws codebuild start-build --project-name aura-ssr-deploy-dev
```

---

## Prevention

### 1. Use Consistent Integration Type

Choose one integration type and use it consistently:

| Integration | Waits for Task? | Output Structure | Use Case |
|-------------|-----------------|------------------|----------|
| `ecs:runTask` | No | `Tasks[]` array | Fire-and-forget |
| `ecs:runTask.sync` | Yes | Direct object | Wait for completion |

### 2. Document CodeBuild-to-Template Mapping

Maintain a mapping in your deployment documentation:

```markdown
| Template | CodeBuild Project | Buildspec |
|----------|-------------------|-----------|
| ssr-training-pipeline.yaml | aura-ssr-deploy-dev | buildspec-ssr.yml |
| sandbox.yaml | aura-serverless-deploy-dev | buildspec-serverless.yml |
```

### 3. Add JSONPath Validation to CI

Add a pre-deployment check for JSONPath expressions:

```bash
# Extract JSONPath expressions from state machine
grep -oP '\$\.[a-zA-Z0-9_.\[\]]+' deploy/cloudformation/ssr-training-pipeline.yaml | sort -u

# Validate against known ECS output structure
# For sync integration: Should NOT contain .Tasks[0]
```

### 4. Test State Machines Before Production

Use Step Functions local testing:

```bash
# Start local Step Functions
docker run -p 8083:8083 amazon/aws-stepfunctions-local

# Create state machine locally and test with sample input
```

---

## ECS RunTask Output Reference

### Sync Integration (`ecs:runTask.sync`)

```json
{
  "Attachments": [...],
  "ClusterArn": "arn:aws:ecs:us-east-1:ACCOUNT:cluster/cluster-name",
  "Containers": [
    {
      "ContainerArn": "arn:aws:ecs:us-east-1:ACCOUNT:container/...",
      "ExitCode": 0,
      "LastStatus": "STOPPED",
      "Name": "container-name",
      "NetworkBindings": [],
      "NetworkInterfaces": [...]
    }
  ],
  "Cpu": "4096",
  "CreatedAt": "2026-01-02T10:00:00Z",
  "DesiredStatus": "STOPPED",
  "LastStatus": "STOPPED",
  "Memory": "16384",
  "StoppedAt": "2026-01-02T10:05:00Z",
  "StoppedReason": "Essential container in task exited",
  "TaskArn": "arn:aws:ecs:us-east-1:ACCOUNT:task/cluster-name/task-id"
}
```

**JSONPath for Exit Code:** `$.Containers[0].ExitCode`

### Async Integration (`ecs:runTask`)

```json
{
  "Tasks": [
    {
      "ClusterArn": "arn:aws:ecs:...",
      "Containers": [
        {
          "ContainerArn": "...",
          "Name": "container-name"
        }
      ],
      "TaskArn": "arn:aws:ecs:..."
    }
  ],
  "Failures": []
}
```

**JSONPath for Task ARN:** `$.Tasks[0].TaskArn`

**Note:** Async integration does not include `ExitCode` because the task hasn't completed yet.

---

## Key Lessons

1. **Always verify which CodeBuild project deploys a given CloudFormation template** - Using the wrong project causes silent failures where CloudFormation reports success but nothing actually changes.

2. **The `.sync` suffix fundamentally changes output structure** - Don't assume sync and async integrations have the same output format.

3. **Check execution history, not just final status** - The execution history shows exactly which state failed and why.

4. **CloudFormation stack update success does not mean state machine updated** - Always verify the deployed state machine definition after deployment.

---

## Related Documentation

- [SSR Training Pipeline CloudFormation](../../deploy/cloudformation/ssr-training-pipeline.yaml)
- [SSR Buildspec](../../deploy/buildspecs/buildspec-ssr.yml)
- [Layer 7 Sandbox Runbook](./LAYER7_SANDBOX_RUNBOOK.md)
- [AWS Step Functions ECS Integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-ecs.html)
- [AWS Step Functions JSONPath Reference](https://docs.aws.amazon.com/step-functions/latest/dg/input-output-example.html)

---

## Appendix: Common JSONPath Patterns for ECS

| Integration Type | Data | JSONPath |
|------------------|------|----------|
| Sync | Container Exit Code | `$.Containers[0].ExitCode` |
| Sync | Task ARN | `$.TaskArn` |
| Sync | Stopped Reason | `$.StoppedReason` |
| Sync | Container Name | `$.Containers[0].Name` |
| Async | Task ARN | `$.Tasks[0].TaskArn` |
| Async | Failure Reason | `$.Failures[0].Reason` |
| Async | Number of Tasks | `$.Tasks` (use States.ArrayLength) |

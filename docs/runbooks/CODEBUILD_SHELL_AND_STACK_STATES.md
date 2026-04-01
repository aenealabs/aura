# Runbook: CodeBuild Shell Syntax and CloudFormation Stack State Handling

**Purpose:** Resolve CodeBuild failures caused by shell syntax errors and improper CloudFormation stack state handling

**Audience:** DevOps Engineers, Platform Team, On-call Engineers

**Estimated Time:** 10-30 minutes

**Last Updated:** Dec 11, 2025

---

## Problem Description

CodeBuild builds may fail due to:
1. Shell syntax errors when using bash-specific features in buildspecs
2. Improper handling of CloudFormation stacks in failed states (ROLLBACK_COMPLETE, CREATE_FAILED)

### Symptoms

**Shell Syntax Error:**
```
/codebuild/output/tmp/script.sh: 12: [[: not found
/codebuild/output/tmp/script.sh: 34: ROLLBACK_COMPLETE: not found
```

**Failed Stack Handling:**
```
An error occurred (ValidationError) when calling the UpdateStack operation:
Stack [stack-name] is in ROLLBACK_COMPLETE state and can not be updated.
```

### Root Causes

1. **Shell Syntax:** CodeBuild defaults to `/bin/sh` (POSIX shell), which doesn't support bash-specific syntax like `[[ ]]` conditionals
2. **Stack States:** Stacks in ROLLBACK_COMPLETE or CREATE_FAILED states cannot be updated - they must be deleted first

---

## Quick Resolution

### Issue 1: Shell Syntax Errors

Add `shell: bash` to the buildspec `env` section:

```yaml
version: 0.2

env:
  shell: bash  # Required for [[ ]] conditionals and other bash features
  variables:
    MY_VAR: "value"
```

### Issue 2: Failed Stack Handling

Delete the failed stack before re-running CodeBuild:

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name $STACK_NAME \
  --query 'Stacks[0].StackStatus' --output text

# If ROLLBACK_COMPLETE or CREATE_FAILED, delete it
aws cloudformation delete-stack --stack-name $STACK_NAME
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME

# Re-run CodeBuild
aws codebuild start-build --project-name $PROJECT_NAME
```

---

## Detailed Diagnostic Steps

### Step 1: Identify Shell Syntax Errors

```bash
# Check CodeBuild logs for shell errors
aws logs filter-log-events \
  --log-group-name /aws/codebuild/$PROJECT_NAME \
  --filter-pattern "[[: not found" \
  --query 'events[-5:].message' \
  --output text
```

Common bash-specific syntax that fails in `/bin/sh`:
- `[[ ]]` - Use `[ ]` instead, or set `shell: bash`
- `(( ))` - Arithmetic evaluation
- `${var//pattern/replacement}` - Pattern substitution
- `<<<` - Here strings
- `{1..10}` - Brace expansion

### Step 2: Check CloudFormation Stack States

```bash
# List all stacks with failed states
aws cloudformation list-stacks \
  --stack-status-filter ROLLBACK_COMPLETE CREATE_FAILED DELETE_FAILED UPDATE_ROLLBACK_FAILED \
  --query "StackSummaries[?contains(StackName, 'aura')].{Name:StackName,Status:StackStatus}" \
  --output table
```

### Step 3: Identify the Failure Reason

```bash
STACK_NAME="aura-example-dev"
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='ROLLBACK_IN_PROGRESS'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" \
  --output table
```

---

## Resolution Procedures

### Procedure 1: Fix Buildspec Shell Configuration

Edit the buildspec to use bash:

```yaml
version: 0.2

# Use bash shell for all commands
env:
  shell: bash
  variables:
    ENVIRONMENT: "dev"

phases:
  build:
    commands:
      # Now bash syntax works
      - |
        if [[ -n "$VAR" && "$VAR" != "None" ]]; then
          echo "Variable is set"
        fi
```

### Procedure 2: Implement Robust Stack State Handling

Add stack status checking to buildspecs:

```yaml
- |
  STACK_NAME="my-stack"

  # Get current stack status
  STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")
  echo "Stack status: $STACK_STATUS"

  # Handle failed states - delete before recreating
  if [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" || \
        "$STACK_STATUS" == "CREATE_FAILED" || \
        "$STACK_STATUS" == "DELETE_FAILED" ]]; then
    echo "Stack is in failed state ($STACK_STATUS), deleting..."
    aws cloudformation delete-stack --stack-name $STACK_NAME
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME
    STACK_STATUS="DOES_NOT_EXIST"
  fi

  # Now decide create vs update
  if [[ "$STACK_STATUS" == "CREATE_COMPLETE" || \
        "$STACK_STATUS" == "UPDATE_COMPLETE" || \
        "$STACK_STATUS" == "UPDATE_ROLLBACK_COMPLETE" ]]; then
    # Update existing stack
    aws cloudformation update-stack --stack-name $STACK_NAME ...
  else
    # Create new stack
    aws cloudformation create-stack --stack-name $STACK_NAME ...
  fi
```

### Procedure 3: Clean Up Orphaned Failed Stacks

When a resource exists outside CloudFormation but a failed stack also exists:

```yaml
- |
  REPO_NAME="aura-api-dev"
  STACK_NAME="aura-ecr-api-dev"

  # Check if resource already exists
  REPO_URI=$(aws ecr describe-repositories --repository-names $REPO_NAME \
    --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "")

  if [[ -n "$REPO_URI" && "$REPO_URI" != "None" ]]; then
    echo "Resource already exists: $REPO_URI"

    # Clean up any failed CloudFormation stack for this resource
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
      --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

    if [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "CREATE_FAILED" ]]; then
      echo "Cleaning up orphaned failed stack..."
      aws cloudformation delete-stack --stack-name $STACK_NAME
      aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME
      echo "Failed stack cleaned up"
    fi
  fi
```

---

## Prevention

### 1. Always Use Bash Shell in Buildspecs

```yaml
env:
  shell: bash
```

### 2. Check Stack Status Before Operations

Never assume a stack can be updated - always check its status first.

### 3. Handle All Failed States

Include handling for all failed states:
- `ROLLBACK_COMPLETE` - Initial creation failed
- `CREATE_FAILED` - Creation failed (rare)
- `DELETE_FAILED` - Deletion failed (resource stuck)
- `UPDATE_ROLLBACK_FAILED` - Update failed and rollback failed

### 4. Use Idempotent Operations

Design buildspecs to be re-runnable without side effects:
- Check if resources exist before creating
- Handle "No updates to be performed" gracefully
- Clean up failed states automatically

---

## CloudFormation Stack State Reference

| State | Can Update? | Can Delete? | Action Required |
|-------|-------------|-------------|-----------------|
| CREATE_COMPLETE | Yes | Yes | None |
| UPDATE_COMPLETE | Yes | Yes | None |
| UPDATE_ROLLBACK_COMPLETE | Yes | Yes | None |
| ROLLBACK_COMPLETE | No | Yes | Delete and recreate |
| CREATE_FAILED | No | Yes | Delete and recreate |
| DELETE_FAILED | No | Retry | Retry delete or skip resources |
| UPDATE_ROLLBACK_FAILED | No | Yes | Continue rollback or delete |

---

## Related Documentation

- [Application Buildspec](../../deploy/buildspecs/buildspec-application.yml)
- [ECR Repository Conflicts Runbook](./ECR_REPOSITORY_CONFLICTS.md)
- [CloudFormation IAM Permissions Runbook](./CLOUDFORMATION_IAM_PERMISSIONS.md)
- [AWS CodeBuild Buildspec Reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
- [AWS CloudFormation Stack States](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-describing-stacks.html)

---

## Appendix: Common Shell Syntax Differences

| Feature | Bash | POSIX sh | Fix |
|---------|------|----------|-----|
| Extended test | `[[ $a == $b ]]` | Not supported | Use `[ "$a" = "$b" ]` or `shell: bash` |
| Pattern match | `[[ $a == *pattern* ]]` | Not supported | Use `case` or `shell: bash` |
| Arithmetic | `(( a + b ))` | Not supported | Use `$((a + b))` or `shell: bash` |
| Here string | `cmd <<< "string"` | Not supported | Use `echo "string" \| cmd` or `shell: bash` |
| Brace expansion | `{1..5}` | Not supported | Use `seq 1 5` or `shell: bash` |
| `$RANDOM` | Supported | Not always | Use `shell: bash` |

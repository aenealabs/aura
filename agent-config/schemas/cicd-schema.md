# CI/CD Task Schema

Schema for specialized agents working on CI/CD related tasks (buildspecs, CodeBuild, deployment pipelines).

---

## Schema Metadata

| Field | Value |
|-------|-------|
| **Name** | CI/CD Task Schema |
| **Domain** | CICD |
| **Version** | 1.0.0 |
| **Last Updated** | 2025-12-04 |

---

## Required Guardrails

These guardrails MUST be loaded before executing any CI/CD task:

| Guardrail ID | Title | Severity |
|--------------|-------|----------|
| GR-CICD-001 | CodeBuild Buildspec Pattern Compliance | Critical |
| GR-SEC-001 | SSM Parameter Store for Configuration | High |
| GR-CFN-001 | GovCloud ARN Partitions | High |
| GR-CFN-002 | CloudFormation Description Standards | Medium |

---

## Pre-Task Checklist

Before modifying any CI/CD configuration, complete these checks:

### 1. Pattern Discovery
```bash
# Search for existing buildspec patterns
grep -A 30 "build:" deploy/buildspecs/buildspec-*.yml

# Check for similar deployment logic
grep -r "cloudformation" deploy/buildspecs/

# Find existing CloudFormation stacks with similar purpose
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `aura`)].StackName' --output table
```

### 2. Reference File Identification
Identify the most similar existing implementation:

| Task Type | Reference File |
|-----------|---------------|
| ECR Repository | `deploy/cloudformation/ecr-dnsmasq.yaml` |
| CloudFormation Deployment | `deploy/buildspecs/buildspec-data.yml` |
| Multi-Phase Build | `deploy/buildspecs/buildspec-application.yml` |
| IAM Permissions | `deploy/cloudformation/iam.yaml` |
| CodeBuild Project | `deploy/cloudformation/codebuild-*.yaml` |

### 3. Environment Variable Check
Verify required environment variables are available:
- `$PROJECT_NAME` - Project identifier (aura)
- `$ENVIRONMENT` - Deployment environment (dev/qa/prod)
- `$AWS_DEFAULT_REGION` - AWS region
- `$DEPLOY_TIMESTAMP` - Unique timestamp for stack tagging

---

## Implementation Patterns

### Pattern 1: Simple CloudFormation Deploy

For single-resource deployments with no conditional logic:

```yaml
- aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-resource-${ENVIRONMENT} \
    --template-file deploy/cloudformation/template.yaml \
    --parameter-overrides \
      Environment=$ENVIRONMENT \
      ProjectName=$PROJECT_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
      Project=$PROJECT_NAME \
      Environment=$ENVIRONMENT \
      Layer=application \
      DeployTimestamp=$DEPLOY_TIMESTAMP \
    --no-fail-on-empty-changeset
```

**When to use:**
- Single resource deployment
- No outputs needed for subsequent steps
- Idempotent operation acceptable

### Pattern 2: Multiline Block with Create/Update Logic

For complex deployments requiring stack existence checks or output retrieval:

```yaml
- |
  echo "Deploying Resource Stack..."
  STACK_NAME="${PROJECT_NAME}-resource-${ENVIRONMENT}"

  # Check if stack exists
  STACK_EXISTS=false
  if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION 2>/dev/null; then
    STACK_EXISTS=true
  fi

  if [ "$STACK_EXISTS" = "true" ]; then
    if aws cloudformation update-stack \
      --stack-name $STACK_NAME \
      --template-body file://deploy/cloudformation/template.yaml \
      --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
      --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT \
      --region $AWS_DEFAULT_REGION \
      --no-cli-pager 2>&1; then
      echo "Stack update initiated, waiting..."
      aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION
    else
      echo "Stack already up-to-date (no changes needed)"
    fi
  else
    aws cloudformation create-stack \
      --stack-name $STACK_NAME \
      --template-body file://deploy/cloudformation/template.yaml \
      --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
      --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT \
      --region $AWS_DEFAULT_REGION \
      --no-cli-pager
    echo "Stack creation initiated, waiting..."
    aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION
  fi

  # Retrieve outputs for subsequent steps
  OUTPUT_VALUE=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`OutputName`].OutputValue' --output text --region $AWS_DEFAULT_REGION)
  echo "Output: $OUTPUT_VALUE"
```

**When to use:**
- Need to retrieve stack outputs
- Different create vs update behavior required
- Multiple commands in sequence

### Pattern 3: Phase Separation with Comments

For multi-phase buildspecs with distinct deployment stages:

```yaml
build:
  commands:
    # ============================================
    # PHASE 1: Deploy First Resource
    # ============================================
    - |
      echo "Phase 1: Deploying first resource..."
      # ... deployment logic

    # ============================================
    # PHASE 2: Deploy Second Resource
    # ============================================
    - |
      echo "Phase 2: Deploying second resource..."
      # ... deployment logic
```

**When to use:**
- Multiple independent resources to deploy
- Clear separation aids debugging
- Each phase has distinct purpose

---

## Anti-Patterns

### Anti-Pattern 1: Shell Script Libraries

**DO NOT** create separate shell script files for buildspec commands:

```yaml
# WRONG: External shell library
- source deploy/scripts/lib/deploy.sh
- deploy_stack "my-stack" "template.yaml"
```

**Reason:** CodeBuild's YAML parser has strict requirements. External libraries add complexity and debugging difficulty without proportional benefit.

### Anti-Pattern 2: Mixed Command Styles

**DO NOT** mix single-line and multiline patterns inconsistently:

```yaml
# WRONG: Inconsistent style
- echo "Simple command"
- |
  echo "Multiline block"
  # More commands
- aws cloudformation deploy --stack-name foo  # Back to single line
```

**Reason:** Makes the buildspec harder to read and maintain. Pick one pattern for the file.

### Anti-Pattern 3: Hardcoded Values

**DO NOT** hardcode account IDs, ARNs, or environment-specific values:

```yaml
# WRONG: Hardcoded account ID
- aws ecr get-login-password | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# CORRECT: Use environment variables
- aws ecr get-login-password | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com
```

---

## Post-Task Validation

After completing any CI/CD modification:

### 1. Syntax Validation
```bash
# Validate YAML syntax (not perfect but catches obvious errors)
python3 -c "import yaml; yaml.safe_load(open('deploy/buildspecs/buildspec-application.yml'))"
```

### 2. CloudFormation Template Validation
```bash
# Lint CloudFormation templates
cfn-lint deploy/cloudformation/new-template.yaml

# AWS native validation
aws cloudformation validate-template --template-body file://deploy/cloudformation/new-template.yaml
```

### 3. CodeBuild Execution
```bash
# Trigger the build
aws codebuild start-build --project-name aura-application-deploy-dev

# Monitor progress
aws codebuild batch-get-builds --ids <build-id> --query 'builds[0].{status:buildStatus,phase:currentPhase}'
```

### 4. Stack Verification
```bash
# Verify stack deployed successfully
aws cloudformation describe-stacks --stack-name <stack-name> --query 'Stacks[0].StackStatus'

# Check for drift
aws cloudformation detect-stack-drift --stack-name <stack-name>
```

---

## Confidence Thresholds

| Confidence Level | Guardrail Loading | Human Review |
|-----------------|-------------------|--------------|
| High (>80%) | Critical only | Not required |
| Medium (50-80%) | Critical + High | Recommended |
| Low (<50%) | All guardrails | Required |

**Confidence decreases when:**
- Task involves unfamiliar file types
- No similar pattern found in codebase
- Multiple valid approaches exist
- Error messages are ambiguous

---

## Related Schemas

| Schema | Use When |
|--------|----------|
| `security-schema.md` | IAM policies, encryption, access control |
| `cloudformation-schema.md` | Infrastructure template creation |
| `kubernetes-schema.md` | EKS manifests, deployments |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-04 | Initial schema from GR-CICD-001 incident |

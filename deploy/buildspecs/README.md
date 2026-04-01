# CodeBuild Buildspec Files

This directory contains AWS CodeBuild buildspec files for deploying Project Aura infrastructure.

## Architecture

The buildspec files follow a modular architecture with three tiers:

### 1. Parent Buildspecs (Layer Orchestrators)
Main buildspecs that deploy an entire infrastructure layer:
- `buildspec-foundation.yml` - Foundation layer (VPC, IAM, WAF)
- `buildspec-data.yml` - Data layer (Neptune, OpenSearch, DynamoDB)
- `buildspec-compute.yml` - Compute layer (EKS, Node Groups)
- `buildspec-application.yml` - Application layer (ECR, Bedrock, IRSA, K8s)
- `buildspec-observability.yml` - Observability layer (Monitoring, Secrets)
- `buildspec-serverless.yml` - Serverless layer (Lambda, Step Functions)
- `buildspec-sandbox.yml` - Sandbox layer (HITL, Test Environments)
- `buildspec-security.yml` - Security layer (GuardDuty, Config)

### 2. Sub-Buildspecs (Component Deployers)
Modular buildspecs that deploy specific components within a layer:

**Application Layer:**
- `buildspec-application-ecr.yml` - ECR repositories (Layer 4.1)
- `buildspec-application-bedrock.yml` - Bedrock infrastructure (Layer 4.2)
- `buildspec-application-irsa.yml` - IRSA roles (Layer 4.3)
- `buildspec-application-k8s.yml` - Kubernetes deployments (Layer 4.4)

**Serverless Layer:**
- `buildspec-serverless-security.yml` - Permission boundary, IAM alerting (Layer 6.0)
- `buildspec-serverless-lambdas.yml` - Lambda packaging (Layer 6.1)
- `buildspec-serverless-stacks.yml` - CloudFormation stacks (Layer 6.2)

**Sandbox Layer:**
- `buildspec-sandbox-infrastructure.yml` - Core infrastructure (Layer 7.1-7.4)
- `buildspec-sandbox-catalog.yml` - Service Catalog & Monitoring (Layer 7.4-7.7)
- `buildspec-sandbox-advanced.yml` - Advanced features (Layer 7.8-7.10)

### 3. Utility Scripts
Shared bash scripts that provide common functionality:

- `deploy/scripts/cfn-deploy-helpers.sh` - CloudFormation deployment utilities
- `deploy/scripts/package-lambdas.sh` - Lambda packaging functions
- `deploy/scripts/validate-dependencies.sh` - Pre-deployment validation
- `deploy/scripts/eks-readiness.sh` - EKS cluster readiness checks

## Usage

### Using Sub-Buildspecs
Sub-buildspecs can be invoked by:
1. Step Functions orchestration via `deployment-pipeline.yaml`
2. Separate CodeBuild projects referencing the sub-buildspec
3. CodeBuild batch builds

### Using Utility Scripts
Source the utility scripts at the start of your buildspec:

```yaml
pre_build:
  commands:
    - source deploy/scripts/cfn-deploy-helpers.sh
    - source deploy/scripts/validate-dependencies.sh
```

Then use helper functions:

```yaml
build:
  commands:
    # Validate dependencies before deployment
    - validate_cfn_stacks "networking-stack" "data-stack"

    # Deploy a CloudFormation stack (idempotent create/update)
    - |
      cfn_deploy_stack \
        "${PROJECT_NAME}-my-stack-${ENVIRONMENT}" \
        "deploy/cloudformation/my-template.yaml" \
        "Environment=${ENVIRONMENT} ProjectName=${PROJECT_NAME}" \
        "Project=${PROJECT_NAME} Environment=${ENVIRONMENT} Layer=4.1"
```

## Key Functions

### cfn_deploy_stack
Idempotent CloudFormation deployment (handles create/update automatically):
```bash
cfn_deploy_stack STACK_NAME TEMPLATE_FILE PARAMETERS TAGS [CAPABILITIES] [REGION]
```

### cfn_get_stack_output
Retrieve a stack output value:
```bash
cfn_get_stack_output STACK_NAME OUTPUT_KEY [DEFAULT_VALUE]
```

### cfn_cleanup_failed
Clean up a failed stack before retrying:
```bash
cfn_cleanup_failed STACK_NAME
```

### validate_cfn_stacks
Verify required stacks exist:
```bash
validate_cfn_stacks "stack1" "stack2" "stack3"
```

### validate_eks_cluster
Check EKS cluster is ready:
```bash
validate_eks_cluster CLUSTER_NAME
```

## Guidelines

1. **Max 600 lines** - Keep buildspec files under 600 lines
2. **Use helper functions** - Prefer `cfn_deploy_stack` over verbose create/update logic
3. **Validate dependencies** - Check required stacks exist before deploying
4. **Use deploy instead of create/update** - `aws cloudformation deploy --no-fail-on-empty-changeset`
5. **Add descriptive comments** - Document what each phase does
6. **Follow naming conventions** - `${PROJECT_NAME}-component-${ENVIRONMENT}`

## Step Functions Orchestration

The `deployment-pipeline.yaml` Step Functions state machine orchestrates full environment deployments:

1. **Infrastructure Phase** - Foundation → Data → Compute → [App|Observability|Serverless] → Sandbox → Security
2. **K8s Config Phase** - Generate kubectl configuration
3. **Container Build Phase** - Build and push container images (parallel)
4. **K8s Deploy Phase** - Apply Kubernetes manifests
5. **Verification Phase** - Validate deployment success

## Related Documentation

- `docs/deployment/CICD_SETUP_GUIDE.md` - Full CI/CD setup guide
- `docs/deployment/DEPLOYMENT_GUIDE.md` - Deployment instructions
- `CLAUDE.md` - Project development guidelines

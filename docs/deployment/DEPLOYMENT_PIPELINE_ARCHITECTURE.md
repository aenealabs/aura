# Deployment Pipeline Architecture

**Last Updated:** 2026-01-09
**Status:** Designed, Ready for Implementation
**Author:** Engineering Team

---

## Overview

The Project Aura deployment pipeline uses AWS Step Functions to orchestrate complete environment deployments with proper dependency management. A single trigger deploys all infrastructure, generates Kubernetes configs, builds container images, and deploys to the EKS cluster.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP FUNCTIONS: aura-deployment-pipeline-{env}           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │ ValidateInput│                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                            │
│  │ NotifyStart │──────────────────────────────────────────► SNS Topic       │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 1: INFRASTRUCTURE                           │   │
│  │  ┌────────┐   ┌────────┐   ┌────────┐                               │   │
│  │  │Layer 1 │──▶│Layer 2 │──▶│Layer 3 │                               │   │
│  │  │Found.  │   │ Data   │   │Compute │                               │   │
│  │  └────────┘   └────────┘   └───┬────┘                               │   │
│  │                                │                                     │   │
│  │              ┌─────────────────┼─────────────────┐                  │   │
│  │              ▼                 ▼                 ▼                  │   │
│  │         ┌────────┐       ┌────────┐       ┌────────┐                │   │
│  │         │Layer 4 │       │Layer 5 │       │Layer 6 │  (parallel)   │   │
│  │         │  App   │       │Observ. │       │Svrless │                │   │
│  │         └───┬────┘       └───┬────┘       └───┬────┘                │   │
│  │              └─────────────────┼─────────────────┘                  │   │
│  │                                ▼                                     │   │
│  │                          ┌────────┐                                  │   │
│  │                          │Layer 7 │                                  │   │
│  │                          │Sandbox │                                  │   │
│  │                          └───┬────┘                                  │   │
│  │                              ▼                                       │   │
│  │                          ┌────────┐                                  │   │
│  │                          │Layer 8 │                                  │   │
│  │                          │Security│                                  │   │
│  │                          └────────┘                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               PHASE 2: KUBERNETES CONFIG GENERATION                  │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ Lambda: K8sConfigGenerator                                    │   │   │
│  │  │ - Collects all CloudFormation outputs                         │   │   │
│  │  │ - Stores endpoints in SSM Parameter Store                     │   │   │
│  │  │ - All infrastructure exists before this runs                  │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               PHASE 3: CONTAINER IMAGE BUILDS                        │   │
│  │                                                                       │   │
│  │    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
│  │    │aura-api │  │orchestr.│  │ memory  │  │  meta   │  │frontend │  │   │
│  │    │  build  │  │  build  │  │  build  │  │  build  │  │  build  │  │   │
│  │    └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │   │
│  │                        (all run in parallel)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               PHASE 4: KUBERNETES DEPLOYMENT                         │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ CodeBuild: aura-k8s-deploy-{env}                              │   │   │
│  │  │ 1. Run generate-k8s-config.sh                                 │   │   │
│  │  │ 2. Install ALB Controller (Helm)                              │   │   │
│  │  │ 3. Apply Kustomize overlays for all services                  │   │   │
│  │  │ 4. Apply Ingress rules                                        │   │   │
│  │  │ 5. Wait for rollouts                                          │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               PHASE 5: VERIFICATION                                  │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ CodeBuild: aura-integration-test-{env}                        │   │   │
│  │  │ - Health checks                                               │   │   │
│  │  │ - Connectivity tests                                          │   │   │
│  │  │ - Integration tests                                           │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                    ┌─────────────┐                        │
│  │NotifySuccess│──► SNS ◄──────────│NotifyFailure│                        │
│  └──────┬──────┘                    └──────┬──────┘                        │
│         ▼                                   ▼                               │
│  ┌─────────────┐                    ┌─────────────┐                        │
│  │  SUCCESS    │                    │   FAILED    │                        │
│  └─────────────┘                    └─────────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Flow

### Why This Order Matters

| Phase | Depends On | Produces |
|-------|------------|----------|
| Layer 1 (Foundation) | - | VPC, Subnets, Security Groups, IAM Roles |
| Layer 2 (Data) | Layer 1 | Neptune, OpenSearch, DynamoDB, S3, ElastiCache |
| Layer 3 (Compute) | Layers 1-2 | EKS Cluster, Node Groups, ECR, IRSA Roles |
| Layers 4-6 | Layer 3 | Application, Observability, Serverless resources |
| Layer 7 (Sandbox) | Layers 1-6 | HITL workflow, SNS topics, ECS cluster |
| Layer 8 (Security) | Layer 1 | AWS Config, GuardDuty |
| K8s Config Gen | All Layers | SSM parameters, Kustomize overlays |
| Container Builds | Layer 3 (ECR) | Docker images in ECR |
| K8s Deployment | Config Gen + Builds | Running pods, services, ingress |
| Verification | K8s Deployment | Test results, health status |

### Parallel Execution

The pipeline maximizes parallelism where dependencies allow:

1. **Layers 4, 5, 6** run in parallel (all depend only on Layer 3)
2. **All 5 container builds** run in parallel (all depend only on ECR)

This reduces total deployment time while respecting dependencies.

---

## Components

### CloudFormation Templates

| Template | Purpose | Layer |
|----------|---------|-------|
| `deployment-pipeline.yaml` | Step Functions state machine, Lambda functions, IAM roles | 6.11 |
| `codebuild-k8s-deploy.yaml` | Kubernetes deployment CodeBuild project | 3.5 |

### Buildspecs

| Buildspec | Purpose |
|-----------|---------|
| `buildspec-k8s-deploy.yml` | Generates K8s configs, deploys to EKS cluster |
| `buildspec-api-build.yml` | Builds aura-api container image |
| `buildspec-orchestrator-build.yml` | Builds agent-orchestrator container image |
| `buildspec-memory-build.yml` | Builds memory-service container image |
| `buildspec-meta-orchestrator-build.yml` | Builds meta-orchestrator container image |
| `buildspec-frontend-build.yml` | Builds aura-frontend container image |

### Lambda Functions

| Function | Purpose |
|----------|---------|
| `aura-codebuild-poller-{env}` | Polls CodeBuild build status |
| `aura-k8s-config-generator-{env}` | Collects CF outputs, stores in SSM |
| `aura-k8s-deployer-{env}` | Placeholder for deployment status |

---

## Usage

### Trigger Full Deployment

```bash
# Start deployment pipeline
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:aura-deployment-pipeline-qa \
  --input '{"environment": "qa", "region": "us-east-1"}'
```

### Monitor Execution

```bash
# List executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:aura-deployment-pipeline-qa

# Get execution status
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:ACCOUNT_ID:execution:aura-deployment-pipeline-qa:EXECUTION_ID
```

### View in Console

Navigate to: **AWS Console > Step Functions > State machines > aura-deployment-pipeline-{env}**

The visual workflow shows:
- Current execution state
- Completed/failed steps
- Execution history
- CloudWatch logs for each step

---

## Error Handling

### Automatic Retry

CodeBuild builds use `.sync` integration which automatically waits for completion. If a build fails, the pipeline fails at that state with full error details.

### Failure Notifications

When any phase fails:
1. SNS notification sent with error details
2. Pipeline transitions to `DeploymentFailed` state
3. Execution stops (no partial deployments)

### Manual Intervention

If the pipeline fails mid-execution:

1. **Fix the issue** (e.g., fix CloudFormation template, fix container build)
2. **Re-trigger the pipeline** - it will re-run from the beginning
3. **CloudFormation stacks** use `--no-fail-on-empty-changeset` so re-running is idempotent

---

## Cost Considerations

| Component | Pricing Model |
|-----------|---------------|
| Step Functions | $0.025 per 1,000 state transitions |
| Lambda | $0.20 per 1M requests + compute time |
| CodeBuild | $0.005/min (small), $0.01/min (medium) |
| CloudWatch Logs | $0.50/GB ingested |

**Estimated cost per deployment:** ~$5-10 (depending on build times)

---

## Future Enhancements

### Short-term

- [ ] Add manual approval step before production deployments
- [ ] Add rollback capability (deploy previous version on failure)
- [ ] Add Slack/Teams notifications

### Medium-term

- [ ] Blue/green deployment support
- [ ] Canary deployment with automatic rollback
- [ ] Multi-region deployment orchestration

### Long-term

- [ ] GitOps integration (ArgoCD trigger instead of CodeBuild)
- [ ] Deployment metrics dashboard
- [ ] Cost tracking per deployment

---

## References

- [AWS Step Functions Developer Guide](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [Step Functions CodeBuild Integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-codebuild.html)
- [QA Deployment Checklist](./QA_DEPLOYMENT_CHECKLIST.md)
- [QA Deployment Automation](./QA_DEPLOYMENT_AUTOMATION.md)

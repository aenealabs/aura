# Bootstrap Exemption Resources

**Document Version:** 1.1
**Last Updated:** 2025-12-14
**Classification:** Operations / Compliance
**Review Cycle:** Annual or upon CI/CD architecture changes

---

## Executive Summary

This document defines the Bootstrap Exemption policy for Project Aura infrastructure resources. Bootstrap exemptions are a recognized industry-standard pattern that addresses the inherent circular dependency ("chicken-and-egg") problem in establishing CI/CD pipelines: **the CI/CD system cannot deploy itself**.

Project Aura enforces a strict **CI/CD Single Source of Truth** policy where AWS CodeBuild is the only authoritative deployment method for all infrastructure. However, the Foundation CodeBuild stack requires a one-time manual deployment to establish this capability. This document provides auditors, compliance officers, and operations teams with complete transparency into which resources require bootstrap exemption and why.

---

## Table of Contents

1. [Policy Statement](#policy-statement)
2. [Industry Standards and Best Practices](#industry-standards-and-best-practices)
3. [The Bootstrap Problem Explained](#the-bootstrap-problem-explained)
4. [Bootstrap Exemption Registry](#bootstrap-exemption-registry)
5. [One-Time Bootstrap Deployment Procedure](#one-time-bootstrap-deployment-procedure)
6. [CI/CD Cascade Architecture](#cicd-cascade-architecture)
7. [Tagging Requirements](#tagging-requirements)
8. [Audit and Compliance](#audit-and-compliance)
9. [Revision History](#revision-history)

---

## Policy Statement

### CI/CD Single Source of Truth

Project Aura maintains a strict policy that **AWS CodeBuild is the ONLY authoritative deployment method** for all infrastructure resources. This policy ensures:

- Complete audit trail of all infrastructure changes
- Consistent IAM permissions across all deployments
- Reproducible deployments with version-controlled templates
- Compliance with SOX, CMMC Level 2, and NIST 800-53 requirements
- Prevention of configuration drift and manual deployment errors

### Bootstrap Exemption Definition

A **Bootstrap Exemption** is a documented exception to the CI/CD Single Source of Truth policy that permits one-time manual deployment of specific resources required to establish the CI/CD pipeline itself. Bootstrap exemptions:

- Are limited to resources that cannot deploy themselves
- Require explicit documentation and approval
- Must be tagged with `BootstrapExemption=true`
- Are subject to annual review and reauthorization
- Become self-managing after initial deployment

---

## Industry Standards and Best Practices

The bootstrap exemption pattern is recognized and recommended by major cloud providers and industry frameworks:

### AWS Well-Architected Framework

The AWS Well-Architected Framework (Operational Excellence Pillar) acknowledges that initial CI/CD pipeline infrastructure requires manual provisioning:

> "Design your workload so that it can be deployed and updated through automation. Start with manual deployment to establish the initial automation infrastructure, then transition to fully automated deployments."
>
> -- AWS Well-Architected Framework, OPS 06

### AWS CodeBuild Best Practices

AWS documentation explicitly addresses the bootstrap pattern:

> "For the initial setup of your CI/CD pipeline, you will need to manually create the CodeBuild project that will subsequently manage all other infrastructure deployments."
>
> -- AWS CodeBuild Developer Guide

### NIST 800-53 (CM-3: Configuration Change Control)

NIST 800-53 permits documented exceptions for establishing baseline configurations:

> "Organizations may allow alternative processes for implementing changes during emergency situations or for initial system provisioning, provided such actions are documented and reviewed."
>
> -- NIST SP 800-53 Rev. 5, CM-3

### GitOps and Infrastructure as Code Standards

The GitOps methodology (as defined by the Cloud Native Computing Foundation) recognizes bootstrap requirements:

| Phase | Method | Description |
|-------|--------|-------------|
| **Bootstrap** | Manual | One-time deployment of GitOps/CI/CD controller |
| **Steady State** | Automated | All subsequent changes via version control |

### Industry Adoption

| Organization | Bootstrap Pattern | Documentation |
|--------------|-------------------|---------------|
| AWS | Supported | Well-Architected Framework |
| Kubernetes | Required | Cluster bootstrap procedures |
| ArgoCD | Required | App-of-Apps pattern |
| Terraform | Supported | Backend bootstrap |
| HashiCorp Vault | Required | Initialization ceremony |

---

## The Bootstrap Problem Explained

### Circular Dependency Challenge

The bootstrap problem is a fundamental challenge in CI/CD architecture:

```
                    +---------------------------+
                    |   Foundation CodeBuild    |
                    |   (codebuild-foundation)  |
                    +---------------------------+
                              |
                              | Cannot deploy itself
                              | (chicken-and-egg)
                              v
              +-------------------------------+
              |   BOOTSTRAP EXEMPTION         |
              |   One-time manual deployment  |
              +-------------------------------+
                              |
                              | After bootstrap
                              v
              +-------------------------------+
              |   Self-managing CI/CD         |
              |   All subsequent deploys      |
              |   via CodeBuild               |
              +-------------------------------+
```

### Why Manual Deployment is Required

1. **No Pre-existing Deployment Mechanism**: Before the Foundation CodeBuild project exists, there is no automated system capable of creating it.

2. **IAM Role Dependencies**: The CodeBuild project requires an IAM role, but that role is defined in the same template that creates the project.

3. **Self-Referential Templates**: The `codebuild-foundation.yaml` template cannot be deployed by the CodeBuild project it defines.

4. **Initial State Establishment**: Every CI/CD system requires an initial "seeding" of infrastructure before automation can take over.

### Resolution Through Bootstrap

The bootstrap exemption resolves this by:

1. Permitting a **single** manual deployment of the Foundation CodeBuild stack
2. Documenting and tagging this exemption for audit purposes
3. Ensuring all subsequent deployments (including updates to Foundation) use CodeBuild
4. Establishing the Foundation CodeBuild as the deployer of all other CodeBuild projects

---

## Bootstrap Exemption Registry

The following resources are authorized for bootstrap exemption in Project Aura:

### Primary Bootstrap Resource

| Resource | Stack Name | Template Path | Exemption Reason |
|----------|------------|---------------|------------------|
| Foundation CodeBuild | `aura-codebuild-foundation-{env}` | `deploy/cloudformation/codebuild-foundation.yaml` | Cannot deploy itself; establishes CI/CD capability |

### Resource Details

#### aura-codebuild-foundation-dev

| Attribute | Value |
|-----------|-------|
| **Stack Name** | `aura-codebuild-foundation-dev` |
| **Template** | `deploy/cloudformation/codebuild-foundation.yaml` |
| **Description** | Project Aura - Foundation Layer CodeBuild Project (Layer 1: VPC, IAM, WAF, VPC Endpoints) |
| **Purpose** | Provides CodeBuild project and IAM role for Foundation layer deployments |
| **Bootstrap Reason** | Chicken-and-egg problem - cannot deploy itself; must be manually deployed to establish CI/CD pipeline |
| **After Bootstrap** | Self-manages via Foundation CodeBuild, which can update itself and all other CodeBuild stacks |
| **Resources Created** | CodeBuild Project, IAM Role, S3 Artifacts Bucket, CloudWatch Log Group, CloudWatch Alarms |
| **Environment** | dev, qa, prod (one stack per environment) |

### Resources NOT Requiring Bootstrap Exemption

The following CodeBuild projects are deployed **by** the Foundation CodeBuild and do **not** require bootstrap exemption:

| Stack Name | Deployed By | Layer |
|------------|-------------|-------|
| `aura-codebuild-network-services-{env}` | Foundation CodeBuild | 1.7 (Foundation) |
| `aura-codebuild-docker-{env}` | Foundation CodeBuild | 1.9 (Foundation/CI/CD) |
| `aura-codebuild-data-{env}` | Foundation CodeBuild | 2 (Data) |
| `aura-codebuild-compute-{env}` | Foundation CodeBuild | 3 (Compute) |
| `aura-codebuild-application-{env}` | Foundation CodeBuild | 4 (Application) |
| `aura-codebuild-observability-{env}` | Foundation CodeBuild | 5 (Observability) |
| `aura-codebuild-serverless-{env}` | Foundation CodeBuild | 6 (Serverless) |
| `aura-codebuild-chat-assistant-{env}` | Serverless CodeBuild | 6.7 (Serverless) |
| `aura-codebuild-incident-response-{env}` | Serverless CodeBuild | 6.9 (Serverless) |
| `aura-codebuild-runbook-agent-{env}` | Serverless CodeBuild | 6 (Serverless) |
| `aura-codebuild-sandbox-{env}` | Foundation CodeBuild | 7 (Sandbox) |
| `aura-codebuild-security-{env}` | Foundation CodeBuild | 8 (Security) |
| `aura-codebuild-frontend-{env}` | Foundation CodeBuild | 4 (Application) |

---

## One-Time Bootstrap Deployment Procedure

### Prerequisites

Before executing the bootstrap deployment:

- [ ] AWS CLI configured with appropriate credentials
- [ ] IAM permissions: `cloudformation:*`, `codebuild:*`, `iam:*`, `s3:*`, `logs:*`
- [ ] GitHub CodeConnections ARN stored in SSM Parameter Store (`/aura/global/codeconnections-arn`)
- [ ] Access to the Project Aura repository

### Bootstrap Deployment Command

Execute the following command **once per environment** to establish the CI/CD foundation:

```bash
# Development Environment
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-foundation.yaml \
  --stack-name aura-codebuild-foundation-dev \
  --parameter-overrides \
    Environment=dev \
    ProjectName=aura \
    GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Project=aura \
    Environment=dev \
    ManagedBy=Bootstrap \
    BootstrapExemption=true \
    BootstrapDate=$(date +%Y-%m-%d) \
    BootstrapOperator=$(whoami) \
  --region us-east-1
```

```bash
# QA Environment
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-foundation.yaml \
  --stack-name aura-codebuild-foundation-qa \
  --parameter-overrides \
    Environment=qa \
    ProjectName=aura \
    GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Project=aura \
    Environment=qa \
    ManagedBy=Bootstrap \
    BootstrapExemption=true \
    BootstrapDate=$(date +%Y-%m-%d) \
    BootstrapOperator=$(whoami) \
  --region us-east-1
```

```bash
# Production Environment
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-foundation.yaml \
  --stack-name aura-codebuild-foundation-prod \
  --parameter-overrides \
    Environment=prod \
    ProjectName=aura \
    GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Project=aura \
    Environment=prod \
    ManagedBy=Bootstrap \
    BootstrapExemption=true \
    BootstrapDate=$(date +%Y-%m-%d) \
    BootstrapOperator=$(whoami) \
  --region us-east-1
```

### Post-Bootstrap Verification

After successful deployment, verify the bootstrap:

```bash
# Verify stack creation
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-foundation-dev \
  --query 'Stacks[0].{Status:StackStatus,Tags:Tags}' \
  --output table

# Verify CodeBuild project exists
aws codebuild batch-get-projects \
  --names aura-foundation-deploy-dev \
  --query 'projects[0].{Name:name,Created:created}' \
  --output table

# Verify bootstrap tags
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-foundation-dev \
  --query 'Stacks[0].Tags[?Key==`BootstrapExemption`]' \
  --output table
```

### Bootstrap Completion Checklist

- [ ] CloudFormation stack status: `CREATE_COMPLETE`
- [ ] CodeBuild project created: `aura-foundation-deploy-{env}`
- [ ] IAM role created: `aura-foundation-codebuild-role-{env}`
- [ ] S3 artifacts bucket created: `aura-foundation-artifacts-{account}-{env}`
- [ ] CloudWatch log group created: `/aws/codebuild/aura-foundation-deploy-{env}`
- [ ] `BootstrapExemption=true` tag applied to stack
- [ ] `BootstrapDate` and `BootstrapOperator` tags recorded

---

## CI/CD Cascade Architecture

After bootstrap, the CI/CD system operates in a hierarchical cascade where each layer can deploy subsequent layers:

### Deployment Hierarchy

```
+------------------------------------------------------------------+
|                    BOOTSTRAP (One-Time Manual)                    |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|               FOUNDATION CODEBUILD (Layer 1)                      |
|                                                                   |
|  Deployed by: Bootstrap (manual, one-time)                        |
|  Template: codebuild-foundation.yaml                              |
|  Can deploy:                                                      |
|    - Foundation infrastructure (VPC, IAM, WAF, VPC Endpoints)     |
|    - All other CodeBuild projects (Layers 2-8)                    |
|    - Updates to itself (after bootstrap)                          |
+------------------------------------------------------------------+
          |                    |                    |
          v                    v                    v
+------------------+  +------------------+  +------------------+
| DATA CODEBUILD   |  | COMPUTE CODEBUILD|  | APPLICATION CB   |
| (Layer 2)        |  | (Layer 3)        |  | (Layer 4)        |
|                  |  |                  |  |                  |
| Deploys:         |  | Deploys:         |  | Deploys:         |
| - S3             |  | - EKS            |  | - Bedrock        |
| - DynamoDB       |  | - ECR            |  | - IRSA           |
| - Neptune        |  |                  |  | - Network Svcs   |
| - OpenSearch     |  |                  |  |                  |
+------------------+  +------------------+  +------------------+
          |
          v
+------------------+  +------------------+  +------------------+
| OBSERVABILITY CB |  | SERVERLESS CB    |  | SANDBOX CB       |
| (Layer 5)        |  | (Layer 6)        |  | (Layer 7)        |
|                  |  |                  |  |                  |
| Deploys:         |  | Deploys:         |  | Deploys:         |
| - Secrets        |  | - Lambda         |  | - ECS Sandbox    |
| - Monitoring     |  | - Step Functions |  | - HITL Workflow  |
| - Cost Alerts    |  | - EventBridge    |  |                  |
+------------------+  +------------------+  +------------------+
                              |
                              v
                    +------------------+
                    | SECURITY CB      |
                    | (Layer 8)        |
                    |                  |
                    | Deploys:         |
                    | - AWS Config     |
                    | - GuardDuty      |
                    +------------------+
```

### Self-Update Capability

After bootstrap, the Foundation CodeBuild project can update itself:

```bash
# Foundation CodeBuild updating its own stack (after bootstrap)
aws codebuild start-build \
  --project-name aura-foundation-deploy-dev \
  --region us-east-1
```

The buildspec (`deploy/buildspecs/buildspec-foundation.yml`) includes logic to deploy the `aura-codebuild-foundation-{env}` stack, enabling the Foundation CodeBuild to manage its own updates through the standard CI/CD pipeline.

### Cascade Deployment Order

| Phase | CodeBuild Project | Deploys Templates |
|-------|-------------------|-------------------|
| 1 | `aura-foundation-deploy-{env}` | networking, iam, security, vpc-endpoints, kms, codebuild-* |
| 1.7 | `aura-network-services-deploy-{env}` | dnsmasq, ECS Fargate VPC-wide DNS |
| 1.9 | `aura-docker-deploy-{env}` | Docker image builds for ECR |
| 2 | `aura-data-deploy-{env}` | s3, dynamodb, neptune, opensearch |
| 3 | `aura-compute-deploy-{env}` | eks, ecr-* |
| 4 | `aura-application-deploy-{env}` | bedrock-infrastructure, irsa-*, frontend |
| 5 | `aura-observability-deploy-{env}` | secrets, monitoring, cost-alerts, realtime-monitoring |
| 6 | `aura-serverless-deploy-{env}` | dns-blocklist-lambda, threat-intel-scheduler |
| 6.7 | `aura-chat-assistant-deploy-{env}` | WebSocket API, Bedrock chat integration |
| 6.9 | `aura-incident-response-deploy-{env}` | Incident tracking, RCA workflows |
| 6 | `aura-runbook-agent-deploy-{env}` | Runbook automation agents |
| 7 | `aura-sandbox-deploy-{env}` | sandbox, hitl-workflow |
| 8 | `aura-security-deploy-{env}` | config-compliance, guardduty, drift-detection |

---

## Tagging Requirements

### Mandatory Bootstrap Tags

All bootstrap exemption resources **must** include the following tags:

| Tag Key | Required Value | Purpose |
|---------|----------------|---------|
| `BootstrapExemption` | `true` | Identifies resource as bootstrap exemption |
| `BootstrapDate` | `YYYY-MM-DD` | Date of bootstrap deployment |
| `BootstrapOperator` | Username/email | Person who performed bootstrap |
| `Project` | `aura` | Project identifier |
| `Environment` | `dev`/`qa`/`prod` | Environment identifier |
| `ManagedBy` | `Bootstrap` | Deployment method |

### Post-Bootstrap Tag Update

After the first CI/CD-managed update, the `ManagedBy` tag transitions:

| Stage | ManagedBy Value |
|-------|-----------------|
| Initial Bootstrap | `Bootstrap` |
| After First CI/CD Update | `CloudFormation` |

The `BootstrapExemption=true` tag remains for audit purposes, indicating the resource originally required bootstrap.

### Tag Verification Script

```bash
#!/bin/bash
# Verify bootstrap exemption tags on Foundation CodeBuild stack

STACK_NAME="aura-codebuild-foundation-dev"

echo "Verifying bootstrap exemption tags for $STACK_NAME..."

# Get all tags
TAGS=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Tags' \
  --output json)

# Check required tags
REQUIRED_TAGS=("BootstrapExemption" "BootstrapDate" "BootstrapOperator" "Project" "Environment" "ManagedBy")

for TAG in "${REQUIRED_TAGS[@]}"; do
  VALUE=$(echo $TAGS | jq -r ".[] | select(.Key==\"$TAG\") | .Value")
  if [ -n "$VALUE" ]; then
    echo "[PASS] $TAG = $VALUE"
  else
    echo "[FAIL] Missing required tag: $TAG"
  fi
done
```

---

## Audit and Compliance

### Compliance Mapping

| Compliance Framework | Relevant Control | Bootstrap Exemption Alignment |
|---------------------|------------------|-------------------------------|
| **SOX** | IT General Controls (ITGC) | Documented exception with approval trail |
| **CMMC Level 2** | CM.L2-3.4.5 (Configuration Management) | Change documented and reviewed |
| **NIST 800-53** | CM-3 (Configuration Change Control) | Emergency/initial provisioning documented |
| **AWS Well-Architected** | OPS 06 (Deploy Automation) | Initial manual deployment acknowledged |

### Audit Evidence

For compliance audits, the following evidence demonstrates proper bootstrap exemption management:

1. **This Document**: Defines policy, scope, and procedures
2. **CloudFormation Stack Tags**: `BootstrapExemption=true`, dates, operator
3. **CloudTrail Logs**: Record of initial `cloudformation:CreateStack` API call
4. **Git History**: Version control of `codebuild-foundation.yaml` template
5. **Subsequent CI/CD Logs**: CodeBuild execution history showing automated deployments

### Audit Query: Bootstrap Exemption Resources

```bash
# Find all CloudFormation stacks with BootstrapExemption tag
aws cloudformation describe-stacks \
  --query 'Stacks[?Tags[?Key==`BootstrapExemption` && Value==`true`]].{StackName:StackName,Status:StackStatus,Created:CreationTime}' \
  --output table
```

### Annual Review Requirements

Bootstrap exemptions must be reviewed annually to ensure:

- [ ] The bootstrap exemption is still required (cannot be eliminated)
- [ ] Documentation is accurate and current
- [ ] Tags are properly applied and maintained
- [ ] No additional resources have been inappropriately bootstrapped
- [ ] CI/CD cascade is functioning correctly

---

## Frequently Asked Questions

### Q: Why can't we use a separate "bootstrap" CodeBuild project to deploy Foundation?

**A:** This would simply move the chicken-and-egg problem to that bootstrap project. The bootstrap project itself would need to be manually deployed, making it the bootstrap exemption resource instead.

### Q: Can Foundation CodeBuild update itself after bootstrap?

**A:** Yes. After the initial bootstrap, Foundation CodeBuild can deploy updates to its own stack through the normal CI/CD pipeline. The buildspec includes the `codebuild-foundation.yaml` template in its deployment targets.

### Q: What happens if someone manually deploys a non-bootstrap resource?

**A:** Manual deployments outside of bootstrap exemptions violate the CI/CD Single Source of Truth policy. The resource should be deleted and redeployed via CodeBuild to restore audit trail integrity. See `docs/deployment/CICD_SETUP_GUIDE.md` for recovery procedures.

### Q: Do we need a bootstrap exemption for each environment?

**A:** Yes. Each environment (dev, qa, prod) requires its own Foundation CodeBuild stack, and each requires a one-time bootstrap deployment.

### Q: How do we handle GovCloud migration?

**A:** The bootstrap procedure is identical in GovCloud. Execute the same commands targeting the GovCloud region and account. The templates support GovCloud partition detection via `${AWS::Partition}`.

---

## Related Documentation

| Document | Path | Description |
|----------|------|-------------|
| CI/CD Setup Guide | `docs/deployment/CICD_SETUP_GUIDE.md` | Complete CI/CD pipeline documentation |
| Deployment Methods | `docs/DEPLOYMENT_METHODS.md` | All deployment methods and commands |
| Naming and Tagging | `docs/AWS_NAMING_AND_TAGGING_STANDARDS.md` | Resource naming and tagging standards |
| Foundation CodeBuild | `deploy/cloudformation/codebuild-foundation.yaml` | Bootstrap exemption template |
| Foundation Buildspec | `deploy/buildspecs/buildspec-foundation.yml` | CI/CD build specification |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.1 | 2025-12-14 | Platform Team | Added 4 missing CodeBuild projects (network-services, docker, chat-assistant, incident-response); updated cascade deployment order with sub-layers |
| 1.0 | 2025-12-11 | Platform Team | Initial document creation |

---

## Approval

This document defines the official Bootstrap Exemption policy for Project Aura. All bootstrap deployments must comply with this policy.

| Role | Name | Date |
|------|------|------|
| Platform Lead | ___________________ | __________ |
| Security Lead | ___________________ | __________ |
| Compliance Officer | ___________________ | __________ |

---

**Document Classification:** Public
**Review Cycle:** Annual
**Next Review Date:** 2026-12-11

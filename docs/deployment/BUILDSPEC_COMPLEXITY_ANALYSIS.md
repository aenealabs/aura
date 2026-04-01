# Buildspec Complexity Analysis

Analysis of 11 CloudFormation templates without deployment pipelines and assessment of existing buildspec complexity to determine the best deployment strategy.

**Analysis Date:** 2025-12-09
**Prepared For:** Project Aura CI/CD Architecture

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Buildspec Complexity Assessment](#1-current-buildspec-complexity-assessment)
3. [Template Analysis](#2-template-analysis)
4. [Decision Matrix](#3-decision-matrix)
5. [New CodeBuild Projects Needed](#4-new-codebuild-projects-needed)
6. [Buildspec Timeout Risk Assessment](#5-buildspec-timeout-risk-assessment)
7. [Updated Layer Structure](#6-updated-layer-structure)
8. [Implementation Plan](#7-implementation-plan)

---

## Executive Summary

### Key Findings

- **11 templates** exist without deployment pipelines
- **3 existing buildspecs** have room for additional stacks
- **3 new CodeBuild projects** recommended
- **0 buildspecs** at risk of timeout (all under 45-minute safe limit)

### Recommendations Summary

| Action | Templates | Rationale |
|--------|-----------|-----------|
| Add to Existing | 5 templates | Fit within current layer structure and time budget |
| Create New Buildspec | 6 templates | Require dedicated pipelines or special handling |

---

## 1. Current Buildspec Complexity Assessment

### Existing Buildspecs Overview

| Buildspec | Stacks Deployed | Est. Deploy Time | Capacity | Timeout Risk |
|-----------|-----------------|------------------|----------|--------------|
| buildspec-foundation.yml | 5 | 15-20 min | MEDIUM (room for 1-2 more) | LOW |
| buildspec-data.yml | 4 | 25-35 min | LOW (Neptune/OpenSearch slow) | LOW |
| buildspec-compute.yml | 1 | 15-20 min | HIGH (room for 3-4 more) | LOW |
| buildspec-application.yml | 5 | 20-30 min | MEDIUM (includes Docker build) | LOW |
| buildspec-observability.yml | 4 | 10-15 min | HIGH (room for 3-4 more) | LOW |
| buildspec-serverless.yml | 3 | 10-15 min | HIGH (room for 3-4 more) | LOW |
| buildspec-sandbox.yml | 2 | 15-20 min | MEDIUM (includes Docker build) | LOW |
| buildspec-security.yml | 2 | 5-10 min | HIGH (room for 4-5 more) | LOW |
| buildspec-coordinator.yml | N/A | Variable | SPECIAL (CI/CD deployment coordinator) | LOW |
| buildspec-service-frontend.yml | 1 | 10-15 min | MEDIUM (includes Docker build) | LOW |
| buildspec-chat-assistant.yml | 1 | 5-10 min | HIGH (room for 2-3 more) | LOW |

### Detailed Buildspec Analysis

#### buildspec-foundation.yml (Layer 1)
- **Stacks:** networking, security, iam, vpc-endpoints, ecr-base-images
- **Time:** 15-20 min (VPC endpoints take 2-5 min each)
- **Complexity:** HIGH (security group state machine, ENI dependency checks)
- **Available Capacity:** Can add 1-2 lightweight stacks

#### buildspec-data.yml (Layer 2)
- **Stacks:** dynamodb, s3, neptune-simplified, opensearch
- **Time:** 25-35 min (OpenSearch alone is ~15 min)
- **Complexity:** MEDIUM (sequential deploys with cleanup)
- **Available Capacity:** LIMITED (already near safe threshold)

#### buildspec-compute.yml (Layer 3)
- **Stacks:** eks
- **Time:** 15-20 min (EKS cluster creation)
- **Complexity:** LOW (single stack with kubectl config)
- **Available Capacity:** HIGH - can add 3-4 IRSA-related stacks

#### buildspec-application.yml (Layer 4)
- **Stacks:** ecr-dnsmasq, ecr-api, aura-bedrock-infrastructure, irsa-aura-api (+ K8s deploys)
- **Time:** 20-30 min (includes Docker builds and K8s deploys)
- **Complexity:** HIGH (6 phases with ECR, Docker, K8s operations)
- **Available Capacity:** MEDIUM - can add 1-2 more stacks

#### buildspec-observability.yml (Layer 5)
- **Stacks:** secrets, monitoring, aura-cost-alerts, realtime-monitoring
- **Time:** 10-15 min (fast deploying stacks)
- **Complexity:** MEDIUM (dependency on Neptune/OpenSearch endpoints)
- **Available Capacity:** HIGH - can add 3-4 more stacks

#### buildspec-serverless.yml (Layer 6)
- **Stacks:** threat-intel-scheduler, hitl-scheduler, hitl-callback
- **Time:** 10-15 min (Lambda packaging + deploy)
- **Complexity:** MEDIUM (includes Lambda packaging and S3 upload)
- **Available Capacity:** HIGH - can add 3-4 more stacks

#### buildspec-sandbox.yml (Layer 7)
- **Stacks:** sandbox, hitl-workflow (+ Docker build)
- **Time:** 15-20 min (includes Docker build and ECS operations)
- **Complexity:** MEDIUM (Docker build, Step Functions)
- **Available Capacity:** MEDIUM - can add 1-2 more stacks

#### buildspec-security.yml (Layer 8)
- **Stacks:** config-compliance, guardduty
- **Time:** 5-10 min (fast deploying stacks)
- **Complexity:** LOW (straightforward deploys)
- **Available Capacity:** HIGH - can add 4-5 more stacks

---

## 2. Template Analysis

### Template Details

#### 1. alb-controller.yaml
- **Description:** AWS Load Balancer Controller IAM Resources
- **Layer:** 3 (Compute)
- **Resources:** IAM Policy (ALBControllerPolicy), IAM Role (ALBControllerRole - IRSA)
- **Dependencies:** EKS OIDC Provider, VPC
- **Est. Deploy Time:** 1-2 min
- **GovCloud:** Compatible

#### 2. cognito.yaml
- **Description:** User Authentication (User Pool, App Client, Groups)
- **Layer:** 4 (Application)
- **Resources:** UserPool, UserPoolDomain, UserPoolClient, 4 User Groups, 3 SSM Parameters
- **Dependencies:** None (standalone authentication)
- **Est. Deploy Time:** 3-5 min
- **GovCloud:** Compatible (Cognito available in GovCloud)

#### 3. bedrock-guardrails.yaml
- **Description:** Bedrock Guardrails for Agent Output Safety
- **Layer:** 4 (Application)
- **Resources:** Bedrock Guardrail, Guardrail Version, 3 SSM Parameters, CloudWatch Alarm
- **Dependencies:** None (standalone safety controls)
- **Est. Deploy Time:** 2-3 min
- **GovCloud:** Compatible (Bedrock available in us-gov-west-1)

#### 4. disaster-recovery.yaml
- **Description:** AWS Backup Infrastructure (Vault, Plans, Selections)
- **Layer:** 5 (Observability)
- **Resources:** KMS Key, Backup Vault, SNS Topic, IAM Role, 2 Backup Plans, 3 Backup Selections, 2 CloudWatch Alarms, EventBridge Rule
- **Dependencies:** Neptune cluster, DynamoDB tables (for backup selections)
- **Est. Deploy Time:** 5-8 min
- **GovCloud:** Compatible

#### 5. a2a-infrastructure.yaml
- **Description:** Agent-to-Agent Protocol Infrastructure (Conditionally created)
- **Layer:** 6 (Serverless)
- **Resources:** 2 DynamoDB Tables, 3 SQS Queues, EventBridge Event Bus + Rules, SNS Topic, CloudWatch Alarms, SSM Parameters
- **Dependencies:** None (uses conditional creation with EnableA2A parameter)
- **Est. Deploy Time:** 5-7 min (when enabled)
- **GovCloud:** Compatible

#### 6. incident-response.yaml
- **Description:** Incident Response Infrastructure
- **Layer:** 6 (Serverless)
- **Resources:** KMS Key, 2 DynamoDB Tables, EventBridge Event Bus + Rule, Lambda Function, SNS Topic, CloudWatch Log Groups
- **Dependencies:** None (standalone incident tracking)
- **Est. Deploy Time:** 5-7 min
- **GovCloud:** Compatible

#### 7. incident-investigation-workflow.yaml
- **Description:** Step Functions Workflow for RCA Investigations
- **Layer:** 6 (Serverless)
- **Resources:** 4 IAM Roles, ECS Task Definition, Step Functions State Machine, 2 EventBridge Rules, CloudWatch Log Groups
- **Dependencies:** incident-response stack (KMS key import), VPC, ECS Cluster, security.yaml (ECSWorkloadSecurityGroup)
- **Est. Deploy Time:** 5-8 min
- **GovCloud:** Compatible (ECS Fargate available)

#### 8. network-services.yaml
- **Description:** VPC-wide DNS via dnsmasq on ECS Fargate
- **Layer:** 1 (Foundation)
- **Resources:** ECS Cluster (optional), Security Group, 2 IAM Roles, CloudWatch Log Group, ECS Task Definition, NLB + Target Group + Listener, ECS Service, 2 CloudWatch Alarms
- **Dependencies:** VPC, Private Subnets
- **Est. Deploy Time:** 8-12 min (NLB + ECS service startup)
- **GovCloud:** Compatible (ECS Fargate + NLB)
- **Note:** Alternative to Kubernetes DaemonSet dnsmasq

#### 9. otel-collector.yaml
- **Description:** OpenTelemetry Collector IAM Resources
- **Layer:** 5 (Observability)
- **Resources:** IAM Policy, IAM Role (IRSA)
- **Dependencies:** EKS OIDC Provider
- **Est. Deploy Time:** 1-2 min
- **GovCloud:** Compatible

#### 10. red-team.yaml
- **Description:** Red-Team/Adversarial Testing Infrastructure (Conditionally created)
- **Layer:** 8 (Security)
- **Resources:** 2 S3 Buckets, KMS Key, 2 DynamoDB Tables, 2 IAM Roles, CloudWatch Log Group, ECS Task Definition, SNS Topic, EventBridge Rule, SSM Parameters
- **Dependencies:** VPC (uses conditional creation with EnableRedTeam parameter)
- **Est. Deploy Time:** 5-8 min (when enabled)
- **GovCloud:** Compatible

#### 11. acm-certificate.yaml
- **Description:** ACM Certificate for HTTPS (aenealabs.com)
- **Layer:** 3 (Compute)
- **Resources:** ACM Certificate with DNS validation
- **Dependencies:** Route 53 Hosted Zone (for DNS validation)
- **Est. Deploy Time:** 2-5 min (DNS validation auto-completes)
- **GovCloud:** Compatible
- **Special:** Must be deployed BEFORE ALB Controller if using TLS termination

---

## 3. Decision Matrix

| Template | Resources | Est. Time | Dependencies | Layer | Recommendation | Rationale |
|----------|-----------|-----------|--------------|-------|----------------|-----------|
| alb-controller.yaml | IAM Policy + IRSA Role | 1-2 min | EKS OIDC | 3 | **Add to compute** | IRSA pattern, fits compute layer |
| cognito.yaml | UserPool + Domain + Client + Groups | 3-5 min | None | 4 | **Add to application** | Authentication fits application |
| bedrock-guardrails.yaml | Guardrail + Version + SSM | 2-3 min | None | 4 | **Add to application** | AI safety fits with Bedrock infra |
| disaster-recovery.yaml | Backup Vault + Plans + Selections | 5-8 min | Neptune, DynamoDB | 5 | **Add to observability** | DR monitoring fits observability |
| a2a-infrastructure.yaml | DynamoDB + SQS + EventBridge | 5-7 min | None | 6 | **Add to serverless** | A2A protocol fits serverless |
| incident-response.yaml | DynamoDB + EventBridge + Lambda | 5-7 min | None | 6 | **Create new buildspec** | Complex workflow, new capability |
| incident-investigation-workflow.yaml | Step Functions + ECS + IAM | 5-8 min | incident-response, VPC | 6 | **Create new buildspec** | Depends on incident-response |
| network-services.yaml | ECS + NLB + Security | 8-12 min | VPC, Subnets | 1 | **Create new buildspec** | Long deploy, VPC-wide service |
| otel-collector.yaml | IAM Policy + IRSA Role | 1-2 min | EKS OIDC | 5 | **Add to observability** | Telemetry fits observability |
| red-team.yaml | S3 + DynamoDB + ECS + IAM | 5-8 min | VPC | 8 | **Add to security** | Adversarial testing is security |
| acm-certificate.yaml | ACM Certificate | 2-5 min | Route 53 | 3 | **Add to compute** | TLS for ALB, fits compute layer |

---

## 4. New CodeBuild Projects Needed

### 4.1 buildspec-incident-response.yml (NEW)

**Project Name:** `aura-incident-response-deploy-{env}`

**Templates Deployed:**
1. `incident-response.yaml` - Base incident tracking infrastructure
2. `incident-investigation-workflow.yaml` - Step Functions RCA workflow

**Layer Assignment:** Layer 6.5 (between Serverless and Sandbox)

**Rationale:**
- `incident-investigation-workflow.yaml` has an explicit dependency on `incident-response.yaml` (imports KMS key ARN)
- Both templates work together for incident management
- Combined deploy time: 10-15 min (within safe limits)
- Requires VPC and ECS cluster from earlier layers

**Dependencies:**
- Layer 1: VPC, security.yaml (ECSWorkloadSecurityGroup)
- Layer 3: ECS Cluster (or creates sandbox ECS cluster)
- Layer 5: Monitoring stack (optional, for SNS topic)

**Bootstrap Requirement:**
- Create CodeBuild project: `codebuild-incident-response.yaml`
- IAM permissions: DynamoDB, Lambda, Step Functions, ECS, EventBridge, SNS, KMS

### 4.2 buildspec-network-services.yml (NEW)

**Project Name:** `aura-network-services-deploy-{env}`

**Templates Deployed:**
1. `network-services.yaml` - VPC-wide dnsmasq on ECS Fargate

**Layer Assignment:** Layer 1.5 (after Foundation, before Data)

**Rationale:**
- Long deployment time (8-12 min) due to NLB + ECS service
- VPC-wide service that other stacks may depend on
- Creates its own ECS cluster (separate from sandbox/application)
- Should be deployed early but after VPC exists

**Dependencies:**
- Layer 1: VPC, Private Subnets, ECR (for dnsmasq image)

**Bootstrap Requirement:**
- Create CodeBuild project: `codebuild-network-services.yaml`
- IAM permissions: ECS, EC2, ELB, CloudWatch, IAM
- Note: Alternative to Kubernetes DaemonSet dnsmasq (use one or the other)

### 4.3 No Additional Buildspecs Required

The remaining 8 templates can be added to existing buildspecs:

| Template | Target Buildspec | Reason |
|----------|------------------|--------|
| alb-controller.yaml | buildspec-compute.yml | IRSA role, EKS dependency |
| acm-certificate.yaml | buildspec-compute.yml | Required before ALB |
| cognito.yaml | buildspec-application.yml | User authentication |
| bedrock-guardrails.yaml | buildspec-application.yml | AI safety controls |
| disaster-recovery.yaml | buildspec-observability.yml | DR monitoring |
| otel-collector.yaml | buildspec-observability.yml | Telemetry IRSA |
| a2a-infrastructure.yaml | buildspec-serverless.yml | A2A protocol |
| red-team.yaml | buildspec-security.yml | Adversarial testing |

---

## 5. Buildspec Timeout Risk Assessment

**CodeBuild Timeout Limit:** 60 minutes (hard limit)
**Safe Threshold:** 45 minutes (15-min buffer for retries/slowness)

### Current Buildspecs After Template Additions

| Buildspec | Current Time | Added Templates | New Est. Time | Risk Level |
|-----------|--------------|-----------------|---------------|------------|
| buildspec-foundation.yml | 15-20 min | (none) | 15-20 min | LOW |
| buildspec-data.yml | 25-35 min | (none) | 25-35 min | LOW |
| buildspec-compute.yml | 15-20 min | +alb-controller, +acm-certificate | 18-27 min | LOW |
| buildspec-application.yml | 20-30 min | +cognito, +bedrock-guardrails | 25-38 min | LOW |
| buildspec-observability.yml | 10-15 min | +disaster-recovery, +otel-collector | 16-25 min | LOW |
| buildspec-serverless.yml | 10-15 min | +a2a-infrastructure | 15-22 min | LOW |
| buildspec-sandbox.yml | 15-20 min | (none) | 15-20 min | LOW |
| buildspec-security.yml | 5-10 min | +red-team | 10-18 min | LOW |
| buildspec-incident-response.yml (NEW) | N/A | +incident-response, +incident-investigation | 10-15 min | LOW |
| buildspec-network-services.yml (NEW) | N/A | +network-services | 8-12 min | LOW |

### Risk Summary

- **HIGH RISK (>45 min):** 0 buildspecs
- **MEDIUM RISK (35-45 min):** 0 buildspecs
- **LOW RISK (<35 min):** All buildspecs

**Conclusion:** No timeout concerns with proposed template additions.

---

## 6. Updated Layer Structure

### Current vs. Proposed Layer Structure

```
CURRENT LAYERS                     PROPOSED LAYERS
================                   ================
Layer 1: Foundation                Layer 1: Foundation
  - networking                       - networking
  - security                         - security
  - iam                              - iam
  - vpc-endpoints                    - vpc-endpoints
  - ecr-base-images                  - ecr-base-images

                                   Layer 1.5: Network Services (NEW)
                                     - network-services

Layer 2: Data                      Layer 2: Data
  - neptune-simplified               - neptune-simplified
  - opensearch                       - opensearch
  - dynamodb                         - dynamodb
  - s3                               - s3

Layer 3: Compute                   Layer 3: Compute
  - eks                              - eks
                                     - acm-certificate (NEW)
                                     - alb-controller (NEW)

Layer 4: Application               Layer 4: Application
  - ecr-dnsmasq                      - ecr-dnsmasq
  - ecr-api                          - ecr-api
  - aura-bedrock-infrastructure      - aura-bedrock-infrastructure
  - irsa-aura-api                    - irsa-aura-api
                                     - cognito (NEW)
                                     - bedrock-guardrails (NEW)

Layer 5: Observability             Layer 5: Observability
  - secrets                          - secrets
  - monitoring                       - monitoring
  - aura-cost-alerts                 - aura-cost-alerts
  - realtime-monitoring              - realtime-monitoring
                                     - disaster-recovery (NEW)
                                     - otel-collector (NEW)

Layer 6: Serverless                Layer 6: Serverless
  - threat-intel-scheduler           - threat-intel-scheduler
  - hitl-scheduler                   - hitl-scheduler
  - hitl-callback                    - hitl-callback
                                     - a2a-infrastructure (NEW)

                                   Layer 6.5: Incident Response (NEW)
                                     - incident-response
                                     - incident-investigation-workflow

Layer 7: Sandbox                   Layer 7: Sandbox
  - sandbox                          - sandbox
  - hitl-workflow                    - hitl-workflow

Layer 8: Security                  Layer 8: Security
  - config-compliance                - config-compliance
  - guardduty                        - guardduty
                                     - red-team (NEW)
```

### Dependency Diagram

```
Layer 1 (Foundation)
    |
    v
Layer 1.5 (Network Services) [OPTIONAL - VPC-wide DNS]
    |
    v
Layer 2 (Data)
    |
    v
Layer 3 (Compute)
    |
    +---> acm-certificate [before ALB]
    +---> alb-controller [after EKS OIDC]
    |
    v
Layer 4 (Application)
    |
    +---> cognito [standalone auth]
    +---> bedrock-guardrails [after bedrock-infrastructure]
    |
    v
Layer 5 (Observability)
    |
    +---> disaster-recovery [after Neptune, DynamoDB]
    +---> otel-collector [after EKS OIDC]
    |
    v
Layer 6 (Serverless)
    |
    +---> a2a-infrastructure [conditional, independent]
    |
    v
Layer 6.5 (Incident Response) [NEW]
    |
    +---> incident-response [first]
    +---> incident-investigation-workflow [depends on incident-response]
    |
    v
Layer 7 (Sandbox)
    |
    v
Layer 8 (Security)
    |
    +---> red-team [conditional, requires VPC]
```

---

## 7. Implementation Plan

### Phase 1: Create New CodeBuild Projects (Day 1)

1. **Create `codebuild-incident-response.yaml`**
   ```bash
   # Location: deploy/cloudformation/codebuild-incident-response.yaml
   # Creates: aura-incident-response-deploy-{env}
   # IAM: DynamoDB, Lambda, Step Functions, ECS, EventBridge, SNS, KMS, Logs
   ```

2. **Create `codebuild-network-services.yaml`**
   ```bash
   # Location: deploy/cloudformation/codebuild-network-services.yaml
   # Creates: aura-network-services-deploy-{env}
   # IAM: ECS, EC2, ELB, CloudWatch, IAM
   ```

3. **Deploy CodeBuild projects to AWS**
   ```bash
   aws cloudformation deploy --stack-name aura-codebuild-incident-response-dev \
     --template-file deploy/cloudformation/codebuild-incident-response.yaml \
     --capabilities CAPABILITY_NAMED_IAM

   aws cloudformation deploy --stack-name aura-codebuild-network-services-dev \
     --template-file deploy/cloudformation/codebuild-network-services.yaml \
     --capabilities CAPABILITY_NAMED_IAM
   ```

### Phase 2: Create New Buildspecs (Day 1)

1. **Create `buildspec-incident-response.yml`**
   ```yaml
   # Location: deploy/buildspecs/buildspec-incident-response.yml
   # Deploys: incident-response.yaml, incident-investigation-workflow.yaml
   ```

2. **Create `buildspec-network-services.yml`**
   ```yaml
   # Location: deploy/buildspecs/buildspec-network-services.yml
   # Deploys: network-services.yaml
   ```

### Phase 3: Update Existing Buildspecs (Day 2)

| Buildspec | Templates to Add | Order in Buildspec |
|-----------|------------------|-------------------|
| buildspec-compute.yml | acm-certificate.yaml, alb-controller.yaml | After EKS (requires OIDC) |
| buildspec-application.yml | cognito.yaml, bedrock-guardrails.yaml | After bedrock-infrastructure |
| buildspec-observability.yml | disaster-recovery.yaml, otel-collector.yaml | After monitoring |
| buildspec-serverless.yml | a2a-infrastructure.yaml | After threat-intel |
| buildspec-security.yml | red-team.yaml | After guardduty |

### Phase 4: Testing (Day 3)

1. **Test new buildspecs independently**
   ```bash
   aws codebuild start-build --project-name aura-incident-response-deploy-dev
   aws codebuild start-build --project-name aura-network-services-deploy-dev
   ```

2. **Test updated buildspecs**
   ```bash
   aws codebuild start-build --project-name aura-compute-deploy-dev
   aws codebuild start-build --project-name aura-application-deploy-dev
   aws codebuild start-build --project-name aura-observability-deploy-dev
   aws codebuild start-build --project-name aura-serverless-deploy-dev
   aws codebuild start-build --project-name aura-security-deploy-dev
   ```

3. **Run full orchestrator test**
   ```bash
   aws codebuild start-build --project-name aura-orchestrator-deploy-dev
   ```

### Phase 5: Documentation Updates (Day 3)

1. Update `CLAUDE.md` with new layer structure
2. Update `DEPLOYMENT_GUIDE.md` with new buildspecs
3. Update `PROJECT_STATUS.md` with deployment status

---

## Appendix: Template Reference

### Templates by Layer (Final)

| Layer | Template | Deployed By | Status |
|-------|----------|-------------|--------|
| 1 | networking.yaml | buildspec-foundation.yml | Deployed |
| 1 | security.yaml | buildspec-foundation.yml | Deployed |
| 1 | iam.yaml | buildspec-foundation.yml | Deployed |
| 1 | vpc-endpoints.yaml | buildspec-foundation.yml | Deployed |
| 1 | ecr-base-images.yaml | buildspec-foundation.yml | Deployed |
| 1.5 | network-services.yaml | buildspec-network-services.yml (NEW) | Not Deployed |
| 2 | neptune-simplified.yaml | buildspec-data.yml | Deployed |
| 2 | opensearch.yaml | buildspec-data.yml | Deployed |
| 2 | dynamodb.yaml | buildspec-data.yml | Deployed |
| 2 | s3.yaml | buildspec-data.yml | Deployed |
| 3 | eks.yaml | buildspec-compute.yml | Deployed |
| 3 | acm-certificate.yaml | buildspec-compute.yml | Not Deployed |
| 3 | alb-controller.yaml | buildspec-compute.yml | Not Deployed |
| 4 | ecr-dnsmasq.yaml | buildspec-application.yml | Deployed |
| 4 | ecr-api.yaml | buildspec-application.yml | Deployed |
| 4 | aura-bedrock-infrastructure.yaml | buildspec-application.yml | Deployed |
| 4 | irsa-aura-api.yaml | buildspec-application.yml | Deployed |
| 4 | cognito.yaml | buildspec-application.yml | Not Deployed |
| 4 | bedrock-guardrails.yaml | buildspec-application.yml | Not Deployed |
| 5 | secrets.yaml | buildspec-observability.yml | Deployed |
| 5 | monitoring.yaml | buildspec-observability.yml | Deployed |
| 5 | aura-cost-alerts.yaml | buildspec-observability.yml | Deployed |
| 5 | realtime-monitoring.yaml | buildspec-observability.yml | Deployed |
| 5 | disaster-recovery.yaml | buildspec-observability.yml | Not Deployed |
| 5 | otel-collector.yaml | buildspec-observability.yml | Not Deployed |
| 6 | threat-intel-scheduler.yaml | buildspec-serverless.yml | Deployed |
| 6 | hitl-scheduler.yaml | buildspec-serverless.yml | Deployed |
| 6 | hitl-callback.yaml | buildspec-serverless.yml | Deployed |
| 6 | a2a-infrastructure.yaml | buildspec-serverless.yml | Not Deployed |
| 6.5 | incident-response.yaml | buildspec-incident-response.yml (NEW) | Not Deployed |
| 6.5 | incident-investigation-workflow.yaml | buildspec-incident-response.yml (NEW) | Not Deployed |
| 7 | sandbox.yaml | buildspec-sandbox.yml | Deployed |
| 7 | hitl-workflow.yaml | buildspec-sandbox.yml | Deployed |
| 8 | config-compliance.yaml | buildspec-security.yml | Deployed |
| 8 | guardduty.yaml | buildspec-security.yml | Deployed |
| 8 | red-team.yaml | buildspec-security.yml | Not Deployed |

### Templates Summary

- **Total Templates:** 36
- **Deployed:** 25 (via existing buildspecs)
- **Not Deployed:** 11 (addressed in this analysis)
- **New Buildspecs Required:** 2

# ADR-039: Self-Service Test Environment Provisioning

**Status:** Deployed
**Date:** 2025-12-15
**Implementation Date:** 2025-12-15
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-005 (HITL Sandbox Architecture), ADR-032 (Configurable Autonomy Framework), ADR-017 (Dynamic Sandbox Resource Allocation)

---

## Executive Summary

This ADR documents the decision to implement a self-service test environment provisioning capability that enables internal teams to spin up AWS test environments directly from the Aura platform for rapid prototyping and proof-of-concept testing.

**Key Outcomes:**
- Self-service environment provisioning via Aura Platform UI
- Hybrid approach: EKS namespaces (quick tests) + AWS Service Catalog (full-stack)
- Integration with existing HITL and Autonomy Policy frameworks
- Cost controls with auto-cleanup and per-user quotas
- Full compliance with CMMC, SOX, and NIST requirements

---

## Context

### Current State

Aura has a mature Layer 7 Sandbox infrastructure designed for isolated patch validation environments. However, this capability is tightly coupled to the autonomous patching workflow and not exposed for general-purpose test environment provisioning.

Internal teams currently must:
1. Request AWS resources through manual ticketing processes
2. Wait for infrastructure team to provision environments
3. Manually track and clean up resources after testing
4. Navigate complex IAM permission requests

### Problem Statement

1. **Development Velocity:** Manual environment provisioning creates 2-5 day delays for prototype testing
2. **Resource Waste:** Forgotten test environments accumulate costs without cleanup governance
3. **Compliance Risk:** Ad-hoc environment creation bypasses audit trails and security controls
4. **Skill Barriers:** Not all teams have CloudFormation/Terraform expertise to self-provision

### Requirements

1. **Self-Service:** Teams must provision environments without infrastructure team intervention
2. **Rapid Provisioning:** Environment available within 5 minutes of request
3. **Compliance:** All provisioning flows through existing HITL/Autonomy Policy framework
4. **Cost Control:** Auto-cleanup, TTL enforcement, per-user quotas, budget alerts
5. **Security Isolation:** Test environments cannot access production data or systems
6. **Template Library:** Pre-approved environment templates for common use cases
7. **Audit Trail:** Full logging of provisioning events for compliance

---

## Decision

**Implement a Hybrid Self-Service Test Environment Framework with the following components:**

### 1. Environment Types

| Type | Mechanism | Use Case | TTL | Approval |
|------|-----------|----------|-----|----------|
| `quick` | EKS Namespace | API prototyping, unit tests | 4 hours | Auto-approved |
| `standard` | Service Catalog | Full-stack with data layer | 24 hours | Auto-approved |
| `extended` | Service Catalog | Multi-day testing | 7 days | HITL required |
| `compliance` | Dedicated VPC | Security/penetration testing | 24 hours | HITL required |

### 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SELF-SERVICE TEST ENVIRONMENT ARCHITECTURE                │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │   Aura Platform UI               │
                    │   /environments/new              │
                    └──────────────┬───────────────────┘
                                   │ Request Environment
                                   ▼
                    ┌──────────────────────────────────┐
                    │   API Gateway + Lambda           │
                    │   environment-provisioner        │
                    └──────────────┬───────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ Autonomy Policy │  │  HITL Workflow  │  │  Budget Check   │
    │ Service         │  │  (if required)  │  │  (AWS Budgets)  │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │ Approved
                                  ▼
              ┌───────────────────┴───────────────────┐
              │                                       │
              ▼                                       ▼
    ┌─────────────────┐                    ┌─────────────────┐
    │ EKS Controller  │                    │ Service Catalog │
    │ (Quick Tests)   │                    │ (Full-Stack)    │
    └────────┬────────┘                    └────────┬────────┘
             │                                       │
             ▼                                       ▼
    ┌─────────────────┐                    ┌─────────────────┐
    │ Namespace +     │                    │ CloudFormation  │
    │ ResourceQuota   │                    │ Stack           │
    └────────┬────────┘                    └────────┬────────┘
             │                                       │
             └───────────────────┬───────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Test Environment       │
                    │   {type}-{user}-{uuid}   │
                    │   .test.aura.local       │
                    │   TTL: Auto-enforced     │
                    └──────────────────────────┘
```

### 3. Template Library (Service Catalog Products)

| Product | Resources Included | Est. Cost/Day |
|---------|-------------------|---------------|
| `python-fastapi` | ECS Task (1 vCPU, 2GB), S3 bucket | $0.50 |
| `react-frontend` | ECS Task (0.5 vCPU, 1GB), CloudFront | $0.30 |
| `full-stack` | ECS Tasks (API + UI), DynamoDB, S3 | $1.20 |
| `data-pipeline` | Step Functions, Lambda, S3, DynamoDB | $0.80 |
| `ml-experiment` | SageMaker Notebook, S3 | $2.50 |

### 4. Cost Governance

| Control | Implementation | Limit |
|---------|---------------|-------|
| Per-user concurrent limit | DynamoDB counter | 3 environments |
| Monthly budget | AWS Budgets | $500/month |
| Auto-cleanup | EventBridge scheduled rule | TTL expiry |
| Idle detection | CloudWatch metrics | 2 hours no activity |
| Fargate Spot | Cost optimization | 60-70% savings |

### 5. Security Controls

| Requirement | Control | Implementation |
|-------------|---------|----------------|
| Network isolation | Security Groups | No ingress from prod subnets |
| Data isolation | IAM Deny Policies | No access to prod DynamoDB/Neptune/S3 |
| Credential scoping | STS Session Policy | Max 4 hour session, limited permissions |
| Audit logging | CloudTrail + DynamoDB | All provisioning events logged |
| Secrets isolation | Secrets Manager namespace | `/aura/{env}/test-envs/*` |

### 6. Integration with Existing Services

| Existing Service | Integration |
|------------------|-------------|
| AutonomyPolicyService | Add `environment_provision` operation type |
| HITL Step Functions | Reuse approval workflow for extended/compliance types |
| dnsmasq (Layer 1) | Auto-register `{env}.test.aura.local` DNS entries |
| Sandbox Security Groups | Reuse egress-only network patterns |
| Cost Alerts (Layer 5) | Extend for test environment budget tracking |
| CloudWatch Dashboards | Add test environment metrics panel |

---

## Alternatives Considered

### Alternative 1: Extend Existing Sandbox Infrastructure Only (Rejected)

Repurpose the Layer 7 Sandbox for general test environments.

**Rejected because:**
- Sandbox is optimized for ephemeral patch testing (minutes, not hours/days)
- No template library or Service Catalog integration
- Missing per-user quotas and governance
- Would require significant refactoring of tightly-coupled code

### Alternative 2: Terraform Cloud Workspaces (Rejected)

Use HashiCorp Terraform Cloud for self-service provisioning.

**Rejected because:**
- Introduces new tool outside existing CloudFormation ecosystem
- Additional licensing cost
- Team must learn Terraform
- Not aligned with GovCloud strategy (CloudFormation-first)

### Alternative 3: AWS Control Tower Account Factory (Rejected)

Provision separate AWS accounts per test environment.

**Rejected because:**
- Over-engineered for rapid prototyping use case
- Account provisioning takes 15-30 minutes
- Higher blast radius per environment
- Complex cleanup and cost allocation

### Alternative 4: EKS Namespaces Only (Considered, Partially Adopted)

Use only EKS namespace isolation for all test environments.

**Partially adopted because:**
- Excellent for quick tests (< 4 hours)
- Lower cost and faster provisioning
- Limited for full-stack environments needing DynamoDB, Step Functions, etc.
- Hybrid approach captures benefits for appropriate use cases

---

## Consequences

### Positive

1. **Developer Velocity:** 2-5 day provisioning reduced to < 5 minutes
2. **Cost Reduction:** Auto-cleanup prevents orphaned resource accumulation
3. **Compliance:** All provisioning audited through existing HITL framework
4. **Self-Service:** Teams empowered without infrastructure ticket queues
5. **Standardization:** Pre-approved templates ensure best practices
6. **Reuse:** 70%+ of implementation leverages existing Layer 7 infrastructure

### Negative

1. **Initial Complexity:** Service Catalog setup requires careful IAM design
2. **Template Maintenance:** Product templates need versioning and updates
3. **Training:** Teams need onboarding on new self-service capabilities
4. **Cost Visibility:** Requires tagging discipline for accurate attribution

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cost overrun from forgotten environments | High | Medium | Auto-cleanup TTL, daily cleanup Lambda |
| Test environment accesses prod data | Low | Critical | Network isolation, IAM deny policies, synthetic data only |
| Resource exhaustion (too many concurrent) | Medium | Medium | Per-user quotas, ECS capacity limits |
| Template drift/outdated products | Medium | Low | Version control, automated testing of templates |
| Compliance gap in audit trail | Low | High | All provisioning via AutonomyPolicyService |
| Privilege escalation via environment | Low | High | Service Catalog launch constraints, IAM boundaries |

---

## Implementation

### Phase 1: Foundation (Weeks 1-2)

| Task | Files | Effort |
|------|-------|--------|
| Environment State DynamoDB table | `deploy/cloudformation/test-env-state.yaml` | 4h |
| Extend AutonomyPolicyService | `src/services/autonomy_policy_service.py` | 8h |
| EnvironmentProvisioningService | `src/services/environment_provisioning_service.py` | 16h |
| API endpoints | `src/api/environment_endpoints.py` | 8h |
| ECS task templates | `deploy/cloudformation/test-env-ecs.yaml` | 8h |

### Phase 2: Service Catalog (Weeks 3-4)

| Task | Files | Effort |
|------|-------|--------|
| Service Catalog Portfolio | `deploy/cloudformation/test-environment-catalog.yaml` | 8h |
| Product templates | `deploy/service-catalog/products/*.yaml` | 16h |
| Launch Constraints (IAM) | `deploy/cloudformation/test-env-iam.yaml` | 8h |
| HITL integration for extended types | `deploy/cloudformation/test-env-approval.yaml` | 8h |
| Buildspec for catalog deployment | `deploy/buildspecs/buildspec-test-env-catalog.yml` | 4h |

### Phase 3: UI & Observability (Weeks 5-6)

| Task | Files | Effort |
|------|-------|--------|
| Environment management page | `frontend/src/pages/Environments.jsx` | 16h |
| Environment dashboard component | `frontend/src/components/EnvironmentDashboard.jsx` | 8h |
| CloudWatch dashboard | `deploy/cloudformation/test-env-monitoring.yaml` | 4h |
| Cost allocation and reporting | Extend `deploy/cloudformation/cost-alerts.yaml` | 4h |
| Runbook documentation | `docs/runbooks/TEST_ENVIRONMENT_RUNBOOK.md` | 4h |

### Phase 4: Advanced Features (Complete - December 2025)

| Task | Files | Status |
|------|-------|--------|
| Scheduled provisioning | `deploy/cloudformation/test-env-scheduler.yaml`, `src/lambda/scheduled_provisioner.py` | Complete |
| EKS namespace controller | `deploy/cloudformation/test-env-namespace.yaml`, `src/lambda/namespace_controller.py` | Complete |
| K8s namespace service | `src/services/k8s_namespace_service.py` | Complete |
| Template marketplace | `deploy/cloudformation/test-env-marketplace.yaml`, `src/lambda/marketplace_handler.py` | Complete |
| Phase 4 tests | `tests/test_scheduled_provisioner.py`, `tests/test_namespace_controller.py`, `tests/test_marketplace_handler.py` | 40 tests |

### CloudFormation Templates (New)

| Template | Layer | Purpose |
|----------|-------|---------|
| `test-env-state.yaml` | 7.3 | DynamoDB state table for environment tracking |
| `test-environment-catalog.yaml` | 7.4 | Service Catalog Portfolio and IAM |
| `test-env-approval.yaml` | 7.5 | HITL approval workflow for extended environments |
| `test-env-monitoring.yaml` | 7.6 | CloudWatch dashboards and alarms |
| `test-env-budgets.yaml` | 7.7 | AWS Budgets for cost governance |
| `test-env-scheduler.yaml` | 7.8 | Scheduled provisioning Lambda and EventBridge |
| `test-env-namespace.yaml` | 7.9 | EKS namespace controller Lambda |
| `test-env-marketplace.yaml` | 7.10 | Template marketplace with HITL approval |

### API Endpoints (New)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/environments` | GET | List user's environments |
| `/api/v1/environments` | POST | Create new environment |
| `/api/v1/environments/{id}` | GET | Get environment details |
| `/api/v1/environments/{id}` | DELETE | Terminate environment |
| `/api/v1/environments/{id}/extend` | POST | Extend TTL (triggers HITL if needed) |
| `/api/v1/environments/templates` | GET | List available templates |
| `/api/v1/environments/quota` | GET | Get user's quota status |

---

## IAM Architecture

### IAM Roles Required

The test environment system requires 7 IAM roles with specific trust relationships and scoped permissions:

| Role Name | Service Principal | Purpose |
|-----------|------------------|---------|
| `${ProjectName}-test-env-provisioner-role-${Environment}` | `lambda.amazonaws.com` | Environment Provisioning Lambda |
| `${ProjectName}-test-env-cleanup-role-${Environment}` | `lambda.amazonaws.com` | TTL Cleanup Lambda |
| `${ProjectName}-test-env-catalog-launch-role-${Environment}` | `servicecatalog.amazonaws.com` | Service Catalog Product Launch |
| `${ProjectName}-test-env-ecs-task-execution-${Environment}` | `ecs-tasks.amazonaws.com` | ECS Task Execution (pull images, secrets) |
| `${ProjectName}-test-env-ecs-task-role-${Environment}` | `ecs-tasks.amazonaws.com` | ECS Task Runtime Permissions |
| `${ProjectName}-test-env-stepfunctions-role-${Environment}` | `states.amazonaws.com` | Step Functions for HITL approval flow |
| `${ProjectName}-test-env-user-role-${Environment}` | Cognito/OIDC | Users provisioning environments via UI |

### Permission Boundary

A permission boundary is attached to ALL test environment roles, establishing a maximum privilege ceiling that prevents privilege escalation:

```yaml
TestEnvPermissionBoundary:
  Type: AWS::IAM::ManagedPolicy
  Properties:
    ManagedPolicyName: !Sub '${ProjectName}-test-env-permission-boundary-${Environment}'
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        # ALLOW: Scoped test environment operations
        - Sid: AllowTestEnvOperations
          Effect: Allow
          Action:
            - s3:*
            - dynamodb:*
            - ecs:*
            - logs:*
            - cloudwatch:*
            - lambda:*
            - states:*
            - sns:*
            - servicecatalog:*
          Resource: '*'

        # ALLOW: EKS Describe (no mutate)
        - Sid: AllowEKSDescribe
          Effect: Allow
          Action:
            - eks:Describe*
            - eks:List*
          Resource:
            - !Sub 'arn:${AWS::Partition}:eks:${AWS::Region}:${AWS::AccountId}:cluster/${ProjectName}-*'

        # ALLOW: IAM PassRole to test environment roles only
        - Sid: AllowPassRoleTestEnv
          Effect: Allow
          Action:
            - iam:PassRole
          Resource:
            - !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-testenv-*'
            - !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-test-env-*'
          Condition:
            StringEquals:
              'iam:PassedToService':
                - ecs-tasks.amazonaws.com
                - lambda.amazonaws.com
                - states.amazonaws.com

        # DENY: Production Resources (Critical)
        - Sid: DenyProductionResources
          Effect: Deny
          Action: '*'
          Resource:
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-*-prod'
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-*-prod/*'
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod'
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod/*'
            - !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${ProjectName}/prod/*'
            - !Sub 'arn:${AWS::Partition}:rds:${AWS::Region}:${AWS::AccountId}:cluster:${ProjectName}-neptune-prod*'
            - !Sub 'arn:${AWS::Partition}:es:${AWS::Region}:${AWS::AccountId}:domain/${ProjectName}-opensearch-prod*'

        # DENY: IAM Privilege Escalation
        - Sid: DenyIAMEscalation
          Effect: Deny
          Action:
            - iam:CreateRole
            - iam:DeleteRole
            - iam:AttachRolePolicy
            - iam:DetachRolePolicy
            - iam:PutRolePolicy
            - iam:DeleteRolePolicy
            - iam:CreatePolicy
            - iam:DeletePolicy
            - iam:CreateUser
            - iam:DeleteUser
            - iam:CreateAccessKey
            - iam:UpdateAssumeRolePolicy
            - iam:PutRolePermissionsBoundary
          Resource: '*'

        # DENY: VPC Modification (Network Isolation)
        - Sid: DenyVPCModification
          Effect: Deny
          Action:
            - ec2:CreateVpc
            - ec2:DeleteVpc
            - ec2:CreateSubnet
            - ec2:DeleteSubnet
            - ec2:CreateInternetGateway
            - ec2:DeleteInternetGateway
            - ec2:CreateNatGateway
            - ec2:DeleteNatGateway
            - ec2:CreateVpcPeeringConnection
          Resource: '*'

        # DENY: Cross-Region Operations
        - Sid: DenyCrossRegion
          Effect: Deny
          Action: '*'
          Resource: '*'
          Condition:
            StringNotEquals:
              'aws:RequestedRegion': !Ref AWS::Region
```

### Provisioner Lambda Role Permissions

The provisioner Lambda requires access to DynamoDB, Service Catalog, Step Functions, SNS, Budgets, CloudWatch, and Secrets Manager:

| Service | Actions | Resource Scope |
|---------|---------|----------------|
| DynamoDB | GetItem, PutItem, UpdateItem, DeleteItem, Query | `${ProjectName}-test-env-state-${Environment}`, `${ProjectName}-autonomy-policies-${Environment}` |
| Service Catalog | ProvisionProduct, TerminateProvisionedProduct, Describe* | Portfolio: `${ProjectName}-test-env-portfolio-${Environment}` |
| Step Functions | StartExecution, DescribeExecution | `${ProjectName}-test-env-approval-${Environment}` |
| SNS | Publish | `${ProjectName}-test-env-notifications-${Environment}` |
| Budgets | ViewBudget, DescribeBudget | `${ProjectName}-test-env-*` |
| CloudWatch | PutMetricData | Namespace: `${ProjectName}/TestEnvironments` |
| Secrets Manager | GetSecretValue | `${ProjectName}/${Environment}/test-envs/*` |

### Service Catalog Launch Role Permissions

The launch role is assumed by Service Catalog when deploying products:

| Service | Actions | Resource Scope |
|---------|---------|----------------|
| CloudFormation | CreateStack, DeleteStack, UpdateStack, Describe* | `${ProjectName}-testenv-*`, `SC-*` |
| ECS | CreateService, DeleteService, RunTask, StopTask, RegisterTaskDefinition | Cluster: `${ProjectName}-testenvs-${Environment}` |
| S3 | CreateBucket, DeleteBucket, PutBucketPolicy, Get/PutObject | `${ProjectName}-testenv-*-${Environment}` |
| DynamoDB | CreateTable, DeleteTable, UpdateTable | `${ProjectName}-testenv-*-${Environment}` |
| Lambda | CreateFunction, DeleteFunction, UpdateFunction* | `${ProjectName}-testenv-*` |
| CloudWatch Logs | CreateLogGroup, DeleteLogGroup, PutRetentionPolicy | `/aws/${ProjectName}/testenv/*` |
| IAM | PassRole | `${ProjectName}-testenv-*`, `${ProjectName}-test-env-ecs-*` |

### ECS Task Role (Runtime Permissions)

Test environment workloads get scoped permissions with explicit production denies:

```yaml
Policies:
  # Allow test environment resources
  - PolicyName: S3Access
    PolicyDocument:
      Statement:
        - Effect: Allow
          Action: [s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket]
          Resource:
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-testenv-*-${Environment}'
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-testenv-*-${Environment}/*'

  # CRITICAL: Explicit deny for production
  - PolicyName: DenyProductionAccess
    PolicyDocument:
      Statement:
        - Effect: Deny
          Action: [dynamodb:*, s3:*, secretsmanager:GetSecretValue]
          Resource:
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-*-prod'
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod'
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod/*'
            - !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${ProjectName}/prod/*'
```

### User Role Configuration

Users assume this role via Cognito/OIDC with a maximum 4-hour session:

```yaml
TestEnvUserRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: !Sub '${ProjectName}-test-env-user-role-${Environment}'
    MaxSessionDuration: 14400  # 4 hours max
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Federated: !Sub 'arn:${AWS::Partition}:cognito-identity:${AWS::Region}:${AWS::AccountId}:identitypool/${CognitoIdentityPoolId}'
          Action: sts:AssumeRoleWithWebIdentity
          Condition:
            StringEquals:
              'cognito-identity.amazonaws.com:aud': !Ref CognitoIdentityPoolId
    PermissionsBoundary: !Ref TestEnvPermissionBoundary
    Policies:
      - PolicyName: EnvironmentAPIAccess
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action: execute-api:Invoke
              Resource:
                - !Sub 'arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:*/*/GET/api/v1/environments*'
                - !Sub 'arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:*/*/POST/api/v1/environments'
                - !Sub 'arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:*/*/DELETE/api/v1/environments/*'
      - PolicyName: ServiceCatalogAccess
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - servicecatalog:DescribeProduct
                - servicecatalog:ListPortfolios
                - servicecatalog:ProvisionProduct
                - servicecatalog:DescribeProvisionedProduct
                - servicecatalog:TerminateProvisionedProduct
              Resource: '*'
              Condition:
                StringEquals:
                  'servicecatalog:userLevel': self
```

### Service Catalog Launch Constraints

Launch constraints ensure users cannot escalate privileges through product provisioning:

```yaml
TestEnvLaunchConstraint:
  Type: AWS::ServiceCatalog::LaunchRoleConstraint
  Properties:
    Description: Launch constraint using service role
    PortfolioId: !Ref TestEnvPortfolio
    ProductId: !Ref TestEnvPythonFastAPIProduct
    RoleArn: !GetAtt ServiceCatalogLaunchRole.Arn

TestEnvTagUpdateConstraint:
  Type: AWS::ServiceCatalog::ResourceUpdateConstraint
  Properties:
    Description: Enforce mandatory tags on all resources
    PortfolioId: !Ref TestEnvPortfolio
    ProductId: !Ref TestEnvPythonFastAPIProduct
    TagUpdateOnProvisionedProduct: ALLOWED
```

### SCP Recommendations

For organizations using AWS Organizations, deploy these SCPs to the OU containing test environment accounts:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyProductionTaggedResources",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:ResourceTag/Environment": "prod" },
        "ArnNotLike": { "aws:PrincipalArn": ["arn:aws:iam::*:role/aura-admin-*"] }
      }
    },
    {
      "Sid": "RequireTestEnvTagging",
      "Effect": "Deny",
      "Action": ["ecs:CreateService", "dynamodb:CreateTable", "s3:CreateBucket", "lambda:CreateFunction"],
      "Resource": "*",
      "Condition": { "Null": { "aws:RequestTag/TestEnvId": "true" } }
    },
    {
      "Sid": "EnforceMaxSessionDuration",
      "Effect": "Deny",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::*:role/aura-test-env-*",
      "Condition": { "NumericGreaterThan": { "sts:DurationSeconds": "14400" } }
    }
  ]
}
```

### CMMC Compliance Mapping

| CMMC Control | Requirement | Implementation |
|--------------|-------------|----------------|
| **AC.L2-3.1.1** | Limit system access to authorized users | Cognito/OIDC federation, user-assumable roles |
| **AC.L2-3.1.1** | Limit access to processes acting on behalf of users | Service roles with permission boundaries |
| **AC.L2-3.1.1** | Limit access to devices | 4-hour max session duration |
| **AC.L2-3.1.2** | Limit transactions based on purpose | Service Catalog products enforce allowed configurations |
| **AC.L2-3.1.2** | Limit transactions based on function | Role-based access with scoped permissions |
| **AC.L2-3.1.2** | Limit transactions based on time | TTL enforcement, max session duration |
| **AU.L2-3.3.1** | Audit logging | CloudTrail + DynamoDB audit table |
| **CM.L2-3.4.1** | Baseline configuration | Service Catalog Product versions |
| **SC.L2-3.13.1** | Boundary protection | Network isolation, security groups, explicit denies |

### IAM CloudFormation Template

The complete IAM configuration is defined in `deploy/cloudformation/test-env-iam.yaml` (Layer 7.4) with the following exports:

| Export Name | Value |
|-------------|-------|
| `${ProjectName}-test-env-permission-boundary-${Environment}` | Permission boundary ARN |
| `${ProjectName}-test-env-provisioner-role-arn-${Environment}` | Provisioner Lambda role ARN |
| `${ProjectName}-test-env-catalog-launch-role-arn-${Environment}` | Service Catalog launch role ARN |
| `${ProjectName}-test-env-ecs-task-role-arn-${Environment}` | ECS task role ARN |
| `${ProjectName}-test-env-ecs-execution-role-arn-${Environment}` | ECS execution role ARN |
| `${ProjectName}-test-env-cleanup-role-arn-${Environment}` | Cleanup Lambda role ARN |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first environment | < 5 minutes | CloudWatch metric |
| Environment availability | 99% | CloudWatch alarm |
| Cost per environment | < $0.50/day | AWS Cost Explorer |
| Auto-cleanup success rate | 100% | Lambda execution logs |
| User adoption | 50% of dev teams in Q1 | Usage analytics |

---

## Phase 4 Implementation (December 2025)

Phase 4 delivers the advanced features that complete the self-service test environment framework:

### Layer 7.8 - Scheduled Provisioning

**CloudFormation:** `deploy/cloudformation/test-env-scheduler.yaml`
**Lambda:** `src/lambda/scheduled_provisioner.py`

| Resource | Purpose |
|----------|---------|
| DynamoDB Table `aura-test-env-schedule-{env}` | Stores scheduled job metadata with status tracking |
| EventBridge Rule | Triggers Lambda every 5 minutes to process pending jobs |
| Lambda Function | Queries pending jobs, invokes provisioner, updates status |
| CloudWatch Alarm | Alerts on scheduler errors (> 5 in 10 minutes) |

**Workflow:**
1. User schedules environment provisioning via API
2. Job stored in DynamoDB with `status: pending` and `scheduled_at` timestamp
3. EventBridge triggers scheduler Lambda every 5 minutes
4. Lambda queries for jobs where `scheduled_at <= now AND status = pending`
5. For each job: invoke provisioner Lambda, update status to `triggered`
6. Handle failures gracefully with error tracking and SNS notifications

**Use Cases:**
- Pre-provision environments for scheduled demo sessions
- Coordinate team testing windows
- Automated environment refresh cycles

### Layer 7.9 - EKS Namespace Controller

**CloudFormation:** `deploy/cloudformation/test-env-namespace.yaml`
**Lambda:** `src/lambda/namespace_controller.py`
**Service:** `src/services/k8s_namespace_service.py`

| Resource | Purpose |
|----------|---------|
| Lambda Function | Manages namespace lifecycle via kubectl subprocess |
| EKS Access Entry | Grants Lambda namespace management permissions |
| CloudWatch Alarms | Error monitoring and duration alerts |

**Namespace Resources Created:**
- Kubernetes Namespace with Aura labels
- ResourceQuota (CPU, memory, pod limits)
- LimitRange (default container limits)
- ServiceAccount (for workload identity)
- NetworkPolicy (optional, default-deny with DNS egress)

**Operations:**
| Operation | Description |
|-----------|-------------|
| `create` | Create namespace with quotas and network policies |
| `delete` | Delete namespace (async, wait=false) |
| `status` | Get namespace phase and metadata |

**Default Quotas:**
- CPU: 2 cores
- Memory: 4Gi
- Pods: 10
- Services: 5
- Secrets: 10
- ConfigMaps: 10

**Use Cases:**
- Rapid API prototyping (< 5 minute provisioning)
- Unit/integration test isolation
- Developer sandbox environments

### Layer 7.10 - Template Marketplace

**CloudFormation:** `deploy/cloudformation/test-env-marketplace.yaml`
**Lambda:** `src/lambda/marketplace_handler.py`

| Resource | Purpose |
|----------|---------|
| DynamoDB Table `aura-test-env-templates-{env}` | Template metadata with status, category, author |
| Submit Lambda | Validates templates, uploads to S3, triggers HITL |
| Approve Lambda | Processes approvals, moves to approved/, creates SC product |
| S3 Paths | `marketplace/pending/` and `marketplace/approved/` |

**Template Categories:**
- `backend` - API and backend services
- `frontend` - Web UI applications
- `full-stack` - Complete application stacks
- `data-pipeline` - Data processing workflows
- `ml-inference` - Machine learning inference
- `testing` - Test harness environments
- `other` - Custom templates

**Submission Workflow:**
1. User submits template via API with metadata
2. Lambda validates CloudFormation structure
3. Template uploaded to `s3://artifacts/marketplace/pending/{template_id}/`
4. Record created in DynamoDB with `status: pending_approval`
5. HITL approval workflow started via Step Functions
6. Admin reviews template for security and compliance
7. On approval: copy to `approved/`, create Service Catalog product
8. On rejection: update status, notify submitter

**DynamoDB Schema:**
```
template_id (PK)
author_id
name
description
category
status (pending_approval, approved, rejected)
s3_key
created_at
version
downloads
rating
metadata { tags, estimated_cost, provisioning_time }
```

**GSIs:**
- `status-created_at-index` - Query templates by status
- `category-created_at-index` - Browse by category
- `author-created_at-index` - View author's submissions

### IAM Roles Added (Phase 4)

| Role | Purpose |
|------|---------|
| `aura-test-env-scheduler-role-{env}` | Scheduler Lambda: DynamoDB, Lambda invoke, CloudWatch |
| `aura-test-env-namespace-controller-role-{env}` | Namespace controller: EKS, DynamoDB, CloudWatch |
| `aura-test-env-marketplace-role-{env}` | Marketplace: DynamoDB, S3, SNS, Step Functions, Service Catalog |

### Tests

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_scheduled_provisioner.py` | 11 | Job processing, error handling, metrics |
| `tests/test_namespace_controller.py` | 14 | CRUD operations, quotas, network policies |
| `tests/test_marketplace_handler.py` | 15 | Submit, approve, reject, validation |

**Total Phase 4 Tests:** 40

---

## Future Enhancements

1. **Environment Cloning:** Clone existing environment with modified parameters
2. **Cost Showback:** Per-team cost dashboards and monthly reports
3. **GitOps Integration:** ArgoCD-managed environment definitions
4. **Spot Instance Support:** Fargate Spot for cost optimization
5. **Multi-Region:** Deploy templates to alternate regions

---

## References

- ADR-005: HITL Sandbox Architecture
- ADR-017: Dynamic Sandbox Resource Allocation
- ADR-032: Configurable Autonomy Framework
- AWS Service Catalog Documentation
- NIST 800-53: Configuration Management (CM) family
- CMMC Level 2: Access Control requirements

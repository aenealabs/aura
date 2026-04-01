# Self-Service Sandbox Capability: Air-Gapped Deployment Runbook

**Version:** 1.0
**Date:** 2026-02-05
**Purpose:** Comprehensive guide for replicating Aura's self-service sandbox provisioning capability in an air-gapped environment

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Core Components](#core-components)
5. [Infrastructure Setup](#infrastructure-setup)
6. [Service Implementation](#service-implementation)
7. [Lambda Functions](#lambda-functions)
8. [API Layer](#api-layer)
9. [Air-Gapped Deployment Considerations](#air-gapped-deployment-considerations)
10. [Security Architecture](#security-architecture)
11. [Monitoring and Observability](#monitoring-and-observability)
12. [Testing Procedures](#testing-procedures)
13. [Operational Runbook](#operational-runbook)

---

## Executive Summary

This runbook enables software engineers to replicate Aura's self-service sandbox provisioning capability independently. The system allows users to spin up isolated test environments on-demand with:

- **Four environment types:** Quick (4hr EKS namespace), Standard (24hr full-stack), Extended (7-day with approval), Compliance (dedicated VPC)
- **Five pre-built templates:** Python FastAPI, React Frontend, Full-Stack, Data Pipeline, ML Experiment
- **Cost governance:** Per-user quotas, TTL enforcement, automatic cleanup
- **HITL integration:** Human-in-the-loop approval for extended/compliance environments
- **Air-gapped compatibility:** No internet dependencies when properly configured

### Key Differentiators for Air-Gapped Deployment

1. **Private ECR repositories** for all container images
2. **VPC endpoints** for all AWS service communication
3. **Offline artifact storage** in S3
4. **No external package manager dependencies** at runtime

---

## Architecture Overview

### High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interface Layer                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │  Frontend   │    │    API      │    │   CLI       │                     │
│  │  (React)    │───▶│  Gateway    │◀───│   Client    │                     │
│  └─────────────┘    └──────┬──────┘    └─────────────┘                     │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                         API Services Layer                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                Environment Provisioning Service (FastAPI)           │   │
│  │  • POST /environments → Create sandbox                              │   │
│  │  • GET /environments → List user sandboxes                          │   │
│  │  • DELETE /environments/{id} → Terminate sandbox                    │   │
│  │  • GET /environments/quota → Check quota status                     │   │
│  │  • GET /environments/templates → List available templates           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                       Provisioning Engine Layer                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │   Autonomy    │  │    HITL       │  │   Service     │                   │
│  │   Policy      │◀─│   Approval    │◀─│   Catalog     │                   │
│  │   Service     │  │   Workflow    │  │   Launcher    │                   │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                   │
│          │                  │                  │                            │
│          ▼                  ▼                  ▼                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  K8s Namespace Service (Quick Envs)                 │   │
│  │  • Creates isolated EKS namespaces for 4-hour quick tests           │   │
│  │  • NetworkPolicies for isolation                                    │   │
│  │  • ResourceQuotas for cost control                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                         Data Layer                                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │   DynamoDB    │  │      S3       │  │   Secrets     │                   │
│  │   State       │  │   Artifacts   │  │   Manager     │                   │
│  │   Table       │  │   Bucket      │  │               │                   │
│  └───────────────┘  └───────────────┘  └───────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Provisioning Flow by Environment Type

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Environment Type Routing                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Request ─┬─► QUICK (4hr) ────► K8s Namespace Service ──► EKS Namespace    │
│           │                      (No approval needed)                       │
│           │                                                                 │
│           ├─► STANDARD (24hr) ─► Service Catalog ────────► CloudFormation  │
│           │                      (No approval needed)                       │
│           │                                                                 │
│           ├─► EXTENDED (7d) ──► HITL Approval ──┬─► Approve ─► Provision   │
│           │                                      └─► Deny ────► Reject     │
│           │                                                                 │
│           └─► COMPLIANCE ─────► HITL Approval ──┬─► Approve ─► Dedicated   │
│                                                  │             VPC Stack    │
│                                                  └─► Deny ────► Reject     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### AWS Services Required

| Service | Purpose | Air-Gapped Note |
|---------|---------|-----------------|
| EKS | Kubernetes cluster for quick environments | Requires VPC endpoint |
| Service Catalog | Product portfolio for environment templates | Requires VPC endpoint |
| DynamoDB | State management, cost tracking | Requires VPC endpoint |
| S3 | Artifact storage, template files | Requires VPC endpoint |
| Lambda | Serverless functions for provisioning | Requires VPC endpoint |
| Step Functions | HITL approval workflow orchestration | Requires VPC endpoint |
| ECR | Container image registry | Requires VPC endpoint |
| Secrets Manager | Credential storage | Requires VPC endpoint |
| CloudWatch | Monitoring and logging | Requires VPC endpoint |
| SNS | Notifications | Requires VPC endpoint |
| IAM | Permissions and roles | No endpoint needed |

### VPC Endpoints Required (Air-Gapped)

```yaml
# deploy/cloudformation/vpc-endpoints-sandbox.yaml
VPCEndpoints:
  # Gateway Endpoints (no cost)
  - com.amazonaws.{region}.s3
  - com.amazonaws.{region}.dynamodb

  # Interface Endpoints (per-hour cost)
  - com.amazonaws.{region}.ecr.api
  - com.amazonaws.{region}.ecr.dkr
  - com.amazonaws.{region}.ecs
  - com.amazonaws.{region}.execute-api
  - com.amazonaws.{region}.lambda
  - com.amazonaws.{region}.logs
  - com.amazonaws.{region}.secretsmanager
  - com.amazonaws.{region}.servicecatalog
  - com.amazonaws.{region}.sns
  - com.amazonaws.{region}.states
  - com.amazonaws.{region}.sts
```

### Software Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Service runtime |
| FastAPI | 0.100+ | API framework |
| boto3 | 1.28+ | AWS SDK |
| kubernetes | 28.1+ | EKS interaction |
| pydantic | 2.0+ | Data validation |

---

## Core Components

### 1. Environment State Schema

```python
# src/services/sandbox/models/environment.py

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class EnvironmentType(str, Enum):
    QUICK = "quick"           # 4 hours, EKS namespace only
    STANDARD = "standard"     # 24 hours, Service Catalog
    EXTENDED = "extended"     # 7 days, requires approval
    COMPLIANCE = "compliance" # Dedicated VPC, requires approval

class EnvironmentStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    FAILED = "failed"
    REJECTED = "rejected"

class EnvironmentTemplate(str, Enum):
    PYTHON_FASTAPI = "python-fastapi"
    REACT_FRONTEND = "react-frontend"
    FULL_STACK = "full-stack"
    DATA_PIPELINE = "data-pipeline"
    ML_EXPERIMENT = "ml-experiment"

class Environment(BaseModel):
    """Core environment model stored in DynamoDB."""
    environment_id: str = Field(..., description="Unique identifier")
    user_id: str = Field(..., description="Owner user ID")
    display_name: str = Field(..., description="Human-readable name")
    environment_type: EnvironmentType
    template: EnvironmentTemplate
    status: EnvironmentStatus = EnvironmentStatus.PENDING_APPROVAL

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None

    # Cost tracking
    cost_estimate_daily: float = 0.0
    actual_cost: float = 0.0

    # Infrastructure references
    namespace: Optional[str] = None  # For QUICK type
    stack_id: Optional[str] = None   # For Service Catalog
    vpc_id: Optional[str] = None     # For COMPLIANCE type

    # HITL approval
    approval_id: Optional[str] = None
    approved_by: Optional[str] = None
    approval_reason: Optional[str] = None

    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 2. Quota Configuration

```python
# src/services/sandbox/config/quotas.py

from dataclasses import dataclass
from typing import Dict

@dataclass
class UserQuota:
    """Per-user quota limits."""
    max_concurrent_environments: int = 3
    max_monthly_cost_usd: float = 500.0
    max_daily_cost_usd: float = 50.0
    max_ttl_hours: int = 168  # 7 days

@dataclass
class EnvironmentTypeQuota:
    """Per-environment-type limits."""
    max_ttl_hours: int
    requires_approval: bool
    max_per_user: int
    estimated_hourly_cost: float

# Default quotas by environment type
DEFAULT_TYPE_QUOTAS: Dict[str, EnvironmentTypeQuota] = {
    "quick": EnvironmentTypeQuota(
        max_ttl_hours=4,
        requires_approval=False,
        max_per_user=5,
        estimated_hourly_cost=0.10
    ),
    "standard": EnvironmentTypeQuota(
        max_ttl_hours=24,
        requires_approval=False,
        max_per_user=3,
        estimated_hourly_cost=0.50
    ),
    "extended": EnvironmentTypeQuota(
        max_ttl_hours=168,
        requires_approval=True,
        max_per_user=2,
        estimated_hourly_cost=0.50
    ),
    "compliance": EnvironmentTypeQuota(
        max_ttl_hours=168,
        requires_approval=True,
        max_per_user=1,
        estimated_hourly_cost=2.00
    ),
}
```

### 3. Template Registry

```python
# src/services/sandbox/templates/registry.py

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class TemplateDefinition:
    """Service Catalog product template definition."""
    template_id: str
    display_name: str
    description: str
    icon: str
    category: str

    # CloudFormation template
    cloudformation_template_url: str

    # Resource estimates
    estimated_hourly_cost: float
    included_services: List[str]

    # Parameters
    default_parameters: Dict[str, str]
    configurable_parameters: List[str]

TEMPLATE_REGISTRY: Dict[str, TemplateDefinition] = {
    "python-fastapi": TemplateDefinition(
        template_id="python-fastapi",
        display_name="Python FastAPI",
        description="FastAPI service with PostgreSQL and Redis",
        icon="python",
        category="backend",
        cloudformation_template_url="s3://artifacts/templates/python-fastapi.yaml",
        estimated_hourly_cost=0.15,
        included_services=["ECS Fargate", "RDS PostgreSQL", "ElastiCache Redis"],
        default_parameters={
            "InstanceSize": "small",
            "DatabaseSize": "db.t3.micro",
            "CacheNodeType": "cache.t3.micro"
        },
        configurable_parameters=["InstanceSize", "DatabaseSize"]
    ),
    "react-frontend": TemplateDefinition(
        template_id="react-frontend",
        display_name="React Frontend",
        description="React SPA with S3 hosting and CloudFront CDN",
        icon="react",
        category="frontend",
        cloudformation_template_url="s3://artifacts/templates/react-frontend.yaml",
        estimated_hourly_cost=0.05,
        included_services=["S3", "CloudFront", "Route53"],
        default_parameters={
            "BucketClass": "STANDARD"
        },
        configurable_parameters=[]
    ),
    "full-stack": TemplateDefinition(
        template_id="full-stack",
        display_name="Full Stack",
        description="Complete stack: React + FastAPI + PostgreSQL + Redis",
        icon="layers",
        category="full-stack",
        cloudformation_template_url="s3://artifacts/templates/full-stack.yaml",
        estimated_hourly_cost=0.35,
        included_services=["ECS Fargate", "RDS", "ElastiCache", "S3", "CloudFront"],
        default_parameters={
            "BackendInstanceSize": "small",
            "DatabaseSize": "db.t3.micro"
        },
        configurable_parameters=["BackendInstanceSize", "DatabaseSize"]
    ),
    "data-pipeline": TemplateDefinition(
        template_id="data-pipeline",
        display_name="Data Pipeline",
        description="ETL pipeline with Step Functions, Glue, and S3",
        icon="pipeline",
        category="data",
        cloudformation_template_url="s3://artifacts/templates/data-pipeline.yaml",
        estimated_hourly_cost=0.25,
        included_services=["Step Functions", "Glue", "S3", "Athena"],
        default_parameters={
            "GlueWorkerType": "G.1X",
            "GlueWorkerCount": "2"
        },
        configurable_parameters=["GlueWorkerType", "GlueWorkerCount"]
    ),
    "ml-experiment": TemplateDefinition(
        template_id="ml-experiment",
        display_name="ML Experiment",
        description="SageMaker notebook with S3 data lake",
        icon="brain",
        category="ml",
        cloudformation_template_url="s3://artifacts/templates/ml-experiment.yaml",
        estimated_hourly_cost=0.50,
        included_services=["SageMaker", "S3", "ECR"],
        default_parameters={
            "NotebookInstanceType": "ml.t3.medium"
        },
        configurable_parameters=["NotebookInstanceType"]
    ),
}
```

---

## Infrastructure Setup

### Phase 1: Foundation Infrastructure

#### 1.1 DynamoDB State Table

```yaml
# deploy/cloudformation/sandbox-state.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Sandbox Capability - State Management (Layer 7.3)'

Parameters:
  ProjectName:
    Type: String
    Default: sandbox
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
  EnvironmentStateTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-env-state-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: environment_id
          AttributeType: S
        - AttributeName: user_id
          AttributeType: S
        - AttributeName: created_at
          AttributeType: S
        - AttributeName: status
          AttributeType: S
      KeySchema:
        - AttributeName: environment_id
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: user-created_at-index
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: created_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: status-created_at-index
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: created_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref StateTableKMSKey
      Tags:
        - Key: Component
          Value: sandbox
        - Key: Environment
          Value: !Ref Environment

  StateTableKMSKey:
    Type: AWS::KMS::Key
    Properties:
      Description: KMS key for sandbox state table encryption
      EnableKeyRotation: true
      KeyPolicy:
        Version: '2012-10-17'
        Statement:
          - Sid: AllowRootAccess
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:root'
            Action: 'kms:*'
            Resource: '*'

  CostTrackingTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-cost-tracking-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: user_id
          AttributeType: S
        - AttributeName: period
          AttributeType: S
      KeySchema:
        - AttributeName: user_id
          KeyType: HASH
        - AttributeName: period
          KeyType: RANGE
      SSESpecification:
        SSEEnabled: true
      Tags:
        - Key: Component
          Value: sandbox

Outputs:
  StateTableName:
    Value: !Ref EnvironmentStateTable
    Export:
      Name: !Sub '${ProjectName}-state-table-${Environment}'
  StateTableArn:
    Value: !GetAtt EnvironmentStateTable.Arn
    Export:
      Name: !Sub '${ProjectName}-state-table-arn-${Environment}'
```

#### 1.2 IAM Permission Boundary

```yaml
# deploy/cloudformation/sandbox-iam.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Sandbox Capability - IAM Roles and Permission Boundary (Layer 7.4)'

Parameters:
  ProjectName:
    Type: String
    Default: sandbox
  Environment:
    Type: String

Resources:
  # CRITICAL: Permission Boundary prevents production access
  SandboxPermissionBoundary:
    Type: AWS::IAM::ManagedPolicy
    Properties:
      ManagedPolicyName: !Sub '${ProjectName}-permission-boundary-${Environment}'
      Description: 'Permission boundary for sandbox environments - blocks production access'
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          # Allow sandbox-tagged resources only
          - Sid: AllowSandboxResources
            Effect: Allow
            Action:
              - 's3:*'
              - 'dynamodb:*'
              - 'sqs:*'
              - 'sns:*'
              - 'logs:*'
              - 'cloudwatch:*'
            Resource: '*'
            Condition:
              StringEquals:
                'aws:ResourceTag/SandboxEnvironment': 'true'

          # Deny production resources explicitly
          - Sid: DenyProductionResources
            Effect: Deny
            Action: '*'
            Resource:
              - !Sub 'arn:${AWS::Partition}:*:*:*:*prod*'
              - !Sub 'arn:${AWS::Partition}:*:*:*:*production*'

          # Deny IAM privilege escalation
          - Sid: DenyPrivilegeEscalation
            Effect: Deny
            Action:
              - 'iam:CreateUser'
              - 'iam:CreateRole'
              - 'iam:AttachRolePolicy'
              - 'iam:PutRolePolicy'
              - 'iam:CreateAccessKey'
              - 'iam:UpdateAssumeRolePolicy'
              - 'sts:AssumeRole'
            Resource: '*'
            Condition:
              StringNotEquals:
                'aws:ResourceTag/SandboxEnvironment': 'true'

          # Deny network modifications
          - Sid: DenyNetworkModifications
            Effect: Deny
            Action:
              - 'ec2:CreateVpc'
              - 'ec2:DeleteVpc'
              - 'ec2:ModifyVpcAttribute'
              - 'ec2:CreateSubnet'
              - 'ec2:DeleteSubnet'
              - 'ec2:CreateInternetGateway'
              - 'ec2:AttachInternetGateway'
            Resource: '*'

          # Deny KMS key creation (use provided keys only)
          - Sid: DenyKMSKeyCreation
            Effect: Deny
            Action:
              - 'kms:CreateKey'
              - 'kms:ScheduleKeyDeletion'
            Resource: '*'

  # Lambda execution role for provisioning
  ProvisioningLambdaRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-provisioner-role-${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - !Sub 'arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        - !Sub 'arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole'
      Policies:
        - PolicyName: ProvisioningPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Sid: DynamoDBAccess
                Effect: Allow
                Action:
                  - 'dynamodb:GetItem'
                  - 'dynamodb:PutItem'
                  - 'dynamodb:UpdateItem'
                  - 'dynamodb:Query'
                  - 'dynamodb:Scan'
                Resource:
                  - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-*'
              - Sid: ServiceCatalogAccess
                Effect: Allow
                Action:
                  - 'servicecatalog:ProvisionProduct'
                  - 'servicecatalog:TerminateProvisionedProduct'
                  - 'servicecatalog:DescribeProvisionedProduct'
                Resource: '*'
              - Sid: StepFunctionsAccess
                Effect: Allow
                Action:
                  - 'states:StartExecution'
                  - 'states:SendTaskSuccess'
                  - 'states:SendTaskFailure'
                Resource:
                  - !Sub 'arn:${AWS::Partition}:states:${AWS::Region}:${AWS::AccountId}:stateMachine:${ProjectName}-*'
              - Sid: EKSAccess
                Effect: Allow
                Action:
                  - 'eks:DescribeCluster'
                  - 'eks:ListClusters'
                Resource: '*'

  # Service Catalog launch role
  ServiceCatalogLaunchRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-sc-launch-role-${Environment}'
      PermissionsBoundary: !Ref SandboxPermissionBoundary
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: servicecatalog.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: LaunchPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Sid: CloudFormationAccess
                Effect: Allow
                Action:
                  - 'cloudformation:CreateStack'
                  - 'cloudformation:DeleteStack'
                  - 'cloudformation:DescribeStacks'
                  - 'cloudformation:UpdateStack'
                Resource:
                  - !Sub 'arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/SC-*'
              - Sid: PassRole
                Effect: Allow
                Action: 'iam:PassRole'
                Resource: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-*'
                Condition:
                  StringEquals:
                    'iam:PassedToService': cloudformation.amazonaws.com

Outputs:
  PermissionBoundaryArn:
    Value: !Ref SandboxPermissionBoundary
    Export:
      Name: !Sub '${ProjectName}-permission-boundary-${Environment}'
  ProvisioningRoleArn:
    Value: !GetAtt ProvisioningLambdaRole.Arn
    Export:
      Name: !Sub '${ProjectName}-provisioner-role-arn-${Environment}'
```

### Phase 2: Service Catalog Portfolio

```yaml
# deploy/cloudformation/sandbox-catalog.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Sandbox Capability - Service Catalog Portfolio (Layer 7.5)'

Parameters:
  ProjectName:
    Type: String
    Default: sandbox
  Environment:
    Type: String
  ArtifactsBucket:
    Type: String
    Description: S3 bucket containing CloudFormation templates

Resources:
  SandboxPortfolio:
    Type: AWS::ServiceCatalog::Portfolio
    Properties:
      DisplayName: !Sub '${ProjectName} Test Environments'
      Description: 'Self-service test environment templates for rapid prototyping'
      ProviderName: 'Platform Team'
      Tags:
        - Key: Component
          Value: sandbox
        - Key: Environment
          Value: !Ref Environment

  # Python FastAPI Product
  PythonFastAPIProduct:
    Type: AWS::ServiceCatalog::CloudFormationProduct
    Properties:
      Name: 'Python FastAPI'
      Description: 'FastAPI service with PostgreSQL and Redis'
      Owner: 'Platform Team'
      Distributor: 'Internal'
      SupportDescription: 'Contact platform-team@company.com'
      SupportEmail: 'platform-team@company.com'
      ProvisioningArtifactParameters:
        - Name: 'v1.0'
          Description: 'Initial release'
          Info:
            LoadTemplateFromURL: !Sub 'https://${ArtifactsBucket}.s3.${AWS::Region}.amazonaws.com/templates/python-fastapi.yaml'
          Type: CLOUD_FORMATION_TEMPLATE
      Tags:
        - Key: TemplateId
          Value: python-fastapi
        - Key: Category
          Value: backend
        - Key: EstimatedHourlyCost
          Value: '0.15'

  PythonFastAPIAssociation:
    Type: AWS::ServiceCatalog::PortfolioProductAssociation
    Properties:
      PortfolioId: !Ref SandboxPortfolio
      ProductId: !Ref PythonFastAPIProduct

  # Full Stack Product
  FullStackProduct:
    Type: AWS::ServiceCatalog::CloudFormationProduct
    Properties:
      Name: 'Full Stack'
      Description: 'Complete stack: React + FastAPI + PostgreSQL + Redis'
      Owner: 'Platform Team'
      ProvisioningArtifactParameters:
        - Name: 'v1.0'
          Description: 'Initial release'
          Info:
            LoadTemplateFromURL: !Sub 'https://${ArtifactsBucket}.s3.${AWS::Region}.amazonaws.com/templates/full-stack.yaml'
          Type: CLOUD_FORMATION_TEMPLATE
      Tags:
        - Key: TemplateId
          Value: full-stack
        - Key: Category
          Value: full-stack
        - Key: EstimatedHourlyCost
          Value: '0.35'

  FullStackAssociation:
    Type: AWS::ServiceCatalog::PortfolioProductAssociation
    Properties:
      PortfolioId: !Ref SandboxPortfolio
      ProductId: !Ref FullStackProduct

  # Launch Constraint - forces use of launch role
  LaunchConstraint:
    Type: AWS::ServiceCatalog::LaunchRoleConstraint
    Properties:
      PortfolioId: !Ref SandboxPortfolio
      ProductId: !Ref PythonFastAPIProduct
      RoleArn:
        Fn::ImportValue: !Sub '${ProjectName}-sc-launch-role-arn-${Environment}'
      Description: 'Use permission-bounded launch role'

  # Principal Association - allow authenticated users
  PrincipalAssociation:
    Type: AWS::ServiceCatalog::PortfolioPrincipalAssociation
    Properties:
      PortfolioId: !Ref SandboxPortfolio
      PrincipalARN: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-user-role-${Environment}'
      PrincipalType: IAM

Outputs:
  PortfolioId:
    Value: !Ref SandboxPortfolio
    Export:
      Name: !Sub '${ProjectName}-portfolio-id-${Environment}'
```

---

## Service Implementation

### Environment Provisioning Service

```python
# src/services/sandbox/environment_provisioning_service.py

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import boto3
from botocore.exceptions import ClientError

from .models.environment import (
    Environment,
    EnvironmentType,
    EnvironmentStatus,
    EnvironmentTemplate,
)
from .config.quotas import DEFAULT_TYPE_QUOTAS, UserQuota
from .templates.registry import TEMPLATE_REGISTRY
from .k8s_namespace_service import K8sNamespaceService

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when user exceeds quota limits."""
    pass


class EnvironmentProvisioningService:
    """
    Core service for self-service sandbox provisioning.

    Supports four environment types:
    - QUICK: EKS namespace (4hr, no approval)
    - STANDARD: Service Catalog product (24hr, no approval)
    - EXTENDED: Service Catalog product (7 days, requires approval)
    - COMPLIANCE: Dedicated VPC (7 days, requires approval)
    """

    def __init__(
        self,
        state_table_name: str,
        cost_table_name: str,
        portfolio_id: str,
        eks_cluster_name: str,
        approval_state_machine_arn: Optional[str] = None,
        region: str = "us-east-1",
    ):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.servicecatalog = boto3.client("servicecatalog", region_name=region)
        self.stepfunctions = boto3.client("stepfunctions", region_name=region)

        self.state_table = self.dynamodb.Table(state_table_name)
        self.cost_table = self.dynamodb.Table(cost_table_name)
        self.portfolio_id = portfolio_id
        self.approval_state_machine_arn = approval_state_machine_arn

        self.k8s_service = K8sNamespaceService(eks_cluster_name, region)

    async def create_environment(
        self,
        user_id: str,
        display_name: str,
        environment_type: EnvironmentType,
        template: EnvironmentTemplate,
        parameters: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Environment:
        """
        Create a new sandbox environment.

        Args:
            user_id: Owner user ID
            display_name: Human-readable name
            environment_type: Type of environment (QUICK, STANDARD, etc.)
            template: Template to use
            parameters: Optional template parameters
            tags: Optional custom tags

        Returns:
            Created Environment object

        Raises:
            QuotaExceededError: If user exceeds quota limits
        """
        # Validate quota
        await self._validate_quota(user_id, environment_type)

        # Generate environment ID
        environment_id = f"env-{uuid.uuid4().hex[:12]}"

        # Calculate TTL
        type_quota = DEFAULT_TYPE_QUOTAS[environment_type.value]
        expires_at = datetime.utcnow() + timedelta(hours=type_quota.max_ttl_hours)

        # Create environment record
        environment = Environment(
            environment_id=environment_id,
            user_id=user_id,
            display_name=display_name,
            environment_type=environment_type,
            template=template,
            status=EnvironmentStatus.PENDING_APPROVAL if type_quota.requires_approval else EnvironmentStatus.PROVISIONING,
            expires_at=expires_at,
            cost_estimate_daily=type_quota.estimated_hourly_cost * 24,
            tags=tags or {},
            metadata={"parameters": parameters or {}},
        )

        # Save to DynamoDB
        await self._save_environment(environment)

        # Route based on type
        if type_quota.requires_approval:
            # Start HITL approval workflow
            await self._start_approval_workflow(environment)
        else:
            # Provision immediately
            await self._provision_environment(environment)

        return environment

    async def _validate_quota(
        self, user_id: str, environment_type: EnvironmentType
    ) -> None:
        """Validate user hasn't exceeded quotas."""
        # Count active environments
        response = self.state_table.query(
            IndexName="user-created_at-index",
            KeyConditionExpression="user_id = :uid",
            FilterExpression="#s IN (:active, :prov, :pend)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":uid": user_id,
                ":active": EnvironmentStatus.ACTIVE.value,
                ":prov": EnvironmentStatus.PROVISIONING.value,
                ":pend": EnvironmentStatus.PENDING_APPROVAL.value,
            },
            Select="COUNT",
        )

        active_count = response.get("Count", 0)
        user_quota = UserQuota()  # Could load from user profile

        if active_count >= user_quota.max_concurrent_environments:
            raise QuotaExceededError(
                f"Maximum concurrent environments ({user_quota.max_concurrent_environments}) exceeded"
            )

        # Check type-specific quota
        type_quota = DEFAULT_TYPE_QUOTAS[environment_type.value]
        type_response = self.state_table.query(
            IndexName="user-created_at-index",
            KeyConditionExpression="user_id = :uid",
            FilterExpression="#s IN (:active, :prov, :pend) AND environment_type = :etype",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":uid": user_id,
                ":active": EnvironmentStatus.ACTIVE.value,
                ":prov": EnvironmentStatus.PROVISIONING.value,
                ":pend": EnvironmentStatus.PENDING_APPROVAL.value,
                ":etype": environment_type.value,
            },
            Select="COUNT",
        )

        type_count = type_response.get("Count", 0)
        if type_count >= type_quota.max_per_user:
            raise QuotaExceededError(
                f"Maximum {environment_type.value} environments ({type_quota.max_per_user}) exceeded"
            )

    async def _provision_environment(self, environment: Environment) -> None:
        """Provision the environment based on type."""
        if environment.environment_type == EnvironmentType.QUICK:
            # Use K8s namespace service
            namespace = await self.k8s_service.create_namespace(
                environment_id=environment.environment_id,
                user_id=environment.user_id,
                ttl_hours=4,
            )
            environment.namespace = namespace
            environment.status = EnvironmentStatus.ACTIVE
        else:
            # Use Service Catalog
            template_def = TEMPLATE_REGISTRY[environment.template.value]
            product_id = await self._get_product_id(environment.template)

            # Provision product
            response = self.servicecatalog.provision_product(
                ProductId=product_id,
                ProvisioningArtifactId=await self._get_artifact_id(product_id),
                ProvisionedProductName=f"sandbox-{environment.environment_id}",
                ProvisioningParameters=[
                    {"Key": k, "Value": v}
                    for k, v in (environment.metadata.get("parameters") or {}).items()
                ],
                Tags=[
                    {"Key": "SandboxEnvironment", "Value": "true"},
                    {"Key": "EnvironmentId", "Value": environment.environment_id},
                    {"Key": "UserId", "Value": environment.user_id},
                    {"Key": "TTL", "Value": environment.expires_at.isoformat()},
                ],
            )

            environment.stack_id = response["RecordDetail"]["ProvisionedProductId"]
            # Status remains PROVISIONING until callback confirms

        await self._save_environment(environment)

    async def _start_approval_workflow(self, environment: Environment) -> None:
        """Start HITL approval workflow via Step Functions."""
        if not self.approval_state_machine_arn:
            raise ValueError("Approval state machine ARN not configured")

        approval_id = f"approval-{uuid.uuid4().hex[:12]}"
        environment.approval_id = approval_id

        response = self.stepfunctions.start_execution(
            stateMachineArn=self.approval_state_machine_arn,
            name=approval_id,
            input=json.dumps({
                "approval_id": approval_id,
                "environment_id": environment.environment_id,
                "user_id": environment.user_id,
                "environment_type": environment.environment_type.value,
                "template": environment.template.value,
                "display_name": environment.display_name,
                "cost_estimate_daily": environment.cost_estimate_daily,
                "expires_at": environment.expires_at.isoformat(),
            }),
        )

        environment.metadata["execution_arn"] = response["executionArn"]
        await self._save_environment(environment)

    async def terminate_environment(
        self, environment_id: str, user_id: str, reason: Optional[str] = None
    ) -> Environment:
        """Terminate a sandbox environment."""
        environment = await self.get_environment(environment_id)

        # Verify ownership (unless admin)
        if environment.user_id != user_id:
            raise PermissionError("Not authorized to terminate this environment")

        environment.status = EnvironmentStatus.TERMINATING
        environment.terminated_at = datetime.utcnow()
        environment.metadata["termination_reason"] = reason
        await self._save_environment(environment)

        # Trigger cleanup based on type
        if environment.namespace:
            await self.k8s_service.delete_namespace(environment.namespace)

        if environment.stack_id:
            self.servicecatalog.terminate_provisioned_product(
                ProvisionedProductId=environment.stack_id,
                IgnoreErrors=True,
            )

        environment.status = EnvironmentStatus.TERMINATED
        await self._save_environment(environment)

        return environment

    async def list_environments(
        self, user_id: str, status_filter: Optional[List[EnvironmentStatus]] = None
    ) -> List[Environment]:
        """List environments for a user."""
        response = self.state_table.query(
            IndexName="user-created_at-index",
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,  # Most recent first
        )

        environments = [
            Environment(**item) for item in response.get("Items", [])
        ]

        if status_filter:
            environments = [e for e in environments if e.status in status_filter]

        return environments

    async def get_environment(self, environment_id: str) -> Environment:
        """Get environment by ID."""
        response = self.state_table.get_item(
            Key={"environment_id": environment_id}
        )

        if "Item" not in response:
            raise ValueError(f"Environment {environment_id} not found")

        return Environment(**response["Item"])

    async def _save_environment(self, environment: Environment) -> None:
        """Save environment to DynamoDB."""
        item = environment.model_dump()
        # Convert datetime to ISO string
        for key in ["created_at", "expires_at", "terminated_at"]:
            if item.get(key):
                item[key] = item[key].isoformat()

        # Set TTL for auto-cleanup (30 days after expiry)
        if environment.expires_at:
            ttl = int((environment.expires_at + timedelta(days=30)).timestamp())
            item["ttl"] = ttl

        self.state_table.put_item(Item=item)

    async def _get_product_id(self, template: EnvironmentTemplate) -> str:
        """Get Service Catalog product ID for template."""
        response = self.servicecatalog.search_products_as_admin(
            PortfolioId=self.portfolio_id,
            Filters={"FullTextSearch": [template.value]},
        )

        for product in response.get("ProductViewDetails", []):
            if template.value in product["ProductViewSummary"]["Name"].lower():
                return product["ProductViewSummary"]["ProductId"]

        raise ValueError(f"No product found for template {template.value}")

    async def _get_artifact_id(self, product_id: str) -> str:
        """Get latest provisioning artifact ID for product."""
        response = self.servicecatalog.describe_product_as_admin(
            Id=product_id
        )

        artifacts = response.get("ProvisioningArtifactSummaries", [])
        if not artifacts:
            raise ValueError(f"No artifacts found for product {product_id}")

        # Return most recent
        return sorted(artifacts, key=lambda x: x.get("CreatedTime", ""), reverse=True)[0]["Id"]
```

### K8s Namespace Service

```python
# src/services/sandbox/k8s_namespace_service.py

import logging
from typing import Optional, Dict, Any

import boto3
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class K8sNamespaceService:
    """
    Service for managing EKS namespaces for quick sandbox environments.

    Creates isolated namespaces with:
    - NetworkPolicies for pod isolation
    - ResourceQuotas for cost control
    - LimitRanges for default resource limits
    """

    def __init__(self, cluster_name: str, region: str = "us-east-1"):
        self.cluster_name = cluster_name
        self.region = region
        self._configure_kubernetes()

    def _configure_kubernetes(self) -> None:
        """Configure kubernetes client for EKS cluster."""
        eks = boto3.client("eks", region_name=self.region)

        # Get cluster info
        cluster_info = eks.describe_cluster(name=self.cluster_name)["cluster"]

        # Configure client
        configuration = client.Configuration()
        configuration.host = cluster_info["endpoint"]
        configuration.verify_ssl = True
        configuration.ssl_ca_cert = self._get_ca_cert(cluster_info["certificateAuthority"]["data"])

        # Get token for authentication
        token = self._get_eks_token()
        configuration.api_key = {"authorization": f"Bearer {token}"}

        client.Configuration.set_default(configuration)

        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()

    def _get_eks_token(self) -> str:
        """Get EKS authentication token."""
        sts = boto3.client("sts", region_name=self.region)

        # Generate presigned URL for token
        url = sts.generate_presigned_url(
            "get_caller_identity",
            HttpMethod="GET",
            Params={},
            ExpiresIn=60,
        )

        # EKS expects the token in a specific format
        import base64
        token = base64.urlsafe_b64encode(
            f"k8s-aws-v1.{base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')}".encode()
        ).decode().rstrip("=")

        return token

    def _get_ca_cert(self, ca_data: str) -> str:
        """Decode and save CA certificate."""
        import base64
        import tempfile

        ca_cert = base64.b64decode(ca_data)

        # Write to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".crt") as f:
            f.write(ca_cert)
            return f.name

    async def create_namespace(
        self,
        environment_id: str,
        user_id: str,
        ttl_hours: int = 4,
        resource_quota: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create isolated namespace for quick sandbox.

        Args:
            environment_id: Unique environment identifier
            user_id: Owner user ID
            ttl_hours: Time to live in hours
            resource_quota: Optional resource quota overrides

        Returns:
            Created namespace name
        """
        namespace_name = f"sandbox-{environment_id}"

        # Default resource quota
        default_quota = {
            "requests.cpu": "2",
            "requests.memory": "4Gi",
            "limits.cpu": "4",
            "limits.memory": "8Gi",
            "persistentvolumeclaims": "5",
            "pods": "20",
        }
        quota = {**default_quota, **(resource_quota or {})}

        # Create namespace
        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels={
                    "sandbox-environment": "true",
                    "environment-id": environment_id,
                    "user-id": user_id,
                    "ttl-hours": str(ttl_hours),
                },
                annotations={
                    "sandbox.platform/created-at": datetime.utcnow().isoformat(),
                    "sandbox.platform/expires-at": (
                        datetime.utcnow() + timedelta(hours=ttl_hours)
                    ).isoformat(),
                },
            )
        )

        try:
            self.core_v1.create_namespace(namespace)
            logger.info(f"Created namespace {namespace_name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.warning(f"Namespace {namespace_name} already exists")
            else:
                raise

        # Create resource quota
        resource_quota_obj = client.V1ResourceQuota(
            metadata=client.V1ObjectMeta(name="sandbox-quota"),
            spec=client.V1ResourceQuotaSpec(hard=quota),
        )

        try:
            self.core_v1.create_namespaced_resource_quota(
                namespace=namespace_name, body=resource_quota_obj
            )
        except ApiException as e:
            if e.status != 409:
                raise

        # Create network policy for isolation
        network_policy = client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(name="sandbox-isolation"),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(),  # All pods
                policy_types=["Ingress", "Egress"],
                ingress=[
                    client.V1NetworkPolicyIngressRule(
                        from_=[
                            client.V1NetworkPolicyPeer(
                                namespace_selector=client.V1LabelSelector(
                                    match_labels={"name": namespace_name}
                                )
                            )
                        ]
                    )
                ],
                egress=[
                    # Allow DNS
                    client.V1NetworkPolicyEgressRule(
                        to=[
                            client.V1NetworkPolicyPeer(
                                namespace_selector=client.V1LabelSelector(
                                    match_labels={"name": "kube-system"}
                                )
                            )
                        ],
                        ports=[
                            client.V1NetworkPolicyPort(port=53, protocol="UDP"),
                            client.V1NetworkPolicyPort(port=53, protocol="TCP"),
                        ],
                    ),
                    # Allow internal namespace
                    client.V1NetworkPolicyEgressRule(
                        to=[
                            client.V1NetworkPolicyPeer(
                                namespace_selector=client.V1LabelSelector(
                                    match_labels={"name": namespace_name}
                                )
                            )
                        ]
                    ),
                ],
            ),
        )

        try:
            self.networking_v1.create_namespaced_network_policy(
                namespace=namespace_name, body=network_policy
            )
        except ApiException as e:
            if e.status != 409:
                raise

        # Create limit range for default limits
        limit_range = client.V1LimitRange(
            metadata=client.V1ObjectMeta(name="sandbox-limits"),
            spec=client.V1LimitRangeSpec(
                limits=[
                    client.V1LimitRangeItem(
                        type="Container",
                        default={"cpu": "500m", "memory": "512Mi"},
                        default_request={"cpu": "100m", "memory": "128Mi"},
                        max={"cpu": "2", "memory": "4Gi"},
                    )
                ]
            ),
        )

        try:
            self.core_v1.create_namespaced_limit_range(
                namespace=namespace_name, body=limit_range
            )
        except ApiException as e:
            if e.status != 409:
                raise

        return namespace_name

    async def delete_namespace(self, namespace_name: str) -> None:
        """Delete namespace and all its resources."""
        try:
            self.core_v1.delete_namespace(
                name=namespace_name,
                body=client.V1DeleteOptions(
                    propagation_policy="Foreground",
                    grace_period_seconds=30,
                ),
            )
            logger.info(f"Deleted namespace {namespace_name}")
        except ApiException as e:
            if e.status != 404:
                raise
            logger.warning(f"Namespace {namespace_name} not found for deletion")

    async def list_sandboxes(self) -> List[Dict[str, Any]]:
        """List all sandbox namespaces."""
        namespaces = self.core_v1.list_namespace(
            label_selector="sandbox-environment=true"
        )

        return [
            {
                "namespace": ns.metadata.name,
                "environment_id": ns.metadata.labels.get("environment-id"),
                "user_id": ns.metadata.labels.get("user-id"),
                "created_at": ns.metadata.annotations.get("sandbox.platform/created-at"),
                "expires_at": ns.metadata.annotations.get("sandbox.platform/expires-at"),
            }
            for ns in namespaces.items
        ]
```

---

## Lambda Functions

### Environment Provisioner Lambda

```python
# src/lambda/environment_provisioner/handler.py

import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
servicecatalog = boto3.client("servicecatalog")
stepfunctions = boto3.client("stepfunctions")

STATE_TABLE = os.environ["STATE_TABLE_NAME"]
PORTFOLIO_ID = os.environ["PORTFOLIO_ID"]
APPROVAL_STATE_MACHINE = os.environ.get("APPROVAL_STATE_MACHINE_ARN")


def handler(event, context):
    """
    Lambda handler for environment provisioning requests.

    Triggered by API Gateway for POST /environments requests.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        body = json.loads(event.get("body", "{}"))
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]

        # Validate request
        required_fields = ["display_name", "environment_type", "template"]
        for field in required_fields:
            if field not in body:
                return response(400, {"error": f"Missing required field: {field}"})

        # Check quota
        table = dynamodb.Table(STATE_TABLE)
        active_count = get_active_count(table, user_id)

        if active_count >= 3:  # Max concurrent
            return response(429, {"error": "Quota exceeded: maximum 3 concurrent environments"})

        # Create environment record
        import uuid
        environment_id = f"env-{uuid.uuid4().hex[:12]}"

        environment_type = body["environment_type"]
        requires_approval = environment_type in ["extended", "compliance"]

        ttl_hours = {
            "quick": 4,
            "standard": 24,
            "extended": 168,
            "compliance": 168,
        }.get(environment_type, 24)

        expires_at = datetime.utcnow().isoformat() + f"+{ttl_hours}:00:00"

        item = {
            "environment_id": environment_id,
            "user_id": user_id,
            "display_name": body["display_name"],
            "environment_type": environment_type,
            "template": body["template"],
            "status": "pending_approval" if requires_approval else "provisioning",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
            "parameters": body.get("parameters", {}),
            "tags": body.get("tags", {}),
        }

        table.put_item(Item=item)

        if requires_approval:
            # Start approval workflow
            approval_id = f"approval-{uuid.uuid4().hex[:12]}"
            stepfunctions.start_execution(
                stateMachineArn=APPROVAL_STATE_MACHINE,
                name=approval_id,
                input=json.dumps({
                    "approval_id": approval_id,
                    "environment_id": environment_id,
                    "user_id": user_id,
                    "environment_type": environment_type,
                    "template": body["template"],
                    "display_name": body["display_name"],
                }),
            )

            # Update with approval ID
            table.update_item(
                Key={"environment_id": environment_id},
                UpdateExpression="SET approval_id = :aid",
                ExpressionAttributeValues={":aid": approval_id},
            )
        else:
            # Provision immediately
            provision_environment(environment_id, body["template"], body.get("parameters", {}))

        return response(201, {
            "environment_id": environment_id,
            "status": item["status"],
            "message": "Environment creation initiated" if not requires_approval else "Awaiting approval",
        })

    except Exception as e:
        logger.exception("Error processing request")
        return response(500, {"error": str(e)})


def get_active_count(table, user_id):
    """Count active environments for user."""
    response = table.query(
        IndexName="user-created_at-index",
        KeyConditionExpression="user_id = :uid",
        FilterExpression="#s IN (:active, :prov, :pend)",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":uid": user_id,
            ":active": "active",
            ":prov": "provisioning",
            ":pend": "pending_approval",
        },
        Select="COUNT",
    )
    return response.get("Count", 0)


def provision_environment(environment_id, template, parameters):
    """Provision Service Catalog product."""
    # Get product ID for template
    products = servicecatalog.search_products_as_admin(
        PortfolioId=PORTFOLIO_ID,
        Filters={"FullTextSearch": [template]},
    )

    product_id = None
    for product in products.get("ProductViewDetails", []):
        if template in product["ProductViewSummary"]["Name"].lower():
            product_id = product["ProductViewSummary"]["ProductId"]
            break

    if not product_id:
        raise ValueError(f"No product found for template: {template}")

    # Get artifact ID
    product_info = servicecatalog.describe_product_as_admin(Id=product_id)
    artifact_id = product_info["ProvisioningArtifactSummaries"][0]["Id"]

    # Provision
    servicecatalog.provision_product(
        ProductId=product_id,
        ProvisioningArtifactId=artifact_id,
        ProvisionedProductName=f"sandbox-{environment_id}",
        ProvisioningParameters=[
            {"Key": k, "Value": v} for k, v in parameters.items()
        ],
        Tags=[
            {"Key": "SandboxEnvironment", "Value": "true"},
            {"Key": "EnvironmentId", "Value": environment_id},
        ],
    )


def response(status_code, body):
    """Format API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
```

### Scheduled Cleanup Lambda

```python
# src/lambda/scheduled_cleanup/handler.py

import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
servicecatalog = boto3.client("servicecatalog")

STATE_TABLE = os.environ["STATE_TABLE_NAME"]


def handler(event, context):
    """
    Scheduled Lambda to cleanup expired environments.

    Triggered by EventBridge rule every 5 minutes.
    """
    logger.info("Starting scheduled cleanup")

    table = dynamodb.Table(STATE_TABLE)
    now = datetime.utcnow().isoformat()

    # Find expired active environments
    response = table.scan(
        FilterExpression="#s = :active AND expires_at < :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":active": "active",
            ":now": now,
        },
    )

    expired_environments = response.get("Items", [])
    logger.info(f"Found {len(expired_environments)} expired environments")

    terminated_count = 0
    error_count = 0

    for env in expired_environments:
        environment_id = env["environment_id"]

        try:
            # Update status to terminating
            table.update_item(
                Key={"environment_id": environment_id},
                UpdateExpression="SET #s = :term, terminated_at = :now, metadata.termination_reason = :reason",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":term": "terminating",
                    ":now": datetime.utcnow().isoformat(),
                    ":reason": "TTL expired",
                },
            )

            # Terminate Service Catalog product if exists
            stack_id = env.get("stack_id")
            if stack_id:
                try:
                    servicecatalog.terminate_provisioned_product(
                        ProvisionedProductId=stack_id,
                        IgnoreErrors=True,
                    )
                except Exception as e:
                    logger.warning(f"Failed to terminate SC product {stack_id}: {e}")

            # Update to terminated
            table.update_item(
                Key={"environment_id": environment_id},
                UpdateExpression="SET #s = :term",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":term": "terminated"},
            )

            terminated_count += 1
            logger.info(f"Terminated environment {environment_id}")

        except Exception as e:
            error_count += 1
            logger.exception(f"Error terminating {environment_id}: {e}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "terminated": terminated_count,
            "errors": error_count,
            "total_expired": len(expired_environments),
        }),
    }
```

---

## API Layer

### FastAPI Router

```python
# src/api/routes/environments.py

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...services.sandbox.environment_provisioning_service import (
    EnvironmentProvisioningService,
    QuotaExceededError,
)
from ...services.sandbox.models.environment import (
    Environment,
    EnvironmentType,
    EnvironmentStatus,
    EnvironmentTemplate,
)
from ..dependencies import get_current_user, get_provisioning_service

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


class CreateEnvironmentRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    environment_type: EnvironmentType
    template: EnvironmentTemplate
    parameters: Optional[dict] = None
    tags: Optional[dict] = None


class EnvironmentResponse(BaseModel):
    environment_id: str
    user_id: str
    display_name: str
    environment_type: EnvironmentType
    template: EnvironmentTemplate
    status: EnvironmentStatus
    created_at: datetime
    expires_at: Optional[datetime]
    cost_estimate_daily: float
    namespace: Optional[str] = None
    stack_id: Optional[str] = None


class QuotaResponse(BaseModel):
    max_concurrent: int
    current_active: int
    remaining: int
    monthly_budget_usd: float
    monthly_spent_usd: float


@router.post("", response_model=EnvironmentResponse, status_code=201)
async def create_environment(
    request: CreateEnvironmentRequest,
    user: dict = Depends(get_current_user),
    service: EnvironmentProvisioningService = Depends(get_provisioning_service),
):
    """Create a new sandbox environment."""
    try:
        environment = await service.create_environment(
            user_id=user["user_id"],
            display_name=request.display_name,
            environment_type=request.environment_type,
            template=request.template,
            parameters=request.parameters,
            tags=request.tags,
        )
        return EnvironmentResponse(**environment.model_dump())

    except QuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[EnvironmentResponse])
async def list_environments(
    status: Optional[List[EnvironmentStatus]] = Query(None),
    user: dict = Depends(get_current_user),
    service: EnvironmentProvisioningService = Depends(get_provisioning_service),
):
    """List user's environments."""
    environments = await service.list_environments(
        user_id=user["user_id"],
        status_filter=status,
    )
    return [EnvironmentResponse(**e.model_dump()) for e in environments]


@router.get("/{environment_id}", response_model=EnvironmentResponse)
async def get_environment(
    environment_id: str,
    user: dict = Depends(get_current_user),
    service: EnvironmentProvisioningService = Depends(get_provisioning_service),
):
    """Get environment details."""
    try:
        environment = await service.get_environment(environment_id)

        # Verify ownership
        if environment.user_id != user["user_id"] and not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Not authorized")

        return EnvironmentResponse(**environment.model_dump())

    except ValueError:
        raise HTTPException(status_code=404, detail="Environment not found")


@router.delete("/{environment_id}")
async def terminate_environment(
    environment_id: str,
    reason: Optional[str] = None,
    user: dict = Depends(get_current_user),
    service: EnvironmentProvisioningService = Depends(get_provisioning_service),
):
    """Terminate an environment."""
    try:
        environment = await service.terminate_environment(
            environment_id=environment_id,
            user_id=user["user_id"],
            reason=reason,
        )
        return {"message": "Environment terminated", "environment_id": environment_id}

    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized")
    except ValueError:
        raise HTTPException(status_code=404, detail="Environment not found")


@router.post("/{environment_id}/extend")
async def extend_environment(
    environment_id: str,
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(get_current_user),
    service: EnvironmentProvisioningService = Depends(get_provisioning_service),
):
    """Extend environment TTL."""
    try:
        environment = await service.extend_ttl(
            environment_id=environment_id,
            user_id=user["user_id"],
            additional_hours=hours,
        )
        return {
            "message": f"TTL extended by {hours} hours",
            "new_expires_at": environment.expires_at.isoformat(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quota", response_model=QuotaResponse)
async def get_quota(
    user: dict = Depends(get_current_user),
    service: EnvironmentProvisioningService = Depends(get_provisioning_service),
):
    """Get user's quota status."""
    quota = await service.get_user_quota(user["user_id"])
    return QuotaResponse(**quota)


@router.get("/templates", response_model=List[dict])
async def list_templates():
    """List available environment templates."""
    from ...services.sandbox.templates.registry import TEMPLATE_REGISTRY

    return [
        {
            "template_id": t.template_id,
            "display_name": t.display_name,
            "description": t.description,
            "category": t.category,
            "estimated_hourly_cost": t.estimated_hourly_cost,
            "included_services": t.included_services,
        }
        for t in TEMPLATE_REGISTRY.values()
    ]
```

---

## Air-Gapped Deployment Considerations

### 1. VPC Endpoints Configuration

```yaml
# deploy/cloudformation/vpc-endpoints-airgapped.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'VPC Endpoints for Air-Gapped Sandbox Deployment'

Parameters:
  VpcId:
    Type: AWS::EC2::VPC::Id
  PrivateSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
  SecurityGroupId:
    Type: AWS::EC2::SecurityGroup::Id

Resources:
  # Gateway Endpoints (free)
  S3Endpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.s3'
      VpcEndpointType: Gateway
      RouteTableIds:
        - !Ref PrivateRouteTable

  DynamoDBEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.dynamodb'
      VpcEndpointType: Gateway
      RouteTableIds:
        - !Ref PrivateRouteTable

  # Interface Endpoints (hourly cost)
  ECRAPIEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.ecr.api'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  ECRDKREndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.ecr.dkr'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  LambdaEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.lambda'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  StepFunctionsEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.states'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  ServiceCatalogEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.servicecatalog'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  SecretsManagerEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.secretsmanager'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  CloudWatchLogsEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.logs'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  SNSEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.sns'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true

  STSEndpoint:
    Type: AWS::EC2::VPCEndpoint
    Properties:
      VpcId: !Ref VpcId
      ServiceName: !Sub 'com.amazonaws.${AWS::Region}.sts'
      VpcEndpointType: Interface
      SubnetIds: !Ref PrivateSubnetIds
      SecurityGroupIds:
        - !Ref SecurityGroupId
      PrivateDnsEnabled: true
```

### 2. Private ECR Strategy

```bash
#!/bin/bash
# scripts/setup-private-ecr.sh
# Script to set up private ECR repositories for air-gapped deployment

set -e

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Create repositories
REPOS=(
    "sandbox-provisioner"
    "sandbox-cleanup"
    "sandbox-namespace-controller"
    "python-base"
    "node-base"
)

for repo in "${REPOS[@]}"; do
    echo "Creating repository: ${repo}"
    aws ecr create-repository \
        --repository-name "${repo}" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=KMS \
        --region "${AWS_REGION}" 2>/dev/null || echo "Repository ${repo} already exists"
done

# Pull, tag, and push base images
echo "Pulling and pushing base images..."

# Python base
docker pull python:3.11-slim
docker tag python:3.11-slim "${ECR_BASE}/python-base:3.11-slim"
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_BASE}"
docker push "${ECR_BASE}/python-base:3.11-slim"

# Node base
docker pull node:20-slim
docker tag node:20-slim "${ECR_BASE}/node-base:20-slim"
docker push "${ECR_BASE}/node-base:20-slim"

echo "Private ECR setup complete!"
echo "Base images available at:"
echo "  - ${ECR_BASE}/python-base:3.11-slim"
echo "  - ${ECR_BASE}/node-base:20-slim"
```

### 3. Offline Dependencies Bundle

```python
# scripts/bundle_dependencies.py
"""
Create offline dependencies bundle for air-gapped deployment.
Run this in an internet-connected environment, then transfer to air-gapped.
"""

import subprocess
import os
import shutil
from pathlib import Path

BUNDLE_DIR = Path("offline-bundle")
REQUIREMENTS = [
    "boto3>=1.28.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "pydantic>=2.0.0",
    "kubernetes>=28.1.0",
]


def create_bundle():
    """Create offline bundle with all dependencies."""
    # Clean and create bundle directory
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True)

    wheels_dir = BUNDLE_DIR / "wheels"
    wheels_dir.mkdir()

    # Download all wheels
    print("Downloading Python packages...")
    subprocess.run([
        "pip", "download",
        "--dest", str(wheels_dir),
        "--platform", "manylinux2014_x86_64",
        "--python-version", "311",
        "--only-binary", ":all:",
    ] + REQUIREMENTS, check=True)

    # Create requirements file
    with open(BUNDLE_DIR / "requirements.txt", "w") as f:
        f.write("\n".join(REQUIREMENTS))

    # Create install script
    install_script = """#!/bin/bash
# Install dependencies from offline bundle
pip install --no-index --find-links=./wheels -r requirements.txt
"""
    with open(BUNDLE_DIR / "install.sh", "w") as f:
        f.write(install_script)
    os.chmod(BUNDLE_DIR / "install.sh", 0o755)

    # Create tar bundle
    print("Creating tar bundle...")
    subprocess.run([
        "tar", "-czvf", "sandbox-offline-bundle.tar.gz",
        "-C", str(BUNDLE_DIR.parent), str(BUNDLE_DIR.name)
    ], check=True)

    print(f"Bundle created: sandbox-offline-bundle.tar.gz")
    print(f"Transfer this file to your air-gapped environment")


if __name__ == "__main__":
    create_bundle()
```

### 4. Air-Gapped Deployment Checklist

```markdown
## Pre-Deployment Checklist

### Network Configuration
- [ ] VPC created with private subnets
- [ ] No NAT Gateway or Internet Gateway attached
- [ ] All required VPC endpoints created and verified
- [ ] Security groups allow HTTPS (443) to VPC endpoints
- [ ] DNS resolution working for AWS service endpoints

### ECR Setup
- [ ] All base images pulled and pushed to private ECR
- [ ] ECR repositories have image scanning enabled
- [ ] ECR lifecycle policies configured for cleanup
- [ ] Lambda images built and pushed

### S3 Artifacts
- [ ] CloudFormation templates uploaded to S3
- [ ] Service Catalog product templates in S3
- [ ] Offline dependency bundle in S3 (if needed)

### IAM Configuration
- [ ] Permission boundary policy created
- [ ] Lambda execution roles created
- [ ] Service Catalog launch role created
- [ ] EKS access entries configured

### Secrets
- [ ] All secrets stored in Secrets Manager
- [ ] KMS keys created with rotation enabled
- [ ] No hardcoded credentials in code or templates

### Validation
- [ ] Can create EKS namespace without internet
- [ ] Can provision Service Catalog product without internet
- [ ] Lambda functions execute successfully
- [ ] CloudWatch logs appearing
- [ ] SNS notifications working
```

---

## Security Architecture

### 10 Security Guardrails

| # | Guardrail | Implementation |
|---|-----------|----------------|
| 1 | **Permission Boundary** | All sandbox roles use permission boundary that denies production access |
| 2 | **Network Isolation** | K8s NetworkPolicies restrict pod-to-pod communication |
| 3 | **Resource Quotas** | K8s ResourceQuotas limit CPU/memory/storage per namespace |
| 4 | **Cost Controls** | AWS Budgets with alerts at 80%, 100%, 120% thresholds |
| 5 | **TTL Enforcement** | Automatic cleanup via scheduled Lambda |
| 6 | **HITL Approval** | Extended/compliance environments require human approval |
| 7 | **Audit Logging** | CloudTrail logs all API calls |
| 8 | **Encryption at Rest** | KMS encryption for DynamoDB, S3, EBS |
| 9 | **Encryption in Transit** | TLS 1.2+ for all API communication |
| 10 | **Tag Enforcement** | All resources tagged with SandboxEnvironment=true |

### IAM Least Privilege Example

```yaml
# Minimal IAM policy for sandbox user
SandboxUserPolicy:
  Version: '2012-10-17'
  Statement:
    # Only allow operations on own environments
    - Sid: ReadOwnEnvironments
      Effect: Allow
      Action:
        - 'dynamodb:GetItem'
        - 'dynamodb:Query'
      Resource: !Sub 'arn:${AWS::Partition}:dynamodb:*:*:table/${ProjectName}-env-state-*'
      Condition:
        ForAllValues:StringEquals:
          'dynamodb:LeadingKeys':
            - '${aws:userid}'

    # Deny production resources
    - Sid: DenyProduction
      Effect: Deny
      Action: '*'
      Resource:
        - 'arn:*:*:*:*:*prod*'
        - 'arn:*:*:*:*:*production*'
```

---

## Monitoring and Observability

### CloudWatch Dashboard

```yaml
# deploy/cloudformation/sandbox-monitoring.yaml
Resources:
  SandboxDashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: !Sub '${ProjectName}-sandbox-${Environment}'
      DashboardBody: !Sub |
        {
          "widgets": [
            {
              "type": "metric",
              "properties": {
                "title": "Active Environments",
                "metrics": [
                  ["${ProjectName}/Sandbox", "ActiveEnvironments"]
                ],
                "period": 300
              }
            },
            {
              "type": "metric",
              "properties": {
                "title": "Daily Cost Estimate",
                "metrics": [
                  ["${ProjectName}/Sandbox", "EstimatedDailyCost"]
                ],
                "period": 3600
              }
            },
            {
              "type": "metric",
              "properties": {
                "title": "Provisioning Errors",
                "metrics": [
                  ["${ProjectName}/Sandbox", "ProvisioningErrors"]
                ],
                "period": 300,
                "stat": "Sum"
              }
            },
            {
              "type": "metric",
              "properties": {
                "title": "Provisioning Duration",
                "metrics": [
                  ["${ProjectName}/Sandbox", "ProvisioningDuration"]
                ],
                "period": 300,
                "stat": "p90"
              }
            }
          ]
        }

  # Alarms
  HighCostAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-sandbox-high-cost-${Environment}'
      MetricName: EstimatedDailyCost
      Namespace: !Sub '${ProjectName}/Sandbox'
      Statistic: Maximum
      Period: 3600
      EvaluationPeriods: 1
      Threshold: 50
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref AlertTopic

  ProvisioningErrorsAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-sandbox-provisioning-errors-${Environment}'
      MetricName: ProvisioningErrors
      Namespace: !Sub '${ProjectName}/Sandbox'
      Statistic: Sum
      Period: 600
      EvaluationPeriods: 1
      Threshold: 5
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref AlertTopic

  AlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub '${ProjectName}-sandbox-alerts-${Environment}'
```

---

## Testing Procedures

### Unit Tests

```python
# tests/unit/test_environment_provisioning_service.py

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.services.sandbox.environment_provisioning_service import (
    EnvironmentProvisioningService,
    QuotaExceededError,
)
from src.services.sandbox.models.environment import (
    EnvironmentType,
    EnvironmentStatus,
    EnvironmentTemplate,
)


@pytest.fixture
def mock_dynamodb():
    with patch("boto3.resource") as mock:
        yield mock


@pytest.fixture
def service(mock_dynamodb):
    return EnvironmentProvisioningService(
        state_table_name="test-state-table",
        cost_table_name="test-cost-table",
        portfolio_id="port-123",
        eks_cluster_name="test-cluster",
    )


class TestQuotaValidation:
    @pytest.mark.asyncio
    async def test_quota_exceeded_raises_error(self, service, mock_dynamodb):
        # Setup: User has 3 active environments
        mock_table = Mock()
        mock_table.query.return_value = {"Count": 3}
        service.state_table = mock_table

        with pytest.raises(QuotaExceededError) as exc:
            await service._validate_quota("user-123", EnvironmentType.STANDARD)

        assert "maximum 3 concurrent" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_quota_allows_creation_when_under_limit(self, service):
        mock_table = Mock()
        mock_table.query.return_value = {"Count": 1}
        service.state_table = mock_table

        # Should not raise
        await service._validate_quota("user-123", EnvironmentType.STANDARD)


class TestEnvironmentCreation:
    @pytest.mark.asyncio
    async def test_quick_environment_skips_approval(self, service):
        service._validate_quota = AsyncMock()
        service._save_environment = AsyncMock()
        service._provision_environment = AsyncMock()
        service._start_approval_workflow = AsyncMock()

        env = await service.create_environment(
            user_id="user-123",
            display_name="Test Env",
            environment_type=EnvironmentType.QUICK,
            template=EnvironmentTemplate.PYTHON_FASTAPI,
        )

        assert env.status == EnvironmentStatus.PROVISIONING
        service._provision_environment.assert_called_once()
        service._start_approval_workflow.assert_not_called()

    @pytest.mark.asyncio
    async def test_extended_environment_requires_approval(self, service):
        service._validate_quota = AsyncMock()
        service._save_environment = AsyncMock()
        service._provision_environment = AsyncMock()
        service._start_approval_workflow = AsyncMock()
        service.approval_state_machine_arn = "arn:aws:states:..."

        env = await service.create_environment(
            user_id="user-123",
            display_name="Test Env",
            environment_type=EnvironmentType.EXTENDED,
            template=EnvironmentTemplate.FULL_STACK,
        )

        assert env.status == EnvironmentStatus.PENDING_APPROVAL
        service._start_approval_workflow.assert_called_once()
        service._provision_environment.assert_not_called()
```

### Integration Tests

```python
# tests/integration/test_sandbox_e2e.py

import pytest
import boto3
import time
from datetime import datetime

# Skip if not in integration test mode
pytestmark = pytest.mark.integration


class TestSandboxE2E:
    @pytest.fixture(scope="class")
    def dynamodb(self):
        return boto3.resource("dynamodb", region_name="us-east-1")

    @pytest.fixture(scope="class")
    def state_table(self, dynamodb):
        return dynamodb.Table("sandbox-env-state-dev")

    def test_create_quick_environment(self, state_table):
        """Test creating a quick environment end-to-end."""
        import uuid

        environment_id = f"test-env-{uuid.uuid4().hex[:8]}"

        # Create environment record
        item = {
            "environment_id": environment_id,
            "user_id": "test-user",
            "display_name": "Integration Test Env",
            "environment_type": "quick",
            "template": "python-fastapi",
            "status": "provisioning",
            "created_at": datetime.utcnow().isoformat(),
        }

        state_table.put_item(Item=item)

        # Verify it was created
        response = state_table.get_item(Key={"environment_id": environment_id})
        assert "Item" in response
        assert response["Item"]["status"] == "provisioning"

        # Cleanup
        state_table.delete_item(Key={"environment_id": environment_id})

    def test_quota_enforcement(self, state_table):
        """Test that quota is enforced."""
        import uuid

        user_id = f"quota-test-{uuid.uuid4().hex[:8]}"
        env_ids = []

        try:
            # Create 3 environments (max allowed)
            for i in range(3):
                env_id = f"test-env-{uuid.uuid4().hex[:8]}"
                env_ids.append(env_id)

                state_table.put_item(Item={
                    "environment_id": env_id,
                    "user_id": user_id,
                    "display_name": f"Test {i}",
                    "environment_type": "quick",
                    "template": "python-fastapi",
                    "status": "active",
                    "created_at": datetime.utcnow().isoformat(),
                })

            # Verify count
            response = state_table.query(
                IndexName="user-created_at-index",
                KeyConditionExpression="user_id = :uid",
                FilterExpression="#s = :active",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":uid": user_id,
                    ":active": "active",
                },
                Select="COUNT",
            )

            assert response["Count"] == 3

        finally:
            # Cleanup
            for env_id in env_ids:
                state_table.delete_item(Key={"environment_id": env_id})
```

---

## Operational Runbook

### Common Operations

#### List All Active Environments

```bash
aws dynamodb scan \
  --table-name sandbox-env-state-dev \
  --filter-expression "#s = :active" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":active": {"S": "active"}}' \
  --query "Items[*].{id: environment_id.S, user: user_id.S, expires: expires_at.S}" \
  --output table
```

#### Manually Terminate Environment

```bash
ENV_ID="env-abc123"
aws dynamodb update-item \
  --table-name sandbox-env-state-dev \
  --key '{"environment_id": {"S": "'$ENV_ID'"}}' \
  --update-expression "SET #s = :term" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":term": {"S": "terminated"}}'
```

#### Check User Quota

```bash
USER_ID="user-123"
aws dynamodb query \
  --table-name sandbox-env-state-dev \
  --index-name user-created_at-index \
  --key-condition-expression "user_id = :uid" \
  --filter-expression "#s IN (:active, :prov)" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":uid": {"S": "'$USER_ID'"}, ":active": {"S": "active"}, ":prov": {"S": "provisioning"}}' \
  --select COUNT
```

### Troubleshooting

#### Environment Stuck in Provisioning

1. Check Lambda logs:

   ```bash
   aws logs tail /aws/lambda/sandbox-provisioner-dev --since 30m
   ```

2. Check Service Catalog status:

   ```bash
   aws servicecatalog describe-provisioned-product \
     --name "sandbox-env-abc123"
   ```

3. Check CloudFormation stack:

   ```bash
   aws cloudformation describe-stacks \
     --query "Stacks[?contains(StackName, 'sandbox')].[StackName,StackStatus]" \
     --output table
   ```

#### VPC Endpoint Issues (Air-Gapped)

1. Test connectivity:

   ```bash
   # From within VPC
   aws s3 ls --endpoint-url https://s3.us-east-1.amazonaws.com
   aws dynamodb list-tables --endpoint-url https://dynamodb.us-east-1.amazonaws.com
   ```

2. Check endpoint status:

   ```bash
   aws ec2 describe-vpc-endpoints \
     --query "VpcEndpoints[*].[ServiceName,State]" \
     --output table
   ```

3. Verify security groups allow HTTPS (443) to endpoints.

---

## Deployment Order

Execute CloudFormation stacks in this order:

1. **Foundation**
   - `vpc-endpoints-airgapped.yaml` (if air-gapped)
   - `sandbox-state.yaml`
   - `sandbox-iam.yaml`

2. **Service Catalog**
   - `sandbox-catalog.yaml`
   - Upload product templates to S3

3. **Lambda Functions**
   - Build and push images to ECR
   - Deploy Lambda functions

4. **API Gateway**
   - Configure routes
   - Deploy API

5. **Monitoring**
   - `sandbox-monitoring.yaml`
   - Configure alarms and dashboards

6. **Validation**
   - Run integration tests
   - Verify end-to-end flow

---

## Summary

This runbook provides a complete implementation guide for replicating Aura's self-service sandbox provisioning capability. The key components are:

1. **EnvironmentProvisioningService** - Core service managing environment lifecycle
2. **K8sNamespaceService** - EKS namespace management for quick environments
3. **Service Catalog Portfolio** - Pre-built environment templates
4. **IAM Permission Boundary** - Security guardrail preventing production access
5. **Lambda Functions** - Serverless provisioning and cleanup
6. **VPC Endpoints** - Air-gapped deployment support

For questions or issues, refer to the troubleshooting section or contact the Platform Team.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-05

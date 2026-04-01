# AWS Naming Conventions & Tagging Standards
## Project Aura Infrastructure Standards

**Version:** 1.1
**Last Updated:** January 2026
**Status:** Official Standard

---

## Why This Matters

Proper naming and tagging:
- ✅ Makes resources easy to find and identify
- ✅ Enables accurate cost tracking by environment/project
- ✅ Simplifies automation and scripts
- ✅ Required for compliance (SOX, CMMC)
- ✅ Prevents accidental deletion of critical resources
- ✅ Enables proper IAM policies and resource filtering

---

## Table of Contents

1. [Naming Conventions](#naming-conventions)
2. [Tagging Standards](#tagging-standards)
3. [Resource-Specific Examples](#resource-specific-examples)
4. [Implementation Checklist](#implementation-checklist)
5. [Automation](#automation)

---

## Naming Conventions

### General Pattern

```
{project}-{resource-type}-{environment}-{description}-{region}
```

**Components:**
- `{project}`: `aura` (always lowercase)
- `{resource-type}`: See table below
- `{environment}`: `dev`, `staging`, `prod`
- `{description}`: Brief descriptor (optional)
- `{region}`: `use1` (us-east-1), `usw2` (us-west-2), etc.

### Resource Type Abbreviations

| AWS Service | Abbreviation | Example |
|-------------|--------------|---------|
| IAM Role | `role` | `aura-role-prod-bedrock` |
| IAM Policy | `policy` | `aura-policy-prod-bedrock` |
| IAM User | `user` | `aura-user-dev-admin` |
| IAM Instance Profile | `profile` | `aura-profile-prod-ecs` |
| DynamoDB Table | `ddb` | `aura-ddb-prod-llm-costs` |
| S3 Bucket | `s3` | `aura-s3-prod-artifacts-use1` |
| Lambda Function | `lambda` | `aura-lambda-prod-approval` |
| ECS Cluster | `ecs` | `aura-ecs-prod-use1` |
| ECS Service | `svc` | `aura-svc-prod-orchestrator` |
| ECS Task Definition | `task` | `aura-task-prod-orchestrator` |
| EC2 Instance | `ec2` | `aura-ec2-dev-bastion` |
| VPC | `vpc` | `aura-vpc-prod-use1` |
| Subnet | `subnet` | `aura-subnet-prod-private-1a` |
| Security Group | `sg` | `aura-sg-prod-ecs` |
| CloudWatch Log Group | `logs` | `/aws/aura/prod/orchestrator` |
| SNS Topic | `sns` | `aura-sns-prod-budget-alerts` |
| SQS Queue | `sqs` | `aura-sqs-prod-tasks` |
| Secrets Manager | `secret` | `aura/prod/bedrock` (uses `/`) |
| CloudFormation Stack | `stack` | `aura-stack-prod-infra` |
| Neptune Cluster | `neptune` | `aura-neptune-prod-use1` |
| OpenSearch Domain | `os` | `aura-os-prod-use1` |
| ALB/NLB | `alb`/`nlb` | `aura-alb-prod-api` |
| CloudWatch Alarm | `alarm` | `aura-alarm-prod-budget-critical` |

### Special Cases

**Secrets Manager:** Uses forward slashes
```
aura/{environment}/{service}
Example: aura/prod/bedrock
         aura/dev/database
```

**CloudWatch Logs:** Uses forward slashes with `/aws/` prefix
```
/aws/aura/{environment}/{service}
Example: /aws/aura/prod/orchestrator
         /aws/aura/dev/lambda/approval
```

**S3 Buckets:** Must be globally unique, include region
```
{project}-{type}-{environment}-{purpose}-{account-id}-{region}
Example: aura-s3-prod-artifacts-123456789012-use1
         aura-s3-dev-logs-123456789012-use1
```

**IAM Resources:** No region (global)
```
{project}-{type}-{environment}-{description}
Example: aura-role-prod-bedrock-service
         aura-policy-dev-bedrock-access
```

**CloudFormation Stacks:** Standard naming for CI/CD deployments
```
{project}-{resource-name}-{environment}
Example: aura-neptune-dev
         aura-eks-qa
         aura-codebuild-application-prod
```

The stack name is derived from the template filename:
| Template File | Stack Name Pattern |
|---------------|-------------------|
| `neptune.yaml` | `aura-neptune-{env}` |
| `codebuild-application.yaml` | `aura-codebuild-application-{env}` |
| `codebuild-application-identity.yaml` | `aura-codebuild-application-identity-{env}` |
| `irsa-memory-service.yaml` | `aura-irsa-memory-service-{env}` |

**Layer-Based CodeBuild Naming:**
```
{project}-{layer}-deploy-{environment}
Example: aura-foundation-deploy-dev
         aura-compute-deploy-qa
         aura-serverless-deploy-prod
```

---

## Tagging Standards

### Mandatory Tags (All Resources)

Every resource **must** have these tags:

| Tag Key | Description | Example Values | Required |
|---------|-------------|----------------|----------|
| `Project` | Project name | `Aura` | ✅ Yes |
| `Environment` | Deployment environment | `development`, `staging`, `production` | ✅ Yes |
| `Owner` | Team or person responsible | `security-team`, `team-owner@company.com` | ✅ Yes |
| `CostCenter` | For billing/chargeback | `engineering`, `r-and-d`, `security` | ✅ Yes |
| `ManagedBy` | How resource is managed | `CloudFormation`, `Terraform`, `Manual` | ✅ Yes |

### Recommended Tags

| Tag Key | Description | Example Values | Required |
|---------|-------------|----------------|----------|
| `Name` | Human-readable name | `Aura LLM Cost Tracker` | ⭐ Recommended |
| `Application` | Application component | `orchestrator`, `bedrock-service` | ⭐ Recommended |
| `Version` | Application version | `v1.0.0`, `2024-11-15` | Optional |
| `Compliance` | Compliance requirements | `SOX`, `CMMC`, `HIPAA` | Optional |
| `DataClassification` | Sensitivity level | `public`, `internal`, `confidential`, `restricted` | Optional |
| `BackupPolicy` | Backup requirements | `daily`, `weekly`, `none` | Optional |
| `Automation` | Automation identifier | `jenkins-job-123`, `github-actions` | Optional |

### Optional Tags (Use Case Specific)

| Tag Key | Description | Example Values |
|---------|-------------|----------------|
| `Schedule` | Operating schedule | `24x7`, `business-hours`, `on-demand` |
| `Monitoring` | Monitoring level | `critical`, `standard`, `minimal` |
| `SLA` | Service level agreement | `tier-1`, `tier-2`, `tier-3` |
| `Contact` | Emergency contact | `slack-channel`, `pagerduty-key` |

---

## Resource-Specific Examples

### IAM Role (Bedrock Service)

**Name:** `aura-role-prod-bedrock-service`

**Tags:**
```json
{
  "Name": "Aura Bedrock Service Role",
  "Project": "Aura",
  "Environment": "production",
  "Owner": "security-team@company.com",
  "CostCenter": "r-and-d",
  "ManagedBy": "CloudFormation",
  "Application": "bedrock-service",
  "Compliance": "SOX,CMMC",
  "DataClassification": "internal"
}
```

**CloudFormation:**
```yaml
AuraServiceRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: aura-role-prod-bedrock-service
    Tags:
      - Key: Name
        Value: Aura Bedrock Service Role
      - Key: Project
        Value: Aura
      - Key: Environment
        Value: production
      - Key: Owner
        Value: security-team@company.com
      - Key: CostCenter
        Value: r-and-d
      - Key: ManagedBy
        Value: CloudFormation
      - Key: Application
        Value: bedrock-service
```

### DynamoDB Table (Cost Tracking)

**Name:** `aura-ddb-prod-llm-costs`

**Tags:**
```json
{
  "Name": "Aura LLM Cost Tracking",
  "Project": "Aura",
  "Environment": "production",
  "Owner": "team-owner@company.com",
  "CostCenter": "r-and-d",
  "ManagedBy": "CloudFormation",
  "Application": "cost-tracking",
  "BackupPolicy": "daily",
  "DataClassification": "internal",
  "Compliance": "SOX"
}
```

### S3 Bucket (Artifacts)

**Name:** `aura-s3-prod-artifacts-123456789012-use1`

**Tags:**
```json
{
  "Name": "Aura Artifacts Bucket",
  "Project": "Aura",
  "Environment": "production",
  "Owner": "devops@company.com",
  "CostCenter": "engineering",
  "ManagedBy": "CloudFormation",
  "Application": "storage",
  "DataClassification": "internal",
  "BackupPolicy": "versioning-enabled"
}
```

### Lambda Function (Approval Service)

**Name:** `aura-lambda-prod-approval-service`

**Tags:**
```json
{
  "Name": "Aura Approval Service",
  "Project": "Aura",
  "Environment": "production",
  "Owner": "security-team@company.com",
  "CostCenter": "security",
  "ManagedBy": "CloudFormation",
  "Application": "hitl-approval",
  "Version": "v1.0.0",
  "Monitoring": "critical",
  "Schedule": "24x7"
}
```

### SNS Topic (Budget Alerts)

**Name:** `aura-sns-prod-budget-alerts`

**Tags:**
```json
{
  "Name": "Aura Budget Alert Topic",
  "Project": "Aura",
  "Environment": "production",
  "Owner": "finance@company.com",
  "CostCenter": "r-and-d",
  "ManagedBy": "CloudFormation",
  "Application": "monitoring",
  "Contact": "slack-#aura-alerts"
}
```

### CloudWatch Log Group

**Name:** `/aws/aura/prod/orchestrator`

**Tags:**
```json
{
  "Name": "Aura Orchestrator Logs",
  "Project": "Aura",
  "Environment": "production",
  "Owner": "devops@company.com",
  "CostCenter": "engineering",
  "ManagedBy": "CloudFormation",
  "Application": "orchestrator",
  "DataClassification": "internal"
}
```

---

## Environment-Specific Conventions

### Development (`dev`)

**Naming:** `aura-{resource}-dev-{description}`

**Tags:**
```json
{
  "Environment": "development",
  "Owner": "engineering@company.com",
  "CostCenter": "r-and-d",
  "Schedule": "business-hours",  // Can be shut down nights/weekends
  "DataClassification": "internal"
}
```

**Characteristics:**
- Can be destroyed/recreated frequently
- Lower retention periods (logs: 7 days)
- Smaller instance sizes
- Less critical monitoring

### Staging (`staging`)

**Naming:** `aura-{resource}-staging-{description}`

**Tags:**
```json
{
  "Environment": "staging",
  "Owner": "qa@company.com",
  "CostCenter": "r-and-d",
  "Schedule": "business-hours-plus",  // Extended hours
  "DataClassification": "internal"
}
```

**Characteristics:**
- Production-like configuration
- Medium retention periods (logs: 30 days)
- Production-equivalent instance sizes
- Standard monitoring

### Production (`prod`)

**Naming:** `aura-{resource}-prod-{description}`

**Tags:**
```json
{
  "Environment": "production",
  "Owner": "security-team@company.com",
  "CostCenter": "security",
  "Schedule": "24x7",
  "Monitoring": "critical",
  "Compliance": "SOX,CMMC",
  "BackupPolicy": "daily",
  "DataClassification": "confidential"
}
```

**Characteristics:**
- Never destroy without approval
- Long retention periods (logs: 90+ days)
- Proper sizing for load
- Critical monitoring and alerting
- Disaster recovery configured

---

## Implementation Checklist

### Phase 1: Update Existing Resources

- [ ] **IAM Resources**
  - [ ] Rename `AuraBedrockServiceRole` → `aura-role-prod-bedrock-service`
  - [ ] Rename `AuraBedrockPolicy` → `aura-policy-prod-bedrock`
  - [ ] Add mandatory tags to all IAM resources

- [ ] **DynamoDB**
  - [ ] Rename `aura-llm-costs` → `aura-ddb-prod-llm-costs`
  - [ ] Add mandatory tags

- [ ] **Secrets Manager**
  - [ ] Verify naming: `aura/prod/bedrock` ✓ (already correct)
  - [ ] Add tags

- [ ] **SNS Topics**
  - [ ] Rename `aura-budget-alerts` → `aura-sns-prod-budget-alerts`
  - [ ] Add tags

- [ ] **CloudWatch Alarms**
  - [ ] Rename to `aura-alarm-prod-daily-budget-warning`
  - [ ] Add tags

### Phase 2: Update CloudFormation Template

- [ ] Update all resource names to follow conventions
- [ ] Add tags to all resources
- [ ] Add `Name` tag for human-readable identification
- [ ] Test deployment in dev environment

### Phase 3: Create Naming Enforcement

- [ ] Add AWS Config rules to enforce tagging
- [ ] Create Lambda function to auto-tag untagged resources
- [ ] Set up CloudWatch Events for tag compliance

---

## Automation

### CloudFormation: Tag All Resources Automatically

```yaml
# In your CloudFormation template
Parameters:
  Environment:
    Type: String
    Default: production
    AllowedValues:
      - development
      - staging
      - production

  Owner:
    Type: String
    Default: security-team@company.com

  CostCenter:
    Type: String
    Default: r-and-d

# Global tags applied to ALL resources
Tags:
  - Key: Project
    Value: Aura
  - Key: Environment
    Value: !Ref Environment
  - Key: Owner
    Value: !Ref Owner
  - Key: CostCenter
    Value: !Ref CostCenter
  - Key: ManagedBy
    Value: CloudFormation

# Then individual resources inherit these + add their own
Resources:
  MyDynamoDBTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub 'aura-ddb-${Environment}-llm-costs'
      Tags:
        # Inherits global tags automatically
        - Key: Name
          Value: Aura LLM Cost Tracking
        - Key: Application
          Value: cost-tracking
```

### AWS Config Rule: Enforce Required Tags

```yaml
RequiredTagsConfigRule:
  Type: AWS::Config::ConfigRule
  Properties:
    ConfigRuleName: aura-required-tags
    Description: Ensures all resources have required tags
    Source:
      Owner: AWS
      SourceIdentifier: REQUIRED_TAGS
    InputParameters:
      tag1Key: Project
      tag2Key: Environment
      tag3Key: Owner
      tag4Key: CostCenter
      tag5Key: ManagedBy
```

### Lambda: Auto-Tag Untagged Resources

```python
# Lambda function triggered by CloudWatch Events
import boto3

def lambda_handler(event, context):
    """Auto-tag newly created resources with default tags."""

    resource_arn = event['detail']['responseElements']['resourceArn']

    default_tags = {
        'Project': 'Aura',
        'Environment': 'production',
        'Owner': 'auto-tagged@company.com',
        'CostCenter': 'engineering',
        'ManagedBy': 'Lambda-AutoTag'
    }

    # Tag the resource
    client = boto3.client('resourcegroupstaggingapi')
    client.tag_resources(
        ResourceARNList=[resource_arn],
        Tags=default_tags
    )
```

---

## Cost Reporting by Tags

### Query Costs by Environment

```bash
# AWS CLI: Get costs for production environment
aws ce get-cost-and-usage \
  --time-period Start=2024-11-01,End=2024-11-30 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=TAG,Key=Environment \
  --filter file://filter.json

# filter.json
{
  "Tags": {
    "Key": "Project",
    "Values": ["Aura"]
  }
}
```

### Cost Allocation Report Example

| Environment | CostCenter | Monthly Cost | % of Total |
|-------------|-----------|--------------|------------|
| production | security | $1,245.67 | 65% |
| staging | r-and-d | $456.23 | 24% |
| development | engineering | $210.45 | 11% |
| **Total** | | **$1,912.35** | **100%** |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│         PROJECT AURA - NAMING QUICK REFERENCE           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Pattern: aura-{type}-{env}-{description}               │
│                                                         │
│  Examples:                                              │
│    IAM Role:      aura-role-prod-bedrock-service        │
│    DynamoDB:      aura-ddb-prod-llm-costs               │
│    Lambda:        aura-lambda-prod-approval             │
│    S3:            aura-s3-prod-logs-{account}-use1      │
│    SNS:           aura-sns-prod-budget-alerts           │
│    Secret:        aura/prod/bedrock                     │
│    Logs:          /aws/aura/prod/orchestrator           │
│                                                         │
│  Mandatory Tags:                                        │
│    • Project: Aura                                      │
│    • Environment: production/staging/development        │
│    • Owner: email@company.com                           │
│    • CostCenter: r-and-d/security/engineering           │
│    • ManagedBy: CloudFormation/Terraform/Manual         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Benefits of This Standard

**Organization:**
- ✅ Find resources instantly (filter by tags)
- ✅ Know what every resource does at a glance
- ✅ Understand dependencies (same tags = related)

**Cost Management:**
- ✅ Track spending by environment/team/project
- ✅ Chargeback to correct cost centers
- ✅ Identify cost optimization opportunities

**Security & Compliance:**
- ✅ Audit who owns what
- ✅ Track data classification
- ✅ SOX/CMMC compliance evidence

**Operations:**
- ✅ Automate resource management
- ✅ Prevent accidental deletion (by Owner tag)
- ✅ Schedule start/stop based on tags

**Team Collaboration:**
- ✅ Everyone follows same pattern
- ✅ New team members onboard faster
- ✅ Less confusion and mistakes

---

## Document Updates

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | Nov 2025 | Initial standard | Project Aura Team |

**Next Review:** January 2026 or when adding new AWS services

---

**Questions?** Update this document via pull request or discuss in #aura-infrastructure Slack channel.

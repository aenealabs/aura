# ADR-059: AWS Organization Account Restructure

| Status | Accepted |
|--------|----------|
| Date | 2026-01-10 |
| Authors | Platform Engineering |
| Reviewers | Architecture Review, Systems Architecture Review |
| Supersedes | - |

## Context

Project Aura's current AWS account structure violates AWS best practices and creates significant security and compliance risks:

### Current State (Problematic)

| Account ID | Name | Role | Issue |
|------------|------|------|-------|
| 123456789012 | aenealabs-dev | Org Management Account | **Running dev workloads** |
| 234567890123 | aenealabs-qa | Workload Account | Correct |

### Problems Identified

1. **Security Risk**: Dev workloads running in Org Management Account means dev compromise = entire org compromise
2. **No SCP Protection**: Service Control Policies do NOT apply to the Management Account, leaving dev unprotected
3. **Compliance Violation**: CMMC Level 3 and NIST 800-53 require separation of duties
4. **GovCloud Blocker**: Cannot achieve FedRAMP authorization with this architecture
5. **Blast Radius**: No isolation between org administration and development activities

### AWS Best Practices Violated

| AWS Recommendation | Current State | Risk Level |
|-------------------|---------------|------------|
| No workloads in Management Account | 86 CloudFormation stacks deployed | Critical |
| Minimal access to Management Account | Dev team has access | High |
| SCPs protect all workloads | Dev is unprotected | Critical |
| Separate accounts per environment | Dev and Org Admin combined | High |

### Infrastructure to Migrate

The Management Account currently contains:

- **86 CloudFormation stacks** across 8 layers
- **EKS cluster** with 3 node groups (general, memory, GPU)
- **Neptune** graph database
- **OpenSearch** vector search cluster
- **DynamoDB** tables (8+)
- **S3 buckets** (data, artifacts, logs)
- **Lambda functions** (16+)
- **CodeBuild projects** (16)
- **ECR repositories** (12+)
- **Secrets Manager** secrets
- **VPC** with public/private subnets, NAT gateways, VPC endpoints

## Decision

Restructure the AWS Organization to follow AWS Well-Architected Framework and multi-account best practices.

### Target Account Structure

```
AWS Organization
├── Management Account (123456789012) ← Org admin ONLY
│   ├── AWS Organizations
│   ├── Service Control Policies (SCPs)
│   ├── IAM Identity Center (SSO)
│   ├── Organization CloudTrail
│   ├── AWS Config Aggregator
│   └── Consolidated Billing
│
├── Security OU
│   ├── Audit Account (NEW)
│   │   ├── Security Hub delegated admin
│   │   ├── GuardDuty delegated admin
│   │   └── AWS Config rules
│   │
│   └── Log Archive Account (NEW)
│       ├── Centralized CloudTrail logs
│       ├── VPC Flow Logs archive
│       └── Application logs (immutable)
│
├── Workloads OU
│   ├── Dev Account (NEW) ← All 86 stacks migrate here
│   │   └── Full Project Aura stack
│   │
│   ├── QA Account (234567890123) ← Existing
│   │   └── Full Project Aura stack
│   │
│   ├── Staging Account (FUTURE)
│   │   └── Pre-production validation
│   │
│   └── Prod Account (FUTURE - GovCloud)
│       └── Production workloads
│
└── Infrastructure OU
    └── Shared Services Account (NEW)
        ├── Shared ECR repositories
        ├── Shared artifacts
        └── Cross-account tooling
```

### Account Purpose Matrix

| Account | Purpose | SCPs Apply | Workloads |
|---------|---------|------------|-----------|
| Management | Org administration only | No | None |
| Audit | Security tooling, delegated admin | Yes | Security only |
| Log Archive | Immutable audit trails | Yes | Logs only |
| Dev (NEW) | Development workloads | Yes | Full stack |
| QA | Quality assurance | Yes | Full stack |
| Staging | Pre-production | Yes | Full stack |
| Prod (GovCloud) | Production | Yes | Full stack |
| Shared Services | Cross-account resources | Yes | Infrastructure |

### VPC CIDR Planning

Non-overlapping CIDRs for future Transit Gateway connectivity:

| Account | CIDR Block | Purpose |
|---------|------------|---------|
| Management | 10.0.0.0/16 | Org resources (minimal) |
| Dev | 10.1.0.0/16 | Development |
| QA | 10.2.0.0/16 | Quality Assurance |
| Staging | 10.3.0.0/16 | Pre-production |
| Prod (GovCloud) | 10.10.0.0/16 | Production |

## Consequences

### Positive

- **SCP Protection**: All workload accounts protected by Service Control Policies
- **Blast Radius Reduction**: Dev compromise no longer compromises entire org
- **CMMC Compliance**: Proper separation of duties for Level 3 certification
- **GovCloud Ready**: Architecture supports GovCloud production deployment
- **Audit Independence**: Separate log archive account for immutable audit trails
- **Security Posture**: GuardDuty, Security Hub, Config at organization level
- **Cost Attribution**: Clear cost allocation per environment
- **Naming Standardization**: CI/CD rebuild automatically fixes legacy naming inconsistencies (see below)

### Negative

- **Migration Effort**: 10-12 weeks, 55-83 person-days estimated
- **Parallel Costs**: ~$1,500-3,500/month during migration (parallel environments)
- **Downtime Risk**: Data migration phases carry risk (mitigated by snapshots)
- **Complexity**: More accounts to manage (mitigated by Organizations)

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data loss during migration | Low | Critical | Multiple snapshots, validation, 30-day retention |
| Extended downtime | Medium | High | Blue-green approach, parallel environments |
| IAM permission issues | High | Medium | Thorough IRSA testing, Access Analyzer |
| CI/CD pipeline breaks | High | Medium | Dual pipelines during transition |
| Cost overrun | High | Low | Budget alerts, cleanup automation |

## Implementation

### Phase 0: Preparation (Week 1-2)

1. Create new Dev workload account
2. Establish OU structure (Security, Workloads, Infrastructure)
3. Configure IAM Identity Center for cross-account access
4. Deploy baseline SCPs to Workloads OU
5. Set up cross-account migration roles

**Baseline SCPs for Workloads OU:**
- Deny regions outside us-east-1, us-west-2, us-gov-west-1
- Deny disabling CloudTrail
- Deny disabling GuardDuty
- Require IMDSv2 for EC2
- Deny public S3 buckets

### Phase 1: Foundation Layer (Week 2-3)

1. Deploy VPC with non-overlapping CIDR (10.1.0.0/16)
2. Create subnets, route tables, NAT gateways
3. Deploy VPC endpoints
4. Create new KMS keys (keys cannot be migrated)
5. Deploy foundation IAM roles

### Phase 2: Data Layer Migration (Week 3-5)

**Highest risk phase - requires careful execution.**

| Service | Migration Method | Estimated Time |
|---------|-----------------|----------------|
| Neptune | Snapshot → Share → Copy → Restore | 30-60 min |
| OpenSearch | S3 snapshot repository → Restore | 15-30 min |
| DynamoDB | PITR export → S3 → Import | 1-2 hours |
| S3 | Cross-account sync | Variable |

### Phase 3: Compute Layer (Week 5-7)

1. Replicate ECR images to new account
2. Create new EKS cluster (clusters cannot be migrated)
3. Deploy node groups (general, memory, GPU)
4. Configure IRSA roles
5. Deploy dnsmasq (ECS Fargate)

### Phase 4: Application Layer (Week 7-8)

1. Redeploy Lambda functions via CloudFormation
2. Deploy API Gateway
3. Deploy Step Functions
4. Configure EventBridge rules

### Phase 5: CI/CD Migration (Week 8-9)

1. Deploy CodeBuild projects to new account
2. Update GitHub webhooks
3. Update buildspec environment variables
4. Validate pipeline execution

### Phase 6: Cutover (Week 9-10)

1. Freeze deployments to old account
2. Final data sync (Neptune, DynamoDB, S3)
3. Update DNS records if applicable
4. Comprehensive validation testing
5. Run integration test suite

### Phase 7: Cleanup (Week 10-12)

1. Validate new environment stability (2-week minimum)
2. Delete CloudWatch resources from Management Account
3. Delete compute resources (EKS, Lambda)
4. Delete data resources (Neptune, OpenSearch, DynamoDB)
5. Delete S3 buckets (after confirming replication)
6. Delete VPC resources
7. Delete workload-specific IAM roles
8. Schedule KMS key deletion (7-30 day wait)

## Automation

Migration automation scripts created:

| Script | Purpose |
|--------|---------|
| `deploy/cloudformation/account-migration-bootstrap.yaml` | Cross-account access, migration bucket, KMS |
| `deploy/scripts/migration/migrate-data-services.sh` | Neptune, OpenSearch, DynamoDB, S3 migration |
| `deploy/scripts/migration/migrate-cicd-pipeline.sh` | ECR, Secrets, SSM, CodeBuild migration |

## Interim Environment Standardization (DEV/QA Parity)

While the full account restructure is pending, DEV and QA environments have been standardized using conditional parameters in the `account-bootstrap.yaml` template. This ensures consistent infrastructure deployment across environments despite DEV's unique position as the management account.

### Bootstrap Conditional Parameters

The `deploy/cloudformation/account-bootstrap.yaml` template supports three conditional parameters to handle environment-specific constraints:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EnableAccountCloudTrail` | `true` | Set to `false` when org-level CloudTrail already covers the account |
| `EnableGuardDuty` | `true` | Set to `false` when GuardDuty is managed by a delegated admin |
| `EnableSecurityAlertsTopic` | `true` | Set to `false` when another stack (e.g., realtime-monitoring) owns the SNS topic |

### DEV vs QA Configuration

| Parameter | DEV | QA | Reason |
|-----------|-----|-----|--------|
| `EnableAccountCloudTrail` | `false` | `true` | DEV has org-level `aura-org-trail` in management account |
| `EnableGuardDuty` | `true` | `true` | Both environments need independent threat detection |
| `EnableSecurityAlertsTopic` | `false` | `true` | DEV's `realtime-monitoring` stack was deployed first and owns the topic |

### Canonical Deployment Order

For new environments, deploy in this order to ensure proper resource ownership:

```bash
# 1. Deploy account-bootstrap FIRST (creates SNS topic, KMS key, SSM params)
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-${ENV} \
  --parameter-overrides Environment=${ENV} ... \
  --capabilities CAPABILITY_NAMED_IAM

# 2. Deploy realtime-monitoring SECOND (references bootstrap's SNS topic)
aws cloudformation deploy \
  --template-file deploy/cloudformation/realtime-monitoring.yaml \
  --stack-name aura-realtime-monitoring-${ENV} \
  --parameter-overrides \
    Environment=${ENV} \
    SecurityAlertsTopicArn=$(aws cloudformation describe-stacks \
      --stack-name aura-account-bootstrap-${ENV} \
      --query 'Stacks[0].Outputs[?OutputKey==`SecurityAlertsTopicArn`].OutputValue' \
      --output text) \
  --capabilities CAPABILITY_NAMED_IAM
```

### Current Parity Status

As of 2026-01-16:

| Environment | Workload Stacks | Bootstrap Stack | Status |
|-------------|-----------------|-----------------|--------|
| DEV | 110 | `aura-account-bootstrap-dev` | Deployed |
| QA | 110 | `aura-account-bootstrap-qa` | Deployed |

This standardization enables single-command deployments across both environments using the same templates with environment-specific parameter overrides.

## Alternatives Considered

### 1. Keep Current Structure

**Rejected**: Unacceptable security risk. Dev compromise = org compromise. Blocks CMMC/FedRAMP certification.

### 2. Move Management to New Account

**Rejected**: AWS Organizations cannot change the management account. Would require recreating the entire org.

### 3. Minimal Migration (Compute Only)

**Rejected**: Doesn't address compliance requirements. Data services in management account still creates risk.

### 4. AWS Control Tower Adoption

**Considered for future**: Control Tower provides account vending and guardrails, but not available in GovCloud. Can adopt in commercial for dev/QA.

## GovCloud Considerations

### Service Differences

| Service | Commercial | GovCloud |
|---------|------------|----------|
| EKS Fargate | Available | NOT Available |
| Neptune Serverless | Available | NOT Available |
| Control Tower | Available | NOT Available |
| IAM Identity Center | Full features | Limited |
| ARN Partition | `arn:aws` | `arn:aws-us-gov` |

### Recommended Approach

1. Complete commercial account restructuring FIRST
2. Stabilize in new Dev account
3. Document all configurations
4. Deploy FRESH to GovCloud (don't migrate)
5. Sync data via approved mechanisms

## Naming Standardization

The CI/CD rebuild approach automatically resolves legacy naming inconsistencies in DEV. The current DEV environment was built incrementally before layer-based naming conventions were established.

### Legacy vs. Standardized Names

| CloudFormation Template | QA (Standardized) | DEV (Legacy) | New DEV (After Migration) |
|------------------------|-------------------|--------------|---------------------------|
| `codebuild-application-identity.yaml` | `aura-codebuild-application-identity-qa` | `aura-codebuild-identity-dev` | `aura-codebuild-application-identity-dev` |
| `codebuild-serverless-documentation.yaml` | `aura-codebuild-serverless-documentation-qa` | `aura-codebuild-documentation-dev` | `aura-codebuild-serverless-documentation-dev` |

### Architecture Improvements

The rebuild also adopts improvements present in QA but missing from legacy DEV:

| Component | DEV (Legacy) | New DEV (After Migration) |
|-----------|--------------|---------------------------|
| EKS Node Groups | Single nodegroup | 3 nodegroups: general, gpu, memory (ADR-058) |
| CodeBuild Projects | 14 projects | 16 projects (+ bootstrap, integration-test, k8s-deploy) |
| ECR Repositories | Missing aura-ecr-api | Full set matching QA |

### Naming Convention Reference

All stacks follow the pattern: `${ProjectName}-${ResourceName}-${Environment}`

See `docs/reference/NAMING_CONVENTIONS.md` for the complete naming standard.

## Related Documents

- ADR-004: Cloud Abstraction Layer (Multi-cloud support)
- ADR-049: Self-Hosted Deployment
- `docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md`
- `docs/deployment/MIGRATION_GUIDE.md`

## References

- [AWS Organizations Best Practices](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_best-practices.html)
- [AWS Multi-Account Strategy](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/organizing-your-aws-environment.html)
- [AWS Well-Architected Framework - Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
- [CMMC Level 3 Requirements](https://dodcio.defense.gov/CMMC/)
- [NIST 800-53 Access Control](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
